#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPORTER_VERSION = "jarri_benchmark_failure_aggregate_v2"

RUN_STEM_RE = re.compile(
    r"^(?P<tdp>\d+?)_(?P<body>.+?)_run(?P<run_index>\d+?)_report$"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace(" ", "_")


def unslug_model(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    if re.match(r"^.+_\d+(?:\.\d+)?[bB]$", text):
        head, size = text.rsplit("_", 1)
        return f"{head.replace('_', '-')}:{size.lower()}"

    return text.replace("_", "-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark failure taxonomy across report JSON files."
    )
    parser.add_argument(
        "input_paths",
        nargs="+",
        help="Benchmark directories and/or report directories and/or individual report JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where aggregate JSON files will be written.",
    )
    return parser.parse_args()


def normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_report_files(input_paths: list[str]) -> list[Path]:
    found: set[Path] = set()

    for raw in input_paths:
        path = Path(raw).expanduser().resolve()

        if path.is_file():
            if path.name.endswith("_report.json"):
                found.add(path)
            continue

        if not path.exists():
            continue

        if path.is_dir():
            if path.name == "reports":
                for item in sorted(path.glob("*_report.json")):
                    found.add(item.resolve())
            else:
                for item in sorted(path.rglob("reports/*_report.json")):
                    found.add(item.resolve())

    return sorted(found)


def infer_experiment_id(report_path: Path) -> str:
    parts = report_path.parts
    if "benchmarks" in parts:
        idx = parts.index("benchmarks")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def parse_run_metadata(report_path: Path, report: dict[str, Any]) -> dict[str, Any]:
    stem = report_path.stem
    match = RUN_STEM_RE.match(stem)

    experiment_id = infer_experiment_id(report_path)

    explicit_model = normalize_text(report.get("model"), "")
    explicit_model_safe = normalize_text(report.get("model_safe"), "")
    explicit_task_id = normalize_text(report.get("task_id"), "")

    power_limit_percent: int | None = None
    run_index: int | None = None
    filename_model_safe = ""
    filename_task_id = ""

    if match:
        power_limit_percent = int(match.group("tdp"))
        run_index = int(match.group("run_index"))
        body = normalize_text(match.group("body"), "")

        if explicit_task_id and body.endswith(f"_{explicit_task_id}"):
            filename_task_id = explicit_task_id
            filename_model_safe = body[: -(len(explicit_task_id) + 1)]
        else:
            filename_task_id = explicit_task_id
            filename_model_safe = body

    model_safe = explicit_model_safe or filename_model_safe
    model = explicit_model or unslug_model(model_safe)
    task_id = explicit_task_id or filename_task_id

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "report_filename": report_path.name,
        "task_id": task_id,
        "model": model,
        "model_safe": model_safe if model_safe else safe_slug(model) if model else "",
        "power_limit_percent": power_limit_percent,
        "run_index": run_index,
    }


def infer_stage(report: dict[str, Any]) -> str:
    if report.get("failure_stage"):
        return normalize_text(report.get("failure_stage"))
    if report.get("hard_failure") is False and report.get("usable_output") is True:
        return "success"
    return "unknown"


def infer_type(report: dict[str, Any]) -> str:
    if report.get("failure_type"):
        return normalize_text(report.get("failure_type"))
    if report.get("hard_failure") is False and report.get("usable_output") is True:
        return "success"
    return "unknown"


def infer_subtypes(report: dict[str, Any]) -> list[str]:
    value = report.get("failure_subtype")
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text(v) for v in value if normalize_text(v)]
    text = normalize_text(value)
    return [text] if text else []


def infer_task_family(report: dict[str, Any], experiment_id: str, task_id: str) -> str:
    family = normalize_text(report.get("task_family"), "")
    if family:
        return family

    if task_id.startswith("fact_"):
        return "fact"
    if task_id.startswith("prose_"):
        return "prose"
    if task_id.startswith("coding_"):
        return "coding"
    if task_id.startswith("math_"):
        return "math"
    if task_id.startswith("logic_"):
        return "knowledge"
    if task_id.startswith("constrained_"):
        return "language"

    if experiment_id.startswith("coding_"):
        return "coding"
    if experiment_id.startswith("math_"):
        return "math"
    if experiment_id.startswith("knowledge_"):
        return "knowledge"
    if experiment_id.startswith("language_"):
        return "language"
    if experiment_id.startswith("fact_"):
        return "fact_prose"

    return "unknown"


def infer_fully_correct(report: dict[str, Any]) -> bool:
    score = report.get("score", {})
    if isinstance(score, dict):
        score_percent = score.get("score_percent")
        try:
            if float(score_percent) >= 100.0:
                return True
        except (TypeError, ValueError):
            pass

    checks = score.get("checks") if isinstance(score, dict) else None
    if isinstance(checks, dict) and checks:
        return all(bool(v) for v in checks.values())

    return bool(report.get("success") is True and report.get("usable_output") is True)


def build_record(report_path: Path) -> dict[str, Any]:
    report = load_json(report_path)
    meta = parse_run_metadata(report_path, report)

    task_family = infer_task_family(report, meta["experiment_id"], meta["task_id"])
    failure_stage = infer_stage(report)
    failure_type = infer_type(report)
    failure_subtypes = infer_subtypes(report)

    score = report.get("score", {}) if isinstance(report.get("score"), dict) else {}
    task_failures = report.get("task_failures", {})
    if not isinstance(task_failures, dict):
        task_failures = {}

    syntax_valid_raw = report.get("syntax_valid")
    parse_valid = bool(syntax_valid_raw) if syntax_valid_raw is not None else (failure_stage != "parse")

    execution_status = normalize_text(report.get("execution_status"), "")
    runtime_valid = execution_status == "ok" or (failure_stage not in {"runtime", "parse"} and execution_status == "")

    usable_output = bool(report.get("usable_output") is True)
    pipeline_usable = bool(report.get("pipeline_usable") is True)
    hard_failure = bool(report.get("hard_failure") is True)
    fully_correct = infer_fully_correct(report)

    return {
        "experiment_id": meta["experiment_id"],
        "report_path": meta["report_path"],
        "report_filename": meta["report_filename"],
        "model": meta["model"],
        "model_safe": meta["model_safe"],
        "task_id": meta["task_id"],
        "task_family": task_family,
        "power_limit_percent": meta["power_limit_percent"],
        "run_index": meta["run_index"],
        "failure_stage": failure_stage,
        "failure_type": failure_type,
        "failure_subtypes": failure_subtypes,
        "quality_class": normalize_text(report.get("quality_class"), ""),
        "artifact_usability": normalize_text(report.get("artifact_usability"), ""),
        "confidence_classification": normalize_text(report.get("confidence_classification"), ""),
        "usable_output": usable_output,
        "pipeline_usable": pipeline_usable,
        "hard_failure": hard_failure,
        "parse_valid": parse_valid,
        "runtime_valid": runtime_valid,
        "fully_correct": fully_correct,
        "score_percent": score.get("score_percent"),
        "passed_checks": score.get("passed_checks"),
        "total_checks": score.get("total_checks"),
        "task_failure_keys": sorted(task_failures.keys()),
        "raw_report": report,
    }


def counter_to_sorted_dict(counter: Counter) -> dict[str, int]:
    return {k: counter[k] for k in sorted(counter.keys(), key=lambda x: str(x))}


def build_success_ladder(records: list[dict[str, Any]]) -> dict[str, int]:
    total = len(records)
    return {
        "total_runs": total,
        "returned_output": total,
        "parse_valid": sum(1 for r in records if r["parse_valid"]),
        "runtime_valid": sum(1 for r in records if r["runtime_valid"]),
        "usable_output": sum(1 for r in records if r["usable_output"]),
        "pipeline_usable": sum(1 for r in records if r["pipeline_usable"]),
        "fully_correct": sum(1 for r in records if r["fully_correct"]),
        "hard_failures": sum(1 for r in records if r["hard_failure"]),
    }


def build_distribution(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter = Counter()
    for record in records:
        value = record.get(field)
        if value in (None, ""):
            value = "unknown"
        counter[normalize_text(value, "unknown")] += 1
    return counter_to_sorted_dict(counter)


def build_subtype_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter()
    for record in records:
        subtypes = record.get("failure_subtypes") or []
        if not subtypes:
            counter["none"] += 1
        else:
            for subtype in subtypes:
                counter[normalize_text(subtype, "unknown")] += 1
    return counter_to_sorted_dict(counter)


def build_task_failure_key_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter()
    for record in records:
        keys = record.get("task_failure_keys") or []
        if not keys:
            counter["none"] += 1
        else:
            for key in keys:
                counter[normalize_text(key, "unknown")] += 1
    return counter_to_sorted_dict(counter)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    parse_failures = sum(1 for r in records if r["failure_stage"] == "parse")
    runtime_failures = sum(1 for r in records if r["failure_stage"] == "runtime")
    constraint_failures = sum(1 for r in records if r["failure_stage"] == "constraint")
    semantic_failures = sum(1 for r in records if r["failure_stage"] == "semantic")

    return {
        "total_runs": total,
        "models": sorted({r["model"] for r in records if r["model"]}),
        "experiments": sorted({r["experiment_id"] for r in records if r["experiment_id"]}),
        "task_ids": sorted({r["task_id"] for r in records if r["task_id"]}),
        "task_families": sorted({r["task_family"] for r in records if r["task_family"]}),
        "tdp_levels": sorted({r["power_limit_percent"] for r in records if r["power_limit_percent"] is not None}),
        "failure_stage_distribution": build_distribution(records, "failure_stage"),
        "failure_type_distribution": build_distribution(records, "failure_type"),
        "failure_subtype_distribution": build_subtype_distribution(records),
        "quality_class_distribution": build_distribution(records, "quality_class"),
        "artifact_usability_distribution": build_distribution(records, "artifact_usability"),
        "confidence_classification_distribution": build_distribution(records, "confidence_classification"),
        "task_failure_key_distribution": build_task_failure_key_distribution(records),
        "success_ladder": build_success_ladder(records),
        "rates": {
            "parse_failure_rate": round(parse_failures / total, 6) if total else 0.0,
            "runtime_failure_rate": round(runtime_failures / total, 6) if total else 0.0,
            "constraint_failure_rate": round(constraint_failures / total, 6) if total else 0.0,
            "semantic_failure_rate": round(semantic_failures / total, 6) if total else 0.0,
            "usable_output_rate": round(sum(1 for r in records if r["usable_output"]) / total, 6) if total else 0.0,
            "pipeline_usable_rate": round(sum(1 for r in records if r["pipeline_usable"]) / total, 6) if total else 0.0,
            "fully_correct_rate": round(sum(1 for r in records if r["fully_correct"]) / total, 6) if total else 0.0,
            "hard_failure_rate": round(sum(1 for r in records if r["hard_failure"]) / total, 6) if total else 0.0,
        },
    }


def group_records(records: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        value = record.get(field)
        key = "unknown" if value in (None, "") else str(value)
        grouped[key].append(record)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))


def build_index_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "input_report_count": len(records),
        "summary": summarize_records(records),
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    report_files = find_report_files(args.input_paths)
    if not report_files:
        raise SystemExit("No report files found.")

    records = [build_record(path) for path in report_files]

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_payload = build_index_summary(records)

    by_model_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_records(group)
            for key, group in group_records(records, "model").items()
        },
    }

    by_task_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_records(group)
            for key, group in group_records(records, "task_id").items()
        },
    }

    by_tdp_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_records(group)
            for key, group in group_records(records, "power_limit_percent").items()
        },
    }

    by_family_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "groups": {
            key: summarize_records(group)
            for key, group in group_records(records, "task_family").items()
        },
    }

    records_payload = {
        "generated_at_utc": utc_now_iso(),
        "exporter_version": EXPORTER_VERSION,
        "record_count": len(records),
        "records": [
            {
                k: v for k, v in record.items() if k != "raw_report"
            }
            for record in records
        ],
    }

    write_json(output_dir / "failure_summary.json", summary_payload)
    write_json(output_dir / "failure_by_model.json", by_model_payload)
    write_json(output_dir / "failure_by_task.json", by_task_payload)
    write_json(output_dir / "failure_by_tdp.json", by_tdp_payload)
    write_json(output_dir / "failure_by_task_family.json", by_family_payload)
    write_json(output_dir / "failure_records.json", records_payload)

    print(
        json.dumps(
            {
                "success": True,
                "exporter_version": EXPORTER_VERSION,
                "input_report_count": len(report_files),
                "output_dir": str(output_dir),
                "written_files": [
                    str(output_dir / "failure_summary.json"),
                    str(output_dir / "failure_by_model.json"),
                    str(output_dir / "failure_by_task.json"),
                    str(output_dir / "failure_by_tdp.json"),
                    str(output_dir / "failure_by_task_family.json"),
                    str(output_dir / "failure_records.json"),
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
