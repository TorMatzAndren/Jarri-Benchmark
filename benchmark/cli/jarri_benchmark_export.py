#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


EXPORTER_VERSION = "jarri_benchmark_export_v3"
DEFAULT_ENERGY_MEASUREMENT_VERSION = "run_sliced_v1"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def compute_stddev(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    return statistics.pstdev(values)


def compute_basic_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "stddev": None,
        }
    return {
        "min": round_or_none(min(values)),
        "max": round_or_none(max(values)),
        "avg": round_or_none(sum(values) / len(values)),
        "median": round_or_none(statistics.median(values)),
        "stddev": round_or_none(compute_stddev(values)),
    }


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def collect_jsonl_files(inputs: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: {path}")
        if path.is_file():
            if path.name.endswith(".jsonl"):
                found.append(path)
            else:
                raise ValueError(f"Input file is not a JSONL ledger: {path}")
        elif path.is_dir():
            found.extend(sorted(path.rglob("llm_benchmark_runs.jsonl")))
        else:
            raise ValueError(f"Unsupported input path: {path}")
    unique = sorted(dict.fromkeys(found))
    if not unique:
        raise FileNotFoundError("No llm_benchmark_runs.jsonl files found in inputs")
    return unique


def iter_jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSON row in {path}:{line_number}")
            yield row


def normalize_row(row: dict[str, Any], source_file: Path, row_index: int) -> dict[str, Any]:
    duration_seconds = safe_float(row.get("duration_seconds"))
    prompt_tokens = safe_int(row.get("prompt_tokens"))
    response_tokens = safe_int(row.get("response_tokens"))
    total_tokens = safe_int(row.get("total_tokens"))
    if total_tokens is None:
        total_tokens = (prompt_tokens or 0) + (response_tokens or 0)

    output_tokens = response_tokens

    tokens_per_second = safe_float(row.get("tokens_per_second"))
    if tokens_per_second is None and duration_seconds and duration_seconds > 0 and response_tokens is not None:
        tokens_per_second = response_tokens / duration_seconds

    llm_energy_joules = safe_float(row.get("llm_energy_joules"))
    llm_energy_wh = safe_float(row.get("llm_energy_wh"))
    llm_energy_kwh = safe_float(row.get("llm_energy_kwh"))

    if llm_energy_wh is None and llm_energy_joules is not None:
        llm_energy_wh = llm_energy_joules / 3600.0
    if llm_energy_kwh is None and llm_energy_wh is not None:
        llm_energy_kwh = llm_energy_wh / 1000.0

    evaluation_score_percent = safe_float(row.get("evaluation_score_percent"))
    if evaluation_score_percent is None:
        evaluation_score_percent = safe_float(row.get("score_per_process"))

    scientific_score_percent = safe_float(row.get("scientific_score_percent"))
    if scientific_score_percent is None:
        scientific_score_percent = evaluation_score_percent

    hard_failure = bool(row.get("hard_failure", False))
    success = bool(row.get("success", False))
    usable_output = row.get("usable_output")
    if usable_output is None:
        usable_output = row.get("usable")
    usable_output = bool(usable_output) if usable_output is not None else False

    energy_valid = row.get("energy_valid")
    if energy_valid is None:
        energy_valid = False
    energy_valid = bool(energy_valid)

    energy_confidence_class = row.get("energy_confidence_class")
    energy_confidence_reason = row.get("energy_confidence_reason")
    energy_measurement_version = row.get("energy_measurement_version")

    llm_joules_per_output_token = None
    llm_wh_per_1000_output_tokens = None
    output_tokens_per_joule = None
    score_per_output_token = None
    score_per_100_output_tokens = None

    if output_tokens is not None and output_tokens > 0 and scientific_score_percent is not None:
        score_per_output_token = scientific_score_percent / output_tokens
        score_per_100_output_tokens = score_per_output_token * 100.0

    if (
        energy_valid
        and llm_energy_joules is not None
        and llm_energy_joules > 0.0
        and output_tokens is not None
        and output_tokens > 0
    ):
        llm_joules_per_output_token = llm_energy_joules / output_tokens
        llm_wh_per_1000_output_tokens = (llm_energy_joules / output_tokens) * 1000.0 / 3600.0
        output_tokens_per_joule = output_tokens / llm_energy_joules

    score_per_second_strict = None
    if scientific_score_percent is not None and duration_seconds is not None and duration_seconds > 0.0:
        score_per_second_strict = scientific_score_percent / duration_seconds

    score_per_wh_strict = None
    if (
        scientific_score_percent is not None
        and energy_valid
        and llm_energy_wh is not None
        and llm_energy_wh > 0.0
    ):
        score_per_wh_strict = scientific_score_percent / llm_energy_wh

    return {
        "source_file": str(source_file),
        "source_row_index": row_index,
        "experiment_id": row.get("experiment_id"),
        "timestamp_utc": row.get("timestamp_utc"),
        "model": row.get("model"),
        "task_id": row.get("task_id"),
        "task_family": row.get("task_family"),
        "prompt_file": row.get("prompt_file"),
        "prompt_hash": row.get("prompt_hash"),
        "power_limit_percent": safe_int(row.get("power_limit_percent")),
        "run_index": safe_int(row.get("run_index")),
        "keep_alive": row.get("keep_alive"),
        "duration_seconds": round_or_none(duration_seconds, 6),
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "tokens_per_second": round_or_none(tokens_per_second, 6),
        "cold_start": bool(row.get("cold_start", False)),
        "gpu_name": row.get("gpu_name"),
        "gpu_uuid": row.get("gpu_uuid"),
        "gpu_driver_version": row.get("gpu_driver_version"),
        "gpu_memory_total_mb": safe_int(row.get("gpu_memory_total_mb")),
        "gpu_index": safe_int(row.get("gpu_index")),
        "gpu_avg_power_w": round_or_none(safe_float(row.get("gpu_avg_power_w")), 6),
        "gpu_peak_power_w": round_or_none(safe_float(row.get("gpu_peak_power_w")), 6),
        "gpu_avg_util_percent": round_or_none(safe_float(row.get("gpu_avg_util_percent")), 6),
        "gpu_peak_util_percent": round_or_none(safe_float(row.get("gpu_peak_util_percent")), 6),
        "gpu_power_sample_count": safe_int(row.get("gpu_power_sample_count")),
        "idle_gpu_watts_discounted": round_or_none(safe_float(row.get("idle_gpu_watts_discounted")), 6),
        "baseline_clamp_events": safe_int(row.get("baseline_clamp_events")),
        "llm_energy_joules": round_or_none(llm_energy_joules, 6),
        "llm_energy_wh": round_or_none(llm_energy_wh, 6),
        "llm_energy_kwh": round_or_none(llm_energy_kwh, 9),
        "llm_joules_per_output_token": round_or_none(llm_joules_per_output_token, 6),
        "llm_wh_per_1000_output_tokens": round_or_none(llm_wh_per_1000_output_tokens, 6),
        "output_tokens_per_joule": round_or_none(output_tokens_per_joule, 6),
        "score_per_output_token": round_or_none(score_per_output_token, 6),
        "score_per_100_output_tokens": round_or_none(score_per_100_output_tokens, 6),
        "evaluation_type": row.get("evaluation_type"),
        "evaluation_score_percent": round_or_none(evaluation_score_percent, 6),
        "scientific_score_percent": round_or_none(scientific_score_percent, 6),
        "evaluation_passed_checks": safe_int(row.get("evaluation_passed_checks")),
        "evaluation_total_checks": safe_int(row.get("evaluation_total_checks")),
        "evaluation_report_path": row.get("evaluation_report_path"),
        "runner_json_path": row.get("runner_json_path"),
        "success": success,
        "usable_output": usable_output,
        "hard_failure": hard_failure,
        "execution_status": row.get("execution_status"),
        "artifact_usability": row.get("artifact_usability"),
        "answer_risk": row.get("answer_risk"),
        "final_answer_chars": safe_int(row.get("final_answer_chars")),
        "thinking_trace_chars": safe_int(row.get("thinking_trace_chars")),
        "energy_valid": energy_valid,
        "energy_confidence_class": energy_confidence_class,
        "energy_confidence_reason": energy_confidence_reason,
        "energy_validity": row.get("energy_validity"),
        "energy_measurement_version": energy_measurement_version,
        "score_per_second_strict": round_or_none(score_per_second_strict, 6),
        "score_per_wh_strict": round_or_none(score_per_wh_strict, 6),
        "error": row.get("error", ""),
    }


def write_json(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def row_passes_filters(
    row: dict[str, Any],
    *,
    require_energy_measurement_version: str | None,
    require_energy_valid: bool,
    require_models: set[str] | None,
    require_task_families: set[str] | None,
    min_run_index: int | None,
) -> tuple[bool, str | None]:
    if require_energy_measurement_version is not None:
        if row.get("energy_measurement_version") != require_energy_measurement_version:
            return False, "energy_measurement_version_mismatch"

    if require_energy_valid and row.get("energy_valid") is not True:
        return False, "energy_not_valid"

    if require_models is not None and row.get("model") not in require_models:
        return False, "model_filtered_out"

    if require_task_families is not None and row.get("task_family") not in require_task_families:
        return False, "task_family_filtered_out"

    if min_run_index is not None:
        run_index = row.get("run_index")
        if run_index is None or int(run_index) < min_run_index:
            return False, "run_index_below_minimum"

    return True, None


def weighted_ratio(
    rows: list[dict[str, Any]],
    numerator_field: str,
    denominator_field: str,
    *,
    require_energy_valid: bool = False,
    scale: float = 1.0,
) -> float | None:
    numerator_total = 0.0
    denominator_total = 0.0

    for row in rows:
        if require_energy_valid and row.get("energy_valid") is not True:
            continue

        numerator = safe_float(row.get(numerator_field))
        denominator = safe_float(row.get(denominator_field))

        if numerator is None or denominator is None or denominator <= 0.0:
            continue

        numerator_total += numerator
        denominator_total += denominator

    if denominator_total <= 0.0:
        return None

    return round_or_none((numerator_total / denominator_total) * scale, 6)


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("model"),
            row.get("gpu_name"),
            row.get("power_limit_percent"),
            row.get("task_id"),
            row.get("task_family"),
        )
        grouped[key].append(row)

    aggregates: list[dict[str, Any]] = []

    metric_fields = [
        "duration_seconds",
        "tokens_per_second",
        "output_tokens",
        "gpu_avg_power_w",
        "gpu_peak_power_w",
        "llm_energy_joules",
        "llm_energy_wh",
        "llm_joules_per_output_token",
        "llm_wh_per_1000_output_tokens",
        "output_tokens_per_joule",
        "score_per_output_token",
        "score_per_100_output_tokens",
        "evaluation_score_percent",
        "scientific_score_percent",
        "score_per_second_strict",
        "score_per_wh_strict",
    ]

    for key in sorted(grouped.keys(), key=lambda k: tuple("" if v is None else str(v) for v in k)):
        model, gpu_name, power_limit_percent, task_id, task_family = key
        group_rows = grouped[key]

        runs = len(group_rows)
        success_rate = sum(1 for row in group_rows if row["success"]) / runs
        usable_rate = sum(1 for row in group_rows if row["usable_output"]) / runs
        hard_failure_rate = sum(1 for row in group_rows if row["hard_failure"]) / runs
        energy_valid_rate = sum(1 for row in group_rows if row["energy_valid"]) / runs

        aggregate: dict[str, Any] = {
            "model": model,
            "gpu_name": gpu_name,
            "power_limit_percent": power_limit_percent,
            "task_id": task_id,
            "task_family": task_family,
            "runs": runs,
            "success_rate": round_or_none(success_rate, 6),
            "usable_rate": round_or_none(usable_rate, 6),
            "hard_failure_rate": round_or_none(hard_failure_rate, 6),
            "energy_valid_rate": round_or_none(energy_valid_rate, 6),
            "energy_measurement_versions": sorted(
                {
                    row["energy_measurement_version"]
                    for row in group_rows
                    if row.get("energy_measurement_version") is not None
                }
            ),
        }

        for field in metric_fields:
            if field in {
                "llm_energy_joules",
                "llm_energy_wh",
                "llm_joules_per_output_token",
                "llm_wh_per_1000_output_tokens",
                "output_tokens_per_joule",
                "score_per_wh_strict",
            }:
                values = [
                    float(row[field]) for row in group_rows
                    if row.get("energy_valid") is True and row.get(field) is not None
                ]
            else:
                values = [float(row[field]) for row in group_rows if row.get(field) is not None]

            stats = compute_basic_stats(values)
            aggregate[f"min_{field}"] = stats["min"]
            aggregate[f"max_{field}"] = stats["max"]
            aggregate[f"avg_{field}"] = stats["avg"]
            aggregate[f"median_{field}"] = stats["median"]
            aggregate[f"stddev_{field}"] = stats["stddev"]

        total_output_tokens = sum(
            int(row.get("output_tokens") or 0)
            for row in group_rows
            if row.get("output_tokens") is not None
        )
        aggregate["total_output_tokens"] = total_output_tokens

        aggregate["weighted_joules_per_output_token"] = weighted_ratio(
            group_rows,
            "llm_energy_joules",
            "output_tokens",
            require_energy_valid=True,
        )
        aggregate["weighted_output_tokens_per_joule"] = weighted_ratio(
            group_rows,
            "output_tokens",
            "llm_energy_joules",
            require_energy_valid=True,
        )
        aggregate["weighted_score_per_output_token"] = weighted_ratio(
            group_rows,
            "scientific_score_percent",
            "output_tokens",
            require_energy_valid=False,
        )
        aggregate["weighted_score_per_100_output_tokens"] = weighted_ratio(
            group_rows,
            "scientific_score_percent",
            "output_tokens",
            require_energy_valid=False,
            scale=100.0,
        )

        aggregates.append(aggregate)

    return aggregates


def choose_best(
    aggregates: list[dict[str, Any]],
    model: str,
    key_field: str,
    reverse: bool = True,
    require_non_null: bool = True,
) -> dict[str, Any] | None:
    model_rows = [row for row in aggregates if row.get("model") == model]
    if require_non_null:
        model_rows = [row for row in model_rows if row.get(key_field) is not None]
    if not model_rows:
        return None

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        primary = row.get(key_field)
        if primary is None:
            primary = -math.inf if reverse else math.inf
        success_fallback = row.get("avg_scientific_score_percent")
        if success_fallback is None:
            success_fallback = -math.inf
        usable = row.get("usable_rate")
        if usable is None:
            usable = -math.inf
        tps = row.get("avg_tokens_per_second")
        if tps is None:
            tps = -math.inf
        return (
            primary,
            success_fallback,
            usable,
            tps,
            -int(row.get("power_limit_percent") or 0),
            row.get("task_id") or "",
        )

    model_rows.sort(key=sort_key, reverse=reverse)
    return model_rows[0]


def build_summary_views(aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    models = sorted({row["model"] for row in aggregates if row.get("model")})

    best_raw_score = []
    best_score_per_wh = []
    best_tokens_per_second = []
    lowest_failure_rate = []
    best_usable_rate = []
    lowest_output_tokens = []
    best_score_per_100_output_tokens = []
    best_output_tokens_per_joule = []
    worst_token_bloat = []

    for model in models:
        row = choose_best(aggregates, model, "avg_scientific_score_percent", reverse=True)
        if row is not None:
            best_raw_score.append(row)

        row = choose_best(aggregates, model, "avg_score_per_wh_strict", reverse=True)
        if row is not None:
            best_score_per_wh.append(row)

        row = choose_best(aggregates, model, "avg_tokens_per_second", reverse=True)
        if row is not None:
            best_tokens_per_second.append(row)

        row = choose_best(aggregates, model, "hard_failure_rate", reverse=False)
        if row is not None:
            lowest_failure_rate.append(row)

        row = choose_best(aggregates, model, "usable_rate", reverse=True)
        if row is not None:
            best_usable_rate.append(row)

        row = choose_best(aggregates, model, "avg_output_tokens", reverse=False)
        if row is not None:
            lowest_output_tokens.append(row)

        row = choose_best(aggregates, model, "weighted_score_per_100_output_tokens", reverse=True)
        if row is not None:
            best_score_per_100_output_tokens.append(row)

        row = choose_best(aggregates, model, "weighted_output_tokens_per_joule", reverse=True)
        if row is not None:
            best_output_tokens_per_joule.append(row)

        row = choose_best(aggregates, model, "avg_output_tokens", reverse=True)
        if row is not None:
            worst_token_bloat.append(row)

    top_configurations_overall = [
        row for row in aggregates
        if row.get("avg_score_per_wh_strict") is not None
    ]
    top_configurations_overall.sort(
        key=lambda row: (
            float(row.get("avg_score_per_wh_strict") or -math.inf),
            float(row.get("avg_scientific_score_percent") or -math.inf),
            float(row.get("usable_rate") or -math.inf),
            -int(row.get("power_limit_percent") or 0),
            row.get("model") or "",
            row.get("task_id") or "",
        ),
        reverse=True,
    )

    return {
        "best_raw_score_per_model": best_raw_score,
        "best_score_per_wh_per_model": best_score_per_wh,
        "best_tokens_per_second_per_model": best_tokens_per_second,
        "lowest_failure_rate_per_model": lowest_failure_rate,
        "best_usable_rate_per_model": best_usable_rate,
        "lowest_output_tokens_per_model": lowest_output_tokens,
        "best_score_per_100_output_tokens_per_model": best_score_per_100_output_tokens,
        "best_output_tokens_per_joule_per_model": best_output_tokens_per_joule,
        "worst_token_bloat_per_model": worst_token_bloat,
        "top_configurations_overall": top_configurations_overall[:25],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export normalized benchmark rows, aggregate tables, and summary views from benchmark JSONL ledgers."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more llm_benchmark_runs.jsonl files or benchmark directories containing them.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write normalized rows, aggregates, and summary outputs into.",
    )
    parser.add_argument(
        "--energy-measurement-version",
        default=DEFAULT_ENERGY_MEASUREMENT_VERSION,
        help="Canonical energy measurement version to mark as current in export metadata.",
    )
    parser.add_argument(
        "--require-energy-measurement-version",
        default=None,
        help="Only include rows matching this energy measurement version.",
    )
    parser.add_argument(
        "--require-energy-valid",
        action="store_true",
        help="Only include rows where energy_valid == true.",
    )
    parser.add_argument(
        "--require-models",
        default="",
        help="Comma-separated model whitelist.",
    )
    parser.add_argument(
        "--require-task-families",
        default="",
        help="Comma-separated task_family whitelist.",
    )
    parser.add_argument(
        "--min-run-index",
        type=int,
        default=None,
        help="Only include rows with run_index >= this value.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_output_dir(output_dir)

    input_files = collect_jsonl_files(args.inputs)

    require_models = {x.strip() for x in args.require_models.split(",") if x.strip()} or None
    require_task_families = {x.strip() for x in args.require_task_families.split(",") if x.strip()} or None

    all_rows: list[dict[str, Any]] = []
    exclusion_reasons: dict[str, int] = defaultdict(int)

    for source_file in input_files:
        for row_index, row in enumerate(iter_jsonl_rows(source_file), start=1):
            normalized = normalize_row(row, source_file, row_index)
            all_rows.append(normalized)

    filtered_rows: list[dict[str, Any]] = []
    for row in all_rows:
        keep, reason = row_passes_filters(
            row,
            require_energy_measurement_version=args.require_energy_measurement_version,
            require_energy_valid=args.require_energy_valid,
            require_models=require_models,
            require_task_families=require_task_families,
            min_run_index=args.min_run_index,
        )
        if keep:
            filtered_rows.append(row)
        else:
            assert reason is not None
            exclusion_reasons[reason] += 1

    filtered_rows.sort(
        key=lambda row: (
            row.get("timestamp_utc") or "",
            row.get("model") or "",
            row.get("power_limit_percent") or 0,
            row.get("task_id") or "",
            row.get("run_index") or 0,
            row.get("source_file") or "",
            row.get("source_row_index") or 0,
        )
    )

    aggregates = aggregate_rows(filtered_rows)
    summary_views = build_summary_views(aggregates)

    export_document = {
        "exporter_version": EXPORTER_VERSION,
        "canonical_energy_measurement_version": args.energy_measurement_version,
        "input_files": [str(path) for path in input_files],
        "filtering": {
            "require_energy_measurement_version": args.require_energy_measurement_version,
            "require_energy_valid": args.require_energy_valid,
            "require_models": sorted(require_models) if require_models else [],
            "require_task_families": sorted(require_task_families) if require_task_families else [],
            "min_run_index": args.min_run_index,
            "input_rows_total": len(all_rows),
            "rows_included": len(filtered_rows),
            "rows_excluded": len(all_rows) - len(filtered_rows),
            "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        },
        "normalized_row_count": len(filtered_rows),
        "aggregate_row_count": len(aggregates),
        "summary": {
            "models": sorted({row.get("model") for row in filtered_rows if row.get("model")}),
            "task_ids": sorted({row.get("task_id") for row in filtered_rows if row.get("task_id")}),
            "gpu_names": sorted({row.get("gpu_name") for row in filtered_rows if row.get("gpu_name")}),
            "energy_measurement_versions_present": sorted(
                {
                    row.get("energy_measurement_version")
                    for row in filtered_rows
                    if row.get("energy_measurement_version") is not None
                }
            ),
        },
        "normalized_rows": filtered_rows,
        "aggregates": aggregates,
        "summary_views": summary_views,
    }

    write_json(output_dir / "benchmark_export.json", export_document)
    write_json(output_dir / "normalized_runs.json", filtered_rows)
    write_json(output_dir / "aggregate_by_model_gpu_tdp_task.json", aggregates)
    write_json(output_dir / "summary_views.json", summary_views)

    write_csv(output_dir / "normalized_runs.csv", filtered_rows)
    write_csv(output_dir / "aggregate_by_model_gpu_tdp_task.csv", aggregates)

    print(json.dumps(
        {
            "success": True,
            "exporter_version": EXPORTER_VERSION,
            "output_dir": str(output_dir),
            "input_file_count": len(input_files),
            "input_rows_total": len(all_rows),
            "rows_included": len(filtered_rows),
            "rows_excluded": len(all_rows) - len(filtered_rows),
            "aggregate_row_count": len(aggregates),
            "written_files": [
                str(output_dir / "benchmark_export.json"),
                str(output_dir / "normalized_runs.json"),
                str(output_dir / "aggregate_by_model_gpu_tdp_task.json"),
                str(output_dir / "summary_views.json"),
                str(output_dir / "normalized_runs.csv"),
                str(output_dir / "aggregate_by_model_gpu_tdp_task.csv"),
            ],
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
