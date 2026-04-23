#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EVALUATOR_VERSION = "constrained_rewrite_eval_v3"
TASK_ID = "constrained_rewrite_v2"
TASK_FAMILY = "language"

REQUIRED_TOKENS = [
    "March",
    "3rd",
    "2021",
    "Arcturus",
    "Systems",
    "4.2",
    "5.6",
    "12",
    "Lina",
    "Verne",
    "three",
    "new",
    "European",
    "markets",
]

REQUIRED_PHRASES = [
    "Arcturus Systems",
    "Lina Verne",
    "three new European markets",
]

FORBIDDEN_PUNCTUATION_PATTERN = r'[;:!?()"]'


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def word_count(line: str) -> int:
    return len(re.findall(r"\b\S+\b", line))


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

    semantic_subtypes = {
        "missing_required_phrase",
        "partial_semantic_match",
    }
    constraint_subtypes = {
        "word_count_violation",
        "missing_required_token",
        "forbidden_punctuation_present",
        "terminal_punctuation_violation",
    }

    if any(subtype in semantic_subtypes for subtype in failure_subtype):
        return "semantic"
    if any(subtype in constraint_subtypes for subtype in failure_subtype):
        return "constraint"

    return "format"


def determine_failure_type(execution_status: str, failure_subtype: list[str]) -> str | None:
    if execution_status != "ok":
        return "format_violation"

    if not failure_subtype:
        return None

    if "missing_required_phrase" in failure_subtype or "partial_semantic_match" in failure_subtype:
        return "semantic_error"

    if (
        "word_count_violation" in failure_subtype
        or "missing_required_token" in failure_subtype
        or "forbidden_punctuation_present" in failure_subtype
        or "terminal_punctuation_violation" in failure_subtype
    ):
        return "constraint_violation"

    return "format_violation"


def determine_success(execution_status: str, failure_type: str | None, score_percent: float) -> bool:
    return execution_status == "ok" and failure_type is None and score_percent == 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--save-report", default="")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    text = read_text(input_path)

    raw_lines = text.splitlines()
    nonempty_lines = [line.rstrip() for line in raw_lines if line.strip()]
    bullet_lines = [line for line in nonempty_lines if line.startswith("- ")]

    word_counts = [word_count(line[2:]) for line in bullet_lines]
    joined_bullets = "\n".join(bullet_lines)

    present_tokens = [token for token in REQUIRED_TOKENS if token in joined_bullets]
    missing_tokens = sorted(token for token in REQUIRED_TOKENS if token not in joined_bullets)

    present_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase in joined_bullets]
    missing_phrases = sorted(phrase for phrase in REQUIRED_PHRASES if phrase not in joined_bullets)

    forbidden_punctuation_matches = sorted(set(re.findall(FORBIDDEN_PUNCTUATION_PATTERN, joined_bullets)))
    bullets_missing_period = [index + 1 for index, line in enumerate(bullet_lines) if not line.endswith(".")]
    bullets_wrong_word_count = [
        {
            "bullet_index": index + 1,
            "expected_words": 12,
            "actual_words": count,
        }
        for index, count in enumerate(word_counts)
        if count != 12
    ]

    checks: dict[str, bool] = {
        "exactly_three_bullets": len(bullet_lines) == 3,
        "bullet_1_has_12_words": len(word_counts) >= 1 and word_counts[0] == 12,
        "bullet_2_has_12_words": len(word_counts) >= 2 and word_counts[1] == 12,
        "bullet_3_has_12_words": len(word_counts) >= 3 and word_counts[2] == 12,
        "all_bullets_end_with_period": len(bullet_lines) == 3 and all(line.endswith(".") for line in bullet_lines),
        "contains_all_required_tokens": len(missing_tokens) == 0,
        "contains_all_required_phrases": len(missing_phrases) == 0,
        "no_forbidden_punctuation": len(forbidden_punctuation_matches) == 0,
    }

    failure_subtype: list[str] = []
    task_failures: dict[str, Any] = {}

    if len(bullet_lines) != 3:
        failure_subtype.append("bullet_count_mismatch")
        task_failures["bullet_count_mismatch"] = {
            "expected_bullets": 3,
            "actual_bullets": len(bullet_lines),
            "nonempty_line_count": len(nonempty_lines),
        }

    if bullets_wrong_word_count:
        failure_subtype.append("word_count_violation")
        task_failures["word_count_violation"] = {
            "violations": bullets_wrong_word_count,
        }

    if missing_tokens:
        failure_subtype.append("missing_required_token")
        task_failures["missing_required_token"] = {
            "missing_tokens": missing_tokens,
            "present_token_count": len(present_tokens),
            "required_token_count": len(REQUIRED_TOKENS),
        }

    if missing_phrases:
        failure_subtype.append("missing_required_phrase")
        task_failures["missing_required_phrase"] = {
            "missing_phrases": missing_phrases,
            "present_phrase_count": len(present_phrases),
            "required_phrase_count": len(REQUIRED_PHRASES),
        }

    if forbidden_punctuation_matches:
        failure_subtype.append("forbidden_punctuation_present")
        task_failures["forbidden_punctuation_present"] = {
            "characters": forbidden_punctuation_matches,
        }

    if bullets_missing_period:
        failure_subtype.append("terminal_punctuation_violation")
        task_failures["terminal_punctuation_violation"] = {
            "bullets_missing_period": bullets_missing_period,
        }

    if present_phrases and missing_phrases:
        failure_subtype.append("partial_semantic_match")
        task_failures["partial_semantic_match"] = {
            "present_phrases": present_phrases,
            "missing_phrases": missing_phrases,
        }

    format_subtypes = {"bullet_count_mismatch"}
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
        "expected_bullet_count": 3,
        "actual_bullet_count": len(bullet_lines),
        "bullet_word_counts": word_counts,
        "required_token_count": len(REQUIRED_TOKENS),
        "present_token_count": len(present_tokens),
        "missing_token_count": len(missing_tokens),
        "required_phrase_count": len(REQUIRED_PHRASES),
        "present_phrase_count": len(present_phrases),
        "missing_phrase_count": len(missing_phrases),
        "forbidden_punctuation_count": len(forbidden_punctuation_matches),
        "bullets_missing_period_count": len(bullets_missing_period),
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
        "required_tokens": REQUIRED_TOKENS,
        "required_phrases": REQUIRED_PHRASES,
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
