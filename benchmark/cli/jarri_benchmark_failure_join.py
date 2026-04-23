#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPORTER_VERSION = "jarri_benchmark_failure_join_v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_path(value: Any) -> str:
    if value is None:
        return ""
    return str(Path(str(value)).expanduser().resolve())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join normalized benchmark runs with failure taxonomy records."
    )
    parser.add_argument(
        "--analysis-root",
        required=True,
        help="Root directory containing exported benchmark analysis folders.",
    )
    parser.add_argument(
        "--failure-records",
        required=True,
        help="Path to failure_records.json from jarri_benchmark_failure_aggregate.py",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where joined outputs will be written.",
    )
    return parser.parse_args()


def build_failure_index(failure_records_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = load_json(failure_records_path)
    records = payload.get("records", [])

    by_report_path: dict[str, dict[str, Any]] = {}
    for record in records:
        key = normalize_path(record.get("report_path"))
        if key:
            by_report_path[key] = record

    return by_report_path, payload


def collect_normalized_runs(analysis_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for normalized_path in sorted(analysis_root.glob("*/normalized_runs.json")):
        experiment_dir = normalized_path.parent
        experiment_id = experiment_dir.name
        payload = load_json(normalized_path)

        if not isinstance(payload, list):
            continue

        for row in payload:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched["_analysis_experiment_id"] = experiment_id
            enriched["_analysis_source_path"] = str(normalized_path.resolve())
            rows.append(enriched)

    return rows


def bool_rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if bool(row.get(key))) / len(rows), 6)


def avg_of(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [safe_float(row.get(key)) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def min_of(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [safe_float(row.get(key)) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(min(values), 6)


def max_of(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [safe_float(row.get(key)) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(max(values), 6)


def distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, list):
            if not value:
                counter["none"] += 1
            else:
                for item in value:
                    counter[str(item)] += 1
        else:
            if value in (None, ""):
                counter["unknown"] += 1
            else:
                counter[str(value)] += 1
    return {k: counter[k] for k in sorted(counter.keys())}


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "models": sorted({str(row.get("model")) for row in rows if row.get("model") not in (None, "")}),
        "task_ids": sorted({str(row.get("task_id")) for row in rows if row.get("task_id") not in (None, "")}),
        "task_families": sorted({str(row.get("task_family")) for row in rows if row.get("task_family") not in (None, "")}),
        "tdp_levels": sorted({safe_int(row.get("power_limit_percent")) for row in rows if safe_int(row.get("power_limit_percent")) is not None}),
        "failure_stage_distribution": distribution(rows, "failure_stage"),
        "failure_type_distribution": distribution(rows, "failure_type"),
        "failure_subtype_distribution": distribution(rows, "failure_subtypes"),
        "quality_class_distribution": distribution(rows, "quality_class"),
        "artifact_usability_distribution": distribution(rows, "artifact_usability"),
        "confidence_classification_distribution": distribution(rows, "confidence_classification"),
        "success_rate": bool_rate(rows, "success"),
        "energy_valid_rate": bool_rate(rows, "energy_valid"),
        "usable_output_rate": bool_rate(rows, "usable_output"),
        "pipeline_usable_rate": bool_rate(rows, "pipeline_usable"),
        "fully_correct_rate": bool_rate(rows, "fully_correct"),
        "hard_failure_rate": bool_rate(rows, "hard_failure"),
        "avg_score_percent": avg_of(rows, "scientific_score_percent"),
        "min_score_percent": min_of(rows, "scientific_score_percent"),
        "max_score_percent": max_of(rows, "scientific_score_percent"),
        "avg_energy_j": avg_of(rows, "llm_energy_joules"),
        "min_energy_j": min_of(rows, "llm_energy_joules"),
        "max_energy_j": max_of(rows, "llm_energy_joules"),
        "avg_score_per_wh_strict": avg_of(rows, "score_per_wh_strict"),
        "avg_tokens_per_second": avg_of(rows, "tokens_per_second"),
    }


def group_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        group_key = "unknown" if value in (None, "") else str(value)
        grouped[group_key].append(row)
    return {k: grouped[k] for k in sorted(grouped.keys())}


def group_by_combo(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        parts = []
        for key in keys:
            value = row.get(key)
            parts.append("unknown" if value in (None, "") else str(value))
        combo_key = " | ".join(parts)
        grouped[combo_key].append(row)
    return {k: grouped[k] for k in sorted(grouped.keys())}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    analysis_root = Path(args.analysis_root).expanduser().resolve()
    failure_records_path = Path(args.failure_records).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    failure_index, failure_payload = build_failure_index(failure_records_path)
    normalized_rows = collect_normalized_runs(analysis_root)

    joined_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []

    for row in normalized_rows:
        report_path = normalize_path(row.get("evaluation_report_path"))
        failure = failure_index.get(report_path)

        joined = dict(row)
        joined["joined_report_path"] = report_path
        joined["failure_join_found"] = failure is not None

        if failure is not None:
            joined["failure_stage"] = failure.get("failure_stage")
            joined["failure_type"] = failure.get("failure_type")
            joined["failure_subtypes"] = failure.get("failure_subtypes", [])
            joined["quality_class"] = failure.get("quality_class")
            joined["artifact_usability"] = failure.get("artifact_usability")
            joined["confidence_classification"] = failure.get("confidence_classification")
            joined["usable_output"] = failure.get("usable_output")
            joined["pipeline_usable"] = failure.get("pipeline_usable")
            joined["hard_failure"] = failure.get("hard_failure")
            joined["parse_valid"] = failure.get("parse_valid")
            joined["runtime_valid"] = failure.get("runtime_valid")
            joined["fully_correct"] = failure.get("fully_correct")
            joined["task_failure_keys"] = failure.get("task_failure_keys", [])
        else:
            joined["failure_stage"] = "unmatched"
            joined["failure_type"] = "unmatched"
            joined["failure_subtypes"] = []
            joined["quality_class"] = "unmatched"
            joined["artifact_usability"] = "unmatched"
            joined["confidence_classification"] = "unmatched"
            joined["usable_output"] = None
            joined["pipeline_usable"] = None
            joined["hard_failure"] = None
            joined["parse_valid"] = None
            joined["runtime_valid"] = None
            joined["fully_correct"] = None
            joined["task_failure_keys"] = []
            unmatched_rows.append(joined)

        joined_rows.append(joined)

    overall_summary = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "analysis_root": str(analysis_root),
        "failure_records_path": str(failure_records_path),
        "failure_exporter_version": failure_payload.get("exporter_version"),
        "normalized_rows_total": len(normalized_rows),
        "joined_rows_total": len(joined_rows),
        "unmatched_rows_total": len(unmatched_rows),
        "summary": summarize_group(joined_rows),
    }

    by_model = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_group(group)
            for key, group in group_by_key(joined_rows, "model").items()
        },
    }

    by_task = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_group(group)
            for key, group in group_by_key(joined_rows, "task_id").items()
        },
    }

    by_tdp = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_group(group)
            for key, group in group_by_key(joined_rows, "power_limit_percent").items()
        },
    }

    by_model_task_tdp = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_group(group)
            for key, group in group_by_combo(joined_rows, ["model", "task_id", "power_limit_percent"]).items()
        },
    }

    joined_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "row_count": len(joined_rows),
        "rows": joined_rows,
    }

    unmatched_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "row_count": len(unmatched_rows),
        "rows": unmatched_rows,
    }

    write_json(output_dir / "joined_failure_energy_summary.json", overall_summary)
    write_json(output_dir / "joined_failure_energy_by_model.json", by_model)
    write_json(output_dir / "joined_failure_energy_by_task.json", by_task)
    write_json(output_dir / "joined_failure_energy_by_tdp.json", by_tdp)
    write_json(output_dir / "joined_failure_energy_by_model_task_tdp.json", by_model_task_tdp)
    write_json(output_dir / "joined_failure_energy_rows.json", joined_payload)
    write_json(output_dir / "joined_failure_energy_unmatched.json", unmatched_payload)

    print(
        json.dumps(
            {
                "success": True,
                "exporter_version": EXPORTER_VERSION,
                "normalized_rows_total": len(normalized_rows),
                "joined_rows_total": len(joined_rows),
                "unmatched_rows_total": len(unmatched_rows),
                "output_dir": str(output_dir),
                "written_files": [
                    str(output_dir / "joined_failure_energy_summary.json"),
                    str(output_dir / "joined_failure_energy_by_model.json"),
                    str(output_dir / "joined_failure_energy_by_task.json"),
                    str(output_dir / "joined_failure_energy_by_tdp.json"),
                    str(output_dir / "joined_failure_energy_by_model_task_tdp.json"),
                    str(output_dir / "joined_failure_energy_rows.json"),
                    str(output_dir / "joined_failure_energy_unmatched.json"),
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
