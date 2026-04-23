#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EVALUATOR_VERSION = "logic_consistency_eval_v3"
TASK_ID = "logic_consistency_v2"
TASK_FAMILY = "knowledge"

EXPECTED_CONSISTENT = "NO"
EXPECTED_PAIRS = {("3", "4")}

SECTION_ANALYSIS = "=== ANALYSIS ==="
SECTION_CONTRADICTIONS = "=== CONTRADICTIONS ==="


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_pairs(text: str) -> tuple[list[tuple[str, str]], set[tuple[str, str]]]:
    ordered_pairs: list[tuple[str, str]] = []
    normalized_pairs: set[tuple[str, str]] = set()

    for line in text.splitlines():
        match = re.search(
            r"Statement\s+(\d+)\s+conflicts\s+with\s+Statement\s+(\d+)",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        a, b = match.group(1), match.group(2)
        normalized = tuple(sorted((a, b)))
        ordered_pairs.append(normalized)
        normalized_pairs.add(normalized)

    return ordered_pairs, normalized_pairs


def determine_quality_class(execution_status: str, score_percent: float) -> str:
    if execution_status != "ok":
        return "failed"
    if score_percent >= 85.0:
        return "high"
    if score_percent >= 65.0:
        return "high_partial"
    if score_percent >= 40.0:
        return "partial"
    if score_percent > 0.0:
        return "weak"
    return "failed"


def build_score(checks: dict[str, bool], hard_failure: bool) -> dict[str, Any]:
    passed = sum(1 for value in checks.values() if value)
    total = len(checks)
    score_percent = round((passed / total) * 100.0, 2) if total else 0.0
    return {
        "checks": checks,
        "passed_checks": passed,
        "total_checks": total,
        "score_percent": score_percent,
        "hard_failure": hard_failure,
    }


def determine_failure_stage(
    execution_status: str,
    failure_subtype: list[str],
) -> str | None:
    if execution_status != "ok":
        return "format"

    if not failure_subtype:
        return None

    semantic_subtypes = {
        "incorrect_consistency_flag",
        "missing_required_pair",
        "extra_pair_detected",
        "partial_pair_detection",
        "exact_pair_set_mismatch",
        "symmetric_duplicate_pair",
    }

    if any(subtype in semantic_subtypes for subtype in failure_subtype):
        return "semantic"

    return "constraint"


def determine_failure_type(
    execution_status: str,
    failure_subtype: list[str],
) -> str | None:
    if execution_status != "ok":
        return "format_violation"

    if not failure_subtype:
        return None

    if "missing_required_pair" in failure_subtype:
        return "logic_error"

    if "extra_pair_detected" in failure_subtype:
        return "over_inference"

    return "semantic_error"


def determine_success(
    execution_status: str,
    failure_type: str | None,
    score_percent: float,
) -> bool:
    return execution_status == "ok" and failure_type is None and score_percent == 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--save-report", default="")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    text = read_text(input_path)
    lines = [line.rstrip() for line in text.splitlines()]

    has_analysis_section = SECTION_ANALYSIS in lines
    has_contradictions_section = SECTION_CONTRADICTIONS in lines

    consistency_match = re.search(r"Consistent:\s*(YES|NO)", text, flags=re.IGNORECASE)
    consistent_value = consistency_match.group(1).upper() if consistency_match else None

    ordered_pairs, parsed_pairs = parse_pairs(text)
    duplicate_pair_count = max(0, len(ordered_pairs) - len(parsed_pairs))

    missing_required_pairs = sorted(EXPECTED_PAIRS - parsed_pairs)
    extra_pairs = sorted(parsed_pairs - EXPECTED_PAIRS)

    checks: dict[str, bool] = {
        "has_analysis_section": has_analysis_section,
        "has_contradictions_section": has_contradictions_section,
        "consistent_flag_present": consistent_value is not None,
        "consistent_flag_exact": consistent_value == EXPECTED_CONSISTENT,
        "required_pair_found": EXPECTED_PAIRS.issubset(parsed_pairs),
        "no_extra_pairs": parsed_pairs.issubset(EXPECTED_PAIRS),
        "exact_pair_set": parsed_pairs == EXPECTED_PAIRS,
        "no_duplicate_pair_mentions": duplicate_pair_count == 0,
    }

    failure_subtype: list[str] = []
    task_failures: dict[str, Any] = {}

    if not has_analysis_section:
        failure_subtype.append("missing_analysis_section")
        task_failures["missing_analysis_section"] = {"detected": True}

    if not has_contradictions_section:
        failure_subtype.append("missing_contradictions_section")
        task_failures["missing_contradictions_section"] = {"detected": True}

    if consistent_value is None:
        failure_subtype.append("missing_consistency_flag")
        task_failures["missing_consistency_flag"] = {"detected": True}
    elif consistent_value != EXPECTED_CONSISTENT:
        failure_subtype.append("incorrect_consistency_flag")
        task_failures["incorrect_consistency_flag"] = {
            "expected": EXPECTED_CONSISTENT,
            "actual": consistent_value,
        }

    if missing_required_pairs:
        failure_subtype.append("missing_required_pair")
        task_failures["missing_required_pair"] = {
            "expected_pairs": [list(pair) for pair in sorted(EXPECTED_PAIRS)],
            "missing_pairs": [list(pair) for pair in missing_required_pairs],
        }

    if extra_pairs:
        failure_subtype.append("extra_pair_detected")
        task_failures["extra_pair_detected"] = {
            "extra_pairs": [list(pair) for pair in extra_pairs],
        }

    if parsed_pairs != EXPECTED_PAIRS:
        failure_subtype.append("exact_pair_set_mismatch")
        task_failures["exact_pair_set_mismatch"] = {
            "expected_pairs": [list(pair) for pair in sorted(EXPECTED_PAIRS)],
            "actual_pairs": [list(pair) for pair in sorted(parsed_pairs)],
        }

    if parsed_pairs and EXPECTED_PAIRS.intersection(parsed_pairs) and parsed_pairs != EXPECTED_PAIRS:
        failure_subtype.append("partial_pair_detection")
        task_failures["partial_pair_detection"] = {
            "matched_pairs": [list(pair) for pair in sorted(EXPECTED_PAIRS.intersection(parsed_pairs))],
            "expected_pair_count": len(EXPECTED_PAIRS),
            "actual_pair_count": len(parsed_pairs),
        }

    if duplicate_pair_count > 0:
        failure_subtype.append("symmetric_duplicate_pair")
        task_failures["symmetric_duplicate_pair"] = {
            "duplicate_pair_mentions": duplicate_pair_count,
            "parsed_pair_mentions": [list(pair) for pair in ordered_pairs],
        }

    # Format-stage failures dominate execution status.
    format_subtypes = {
        "missing_analysis_section",
        "missing_contradictions_section",
        "missing_consistency_flag",
    }
    if any(subtype in format_subtypes for subtype in failure_subtype):
        execution_status = "format_violation"
        hard_failure = True
    else:
        execution_status = "ok"
        hard_failure = False

    score = build_score(checks, hard_failure=hard_failure)
    failure_subtype = sorted(set(failure_subtype))
    failure_stage = determine_failure_stage(execution_status, failure_subtype)
    failure_type = determine_failure_type(execution_status, failure_subtype)
    success = determine_success(execution_status, failure_type, score["score_percent"])

    artifact_usability = (
        "unusable" if execution_status != "ok"
        else "usable" if score["score_percent"] >= 85.0
        else "partial" if score["score_percent"] > 0.0
        else "unusable"
    )

    task_metrics = {
        "expected_consistent_flag": EXPECTED_CONSISTENT,
        "actual_consistent_flag": consistent_value,
        "expected_pairs": [list(pair) for pair in sorted(EXPECTED_PAIRS)],
        "actual_pairs": [list(pair) for pair in sorted(parsed_pairs)],
        "actual_pair_mentions": [list(pair) for pair in ordered_pairs],
        "missing_required_pair_count": len(missing_required_pairs),
        "extra_pair_count": len(extra_pairs),
        "duplicate_pair_mentions": duplicate_pair_count,
        "analysis_section_present": has_analysis_section,
        "contradictions_section_present": has_contradictions_section,
    }

    report = {
        "success": success,
        "evaluator_version": EVALUATOR_VERSION,
        "task_id": TASK_ID,
        "task_family": TASK_FAMILY,
        "execution_status": execution_status,
        "failure_type": failure_type,
        "failure_stage": failure_stage,
        "failure_subtype": failure_subtype,
        "quality_class": determine_quality_class(execution_status, score["score_percent"]),
        "artifact_usability": artifact_usability,
        "usable_output": artifact_usability in ("partial", "usable"),
        "pipeline_usable": success,
        "hard_failure": hard_failure,
        "score": score,
        "expected": {
            "consistent": EXPECTED_CONSISTENT,
            "contradiction_pairs": [list(pair) for pair in sorted(EXPECTED_PAIRS)],
        },
        "task_metrics": task_metrics,
        "task_failures": task_failures,
    }

    if args.save_report:
        Path(args.save_report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
