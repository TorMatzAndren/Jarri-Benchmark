#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_ROOT = PROJECT_ROOT / "benchmarks"
ANALYSIS_ROOT = BENCHMARKS_ROOT / "_analysis"
DB_PATH = BENCHMARKS_ROOT / "_db" / "benchmark.duckdb"

EXPERIMENT_IDS = [
    "coding_measurement_v3",
    "fact_prose_v2",
    "knowledge_measurement_v2",
    "language_measurement_v2",
    "math_measurement_v1",
]


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def safe_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


def safe_json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_analysis_paths() -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    normalized_paths: list[tuple[str, Path]] = []
    aggregate_paths: list[tuple[str, Path]] = []

    for experiment_id in EXPERIMENT_IDS:
        exp_root = ANALYSIS_ROOT / experiment_id
        normalized = exp_root / "normalized_runs.json"
        aggregate = exp_root / "aggregate_by_model_gpu_tdp_task.json"

        if normalized.exists():
            normalized_paths.append((experiment_id, normalized))
        if aggregate.exists():
            aggregate_paths.append((experiment_id, aggregate))

    return normalized_paths, aggregate_paths


def normalize_normalized_row(experiment_id: str, source_file: Path, row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = safe_int(row.get("prompt_tokens"))
    response_tokens = safe_int(row.get("response_tokens"))
    output_tokens = safe_int(row.get("output_tokens"))
    if output_tokens is None:
        output_tokens = response_tokens

    total_tokens = safe_int(row.get("total_tokens"))
    if total_tokens is None:
        total_tokens = (prompt_tokens or 0) + (response_tokens or 0)

    scientific_score_percent = safe_float(row.get("scientific_score_percent"))
    evaluation_score_percent = safe_float(row.get("evaluation_score_percent"))
    if scientific_score_percent is None:
        scientific_score_percent = evaluation_score_percent

    llm_energy_joules = safe_float(row.get("llm_energy_joules"))
    llm_energy_wh = safe_float(row.get("llm_energy_wh"))
    if llm_energy_wh is None and llm_energy_joules is not None:
        llm_energy_wh = llm_energy_joules / 3600.0

    score_per_output_token = safe_float(row.get("score_per_output_token"))
    if score_per_output_token is None and scientific_score_percent is not None and output_tokens and output_tokens > 0:
        score_per_output_token = scientific_score_percent / output_tokens

    score_per_100_output_tokens = safe_float(row.get("score_per_100_output_tokens"))
    if score_per_100_output_tokens is None and score_per_output_token is not None:
        score_per_100_output_tokens = score_per_output_token * 100.0

    llm_joules_per_output_token = safe_float(row.get("llm_joules_per_output_token"))
    if llm_joules_per_output_token is None and llm_energy_joules is not None and output_tokens and output_tokens > 0:
        llm_joules_per_output_token = llm_energy_joules / output_tokens

    output_tokens_per_joule = safe_float(row.get("output_tokens_per_joule"))
    if output_tokens_per_joule is None and llm_energy_joules is not None and llm_energy_joules > 0 and output_tokens and output_tokens > 0:
        output_tokens_per_joule = output_tokens / llm_energy_joules

    return {
        "analysis_experiment_id": experiment_id,
        "analysis_source_file": str(source_file),
        "source_row_index": row_index,
        "source_file": safe_str(row.get("source_file")),
        "experiment_id": safe_str(row.get("experiment_id")),
        "timestamp_utc": safe_str(row.get("timestamp_utc")),
        "model": safe_str(row.get("model")),
        "task_id": safe_str(row.get("task_id")),
        "task_family": safe_str(row.get("task_family")),
        "prompt_file": safe_str(row.get("prompt_file")),
        "prompt_hash": safe_str(row.get("prompt_hash")),
        "power_limit_percent": safe_int(row.get("power_limit_percent")),
        "power_limit_request": safe_str(row.get("power_limit_request")),
        "power_limit_request_mode": safe_str(row.get("power_limit_request_mode")),
        "power_limit_requested_watts": safe_float(row.get("power_limit_requested_watts")),
        "power_limit_applied_watts": safe_float(row.get("power_limit_applied_watts")),
        "run_index": safe_int(row.get("run_index")),
        "keep_alive": safe_str(row.get("keep_alive")),
        "duration_seconds": safe_float(row.get("duration_seconds")),
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "tokens_per_second": safe_float(row.get("tokens_per_second")),
        "cold_start": safe_bool(row.get("cold_start")),
        "gpu_name": safe_str(row.get("gpu_name")),
        "gpu_uuid": safe_str(row.get("gpu_uuid")),
        "gpu_driver_version": safe_str(row.get("gpu_driver_version")),
        "gpu_memory_total_mb": safe_int(row.get("gpu_memory_total_mb")),
        "gpu_index": safe_int(row.get("gpu_index")),
        "gpu_avg_power_w": safe_float(row.get("gpu_avg_power_w")),
        "gpu_peak_power_w": safe_float(row.get("gpu_peak_power_w")),
        "gpu_avg_util_percent": safe_float(row.get("gpu_avg_util_percent")),
        "gpu_peak_util_percent": safe_float(row.get("gpu_peak_util_percent")),
        "gpu_power_sample_count": safe_int(row.get("gpu_power_sample_count")),
        "idle_gpu_watts_discounted": safe_float(row.get("idle_gpu_watts_discounted")),
        "baseline_clamp_events": safe_int(row.get("baseline_clamp_events")),
        "llm_energy_joules": llm_energy_joules,
        "llm_energy_wh": llm_energy_wh,
        "llm_energy_kwh": safe_float(row.get("llm_energy_kwh")),
        "llm_joules_per_output_token": llm_joules_per_output_token,
        "llm_wh_per_1000_output_tokens": safe_float(row.get("llm_wh_per_1000_output_tokens")),
        "output_tokens_per_joule": output_tokens_per_joule,
        "score_per_output_token": score_per_output_token,
        "score_per_100_output_tokens": score_per_100_output_tokens,
        "evaluation_type": safe_str(row.get("evaluation_type")),
        "evaluation_score_percent": evaluation_score_percent,
        "scientific_score_percent": scientific_score_percent,
        "evaluation_passed_checks": safe_int(row.get("evaluation_passed_checks")),
        "evaluation_total_checks": safe_int(row.get("evaluation_total_checks")),
        "evaluation_report_path": safe_str(row.get("evaluation_report_path")),
        "runner_json_path": safe_str(row.get("runner_json_path")),
        "success": safe_bool(row.get("success")),
        "usable_output": safe_bool(row.get("usable_output")),
        "usable": safe_bool(row.get("usable")),
        "hard_failure": safe_bool(row.get("hard_failure")),
        "execution_status": safe_str(row.get("execution_status")),
        "artifact_usability": safe_str(row.get("artifact_usability")),
        "answer_risk": safe_str(row.get("answer_risk")),
        "final_answer_chars": safe_int(row.get("final_answer_chars")),
        "thinking_trace_chars": safe_int(row.get("thinking_trace_chars")),
        "energy_valid": safe_bool(row.get("energy_valid")),
        "energy_confidence_class": safe_str(row.get("energy_confidence_class")),
        "energy_confidence_reason": safe_str(row.get("energy_confidence_reason")),
        "energy_validity": safe_str(row.get("energy_validity")),
        "energy_measurement_version": safe_str(row.get("energy_measurement_version")),
        "score_per_second_strict": safe_float(row.get("score_per_second_strict")),
        "score_per_wh_strict": safe_float(row.get("score_per_wh_strict")),
        "error": safe_str(row.get("error")),
    }


def normalize_aggregate_row(experiment_id: str, source_file: Path, row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    runs = safe_int(row.get("runs"))
    avg_output_tokens = safe_float(row.get("avg_output_tokens"))
    total_output_tokens = safe_float(row.get("total_output_tokens"))
    avg_scientific_score_percent = safe_float(row.get("avg_scientific_score_percent"))
    avg_llm_energy_joules = safe_float(row.get("avg_llm_energy_joules"))

    weighted_score_per_output_token = safe_float(row.get("weighted_score_per_output_token"))
    if weighted_score_per_output_token is None and avg_scientific_score_percent is not None and avg_output_tokens and avg_output_tokens > 0:
        weighted_score_per_output_token = avg_scientific_score_percent / avg_output_tokens

    weighted_score_per_100_output_tokens = safe_float(row.get("weighted_score_per_100_output_tokens"))
    if weighted_score_per_100_output_tokens is None and weighted_score_per_output_token is not None:
        weighted_score_per_100_output_tokens = weighted_score_per_output_token * 100.0

    weighted_joules_per_output_token = safe_float(row.get("weighted_joules_per_output_token"))
    if weighted_joules_per_output_token is None and avg_llm_energy_joules is not None and avg_output_tokens and avg_output_tokens > 0:
        weighted_joules_per_output_token = avg_llm_energy_joules / avg_output_tokens

    weighted_output_tokens_per_joule = safe_float(row.get("weighted_output_tokens_per_joule"))
    if weighted_output_tokens_per_joule is None and avg_llm_energy_joules is not None and avg_llm_energy_joules > 0 and avg_output_tokens and avg_output_tokens > 0:
        weighted_output_tokens_per_joule = avg_output_tokens / avg_llm_energy_joules

    return {
        "analysis_experiment_id": experiment_id,
        "analysis_source_file": str(source_file),
        "source_row_index": row_index,
        "model": safe_str(row.get("model")),
        "gpu_name": safe_str(row.get("gpu_name")),
        "power_limit_percent": safe_int(row.get("power_limit_percent")),
        "power_limit_request": safe_str(row.get("power_limit_request")),
        "power_limit_applied_watts": safe_float(row.get("power_limit_applied_watts")),
        "task_id": safe_str(row.get("task_id")),
        "task_family": safe_str(row.get("task_family")),
        "runs": runs,
        "success_rate": safe_float(row.get("success_rate")),
        "usable_rate": safe_float(row.get("usable_rate")),
        "hard_failure_rate": safe_float(row.get("hard_failure_rate")),
        "energy_valid_rate": safe_float(row.get("energy_valid_rate")),
        "energy_measurement_versions_json": safe_json_text(row.get("energy_measurement_versions")),
        "avg_duration_seconds": safe_float(row.get("avg_duration_seconds")),
        "avg_tokens_per_second": safe_float(row.get("avg_tokens_per_second")),
        "avg_gpu_avg_power_w": safe_float(row.get("avg_gpu_avg_power_w")),
        "avg_gpu_peak_power_w": safe_float(row.get("avg_gpu_peak_power_w")),
        "avg_llm_energy_joules": avg_llm_energy_joules,
        "avg_llm_energy_wh": safe_float(row.get("avg_llm_energy_wh")),
        "avg_llm_joules_per_output_token": safe_float(row.get("avg_llm_joules_per_output_token")),
        "avg_llm_wh_per_1000_output_tokens": safe_float(row.get("avg_llm_wh_per_1000_output_tokens")),
        "avg_output_tokens_per_joule": safe_float(row.get("avg_output_tokens_per_joule")),
        "avg_evaluation_score_percent": safe_float(row.get("avg_evaluation_score_percent")),
        "avg_scientific_score_percent": avg_scientific_score_percent,
        "avg_score_per_second_strict": safe_float(row.get("avg_score_per_second_strict")),
        "avg_score_per_wh_strict": safe_float(row.get("avg_score_per_wh_strict")),
        "min_output_tokens": safe_float(row.get("min_output_tokens")),
        "max_output_tokens": safe_float(row.get("max_output_tokens")),
        "avg_output_tokens": avg_output_tokens,
        "median_output_tokens": safe_float(row.get("median_output_tokens")),
        "stddev_output_tokens": safe_float(row.get("stddev_output_tokens")),
        "total_output_tokens": total_output_tokens,
        "weighted_score_per_output_token": weighted_score_per_output_token,
        "weighted_score_per_100_output_tokens": weighted_score_per_100_output_tokens,
        "weighted_joules_per_output_token": weighted_joules_per_output_token,
        "weighted_output_tokens_per_joule": weighted_output_tokens_per_joule,
    }


def load_normalized_rows(paths: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for experiment_id, path in paths:
        payload = read_json_file(path)
        if not isinstance(payload, list):
            raise ValueError(f"Expected JSON list in {path}")
        for row_index, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Expected object rows in {path}")
            out.append(normalize_normalized_row(experiment_id, path, row_index, row))
    return out


def load_aggregate_rows(paths: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for experiment_id, path in paths:
        payload = read_json_file(path)
        if not isinstance(payload, list):
            raise ValueError(f"Expected JSON list in {path}")
        for row_index, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Expected object rows in {path}")
            out.append(normalize_aggregate_row(experiment_id, path, row_index, row))
    return out


def create_indexes(con: duckdb.DuckDBPyConnection) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_normalized_runs_model ON normalized_runs(model)",
        "CREATE INDEX IF NOT EXISTS idx_normalized_runs_task_id ON normalized_runs(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_normalized_runs_task_family ON normalized_runs(task_family)",
        "CREATE INDEX IF NOT EXISTS idx_normalized_runs_tdp ON normalized_runs(power_limit_percent)",
        "CREATE INDEX IF NOT EXISTS idx_normalized_runs_model_task_tdp ON normalized_runs(model, task_id, power_limit_percent)",
        "CREATE INDEX IF NOT EXISTS idx_aggregate_model ON aggregate_by_model_gpu_tdp_task(model)",
        "CREATE INDEX IF NOT EXISTS idx_aggregate_task_id ON aggregate_by_model_gpu_tdp_task(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_aggregate_model_task_tdp ON aggregate_by_model_gpu_tdp_task(model, task_id, power_limit_percent)",
    ]
    for statement in statements:
        try:
            con.execute(statement)
        except duckdb.Error:
            pass


def main() -> int:
    normalized_paths, aggregate_paths = load_analysis_paths()

    if not normalized_paths:
        raise SystemExit(f"No normalized_runs.json files found under {ANALYSIS_ROOT}")
    if not aggregate_paths:
        raise SystemExit(f"No aggregate_by_model_gpu_tdp_task.json files found under {ANALYSIS_ROOT}")

    normalized_df = pd.DataFrame(load_normalized_rows(normalized_paths))
    aggregate_df = pd.DataFrame(load_aggregate_rows(aggregate_paths))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_PATH))
    con.execute("BEGIN TRANSACTION")

    try:
        con.register("normalized_df", normalized_df)
        con.register("aggregate_df", aggregate_df)

        con.execute("DROP TABLE IF EXISTS normalized_runs")
        con.execute("DROP TABLE IF EXISTS aggregate_by_model_gpu_tdp_task")

        con.execute("CREATE TABLE normalized_runs AS SELECT * FROM normalized_df")
        con.execute("CREATE TABLE aggregate_by_model_gpu_tdp_task AS SELECT * FROM aggregate_df")

        con.execute("CREATE OR REPLACE VIEW benchmark_runs AS SELECT * FROM normalized_runs")
        con.execute("CREATE OR REPLACE VIEW benchmark_normalized_runs AS SELECT * FROM normalized_runs")
        con.execute("CREATE OR REPLACE VIEW benchmark_aggregates AS SELECT * FROM aggregate_by_model_gpu_tdp_task")

        con.execute("""
            CREATE OR REPLACE VIEW normalized_run_token_surface AS
            SELECT
                experiment_id,
                task_id,
                task_family,
                model,
                power_limit_percent,
                power_limit_request,
                power_limit_applied_watts,
                run_index,
                timestamp_utc,
                duration_seconds,
                prompt_tokens,
                response_tokens,
                output_tokens,
                total_tokens,
                tokens_per_second,
                llm_energy_joules,
                llm_energy_wh,
                llm_joules_per_output_token,
                llm_wh_per_1000_output_tokens,
                output_tokens_per_joule,
                score_per_output_token,
                score_per_100_output_tokens,
                scientific_score_percent,
                COALESCE(usable_output, usable) AS usable_output,
                hard_failure,
                energy_valid,
                energy_confidence_class
            FROM normalized_runs
        """)

        con.execute("""
            CREATE OR REPLACE VIEW model_task_token_efficiency AS
            SELECT
                model,
                task_id,
                task_family,
                power_limit_percent,
                power_limit_request,
                power_limit_applied_watts,
                runs,
                avg_scientific_score_percent,
                usable_rate,
                hard_failure_rate,
                avg_output_tokens,
                median_output_tokens,
                min_output_tokens,
                max_output_tokens,
                total_output_tokens,
                weighted_score_per_output_token,
                weighted_score_per_100_output_tokens,
                weighted_joules_per_output_token,
                weighted_output_tokens_per_joule,
                avg_llm_joules_per_output_token,
                avg_output_tokens_per_joule,
                avg_llm_wh_per_1000_output_tokens,
                avg_score_per_wh_strict,
                avg_tokens_per_second
            FROM aggregate_by_model_gpu_tdp_task
        """)

        con.execute("""
            CREATE OR REPLACE VIEW model_token_efficiency AS
            SELECT
                model,
                COUNT(*) AS configuration_rows,
                AVG(avg_scientific_score_percent) AS avg_score_percent,
                AVG(usable_rate) AS avg_usable_rate,
                AVG(hard_failure_rate) AS avg_hard_failure_rate,
                AVG(avg_output_tokens) AS avg_output_tokens,
                MEDIAN(avg_output_tokens) AS median_output_tokens,
                SUM(COALESCE(total_output_tokens, 0)) AS total_output_tokens,
                AVG(weighted_score_per_output_token) AS avg_weighted_score_per_output_token,
                AVG(weighted_score_per_100_output_tokens) AS avg_weighted_score_per_100_output_tokens,
                AVG(weighted_joules_per_output_token) AS avg_weighted_joules_per_output_token,
                AVG(weighted_output_tokens_per_joule) AS avg_weighted_output_tokens_per_joule,
                AVG(avg_score_per_wh_strict) AS avg_score_per_wh_strict,
                AVG(avg_tokens_per_second) AS avg_tokens_per_second
            FROM aggregate_by_model_gpu_tdp_task
            GROUP BY model
            ORDER BY avg_weighted_score_per_100_output_tokens DESC NULLS LAST, avg_score_percent DESC NULLS LAST
        """)

        create_indexes(con)

        normalized_count = con.execute("SELECT COUNT(*) FROM normalized_runs").fetchone()[0]
        aggregate_count = con.execute("SELECT COUNT(*) FROM aggregate_by_model_gpu_tdp_task").fetchone()[0]

        con.execute("COMMIT")
        con.unregister("normalized_df")
        con.unregister("aggregate_df")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    print(json.dumps(
        {
            "success": True,
            "duckdb_path": str(DB_PATH),
            "project_root": str(PROJECT_ROOT),
            "normalized_source_count": len(normalized_paths),
            "aggregate_source_count": len(aggregate_paths),
            "normalized_run_count": normalized_count,
            "aggregate_row_count": aggregate_count,
            "views": [
                "benchmark_runs",
                "benchmark_normalized_runs",
                "benchmark_aggregates",
                "normalized_run_token_surface",
                "model_task_token_efficiency",
                "model_token_efficiency",
            ],
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
