#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "benchmarks" / "_db" / "benchmark.duckdb"
OUT_PATH = PROJECT_ROOT / "benchmark_ui" / "data" / "duckdb_pareto_frontiers.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sanitize(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: sanitize(v) for k, v in row.items()}


def fetch_dicts(con: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    cur = con.execute(query)
    names = [d[0] for d in cur.description]
    return [sanitize_row(dict(zip(names, row))) for row in cur.fetchall()]


def pareto_split(
    rows: list[dict[str, Any]],
    maximize: list[str],
    minimize: list[str],
) -> dict[str, list[dict[str, Any]]]:
    valid = [
        row for row in rows
        if all(row.get(k) is not None for k in maximize + minimize)
    ]

    frontier: list[dict[str, Any]] = []
    dominated_rows: list[dict[str, Any]] = []

    for candidate in valid:
        dominated = False

        for other in valid:
            if other is candidate:
                continue

            no_worse = True
            strictly_better = False

            for key in maximize:
                if other[key] < candidate[key]:
                    no_worse = False
                    break
                if other[key] > candidate[key]:
                    strictly_better = True

            if not no_worse:
                continue

            for key in minimize:
                if other[key] > candidate[key]:
                    no_worse = False
                    break
                if other[key] < candidate[key]:
                    strictly_better = True

            if no_worse and strictly_better:
                dominated = True
                break

        if dominated:
            dominated_rows.append(candidate)
        else:
            frontier.append(candidate)

    return {
        "frontier": frontier,
        "dominated": dominated_rows,
    }


def load_global_model_rows(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return fetch_dicts(con, """
        SELECT
            model,
            COUNT(*) AS benchmark_count,
            COUNT(*) AS rows,
            AVG(scientific_score_percent) AS avg_score_percent,
            AVG(CASE WHEN scientific_score_percent >= 99.999 THEN 1.0 ELSE 0.0 END) AS fully_correct_rate,
            AVG(llm_energy_joules) AS avg_energy_j,
            AVG(output_tokens) AS avg_output_tokens,
            AVG(tokens_per_second) AS avg_tokens_per_second,
            AVG(score_per_100_output_tokens) AS avg_score_per_100_output_tokens,
            AVG(llm_joules_per_output_token) AS avg_joules_per_output_token,
            AVG(output_tokens_per_joule) AS avg_output_tokens_per_joule
        FROM normalized_runs
        WHERE model IS NOT NULL
        GROUP BY model
        ORDER BY model
    """)


def load_task_rows(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return fetch_dicts(con, """
        SELECT
            model,
            task_id,
            task_family,
            power_limit_percent AS tdp_level,
            COUNT(*) AS benchmark_count,
            COUNT(*) AS rows,
            AVG(scientific_score_percent) AS avg_score_percent,
            AVG(CASE WHEN scientific_score_percent >= 99.999 THEN 1.0 ELSE 0.0 END) AS fully_correct_rate,
            AVG(llm_energy_joules) AS avg_energy_j,
            AVG(output_tokens) AS avg_output_tokens,
            AVG(tokens_per_second) AS avg_tokens_per_second,
            AVG(score_per_100_output_tokens) AS avg_score_per_100_output_tokens,
            AVG(llm_joules_per_output_token) AS avg_joules_per_output_token,
            AVG(output_tokens_per_joule) AS avg_output_tokens_per_joule
        FROM normalized_runs
        WHERE model IS NOT NULL
          AND task_id IS NOT NULL
          AND power_limit_percent IS NOT NULL
        GROUP BY model, task_id, task_family, power_limit_percent
        ORDER BY task_id, model, power_limit_percent
    """)


def group_task_frontiers(task_rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in task_rows:
        task_id = str(row.get("task_id") or "")
        if not task_id:
            continue
        grouped.setdefault(task_id, []).append(row)

    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for task_id, rows in grouped.items():
        out[task_id] = pareto_split(
            rows,
            maximize=["fully_correct_rate", "avg_score_per_100_output_tokens"],
            minimize=["avg_energy_j", "avg_output_tokens"],
        )

    return out


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(f"Missing DuckDB file: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        model_rows = load_global_model_rows(con)
        task_rows = load_task_rows(con)
    finally:
        con.close()

    global_model_frontier = pareto_split(
        model_rows,
        maximize=["fully_correct_rate", "avg_score_per_100_output_tokens"],
        minimize=["avg_energy_j", "avg_output_tokens"],
    )

    per_task_frontier = group_task_frontiers(task_rows)

    flat_task_frontier = []
    for task_id, split in per_task_frontier.items():
        for row in split["frontier"]:
            flat_task_frontier.append({**row, "frontier_task_id": task_id})

    payload = {
        "generated_at_utc": utc_now_iso(),
        "source": str(DB_PATH),
        "project_root": str(PROJECT_ROOT),
        "frontier_definition": {
            "maximize": [
                "fully_correct_rate",
                "avg_score_per_100_output_tokens",
            ],
            "minimize": [
                "avg_energy_j",
                "avg_output_tokens",
            ],
        },

        "global_model_frontier": global_model_frontier,
        "per_task_frontier": per_task_frontier,

        "model_frontier_row_count": len(global_model_frontier["frontier"]),
        "task_frontier_row_count": len(flat_task_frontier),

        "model_frontier": global_model_frontier["frontier"],
        "model_dominated": global_model_frontier["dominated"],
        "task_frontier": flat_task_frontier,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(OUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
