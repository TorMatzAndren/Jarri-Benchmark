#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DUCKDB_PATH = PROJECT_ROOT / "benchmarks" / "_db" / "benchmark.duckdb"
OUT_PATH = PROJECT_ROOT / "benchmark_ui" / "data" / "duckdb_task_rankings.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_relation_columns(con: duckdb.DuckDBPyConnection, relation_name: str) -> set[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM {relation_name}").fetchall()
    return {str(row[0]) for row in rows}


def first_existing(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def build_avg_expr(columns: set[str], candidates: list[str], alias: str, default_sql: str = "NULL") -> str:
    column = first_existing(columns, candidates)
    if column is None:
        return f"{default_sql} AS {alias}"
    return f"ROUND(AVG({column}), 6) AS {alias}"


def build_min_expr(columns: set[str], candidates: list[str], alias: str, default_sql: str = "NULL") -> str:
    column = first_existing(columns, candidates)
    if column is None:
        return f"{default_sql} AS {alias}"
    return f"MIN({column}) AS {alias}"


def build_max_expr(columns: set[str], candidates: list[str], alias: str, default_sql: str = "NULL") -> str:
    column = first_existing(columns, candidates)
    if column is None:
        return f"{default_sql} AS {alias}"
    return f"MAX({column}) AS {alias}"


def build_rate_expr(columns: set[str], candidate: str, alias: str, truthy_sql: str = "TRUE") -> str:
    if candidate not in columns:
        return f"NULL AS {alias}"
    return f"ROUND(AVG(CASE WHEN {candidate} = {truthy_sql} THEN 1.0 ELSE 0.0 END), 6) AS {alias}"


def build_runtime_filter(columns: set[str]) -> str:
    runtime_col = first_existing(columns, ["gpu_residency_mode", "runtime_residency_status", "canonical_runtime"])
    if runtime_col is None:
        return "1=1"
    return f"({runtime_col} IS NULL OR {runtime_col} = 'full_gpu')"


def build_query(columns: set[str]) -> str:
    task_col = first_existing(columns, ["task_id"])
    family_col = first_existing(columns, ["task_family"])
    if task_col is None:
        raise RuntimeError("No task_id column found in benchmark_normalized_runs.")

    runtime_filter = build_runtime_filter(columns)

    family_select = f"{family_col} AS task_family" if family_col else "'unknown' AS task_family"

    query = f"""
        SELECT
            {task_col} AS task_id,
            {family_select},
            COUNT(*) AS rows,
            COUNT(DISTINCT model) AS model_count,
            {build_avg_expr(columns, ["scientific_score_percent", "evaluation_score_percent"], "avg_score_percent", "0.0")},
            {build_min_expr(columns, ["scientific_score_percent", "evaluation_score_percent"], "min_score_percent", "NULL")},
            {build_max_expr(columns, ["scientific_score_percent", "evaluation_score_percent"], "max_score_percent", "NULL")},
            {build_avg_expr(columns, ["duration_seconds"], "avg_duration_seconds", "NULL")},
            {build_avg_expr(columns, ["tokens_per_second"], "avg_tokens_per_second", "NULL")},
            {build_avg_expr(columns, ["score_per_second_strict"], "avg_score_per_second_strict", "NULL")},
            {build_avg_expr(columns, ["score_per_wh_strict"], "avg_score_per_wh_strict", "NULL")},
            {build_avg_expr(columns, ["llm_energy_joules"], "avg_energy_j", "NULL")},
            {build_avg_expr(columns, ["output_tokens", "response_tokens"], "avg_output_tokens", "NULL")},
            {build_avg_expr(columns, ["total_tokens"], "avg_total_tokens", "NULL")},
            {build_avg_expr(columns, ["llm_joules_per_output_token"], "avg_joules_per_output_token", "NULL")},
            {build_avg_expr(columns, ["output_tokens_per_joule"], "avg_output_tokens_per_joule", "NULL")},
            {build_avg_expr(columns, ["score_per_100_output_tokens"], "avg_score_per_100_output_tokens", "NULL")},
            {build_avg_expr(columns, ["score_per_output_token"], "avg_score_per_output_token", "NULL")},
            {build_rate_expr(columns, "success", "success_rate")},
            {build_rate_expr(columns, "usable_output", "usable_output_rate")},
            {build_rate_expr(columns, "hard_failure", "hard_failure_rate", "TRUE")},
            {build_rate_expr(columns, "energy_valid", "energy_valid_rate")}
        FROM benchmark_normalized_runs
        WHERE {runtime_filter}
        GROUP BY 1, 2
        ORDER BY
            avg_score_percent DESC NULLS LAST,
            usable_output_rate DESC NULLS LAST,
            avg_score_per_100_output_tokens DESC NULLS LAST,
            avg_output_tokens ASC NULLS LAST,
            task_id ASC
    """
    return query


def main() -> int:
    if not DUCKDB_PATH.exists():
        raise SystemExit(f"Missing DuckDB file: {DUCKDB_PATH}")

    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        columns = get_relation_columns(con, "benchmark_normalized_runs")
        query = build_query(columns)
        rows = con.execute(query).fetchall()
        result_columns = [desc[0] for desc in con.description]

        out_rows: list[dict[str, Any]] = [dict(zip(result_columns, row)) for row in rows]

        payload = {
            "generated_at_utc": utc_now_iso(),
            "duckdb_path": str(DUCKDB_PATH),
            "source_relation": "benchmark_normalized_runs",
            "runtime_filter_mode": "full_gpu_if_runtime_column_exists",
            "row_count": len(out_rows),
            "rows": out_rows,
        }

        OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(str(OUT_PATH))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
