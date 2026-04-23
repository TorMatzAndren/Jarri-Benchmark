#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


EVALUATOR_VERSION = "math_dependency_eval_v3"
TASK_ID = "math_dependency_v1"
TASK_FAMILY = "math"

VALUES = {
    "A": 120,
    "B": 80,
    "C": 150,
    "D": 50,
}

SECTION_INITIAL = "=== INITIAL ==="
SECTION_FILTERED = "=== FILTERED ==="
SECTION_FINAL = "=== FINAL ==="


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_expected() -> dict[str, Any]:
    total_initial = sum(VALUES.values())
    initial = {key: round2(value / total_initial * 100.0) for key, value in VALUES.items()}

    smallest_label = min(VALUES.items(), key=lambda item: item[1])[0]
    filtered_values = {key: value for key, value in VALUES.items() if key != smallest_label}
    total_filtered = sum(filtered_values.values())
    filtered = {key: round2(value / total_filtered * 100.0) for key, value in filtered_values.items()}

    final_score = (total_filtered * len(filtered_values)) % 97

    return {
        "initial_total": total_initial,
        "initial_percents": initial,
        "smallest_label": smallest_label,
        "filtered_total": total_filtered,
        "filtered_percents": filtered,
        "final_score": final_score,
    }


def parse_percent(line: str, label: str) -> float | None:
    match = re.search(rf"^{label}:\s*([0-9]+(?:\.[0-9]+)?)%$", line.strip())
    if not match:
        return None
    return float(match.group(1))


def approx_equal(actual: float | None, expected: float | None, tol: float = 0.02) -> bool:
    if actual is None or expected is None:
        return False
    return abs(actual - expected) <= tol


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


def determine_failure_stage(execution_status: str, failure_subtype: list[str]) -> str | None:
    if execution_status != "ok":
        return "format"

    if not failure_subtype:
        return None

    parse_subtypes = {
        "missing_initial_total",
        "missing_filtered_total",
        "missing_final_score",
        "missing_initial_percent",
        "missing_filtered_percent",
    }
    semantic_subtypes = {
        "initial_total_incorrect",
        "filtered_total_incorrect",
        "smallest_value_not_removed",
        "final_score_mismatch",
        "percentage_mismatch",
        "rounding_error",
    }

    if any(subtype in parse_subtypes for subtype in failure_subtype):
        return "parse"
    if any(subtype in semantic_subtypes for subtype in failure_subtype):
        return "semantic"

    return "constraint"


def determine_failure_type(execution_status: str, failure_subtype: list[str]) -> str | None:
    if execution_status != "ok":
        return "format_violation"

    if not failure_subtype:
        return None

    if "smallest_value_not_removed" in failure_subtype:
        return "logic_error"

    if "initial_total_incorrect" in failure_subtype or "filtered_total_incorrect" in failure_subtype:
        return "arithmetic_error"

    if "final_score_mismatch" in failure_subtype:
        return "dependency_error"

    if "percentage_mismatch" in failure_subtype or "rounding_error" in failure_subtype:
        return "precision_error"

    if any(
        subtype in failure_subtype
        for subtype in {
            "missing_initial_total",
            "missing_filtered_total",
            "missing_final_score",
            "missing_initial_percent",
            "missing_filtered_percent",
        }
    ):
        return "parse_failure"

    return "semantic_error"


def determine_success(execution_status: str, failure_type: str | None, score_percent: float) -> bool:
    return execution_status == "ok" and failure_type is None and score_percent == 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--save-report", default="")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    text = read_text(input_path)
    expected = compute_expected()

    lines = [line.rstrip() for line in text.splitlines()]

    has_initial = SECTION_INITIAL in lines
    has_filtered = SECTION_FILTERED in lines
    has_final = SECTION_FINAL in lines

    try:
        i0 = lines.index(SECTION_INITIAL)
        i1 = lines.index(SECTION_FILTERED)
        i2 = lines.index(SECTION_FINAL)
    except ValueError:
        i0 = i1 = i2 = -1

    valid_section_order = i0 != -1 and i1 != -1 and i2 != -1 and i0 < i1 < i2

    initial_block: list[str] = []
    filtered_block: list[str] = []
    final_block: list[str] = []

    if valid_section_order:
        initial_block = lines[i0 + 1:i1]
        filtered_block = lines[i1 + 1:i2]
        final_block = lines[i2 + 1:]

    initial_total = None
    filtered_total = None
    final_score = None

    if valid_section_order:
        for line in initial_block:
            match = re.match(r"Total:\s*(\d+)$", line.strip())
            if match:
                initial_total = int(match.group(1))

        for line in filtered_block:
            match = re.match(r"Total:\s*(\d+)$", line.strip())
            if match:
                filtered_total = int(match.group(1))

        for line in final_block:
            match = re.match(r"Score:\s*(\d+)$", line.strip())
            if match:
                final_score = int(match.group(1))

    parsed_initial = {key: None for key in ["A", "B", "C", "D"]}
    parsed_filtered = {key: None for key in ["A", "B", "C", "D"]}

    if valid_section_order:
        for line in initial_block:
            for label in parsed_initial:
                value = parse_percent(line, label)
                if value is not None:
                    parsed_initial[label] = value

        for line in filtered_block:
            for label in parsed_filtered:
                value = parse_percent(line, label)
                if value is not None:
                    parsed_filtered[label] = value

    checks: dict[str, bool] = {
        "has_initial_section": has_initial,
        "has_filtered_section": has_filtered,
        "has_final_section": has_final,
        "valid_section_order": valid_section_order,
        "initial_total_present": initial_total is not None,
        "filtered_total_present": filtered_total is not None,
        "final_score_present": final_score is not None,
        "initial_total_exact": initial_total == expected["initial_total"],
        "removed_smallest_value": parsed_filtered[expected["smallest_label"]] is None,
        "filtered_total_exact": filtered_total == expected["filtered_total"],
        "final_score_exact": final_score == expected["final_score"],
        "initial_A_approx": approx_equal(parsed_initial["A"], expected["initial_percents"]["A"]),
        "initial_B_approx": approx_equal(parsed_initial["B"], expected["initial_percents"]["B"]),
        "initial_C_approx": approx_equal(parsed_initial["C"], expected["initial_percents"]["C"]),
        "initial_D_approx": approx_equal(parsed_initial["D"], expected["initial_percents"]["D"]),
        "filtered_A_approx": approx_equal(parsed_filtered["A"], expected["filtered_percents"]["A"]),
        "filtered_B_approx": approx_equal(parsed_filtered["B"], expected["filtered_percents"]["B"]),
        "filtered_C_approx": approx_equal(parsed_filtered["C"], expected["filtered_percents"]["C"]),
    }

    failure_subtype: list[str] = []
    task_failures: dict[str, Any] = {}

    if not has_initial:
        failure_subtype.append("missing_initial_section")
        task_failures["missing_initial_section"] = {"detected": True}

    if not has_filtered:
        failure_subtype.append("missing_filtered_section")
        task_failures["missing_filtered_section"] = {"detected": True}

    if not has_final:
        failure_subtype.append("missing_final_section")
        task_failures["missing_final_section"] = {"detected": True}

    if has_initial and has_filtered and has_final and not valid_section_order:
        failure_subtype.append("invalid_section_order")
        task_failures["invalid_section_order"] = {
            "section_positions": {
                "initial": i0,
                "filtered": i1,
                "final": i2,
            }
        }

    if valid_section_order and initial_total is None:
        failure_subtype.append("missing_initial_total")
        task_failures["missing_initial_total"] = {"detected": True}

    if valid_section_order and filtered_total is None:
        failure_subtype.append("missing_filtered_total")
        task_failures["missing_filtered_total"] = {"detected": True}

    if valid_section_order and final_score is None:
        failure_subtype.append("missing_final_score")
        task_failures["missing_final_score"] = {"detected": True}

    missing_initial_percent_labels = sorted(label for label, value in parsed_initial.items() if value is None)
    if valid_section_order and missing_initial_percent_labels:
        failure_subtype.append("missing_initial_percent")
        task_failures["missing_initial_percent"] = {
            "labels": missing_initial_percent_labels,
        }

    expected_filtered_labels = sorted(expected["filtered_percents"].keys())
    missing_filtered_percent_labels = sorted(
        label for label in expected_filtered_labels if parsed_filtered[label] is None
    )
    if valid_section_order and missing_filtered_percent_labels:
        failure_subtype.append("missing_filtered_percent")
        task_failures["missing_filtered_percent"] = {
            "labels": missing_filtered_percent_labels,
        }

    if initial_total is not None and initial_total != expected["initial_total"]:
        failure_subtype.append("initial_total_incorrect")
        task_failures["initial_total_incorrect"] = {
            "expected": expected["initial_total"],
            "actual": initial_total,
        }

    if filtered_total is not None and filtered_total != expected["filtered_total"]:
        failure_subtype.append("filtered_total_incorrect")
        task_failures["filtered_total_incorrect"] = {
            "expected": expected["filtered_total"],
            "actual": filtered_total,
        }

    if parsed_filtered[expected["smallest_label"]] is not None:
        failure_subtype.append("smallest_value_not_removed")
        task_failures["smallest_value_not_removed"] = {
            "label": expected["smallest_label"],
            "unexpected_value": parsed_filtered[expected["smallest_label"]],
        }

    if final_score is not None and final_score != expected["final_score"]:
        failure_subtype.append("final_score_mismatch")
        task_failures["final_score_mismatch"] = {
            "expected": expected["final_score"],
            "actual": final_score,
        }

    percentage_mismatches: list[dict[str, Any]] = []
    rounding_mismatches: list[dict[str, Any]] = []

    for label in ["A", "B", "C", "D"]:
        actual = parsed_initial[label]
        expected_value = expected["initial_percents"][label]
        if actual is not None and not approx_equal(actual, expected_value):
            mismatch = {
                "section": "initial",
                "label": label,
                "expected": expected_value,
                "actual": actual,
                "delta": round(actual - expected_value, 4),
            }
            delta = actual - expected_value
            if abs(delta) <= 0.05:
                rounding_mismatches.append(mismatch)
            else:
                percentage_mismatches.append(mismatch)

    for label in expected_filtered_labels:
        actual = parsed_filtered[label]
        expected_value = expected["filtered_percents"][label]
        if actual is not None and not approx_equal(actual, expected_value):
            mismatch = {
                "section": "filtered",
                "label": label,
                "expected": expected_value,
                "actual": actual,
                "delta": round(actual - expected_value, 4),
            }
            delta = actual - expected_value
            if abs(delta) <= 0.05:
                rounding_mismatches.append(mismatch)
            else:
                percentage_mismatches.append(mismatch)

    if percentage_mismatches:
        failure_subtype.append("percentage_mismatch")
        task_failures["percentage_mismatch"] = {
            "mismatches": percentage_mismatches,
        }

    if rounding_mismatches:
        failure_subtype.append("rounding_error")
        task_failures["rounding_error"] = {
            "mismatches": rounding_mismatches,
        }

    format_subtypes = {
        "missing_initial_section",
        "missing_filtered_section",
        "missing_final_section",
        "invalid_section_order",
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
        "expected": expected,
        "parsed_initial_total": initial_total,
        "parsed_filtered_total": filtered_total,
        "parsed_final_score": final_score,
        "parsed_initial_percents": parsed_initial,
        "parsed_filtered_percents": parsed_filtered,
        "missing_initial_percent_labels": missing_initial_percent_labels,
        "missing_filtered_percent_labels": missing_filtered_percent_labels,
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
        "expected": expected,
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
