#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
OUT_PATH = PROJECT_ROOT / "benchmark_ui" / "data" / "duckdb_task_registry.json"


TASK_METADATA = {
    "coding_fs_strict_v3": {
        "title": "Strict filesystem coding task",
        "description": "The model must produce code that solves a structured filesystem-style programming task under exact output constraints.",
        "success_definition": "Success requires syntactically valid code, successful execution, and correct structured output according to the evaluator.",
        "common_failure_modes": [
            "syntax_error",
            "parse_failure",
            "execution_failure",
            "wrong_summary_block",
            "structural_noncompliance",
        ],
        "primary_axis": "execution_reliability",
        "family": "coding",
    },
    "math_dependency_v1": {
        "title": "Math dependency reasoning task",
        "description": "The model must follow a dependency chain correctly and produce exact numeric reasoning without dropping intermediate logic.",
        "success_definition": "Success requires exact arithmetic and correct dependency resolution under evaluator checks.",
        "common_failure_modes": [
            "arithmetic_error",
            "dependency_break",
            "reasoning_omission",
            "semantic_mismatch",
        ],
        "primary_axis": "arithmetic_exactness",
        "family": "math",
    },
    "logic_consistency_v2": {
        "title": "Closed-world logic consistency task",
        "description": "The model must maintain internal consistency across a constrained logic scenario without inventing unsupported facts.",
        "success_definition": "Success requires consistent reasoning and exact evaluator-compliant answers.",
        "common_failure_modes": [
            "consistency_break",
            "semantic_mismatch",
            "coverage_failure",
            "constraint_failure",
        ],
        "primary_axis": "formal_reasoning_consistency",
        "family": "knowledge",
    },
    "constrained_rewrite_v2": {
        "title": "Constrained rewrite task",
        "description": "The model must rewrite text while obeying explicit structural and semantic constraints.",
        "success_definition": "Success requires constraint compliance, preserved meaning, and evaluator-approved structure.",
        "common_failure_modes": [
            "constraint_failure",
            "semantic_drift",
            "format_deviation",
            "coverage_failure",
        ],
        "primary_axis": "constraint_precision",
        "family": "language",
    },
    "fact_task_1": {
        "title": "Structured fact task 1",
        "description": "The model must retrieve or reproduce structured factual information in the expected form.",
        "success_definition": "Success requires correct factual fields and compliant structure.",
        "common_failure_modes": [
            "field_mismatch",
            "factual_error",
            "semantic_mismatch",
            "format_deviation",
        ],
        "primary_axis": "semantic_fidelity",
        "family": "fact_prose",
    },
    "fact_task_2": {
        "title": "Structured fact task 2",
        "description": "The model must follow a multi-step factual chain without dropping dependencies or inventing unsupported answers.",
        "success_definition": "Success requires correct chain resolution and evaluator-compliant structured output.",
        "common_failure_modes": [
            "dependency_break",
            "semantic_mismatch",
            "factual_error",
            "constraint_failure",
        ],
        "primary_axis": "dependency_chain_integrity",
        "family": "fact_prose",
    },
    "fact_task_3": {
        "title": "Structured fact task 3",
        "description": "The model must resolve a factual extraction or reasoning problem with strict output expectations.",
        "success_definition": "Success requires correct factual extraction and structure.",
        "common_failure_modes": [
            "semantic_mismatch",
            "field_mismatch",
            "coverage_failure",
            "constraint_failure",
        ],
        "primary_axis": "semantic_fidelity",
        "family": "fact_prose",
    },
    "prose_task_1": {
        "title": "Prose task 1",
        "description": "The model must produce prose output that satisfies evaluator criteria while preserving intent and structure.",
        "success_definition": "Success requires semantic fidelity and structural compliance.",
        "common_failure_modes": [
            "semantic_drift",
            "constraint_failure",
            "coverage_failure",
        ],
        "primary_axis": "semantic_fidelity",
        "family": "fact_prose",
    },
    "prose_task_2": {
        "title": "Prose task 2",
        "description": "The model must produce evaluator-compliant prose under explicit content constraints.",
        "success_definition": "Success requires semantic compliance and structural correctness.",
        "common_failure_modes": [
            "constraint_failure",
            "semantic_drift",
            "coverage_failure",
        ],
        "primary_axis": "constraint_precision",
        "family": "fact_prose",
    },
    "prose_task_3": {
        "title": "Prose task 3",
        "description": "The model must solve a prose-oriented evaluator task with exactness and controlled output behavior.",
        "success_definition": "Success requires evaluator-compliant prose with preserved required content.",
        "common_failure_modes": [
            "semantic_drift",
            "constraint_failure",
            "format_deviation",
        ],
        "primary_axis": "semantic_fidelity",
        "family": "fact_prose",
    },
}


BENCHMARK_ROOTS = {
    "coding": BENCHMARKS_DIR / "coding_measurement_v3",
    "math": BENCHMARKS_DIR / "math_measurement_v1",
    "knowledge": BENCHMARKS_DIR / "knowledge_measurement_v2",
    "language": BENCHMARKS_DIR / "language_measurement_v2",
    "fact_prose": BENCHMARKS_DIR / "fact_prose_v2",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def summarize_prompt(text: str | None, max_chars: int = 260) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def detect_task_id_from_prompt_path(path: Path) -> str:
    name = path.stem
    if name.startswith("prompt_"):
        return name[len("prompt_"):]
    return name


def collect_prompt_files(root: Path) -> list[Path]:
    return sorted(root.glob("prompt_*.txt"))


def main() -> int:
    rows: list[dict] = []

    for family_name, root in BENCHMARK_ROOTS.items():
        if not root.exists():
            continue

        manifest_path = root / "manifest.json"
        prompt_files = collect_prompt_files(root)

        for prompt_path in prompt_files:
            task_id = detect_task_id_from_prompt_path(prompt_path)
            prompt_text = read_text_safe(prompt_path)
            metadata = TASK_METADATA.get(task_id, {})

            row = {
                "task_id": task_id,
                "task_title": metadata.get("title") or task_id.replace("_", " ").title(),
                "task_family": metadata.get("family") or family_name,
                "task_description": metadata.get("description"),
                "success_definition": metadata.get("success_definition"),
                "common_failure_modes": metadata.get("common_failure_modes", []),
                "primary_axis": metadata.get("primary_axis"),
                "benchmark_root": str(root),
                "prompt_path": str(prompt_path),
                "manifest_path": str(manifest_path),
                "prompt_first_line": first_nonempty_line(prompt_text),
                "prompt_preview": summarize_prompt(prompt_text),
            }

            rows.append(row)

    payload = {
        "generated_at_utc": utc_now_iso(),
        "source": "benchmark prompt roots",
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
