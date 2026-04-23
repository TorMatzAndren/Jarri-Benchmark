#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, UTC
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "benchmark_ui" / "data"
FAILURE_RECORDS_PATH = DATA_DIR / "failures" / "failure_records.json"
TASK_RANKINGS_PATH = DATA_DIR / "duckdb_task_rankings.json"
OUT_PATH = DATA_DIR / "duckdb_failure_surfaces.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_records(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return payload["records"]
        if isinstance(payload.get("rows"), list):
            return payload["rows"]
        if isinstance(payload.get("failure_records"), list):
            return payload["failure_records"]
    return []


def get_first(record: dict, keys: list[str], default=None):
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return default


def normalize_subtypes(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        return [value]
    return [str(value)]


def counter_to_rows(counter: Counter, total: int) -> list[dict]:
    rows = []
    for name, count in counter.most_common():
        rows.append({
            "name": name,
            "count": count,
            "rate": (count / total) if total else 0.0,
        })
    return rows


def main() -> int:
    failure_payload = load_json(FAILURE_RECORDS_PATH)
    task_rankings_payload = load_json(TASK_RANKINGS_PATH)

    records = normalize_records(failure_payload)
    task_rows = task_rankings_payload.get("rows", []) if isinstance(task_rankings_payload, dict) else []

    benchmark_counts: dict[tuple[str, str], int] = {}
    task_meta: dict[tuple[str, str], dict] = {}

    for row in task_rows:
        key = (str(row.get("model")), str(row.get("task_id")))
        benchmark_counts[key] = benchmark_counts.get(key, 0) + int(row.get("benchmark_count") or 0)
        task_meta[key] = {
            "task_family": row.get("task_family"),
        }

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        model = str(get_first(record, ["model", "model_name"], "unknown"))
        task_id = str(get_first(record, ["task_id", "task", "benchmark_task_id"], "unknown"))
        grouped[(model, task_id)].append(record)

    rows: list[dict] = []

    for (model, task_id), group_records in sorted(grouped.items()):
        total_failures = len(group_records)
        benchmark_count = benchmark_counts.get((model, task_id), 0)

        stage_counter = Counter()
        type_counter = Counter()
        subtype_counter = Counter()

        representative_failures = []

        for record in group_records:
            stage = str(get_first(record, ["failure_stage", "stage"], "unknown"))
            ftype = str(get_first(record, ["failure_type", "type"], "unknown"))
            subtypes = normalize_subtypes(get_first(record, ["failure_subtype", "subtype", "failure_subtypes"], []))

            stage_counter[stage] += 1
            type_counter[ftype] += 1
            for subtype in subtypes:
                subtype_counter[subtype] += 1

            if len(representative_failures) < 8:
                representative_failures.append({
                    "failure_stage": stage,
                    "failure_type": ftype,
                    "failure_subtype": subtypes,
                    "score_percent": get_first(record, ["score_percent"]),
                    "quality_class": get_first(record, ["quality_class"]),
                    "artifact_usability": get_first(record, ["artifact_usability"]),
                    "pipeline_usable": get_first(record, ["pipeline_usable"]),
                    "hard_failure": get_first(record, ["hard_failure"]),
                })

        rows.append({
            "model": model,
            "task_id": task_id,
            "task_family": task_meta.get((model, task_id), {}).get("task_family"),
            "benchmark_count": benchmark_count,
            "failure_record_count": total_failures,
            "failure_record_rate_vs_benchmarks": (total_failures / benchmark_count) if benchmark_count else None,
            "dominant_failure_stage": counter_to_rows(stage_counter, total_failures)[:5],
            "dominant_failure_type": counter_to_rows(type_counter, total_failures)[:5],
            "dominant_failure_subtype": counter_to_rows(subtype_counter, total_failures)[:8],
            "failure_stage_distribution": counter_to_rows(stage_counter, total_failures),
            "failure_type_distribution": counter_to_rows(type_counter, total_failures),
            "failure_subtype_distribution": counter_to_rows(subtype_counter, total_failures),
            "representative_failures": representative_failures,
        })

    payload = {
        "generated_at_utc": utc_now_iso(),
        "source_failure_records": str(FAILURE_RECORDS_PATH),
        "source_task_rankings": str(TASK_RANKINGS_PATH),
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
