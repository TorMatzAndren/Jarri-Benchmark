#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "benchmark_ui" / "data"
DUCKDB_PATH = PROJECT_ROOT / "benchmarks" / "_db" / "benchmark.duckdb"

JOINED_BY_MODEL = UI_ROOT / "joined" / "joined_failure_energy_by_model.json"
JOINED_BY_TASK = UI_ROOT / "joined" / "joined_failure_energy_by_task.json"
POLICY_PATH = PROJECT_ROOT / "benchmark_runtime_policy.json"
OUT_MODEL_PROFILES = UI_ROOT / "ui_model_profiles.json"

TASK_AXIS_MAP = {
    "coding_fs_strict_v3": {"primary_axis": "execution_reliability"},
    "constrained_rewrite_v2": {"primary_axis": "constraint_precision"},
    "fact_task_1": {"primary_axis": "semantic_fidelity"},
    "fact_task_2": {"primary_axis": "dependency_chain_integrity"},
    "fact_task_3": {"primary_axis": "semantic_fidelity"},
    "logic_consistency_v2": {"primary_axis": "formal_reasoning_consistency"},
    "math_dependency_v1": {"primary_axis": "arithmetic_exactness"},
    "prose_task_1": {"primary_axis": "constraint_precision"},
    "prose_task_2": {"primary_axis": "constraint_precision"},
    "prose_task_3": {"primary_axis": "constraint_precision"},
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_excluded_models() -> set[str]:
    raw = load_json(POLICY_PATH)
    policy = raw.get("canonical_runtime_policy", {}) or {}
    return set(policy.get("exclude_models", []) or [])


def safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except Exception:
        return 0


def weighted_average(items: list[tuple[float, int]]) -> float:
    total_weight = sum(weight for _, weight in items)
    if total_weight == 0:
        return 0.0
    return sum(value * weight for value, weight in items) / total_weight


def pick_top_failure_type(group: dict[str, Any]) -> str:
    dist = group.get("failure_type_distribution", {}) or {}
    filtered = [(k, v) for k, v in dist.items() if k != "success"]
    if not filtered:
        return "unknown"
    filtered.sort(key=lambda x: x[1], reverse=True)
    return filtered[0][0]


def get_relation_columns(con: duckdb.DuckDBPyConnection, relation_name: str) -> set[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM {relation_name}").fetchall()
    return {str(row[0]) for row in rows}


def first_existing(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def load_model_token_efficiency(excluded_models: set[str]) -> dict[str, dict[str, Any]]:
    if not DUCKDB_PATH.exists():
        return {}

    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        candidate_relations = [
            "model_token_efficiency",
            "duckdb_model_rankings",
            "benchmark_aggregates",
        ]

        relation_name = None
        relation_columns: set[str] = set()

        for candidate in candidate_relations:
            try:
                cols = get_relation_columns(con, candidate)
                relation_name = candidate
                relation_columns = cols
                break
            except Exception:
                continue

        if relation_name is None:
            return {}

        model_col = first_existing(relation_columns, ["model"])
        rows_col = first_existing(relation_columns, ["configuration_rows", "rows", "runs"])
        score_col = first_existing(relation_columns, ["avg_score_percent", "avg_scientific_score_percent"])
        output_tokens_col = first_existing(relation_columns, ["avg_output_tokens"])
        score_per_100_output_tokens_col = first_existing(
            relation_columns,
            ["avg_score_per_100_output_tokens", "avg_weighted_score_per_100_output_tokens"],
        )
        joules_per_output_token_col = first_existing(
            relation_columns,
            ["avg_joules_per_output_token", "avg_weighted_joules_per_output_token"],
        )
        output_tokens_per_joule_col = first_existing(
            relation_columns,
            ["avg_output_tokens_per_joule", "avg_weighted_output_tokens_per_joule"],
        )
        score_per_output_token_col = first_existing(
            relation_columns,
            ["avg_score_per_output_token", "avg_weighted_score_per_output_token"],
        )

        if model_col is None:
            return {}

        select_parts = [
            f"{model_col} AS model",
            f"{rows_col} AS configuration_rows" if rows_col else "0 AS configuration_rows",
            f"{score_col} AS avg_score_percent" if score_col else "0.0 AS avg_score_percent",
            f"{output_tokens_col} AS avg_output_tokens" if output_tokens_col else "0.0 AS avg_output_tokens",
            (
                f"{score_per_100_output_tokens_col} AS avg_score_per_100_output_tokens"
                if score_per_100_output_tokens_col else
                "0.0 AS avg_score_per_100_output_tokens"
            ),
            (
                f"{joules_per_output_token_col} AS avg_joules_per_output_token"
                if joules_per_output_token_col else
                "0.0 AS avg_joules_per_output_token"
            ),
            (
                f"{output_tokens_per_joule_col} AS avg_output_tokens_per_joule"
                if output_tokens_per_joule_col else
                "0.0 AS avg_output_tokens_per_joule"
            ),
            (
                f"{score_per_output_token_col} AS avg_score_per_output_token"
                if score_per_output_token_col else
                "0.0 AS avg_score_per_output_token"
            ),
        ]

        query = f"""
            SELECT
                {", ".join(select_parts)}
            FROM {relation_name}
        """

        rows = con.execute(query).fetchall()

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            model = str(row[0])
            if model in excluded_models:
                continue

            out[model] = {
                "configuration_rows": safe_int(row[1]),
                "avg_score_percent": safe_float(row[2]),
                "avg_output_tokens": safe_float(row[3]),
                "avg_score_per_100_output_tokens": safe_float(row[4]),
                "avg_joules_per_output_token": safe_float(row[5]),
                "avg_output_tokens_per_joule": safe_float(row[6]),
                "avg_score_per_output_token": safe_float(row[7]),
                "relation_used": relation_name,
            }

        return out
    finally:
        con.close()


def main() -> int:
    excluded_models = load_excluded_models()
    joined_by_model = load_json(JOINED_BY_MODEL)
    joined_by_task = load_json(JOINED_BY_TASK)
    token_efficiency_by_model = load_model_token_efficiency(excluded_models)

    task_groups = joined_by_task.get("groups", {}) or {}
    model_groups = joined_by_model.get("groups", {}) or {}

    axis_accumulator: dict[str, dict[str, list[tuple[float, int]]]] = defaultdict(lambda: defaultdict(list))
    axis_failure_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    model_top_failures: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for task_id, group in task_groups.items():
        rows = int(group.get("rows", 0) or 0)
        models = [m for m in (group.get("models", []) or []) if m not in excluded_models]
        primary_axis = TASK_AXIS_MAP.get(task_id, {}).get("primary_axis", "unmapped")
        top_failure = pick_top_failure_type(group)

        for model in models:
            axis_accumulator[model][primary_axis].append((safe_float(group.get("fully_correct_rate", 0.0)), rows))
            axis_accumulator[model][f"{primary_axis}__usable"].append((safe_float(group.get("usable_output_rate", 0.0)), rows))
            axis_accumulator[model][f"{primary_axis}__pipeline"].append((safe_float(group.get("pipeline_usable_rate", 0.0)), rows))
            axis_accumulator[model][f"{primary_axis}__energy"].append((safe_float(group.get("avg_energy_j", 0.0)), rows))
            axis_failure_counter[model][f"{primary_axis}::{top_failure}"] += rows

            failure_dist = group.get("failure_type_distribution", {}) or {}
            filtered_failures = [(k, v) for k, v in failure_dist.items() if k != "success"]
            filtered_failures.sort(key=lambda x: x[1], reverse=True)
            if filtered_failures:
                model_top_failures[model].append({
                    "task": task_id,
                    "failure_type": filtered_failures[0][0],
                    "count": int(filtered_failures[0][1]),
                })

    profiles: list[dict[str, Any]] = []

    for model_name, group in model_groups.items():
        if model_name in excluded_models:
            continue

        token_metrics = token_efficiency_by_model.get(model_name, {})

        summary = {
            "usable_output_rate": safe_float(group.get("usable_output_rate", 0.0)),
            "pipeline_usable_rate": safe_float(group.get("pipeline_usable_rate", 0.0)),
            "fully_correct_rate": safe_float(group.get("fully_correct_rate", 0.0)),
            "hard_failure_rate": safe_float(group.get("hard_failure_rate", 0.0)),
            "avg_energy_j": safe_float(group.get("avg_energy_j", 0.0)),
            "avg_score_percent": safe_float(group.get("avg_score_percent", 0.0)),
            "score_per_wh_strict": safe_float(group.get("avg_score_per_wh_strict", 0.0)),
            "avg_tokens_per_second": safe_float(group.get("avg_tokens_per_second", 0.0)),
            "avg_output_tokens": safe_float(token_metrics.get("avg_output_tokens", 0.0)),
            "avg_score_per_100_output_tokens": safe_float(token_metrics.get("avg_score_per_100_output_tokens", 0.0)),
            "avg_joules_per_output_token": safe_float(token_metrics.get("avg_joules_per_output_token", 0.0)),
            "avg_output_tokens_per_joule": safe_float(token_metrics.get("avg_output_tokens_per_joule", 0.0)),
            "avg_score_per_output_token": safe_float(token_metrics.get("avg_score_per_output_token", 0.0)),
        }

        axes: dict[str, Any] = {}
        model_axis_entries = axis_accumulator.get(model_name, {})
        primary_axes = sorted({key.split("__")[0] for key in model_axis_entries.keys() if "__" not in key})

        for axis_name in primary_axes:
            fully_correct_rate = weighted_average(model_axis_entries.get(axis_name, []))
            usable_output_rate = weighted_average(model_axis_entries.get(f"{axis_name}__usable", []))
            pipeline_usable_rate = weighted_average(model_axis_entries.get(f"{axis_name}__pipeline", []))
            avg_energy_j = weighted_average(model_axis_entries.get(f"{axis_name}__energy", []))

            failure_counts = []
            for key, count in axis_failure_counter.get(model_name, {}).items():
                prefix, failure_type = key.split("::", 1)
                if prefix == axis_name:
                    failure_counts.append((failure_type, count))
            failure_counts.sort(key=lambda x: x[1], reverse=True)
            dominant_failure = failure_counts[0][0] if failure_counts else "unknown"

            axes[axis_name] = {
                "usable_output_rate": usable_output_rate,
                "pipeline_usable_rate": pipeline_usable_rate,
                "fully_correct_rate": fully_correct_rate,
                "avg_energy_j": avg_energy_j,
                "capability_per_joule": safe_div(fully_correct_rate, avg_energy_j),
                "pipeline_capability_per_joule": safe_div(pipeline_usable_rate, avg_energy_j),
                "dominant_failure": dominant_failure,
            }

        top_failures = model_top_failures.get(model_name, [])
        top_failures.sort(key=lambda x: x["count"], reverse=True)
        top_failures = top_failures[:8]

        profiles.append({
            "name": model_name,
            "summary": summary,
            "axes": axes,
            "top_failures": top_failures,
            "token_efficiency_source": token_metrics.get("relation_used"),
        })

    profiles.sort(key=lambda x: x["summary"]["fully_correct_rate"], reverse=True)

    output = {
        "generated_at_utc": utc_now_iso(),
        "policy_path": str(POLICY_PATH),
        "excluded_models": sorted(excluded_models),
        "source_files": [
            "joined/joined_failure_energy_by_model.json",
            "joined/joined_failure_energy_by_task.json",
            str(DUCKDB_PATH),
        ],
        "models": profiles,
    }

    OUT_MODEL_PROFILES.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(OUT_MODEL_PROFILES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
