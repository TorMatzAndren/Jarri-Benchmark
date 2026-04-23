#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "benchmarks" / "_db" / "benchmark.duckdb"
UI_ROOT = PROJECT_ROOT / "benchmark_ui" / "data"
OUT_PATH = UI_ROOT / "duckdb_model_task_tdp.json"

JOINED_JSON_PATH = UI_ROOT / "joined" / "joined_failure_energy_by_model_task_tdp.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sanitize_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: sanitize_value(value) for key, value in row.items()}


def load_joined_groups() -> dict[str, Any]:
    if not JOINED_JSON_PATH.exists():
        return {}
    payload = json.loads(JOINED_JSON_PATH.read_text(encoding="utf-8"))
    groups = payload.get("groups", {})
    return groups if isinstance(groups, dict) else {}


def relation_exists(con: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    try:
        con.execute(f"DESCRIBE SELECT * FROM {relation_name}")
        return True
    except duckdb.Error:
        return False


def get_relation_columns(con: duckdb.DuckDBPyConnection, relation_name: str) -> set[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM {relation_name}").fetchall()
    return {str(row[0]) for row in rows}


def first_existing(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def sql_expr(columns: set[str], candidates: list[str], alias: str, default_sql: str = "NULL") -> str:
    column = first_existing(columns, candidates)
    if column is None:
        return f"{default_sql} AS {alias}"
    return f"{column} AS {alias}"


def build_query(columns: set[str]) -> str:
    model_col = first_existing(columns, ["model"])
    task_col = first_existing(columns, ["task_id"])
    family_col = first_existing(columns, ["task_family"])
    tdp_col = first_existing(columns, ["power_limit_percent", "tdp_level"])

    if model_col is None or task_col is None:
        raise RuntimeError("model_task_token_efficiency is missing required model/task_id columns.")

    family_expr = f"{family_col} AS task_family" if family_col else "NULL AS task_family"
    tdp_expr = f"{tdp_col} AS tdp_level" if tdp_col else "NULL AS tdp_level"

    return f"""
        SELECT
            {model_col} AS model,
            {task_col} AS task_id,
            {family_expr},
            {tdp_expr},
            {sql_expr(columns, ['runs'], 'benchmark_count', 'NULL')},
            {sql_expr(columns, ['avg_score_percent', 'avg_scientific_score_percent'], 'avg_score_percent', 'NULL')},
            {sql_expr(columns, ['avg_output_tokens'], 'avg_output_tokens', 'NULL')},
            {sql_expr(columns, ['total_output_tokens'], 'total_output_tokens', 'NULL')},
            {sql_expr(columns, ['weighted_score_per_100_output_tokens', 'avg_weighted_score_per_100_output_tokens'], 'weighted_score_per_100_output_tokens', 'NULL')},
            {sql_expr(columns, ['weighted_score_per_output_token', 'avg_weighted_score_per_output_token'], 'weighted_score_per_output_token', 'NULL')},
            {sql_expr(columns, ['weighted_joules_per_output_token', 'avg_weighted_joules_per_output_token'], 'weighted_joules_per_output_token', 'NULL')},
            {sql_expr(columns, ['weighted_output_tokens_per_joule', 'avg_weighted_output_tokens_per_joule'], 'weighted_output_tokens_per_joule', 'NULL')},
            {sql_expr(columns, ['avg_energy_j', 'avg_llm_energy_joules'], 'avg_energy_j', 'NULL')},
            {sql_expr(columns, ['avg_tokens_per_second'], 'avg_tokens_per_second', 'NULL')},
            {sql_expr(columns, ['avg_score_per_wh_strict'], 'avg_score_per_wh_strict', 'NULL')},
            {sql_expr(columns, ['usable_output_rate', 'usable_rate'], 'usable_output_rate', 'NULL')},
            {sql_expr(columns, ['pipeline_usable_rate'], 'pipeline_usable_rate', 'NULL')},
            {sql_expr(columns, ['fully_correct_rate', 'success_rate'], 'fully_correct_rate', 'NULL')},
            {sql_expr(columns, ['hard_failure_rate'], 'hard_failure_rate', 'NULL')},
            {sql_expr(columns, ['gpu_name'], 'gpu_name', 'NULL')}
        FROM model_task_token_efficiency
        ORDER BY
            model ASC,
            task_id ASC,
            tdp_level ASC NULLS LAST
    """


def enrich_with_joined_json(rows: list[dict[str, Any]], joined_groups: dict[str, Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for row in rows:
        model = row.get("model")
        task_id = row.get("task_id")
        tdp_level = row.get("tdp_level")

        matched_group = None
        for _, group in joined_groups.items():
            models = group.get("models", []) or []
            task_ids = group.get("task_ids", []) or []
            tdp_levels = group.get("tdp_levels", []) or []
            if model in models and task_id in task_ids and tdp_level in tdp_levels:
                matched_group = group
                break

        merged = dict(row)
        if matched_group is None:
            merged["joined_group_found"] = False
            merged["success_rate"] = None
            merged["energy_valid_rate"] = None
            merged["failure_stage_distribution"] = {}
            merged["failure_type_distribution"] = {}
            merged["failure_subtype_distribution"] = {}
            merged["artifact_usability_distribution"] = {}
            merged["quality_class_distribution"] = {}
            merged["confidence_classification_distribution"] = {}
        else:
            merged["joined_group_found"] = True
            merged["success_rate"] = sanitize_value(matched_group.get("success_rate"))
            merged["energy_valid_rate"] = sanitize_value(matched_group.get("energy_valid_rate"))
            merged["failure_stage_distribution"] = matched_group.get("failure_stage_distribution", {}) or {}
            merged["failure_type_distribution"] = matched_group.get("failure_type_distribution", {}) or {}
            merged["failure_subtype_distribution"] = matched_group.get("failure_subtype_distribution", {}) or {}
            merged["artifact_usability_distribution"] = matched_group.get("artifact_usability_distribution", {}) or {}
            merged["quality_class_distribution"] = matched_group.get("quality_class_distribution", {}) or {}
            merged["confidence_classification_distribution"] = matched_group.get("confidence_classification_distribution", {}) or {}

        enriched.append(sanitize_row(merged))

    return enriched


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(f"Missing DuckDB file: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        if not relation_exists(con, "model_task_token_efficiency"):
            raise SystemExit("Missing DuckDB relation: model_task_token_efficiency")

        columns = get_relation_columns(con, "model_task_token_efficiency")
        query = build_query(columns)
        cursor = con.execute(query)
        fieldnames = [desc[0] for desc in cursor.description]
        base_rows = [sanitize_row(dict(zip(fieldnames, row))) for row in cursor.fetchall()]
    finally:
        con.close()

    joined_groups = load_joined_groups()
    rows = enrich_with_joined_json(base_rows, joined_groups)

    payload = {
        "generated_at_utc": utc_now_iso(),
        "source": str(DB_PATH),
        "source_relations": {
            "model_task_token_efficiency": True,
        },
        "joined_json_path": str(JOINED_JSON_PATH),
        "row_count": len(rows),
        "rows": rows,
    }

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(str(OUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
