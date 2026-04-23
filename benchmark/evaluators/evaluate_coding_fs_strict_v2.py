#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


EVALUATOR_VERSION = "coding_fs_strict_eval_v3"
TASK_ID = "coding_fs_strict_v3"
TASK_FAMILY = "coding"
RUNTIME_TIMEOUT_SECONDS = 60


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_code_block(text: str) -> tuple[str, str]:
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[0].strip() + "\n", "markdown_fence"

    stripped = text.strip()
    if stripped.startswith("import ") or stripped.startswith("from ") or "def " in stripped:
        return stripped + ("\n" if not stripped.endswith("\n") else ""), "raw_text"

    return "", "none"


def syntax_check(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, f"{exc.msg} (line {exc.lineno}, col {exc.offset})"


def write_candidate(tmpdir: Path, code: str) -> Path:
    candidate = tmpdir / "candidate.py"
    candidate.write_text(code, encoding="utf-8")
    return candidate


def normalize_rel(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return "." if rel == "" else rel


def build_fixture(tmpdir: Path) -> dict[str, Any]:
    root = tmpdir / "tree"
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    (root / "nested" / "deep").mkdir(parents=True, exist_ok=True)
    (root / "empty").mkdir(parents=True, exist_ok=True)

    files = {
        root / "readme.txt": 100,
        root / "docs" / "report.md": 200,
        root / "docs" / "LICENSE": 50,
        root / "logs" / "app.log": 300,
        root / "logs" / "trace.log": 250,
        root / "bin" / "blob.bin": 400,
        root / "nested" / "deep" / "data.csv": 500,
        root / "nested" / "deep" / "image.jpg": 350,
    }
    for path, size in files.items():
        path.write_bytes(b"x" * size)

    total_files = len(files)
    total_directories = sum(1 for entry in root.rglob("*") if entry.is_dir()) + 1
    total_size = sum(files.values())

    ext_counts: dict[str, int] = {}
    all_files: list[tuple[str, int]] = []
    direct_file_counts: dict[str, int] = {}

    for dirpath, _, filenames in os.walk(root):
        dir_path = Path(dirpath)
        rel_dir = normalize_rel(dir_path, root)
        direct_file_counts[rel_dir] = len(filenames)

        for filename in filenames:
            file_path = dir_path / filename
            rel_file = normalize_rel(file_path, root)
            size = file_path.stat().st_size
            all_files.append((rel_file, size))
            ext = file_path.suffix.lower() if file_path.suffix else "[no_ext]"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

    extension_distribution = sorted(ext_counts.items(), key=lambda item: (-item[1], item[0]))
    largest_files = sorted(all_files, key=lambda item: (-item[1], item[0]))[:3]
    top_dirs = sorted(direct_file_counts.items(), key=lambda item: (-item[1], item[0]))[:3]

    return {
        "path": str(root),
        "total_files": total_files,
        "total_directories_including_root": total_directories,
        "total_size_bytes": total_size,
        "checksum": total_size % 1000000,
        "extension_distribution": extension_distribution,
        "largest_files": largest_files,
        "top_directories_by_direct_file_count": top_dirs,
    }


def run_candidate(candidate_path: Path, target_path: str) -> dict[str, Any]:
    command = [sys.executable, str(candidate_path), target_path]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=RUNTIME_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"Timed out after {RUNTIME_TIMEOUT_SECONDS} seconds",
            "timed_out": True,
        }


def parse_section(text: str, header: str, next_headers: list[str]) -> list[str]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == header:
            start = index + 1
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip() in next_headers:
            end = index
            break
    return [line.rstrip() for line in lines[start:end] if line.strip()]


def parse_ext_lines(lines: list[str]) -> list[tuple[str, int]]:
    rows = []
    for line in lines:
        match = re.match(r"(\.?[A-Za-z0-9_]+|\[no_ext\])\s*:\s*(\d+)$", line.strip())
        if match:
            ext = match.group(1)
            if ext != "[no_ext]" and not ext.startswith("."):
                ext = "." + ext
            rows.append((ext.lower(), int(match.group(2))))
    return rows


def parse_largest_lines(lines: list[str]) -> list[tuple[str, int]]:
    rows = []
    for line in lines:
        match = re.match(r"(.+?)\s*-\s*(\d+)\s*bytes$", line.strip())
        if match:
            rows.append((match.group(1).strip(), int(match.group(2))))
    return rows


def parse_dir_lines(lines: list[str]) -> list[tuple[str, int]]:
    rows = []
    for line in lines:
        match = re.match(r"(.+?)\s*-\s*(\d+)\s*files$", line.strip())
        if match:
            rows.append((match.group(1).strip(), int(match.group(2))))
    return rows


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
    if execution_status == "extraction_failed":
        return "format"
    if execution_status == "syntax_error":
        return "parse"
    if execution_status in {"runtime_error", "timeout"}:
        return "execute"

    if not failure_subtype:
        return None

    semantic_subtypes = {
        "summary_total_files_incorrect",
        "summary_total_directories_incorrect",
        "summary_total_size_incorrect",
        "checksum_incorrect",
        "extension_distribution_incorrect",
        "largest_files_incorrect",
        "top_directories_incorrect",
        "partial_semantic_match",
    }
    constraint_subtypes = {
        "invalid_output_format",
        "extension_distribution_unsorted",
        "largest_files_unsorted",
        "top_directories_unsorted",
    }

    if any(subtype in semantic_subtypes for subtype in failure_subtype):
        return "semantic"
    if any(subtype in constraint_subtypes for subtype in failure_subtype):
        return "constraint"

    return "constraint"


def determine_failure_type(execution_status: str, failure_subtype: list[str]) -> str | None:
    if execution_status == "extraction_failed":
        return "format_violation"
    if execution_status == "syntax_error":
        return "parse_failure"
    if execution_status in {"runtime_error", "timeout"}:
        return "runtime_error"

    if not failure_subtype:
        return None

    if any(
        subtype in failure_subtype
        for subtype in {
            "summary_total_files_incorrect",
            "summary_total_directories_incorrect",
            "summary_total_size_incorrect",
            "checksum_incorrect",
            "extension_distribution_incorrect",
            "largest_files_incorrect",
            "top_directories_incorrect",
            "partial_semantic_match",
        }
    ):
        return "semantic_error"

    if any(
        subtype in failure_subtype
        for subtype in {
            "invalid_output_format",
            "extension_distribution_unsorted",
            "largest_files_unsorted",
            "top_directories_unsorted",
        }
    ):
        return "constraint_violation"

    return "semantic_error"


def determine_success(execution_status: str, failure_type: str | None, score_percent: float) -> bool:
    return execution_status == "ok" and failure_type is None and score_percent == 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--save-code", default="")
    parser.add_argument("--save-report", default="")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    raw_text = read_text(input_path)

    code, extraction_mode = extract_code_block(raw_text)
    syntax_valid, syntax_error = syntax_check(code) if code else (False, "No code extracted")

    runtime: dict[str, Any] | None = None
    expected: dict[str, Any] | None = None
    checks: dict[str, bool] = {}
    failure_subtype: list[str] = []
    task_failures: dict[str, Any] = {}
    task_metrics: dict[str, Any] = {}

    execution_status = "runtime_not_attempted"

    with tempfile.TemporaryDirectory(prefix="jarri_eval_coding_fs_strict_v3_") as tmp:
        tmpdir = Path(tmp)
        expected = build_fixture(tmpdir)

        if code and syntax_valid:
            candidate_path = write_candidate(tmpdir, code)
            if args.save_code:
                Path(args.save_code).write_text(code, encoding="utf-8")

            runtime = run_candidate(candidate_path, expected["path"])

            if runtime["timed_out"]:
                execution_status = "timeout"
            elif runtime["returncode"] != 0:
                execution_status = "runtime_error"
            else:
                execution_status = "ok"

            if execution_status == "ok":
                stdout = runtime["stdout"]

                total_files = re.search(r"Total files:\s*(\d+)", stdout)
                total_dirs = re.search(r"Total directories:\s*(\d+)", stdout)
                total_size = re.search(r"Total size:\s*(\d+)\s*bytes", stdout)
                checksum = re.search(r"Checksum:\s*(\d+)", stdout)

                ext_lines = parse_ext_lines(
                    parse_section(
                        stdout,
                        "=== EXTENSION DISTRIBUTION ===",
                        [
                            "=== LARGEST FILES ===",
                            "=== TOP DIRECTORIES BY DIRECT FILE COUNT ===",
                            "=== FINAL CHECKSUM ===",
                        ],
                    )
                )
                largest_lines = parse_largest_lines(
                    parse_section(
                        stdout,
                        "=== LARGEST FILES ===",
                        [
                            "=== TOP DIRECTORIES BY DIRECT FILE COUNT ===",
                            "=== FINAL CHECKSUM ===",
                        ],
                    )
                )
                dir_lines = parse_dir_lines(
                    parse_section(
                        stdout,
                        "=== TOP DIRECTORIES BY DIRECT FILE COUNT ===",
                        ["=== FINAL CHECKSUM ==="],
                    )
                )

                expected_ext = expected["extension_distribution"]
                expected_largest = expected["largest_files"]
                expected_dirs = expected["top_directories_by_direct_file_count"]

                checks = {
                    "summary_total_files_exact": bool(total_files and int(total_files.group(1)) == expected["total_files"]),
                    "summary_total_directories_exact": bool(total_dirs and int(total_dirs.group(1)) == expected["total_directories_including_root"]),
                    "summary_total_size_exact": bool(total_size and int(total_size.group(1)) == expected["total_size_bytes"]),
                    "checksum_exact": bool(checksum and int(checksum.group(1)) == expected["checksum"]),
                    "extension_distribution_exact": ext_lines == expected_ext,
                    "extension_distribution_sorted": ext_lines == sorted(ext_lines, key=lambda item: (-item[1], item[0])),
                    "largest_files_exact": largest_lines == expected_largest,
                    "largest_files_sorted": largest_lines == sorted(largest_lines, key=lambda item: (-item[1], item[0])),
                    "top_directories_exact": dir_lines == expected_dirs,
                    "top_directories_sorted": dir_lines == sorted(dir_lines, key=lambda item: (-item[1], item[0])),
                }

                if not total_files:
                    failure_subtype.append("invalid_output_format")
                    task_failures["invalid_output_format"] = task_failures.get("invalid_output_format", {})
                    task_failures["invalid_output_format"]["missing_total_files_line"] = True

                if not total_dirs:
                    failure_subtype.append("invalid_output_format")
                    task_failures["invalid_output_format"] = task_failures.get("invalid_output_format", {})
                    task_failures["invalid_output_format"]["missing_total_directories_line"] = True

                if not total_size:
                    failure_subtype.append("invalid_output_format")
                    task_failures["invalid_output_format"] = task_failures.get("invalid_output_format", {})
                    task_failures["invalid_output_format"]["missing_total_size_line"] = True

                if not checksum:
                    failure_subtype.append("invalid_output_format")
                    task_failures["invalid_output_format"] = task_failures.get("invalid_output_format", {})
                    task_failures["invalid_output_format"]["missing_checksum_line"] = True

                if total_files and int(total_files.group(1)) != expected["total_files"]:
                    failure_subtype.append("summary_total_files_incorrect")
                    task_failures["summary_total_files_incorrect"] = {
                        "expected": expected["total_files"],
                        "actual": int(total_files.group(1)),
                    }

                if total_dirs and int(total_dirs.group(1)) != expected["total_directories_including_root"]:
                    failure_subtype.append("summary_total_directories_incorrect")
                    task_failures["summary_total_directories_incorrect"] = {
                        "expected": expected["total_directories_including_root"],
                        "actual": int(total_dirs.group(1)),
                    }

                if total_size and int(total_size.group(1)) != expected["total_size_bytes"]:
                    failure_subtype.append("summary_total_size_incorrect")
                    task_failures["summary_total_size_incorrect"] = {
                        "expected": expected["total_size_bytes"],
                        "actual": int(total_size.group(1)),
                    }

                if checksum and int(checksum.group(1)) != expected["checksum"]:
                    failure_subtype.append("checksum_incorrect")
                    task_failures["checksum_incorrect"] = {
                        "expected": expected["checksum"],
                        "actual": int(checksum.group(1)),
                    }

                if ext_lines != expected_ext:
                    failure_subtype.append("extension_distribution_incorrect")
                    task_failures["extension_distribution_incorrect"] = {
                        "expected": expected_ext,
                        "actual": ext_lines,
                    }

                if ext_lines and ext_lines != sorted(ext_lines, key=lambda item: (-item[1], item[0])):
                    failure_subtype.append("extension_distribution_unsorted")
                    task_failures["extension_distribution_unsorted"] = {
                        "actual": ext_lines,
                    }

                if largest_lines != expected_largest:
                    failure_subtype.append("largest_files_incorrect")
                    task_failures["largest_files_incorrect"] = {
                        "expected": expected_largest,
                        "actual": largest_lines,
                    }

                if largest_lines and largest_lines != sorted(largest_lines, key=lambda item: (-item[1], item[0])):
                    failure_subtype.append("largest_files_unsorted")
                    task_failures["largest_files_unsorted"] = {
                        "actual": largest_lines,
                    }

                if dir_lines != expected_dirs:
                    failure_subtype.append("top_directories_incorrect")
                    task_failures["top_directories_incorrect"] = {
                        "expected": expected_dirs,
                        "actual": dir_lines,
                    }

                if dir_lines and dir_lines != sorted(dir_lines, key=lambda item: (-item[1], item[0])):
                    failure_subtype.append("top_directories_unsorted")
                    task_failures["top_directories_unsorted"] = {
                        "actual": dir_lines,
                    }

                exact_hits = sum(
                    1
                    for key in [
                        "extension_distribution_exact",
                        "largest_files_exact",
                        "top_directories_exact",
                    ]
                    if checks.get(key)
                )
                if 0 < exact_hits < 3:
                    failure_subtype.append("partial_semantic_match")
                    task_failures["partial_semantic_match"] = {
                        "exact_hits": exact_hits,
                        "semantic_fields": {
                            "extension_distribution_exact": checks["extension_distribution_exact"],
                            "largest_files_exact": checks["largest_files_exact"],
                            "top_directories_exact": checks["top_directories_exact"],
                        },
                    }

                task_metrics = {
                    "expected_fixture": expected,
                    "parsed_extension_distribution": ext_lines,
                    "parsed_largest_files": largest_lines,
                    "parsed_top_directories": dir_lines,
                    "stdout_length_chars": len(stdout),
                }

        elif extraction_mode == "none":
            execution_status = "extraction_failed"
        else:
            execution_status = "syntax_error"

    if execution_status != "ok":
        checks = {}
        if execution_status == "extraction_failed":
            failure_subtype = ["code_extraction_failed"]
            task_failures = {
                "code_extraction_failed": {
                    "extraction_mode": extraction_mode,
                }
            }
        elif execution_status == "syntax_error":
            failure_subtype = ["syntax_error"]
            task_failures = {
                "syntax_error": {
                    "message": syntax_error,
                }
            }
        elif execution_status == "timeout":
            failure_subtype = ["timeout"]
            task_failures = {
                "timeout": {
                    "timeout_seconds": RUNTIME_TIMEOUT_SECONDS,
                    "stderr": (runtime or {}).get("stderr", ""),
                }
            }
        elif execution_status == "runtime_error":
            failure_subtype = ["runtime_error"]
            task_failures = {
                "runtime_error": {
                    "returncode": (runtime or {}).get("returncode"),
                    "stderr": (runtime or {}).get("stderr", ""),
                }
            }

    hard_failure = execution_status != "ok"
    score = build_score(checks, hard_failure=hard_failure)
    failure_subtype = sorted(set(failure_subtype))
    failure_stage = determine_failure_stage(execution_status, failure_subtype)
    failure_type = determine_failure_type(execution_status, failure_subtype)
    success = determine_success(execution_status, failure_type, score["score_percent"])

    artifact_usability = (
        "unusable" if execution_status != "ok"
        else "usable" if score["score_percent"] >= 85.0
        else "partial"
    )

    report = {
        "success": success,
        "evaluator_version": EVALUATOR_VERSION,
        "task_id": TASK_ID,
        "task_family": TASK_FAMILY,
        "extraction_mode": extraction_mode,
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "runtime": runtime or {
            "command": [],
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        },
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
        "expected_fixture": expected,
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
