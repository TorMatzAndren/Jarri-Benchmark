#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_ROOT = PROJECT_ROOT / "benchmarks"
POLICY_PATH = PROJECT_ROOT / "benchmark_runtime_policy.json"
OUT_DIR = BENCHMARKS_ROOT / "_analysis_inventory"
OUT_PATH = OUT_DIR / "benchmark_runtime_policy_enforcement.json"


CANONICAL_LEDGERS = [
    BENCHMARKS_ROOT / "coding_measurement_v3" / "llm_benchmark_runs.jsonl",
    BENCHMARKS_ROOT / "fact_prose_v2" / "llm_benchmark_runs.jsonl",
    BENCHMARKS_ROOT / "knowledge_measurement_v2" / "llm_benchmark_runs.jsonl",
    BENCHMARKS_ROOT / "language_measurement_v2" / "llm_benchmark_runs.jsonl",
    BENCHMARKS_ROOT / "math_measurement_v1" / "llm_benchmark_runs.jsonl",
]


@dataclass
class Policy:
    exclude_models: set[str]
    exclude_runtime_statuses: set[str]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy() -> Policy:
    raw = load_json(POLICY_PATH)
    runtime_policy = raw.get("canonical_runtime_policy", {}) or {}
    return Policy(
        exclude_models=set(runtime_policy.get("exclude_models", []) or []),
        exclude_runtime_statuses=set(runtime_policy.get("exclude_runtime_statuses", []) or [])
    )


def should_reject(row: dict[str, Any], policy: Policy) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    model = row.get("model")
    if model in policy.exclude_models:
        reasons.append("excluded_model")

    runtime_validation = row.get("runtime_validation", {}) or {}
    runtime_status = runtime_validation.get("residency_status") or runtime_validation.get("runtime_status")
    canonical_runtime = runtime_validation.get("canonical_runtime")

    if runtime_status in policy.exclude_runtime_statuses:
        reasons.append(f"excluded_runtime_status:{runtime_status}")

    if canonical_runtime is False:
        reasons.append("canonical_runtime_false")

    processor_split = runtime_validation.get("processor_split")
    if isinstance(processor_split, str) and "CPU/GPU" in processor_split:
        reasons.append(f"processor_split_hybrid:{processor_split}")

    return (len(reasons) > 0, reasons)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
      return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    policy = load_policy()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "generated_at_utc": utc_now_iso(),
        "policy_path": str(POLICY_PATH),
        "ledgers": [],
        "totals": {
            "rows_seen": 0,
            "rows_retained": 0,
            "rows_rejected": 0
        },
        "status": "ok"
    }

    for ledger_path in CANONICAL_LEDGERS:
        rows = read_jsonl(ledger_path)
        retained: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for row in rows:
            reject, reasons = should_reject(row, policy)
            summary["totals"]["rows_seen"] += 1

            if reject:
                rejected_row = dict(row)
                rejected_row["_runtime_policy_rejection_reasons"] = reasons
                rejected.append(rejected_row)
                summary["totals"]["rows_rejected"] += 1
            else:
                retained.append(row)
                summary["totals"]["rows_retained"] += 1

        quarantine_path = ledger_path.with_suffix(".runtime_rejected.jsonl")
        backup_path = ledger_path.with_suffix(".pre_runtime_policy_backup.jsonl")

        if ledger_path.exists() and not backup_path.exists():
            backup_path.write_text(ledger_path.read_text(encoding="utf-8"), encoding="utf-8")

        if ledger_path.exists():
            write_jsonl(ledger_path, retained)

        if rejected:
            write_jsonl(quarantine_path, rejected)
        elif quarantine_path.exists():
            quarantine_path.unlink()

        rejected_models = {}
        for row in rejected:
            model = row.get("model", "unknown")
            rejected_models[model] = rejected_models.get(model, 0) + 1

        summary["ledgers"].append({
            "ledger_path": str(ledger_path),
            "backup_path": str(backup_path),
            "quarantine_path": str(quarantine_path),
            "rows_seen": len(rows),
            "rows_retained": len(retained),
            "rows_rejected": len(rejected),
            "rejected_models": rejected_models
        })

    OUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(OUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
