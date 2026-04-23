#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "benchmark_ui" / "data"

JOINED_BY_MODEL_TASK_TDP = UI_ROOT / "joined" / "joined_failure_energy_by_model_task_tdp.json"
JOINED_BY_TASK = UI_ROOT / "joined" / "joined_failure_energy_by_task.json"
FAILURE_BY_TASK = UI_ROOT / "failures" / "failure_by_task.json"
FAILURE_RECORDS = UI_ROOT / "failures" / "failure_records.json"
DUCKDB_MODEL_TASK_TDP = UI_ROOT / "duckdb_model_task_tdp.json"
POLICY_PATH = PROJECT_ROOT / "benchmark_runtime_policy.json"

OUT_PATH = UI_ROOT / "ui_model_task_taskdetail.json"

TASK_AXIS_MAP = {
    "coding_fs_strict_v3": "execution_reliability",
    "constrained_rewrite_v2": "constraint_precision",
    "fact_task_1": "semantic_fidelity",
    "fact_task_2": "dependency_chain_integrity",
    "fact_task_3": "semantic_fidelity",
    "logic_consistency_v2": "formal_reasoning_consistency",
    "math_dependency_v1": "arithmetic_exactness",
    "prose_task_1": "constraint_precision",
    "prose_task_2": "constraint_precision",
    "prose_task_3": "constraint_precision",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return load_json(path)


def load_excluded_models() -> set[str]:
    raw = load_json(POLICY_PATH)
    policy = raw.get("canonical_runtime_policy", {}) or {}
    return set(policy.get("exclude_models", []) or [])


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


def safe_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    text = str(value).strip()
    return text if text else None


def weighted_average(items: list[tuple[float, int]]) -> float:
    total_weight = sum(weight for _, weight in items)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in items) / total_weight


def top_k_distribution(
    distribution: dict[str, Any],
    k: int = 5,
    exclude_success: bool = False,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, value in (distribution or {}).items():
        if exclude_success and key == "success":
            continue
        items.append({
            "name": str(key),
            "count": safe_int(value),
        })
    items.sort(key=lambda x: (-x["count"], x["name"]))
    return items[:k]


def first_nonempty_string(values: list[Any], default: str = "unknown") -> str:
    for value in values:
        text = safe_str(value)
        if text:
            return text
    return default


def build_duckdb_index(payload: Any, excluded_models: set[str]) -> dict[tuple[str, str, int], dict[str, Any]]:
    index: dict[tuple[str, str, int], dict[str, Any]] = {}

    if payload is None:
        return index

    if isinstance(payload, dict):
        rows = payload.get("rows")
        if rows is None:
            rows = payload.get("data")
        if rows is None and isinstance(payload.get("groups"), dict):
            flattened: list[dict[str, Any]] = []
            for _, group_value in payload["groups"].items():
                if isinstance(group_value, list):
                    flattened.extend(item for item in group_value if isinstance(item, dict))
            rows = flattened
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    if not isinstance(rows, list):
        return index

    for row in rows:
        if not isinstance(row, dict):
            continue

        model = safe_str(row.get("model"))
        task_id = safe_str(row.get("task_id"))
        tdp_level = safe_int(row.get("power_limit_percent"))

        if not model or not task_id:
            continue
        if model in excluded_models:
            continue
        if tdp_level <= 0:
            continue

        index[(model, task_id, tdp_level)] = {
            "model": model,
            "task_id": task_id,
            "tdp_level": tdp_level,
            "rows": safe_int(row.get("rows")),
            "task_family": first_nonempty_string(
                [
                    row.get("task_family"),
                    row.get("family"),
                ],
                default="unknown",
            ),
            "usable_output_rate": safe_float(row.get("usable_output_rate")),
            "pipeline_usable_rate": safe_float(row.get("pipeline_usable_rate")),
            "fully_correct_rate": safe_float(row.get("fully_correct_rate")),
            "hard_failure_rate": safe_float(row.get("hard_failure_rate")),
            "avg_score_percent": safe_float(row.get("avg_score_percent")),
            "avg_energy_j": safe_float(row.get("avg_energy_j")),
            "avg_tokens_per_second": safe_float(row.get("avg_tokens_per_second")),
            "avg_score_per_wh_strict": safe_float(row.get("avg_score_per_wh_strict")),
            "avg_output_tokens": safe_float(row.get("avg_output_tokens")),
            "total_output_tokens": safe_float(row.get("total_output_tokens")),
            "avg_joules_per_output_token": safe_float(
                row.get("weighted_joules_per_output_token", row.get("avg_joules_per_output_token"))
            ),
            "avg_output_tokens_per_joule": safe_float(
                row.get("weighted_output_tokens_per_joule", row.get("avg_output_tokens_per_joule"))
            ),
            "avg_score_per_100_output_tokens": safe_float(
                row.get("weighted_score_per_100_output_tokens", row.get("avg_score_per_100_output_tokens"))
            ),
            "avg_score_per_output_token": safe_float(
                row.get("weighted_score_per_output_token", row.get("avg_score_per_output_token"))
            ),
            "failure_stage_distribution": row.get("failure_stage_distribution", {}) or {},
            "failure_type_distribution": row.get("failure_type_distribution", {}) or {},
            "failure_subtype_distribution": row.get("failure_subtype_distribution", {}) or {},
            "_source": "duckdb_model_task_tdp",
        }

    return index


def build_joined_fallback_rows(
    joined_groups: dict[str, Any],
    excluded_models: set[str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    per_model_task_tdp: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for _, group in joined_groups.items():
        if not isinstance(group, dict):
            continue

        models = [m for m in (group.get("models", []) or []) if m not in excluded_models]
        task_ids = group.get("task_ids", []) or []
        tdp_levels = group.get("tdp_levels", []) or []

        task_family = first_nonempty_string(group.get("task_families", []) or [], default="unknown")

        for model in models:
            for task_id in task_ids:
                for tdp in tdp_levels:
                    per_model_task_tdp[(model, task_id)].append({
                        "model": model,
                        "task_id": task_id,
                        "tdp_level": safe_int(tdp),
                        "rows": safe_int(group.get("rows")),
                        "task_family": task_family,
                        "usable_output_rate": safe_float(group.get("usable_output_rate")),
                        "pipeline_usable_rate": safe_float(group.get("pipeline_usable_rate")),
                        "fully_correct_rate": safe_float(group.get("fully_correct_rate")),
                        "hard_failure_rate": safe_float(group.get("hard_failure_rate")),
                        "avg_score_percent": safe_float(group.get("avg_score_percent")),
                        "avg_energy_j": safe_float(group.get("avg_energy_j")),
                        "avg_tokens_per_second": safe_float(group.get("avg_tokens_per_second")),
                        "avg_score_per_wh_strict": safe_float(group.get("avg_score_per_wh_strict")),
                        "avg_output_tokens": 0.0,
                        "total_output_tokens": 0.0,
                        "avg_joules_per_output_token": 0.0,
                        "avg_output_tokens_per_joule": 0.0,
                        "avg_score_per_100_output_tokens": 0.0,
                        "avg_score_per_output_token": 0.0,
                        "failure_stage_distribution": group.get("failure_stage_distribution", {}) or {},
                        "failure_type_distribution": group.get("failure_type_distribution", {}) or {},
                        "failure_subtype_distribution": group.get("failure_subtype_distribution", {}) or {},
                        "_source": "joined_fallback",
                    })

    return per_model_task_tdp


def merge_duckdb_rows_over_fallback(
    joined_groups: dict[str, Any],
    duckdb_index: dict[tuple[str, str, int], dict[str, Any]],
    excluded_models: set[str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    per_model_task_tdp = build_joined_fallback_rows(joined_groups, excluded_models)

    for (model, task_id, tdp_level), duckdb_row in duckdb_index.items():
        bucket = per_model_task_tdp[(model, task_id)]
        replaced = False

        for idx, existing in enumerate(bucket):
            if safe_int(existing.get("tdp_level")) == tdp_level:
                merged = dict(existing)
                merged.update(duckdb_row)
                bucket[idx] = merged
                replaced = True
                break

        if not replaced:
            bucket.append(dict(duckdb_row))

    return per_model_task_tdp


def build_representative_failures(
    failure_rows: list[dict[str, Any]],
    model: str,
    task_id: str,
) -> list[dict[str, Any]]:
    representative_failures: list[dict[str, Any]] = []

    for row in failure_rows:
        if not isinstance(row, dict):
            continue

        row_model = safe_str(row.get("model"))
        row_task = safe_str(row.get("task_id")) or safe_str(row.get("task"))

        if row_model == model and row_task == task_id:
            representative_failures.append({
                "failure_stage": first_nonempty_string([row.get("failure_stage")], default="unknown"),
                "failure_type": first_nonempty_string([row.get("failure_type")], default="unknown"),
                "failure_subtype": row.get("failure_subtype", row.get("failure_subtypes", [])),
                "quality_class": first_nonempty_string([row.get("quality_class")], default="unknown"),
                "artifact_usability": first_nonempty_string([row.get("artifact_usability")], default="unknown"),
                "score_percent": row.get("score_percent"),
                "report_path": row.get("report_path"),
                "result_path": row.get("result_path"),
            })

    return representative_failures[:8]


def main() -> int:
    excluded_models = load_excluded_models()

    joined_model_task_tdp = load_json(JOINED_BY_MODEL_TASK_TDP)
    joined_by_task = load_json(JOINED_BY_TASK)
    failure_by_task = load_json(FAILURE_BY_TASK)
    failure_records = load_json(FAILURE_RECORDS)
    duckdb_model_task_tdp = load_optional_json(DUCKDB_MODEL_TASK_TDP)

    joined_groups = joined_model_task_tdp.get("groups", {}) or {}
    task_groups = joined_by_task.get("groups", {}) or {}
    failure_task_groups = failure_by_task.get("groups", {}) or {}
    failure_rows = failure_records.get("rows", []) or failure_records.get("records", []) or []

    duckdb_index = build_duckdb_index(duckdb_model_task_tdp, excluded_models)
    per_model_task_tdp = merge_duckdb_rows_over_fallback(joined_groups, duckdb_index, excluded_models)

    detailed_rows: list[dict[str, Any]] = []

    for (model, task_id), tdp_rows in sorted(per_model_task_tdp.items(), key=lambda x: (x[0][0], x[0][1])):
        tdp_rows.sort(key=lambda x: x["tdp_level"])

        task_group = task_groups.get(task_id, {}) or {}
        failure_task_group = failure_task_groups.get(task_id, {}) or {}

        representative_failures = build_representative_failures(failure_rows, model, task_id)

        aggregate_stage: dict[str, int] = defaultdict(int)
        aggregate_type: dict[str, int] = defaultdict(int)
        aggregate_subtype: dict[str, int] = defaultdict(int)

        for tdp_row in tdp_rows:
            for key, value in (tdp_row.get("failure_stage_distribution") or {}).items():
                aggregate_stage[str(key)] += safe_int(value)
            for key, value in (tdp_row.get("failure_type_distribution") or {}).items():
                aggregate_type[str(key)] += safe_int(value)
            for key, value in (tdp_row.get("failure_subtype_distribution") or {}).items():
                aggregate_subtype[str(key)] += safe_int(value)

        task_family = first_nonempty_string(
            [
                (task_group.get("task_families", []) or ["unknown"])[0] if isinstance(task_group.get("task_families", []), list) else None,
                tdp_rows[0].get("task_family") if tdp_rows else None,
            ],
            default="unknown",
        )

        detailed_rows.append({
            "model": model,
            "task_id": task_id,
            "task_family": task_family,
            "primary_axis": TASK_AXIS_MAP.get(task_id, "unmapped"),
            "summary": {
                "usable_output_rate": weighted_average([(r["usable_output_rate"], r["rows"]) for r in tdp_rows]),
                "pipeline_usable_rate": weighted_average([(r["pipeline_usable_rate"], r["rows"]) for r in tdp_rows]),
                "fully_correct_rate": weighted_average([(r["fully_correct_rate"], r["rows"]) for r in tdp_rows]),
                "hard_failure_rate": weighted_average([(r["hard_failure_rate"], r["rows"]) for r in tdp_rows]),
                "avg_score_percent": weighted_average([(r["avg_score_percent"], r["rows"]) for r in tdp_rows]),
                "avg_energy_j": weighted_average([(r["avg_energy_j"], r["rows"]) for r in tdp_rows]),
                "avg_tokens_per_second": weighted_average([(r["avg_tokens_per_second"], r["rows"]) for r in tdp_rows]),
                "avg_score_per_wh_strict": weighted_average([(r["avg_score_per_wh_strict"], r["rows"]) for r in tdp_rows]),
                "avg_output_tokens": weighted_average([(r["avg_output_tokens"], r["rows"]) for r in tdp_rows]),
                "avg_joules_per_output_token": weighted_average([(r["avg_joules_per_output_token"], r["rows"]) for r in tdp_rows]),
                "avg_output_tokens_per_joule": weighted_average([(r["avg_output_tokens_per_joule"], r["rows"]) for r in tdp_rows]),
                "avg_score_per_100_output_tokens": weighted_average([(r["avg_score_per_100_output_tokens"], r["rows"]) for r in tdp_rows]),
                "avg_score_per_output_token": weighted_average([(r["avg_score_per_output_token"], r["rows"]) for r in tdp_rows]),
            },
            "dominant_failure_stage": top_k_distribution(dict(aggregate_stage), k=1, exclude_success=True),
            "dominant_failure_type": top_k_distribution(dict(aggregate_type), k=1, exclude_success=True),
            "dominant_failure_subtypes": top_k_distribution(dict(aggregate_subtype), k=5),
            "task_level_failure_type_distribution": top_k_distribution(
                failure_task_group.get("failure_type_distribution", {}) or {},
                k=5,
                exclude_success=True,
            ),
            "tdp_rows": [
                {
                    "tdp_level": row["tdp_level"],
                    "rows": row["rows"],
                    "task_family": row.get("task_family", task_family),
                    "usable_output_rate": row["usable_output_rate"],
                    "pipeline_usable_rate": row["pipeline_usable_rate"],
                    "fully_correct_rate": row["fully_correct_rate"],
                    "hard_failure_rate": row["hard_failure_rate"],
                    "avg_score_percent": row["avg_score_percent"],
                    "avg_energy_j": row["avg_energy_j"],
                    "avg_tokens_per_second": row["avg_tokens_per_second"],
                    "avg_score_per_wh_strict": row["avg_score_per_wh_strict"],
                    "avg_output_tokens": row["avg_output_tokens"],
                    "total_output_tokens": row["total_output_tokens"],
                    "avg_joules_per_output_token": row["avg_joules_per_output_token"],
                    "avg_output_tokens_per_joule": row["avg_output_tokens_per_joule"],
                    "avg_score_per_100_output_tokens": row["avg_score_per_100_output_tokens"],
                    "avg_score_per_output_token": row["avg_score_per_output_token"],
                    "failure_stage_distribution": row["failure_stage_distribution"],
                    "failure_type_distribution": row["failure_type_distribution"],
                    "failure_subtype_distribution": row["failure_subtype_distribution"],
                    "metric_source": row.get("_source", "unknown"),
                }
                for row in tdp_rows
            ],
            "representative_failures": representative_failures,
        })

    output = {
        "generated_at_utc": utc_now_iso(),
        "policy_path": str(POLICY_PATH),
        "excluded_models": sorted(excluded_models),
        "source_files": [
            "joined/joined_failure_energy_by_model_task_tdp.json",
            "joined/joined_failure_energy_by_task.json",
            "failures/failure_by_task.json",
            "failures/failure_records.json",
            "duckdb_model_task_tdp.json",
        ],
        "rows": detailed_rows,
    }

    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(OUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
