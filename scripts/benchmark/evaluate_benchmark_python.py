#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any


RUNTIME_TIMEOUT_SECONDS = 20


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


def detect_features(code: str) -> dict[str, Any]:
    return {
        "uses_argparse": "argparse" in code,
        "uses_os_walk": "os.walk" in code,
        "uses_csv": "csv." in code or "import csv" in code or "from csv" in code,
        "uses_counter": "Counter(" in code or "from collections import Counter" in code,
        "uses_pathlib": "pathlib" in code or "Path(" in code,
        "has_try_except": "try:" in code and "except" in code,
        "mentions_stat": ".stat(" in code or "os.stat(" in code or "getmtime(" in code or "getsize(" in code,
        "contains_markdown_fence": "```" in code,
        "reads_stdin": "sys.stdin" in code,
        "uses_input_prompt": "input(" in code,
        "has_infinite_loop_pattern": bool(re.search(r"while\s+True\s*:", code)),
    }


def write_candidate(tmpdir: Path, code: str) -> Path:
    candidate = tmpdir / "candidate.py"
    candidate.write_text(code, encoding="utf-8")
    return candidate


def build_folder_fixture(tmpdir: Path) -> dict[str, Any]:
    root = tmpdir / "test_tree"
    (root / "nested" / "deep").mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)

    files = {
        root / "readme.txt": 60,
        root / "nested" / "deep" / "data.csv": 600,
        root / "nested" / "deep" / "archive.bin": 5000,
        root / "images" / "photo.jpg": 1400,
        root / "docs" / "report.md": 180,
    }

    for path, size in files.items():
        path.write_bytes(b"x" * size)

    recent_paths = [
        root / "readme.txt",
        root / "nested" / "deep" / "data.csv",
        root / "nested" / "deep" / "archive.bin",
        root / "images" / "photo.jpg",
        root / "docs" / "report.md",
    ]

    return {
        "path": str(root),
        "expected_files": 5,
        "expected_folders_excluding_root": 4,
        "expected_folders_including_root": 5,
        "expected_recent_files": len(recent_paths),
        "extensions_present": [".txt", ".md", ".jpg", ".csv", ".bin"],
        "expected_sizes_desc": [5000, 1400, 600, 180, 60],
    }


def build_csv_fixture(tmpdir: Path) -> dict[str, Any]:
    path = tmpdir / "sample.csv"
    path.write_text(
        textwrap.dedent(
            """\
            name,age,city,score
            Alice,25,Stockholm,91
            Bob,31,Gothenburg,84
            Cara,40,Malmo,88
            Alice,29,Stockholm,90
            Bob,28,Gothenburg,86
            """
        ),
        encoding="utf-8",
    )
    return {
        "path": str(path),
        "expected_rows": 5,
        "expected_columns": ["name", "age", "city", "score"],
        "expected_numeric_columns": ["age", "score"],
        "expected_text_columns": ["name", "city"],
    }


def build_log_fixture(tmpdir: Path) -> dict[str, Any]:
    path = tmpdir / "app.log"
    path.write_text(
        textwrap.dedent(
            """\
            2026-04-14 10:00:00 INFO Service started
            2026-04-14 10:01:00 INFO User login ok
            2026-04-14 10:02:00 ERROR Database unavailable
            2026-04-14 10:03:00 ERROR Database unavailable
            2026-04-14 10:04:00 WARNING Disk almost full
            2026-04-14 10:05:00 ERROR Timeout contacting backend
            2026-04-14 10:06:00 INFO Service healthy
            """
        ),
        encoding="utf-8",
    )
    return {
        "path": str(path),
        "expected_total_lines": 7,
        "expected_info": 3,
        "expected_warning": 1,
        "expected_error": 3,
        "expected_earliest": "2026-04-14 10:00:00",
        "expected_latest": "2026-04-14 10:06:00",
        "expected_top_error": "Database unavailable",
    }


def build_fixture(tmpdir: Path, task: str) -> dict[str, Any]:
    if task == "folder_scan":
        return build_folder_fixture(tmpdir)
    if task == "csv_summary":
        return build_csv_fixture(tmpdir)
    if task == "log_parser":
        return build_log_fixture(tmpdir)
    raise ValueError(f"Unsupported task: {task}")


def run_candidate(candidate_path: Path, task: str, expected: dict[str, Any]) -> dict[str, Any]:
    command = [sys.executable, str(candidate_path), expected["path"]]
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
            "stderr": "Timed out after 20 seconds",
            "timed_out": True,
        }


def find_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_size_lines(stdout: str) -> list[int]:
    out: list[int] = []
    for line in stdout.splitlines():
        m = re.search(r"(\d+)\s+bytes", line, flags=re.IGNORECASE)
        if m:
            out.append(int(m.group(1)))
    return out


def parse_extension_lines(stdout: str) -> list[str]:
    out: list[str] = []
    for line in stdout.splitlines():
        m = re.match(r"\s*(\.[A-Za-z0-9]+)\s*[:\-]\s*\d+\s*$", line)
        if m:
            out.append(m.group(1))
    return out


def evaluate_folder_scan(stdout: str, expected: dict[str, Any]) -> dict[str, Any]:
    total_files = find_int(r"total\s+files\s*:\s*(\d+)", stdout)
    total_folders = find_int(r"total\s+folders\s*:\s*(\d+)", stdout)

    parsed_sizes = parse_size_lines(stdout)
    parsed_exts = parse_extension_lines(stdout)

    checks = {
        "reports_total_files": total_files is not None,
        "reports_total_folders": total_folders is not None,
        "reports_exact_total_files": total_files == expected["expected_files"],
        "reports_exact_total_folders": total_folders in {
            expected["expected_folders_excluding_root"],
            expected["expected_folders_including_root"],
        },
        "largest_files_sorted_descending": parsed_sizes[:5] == expected["expected_sizes_desc"],
        "largest_files_count_reasonable": len(parsed_sizes) >= 5,
        "extension_count_lines_reasonable": set(parsed_exts) >= set(expected["extensions_present"]),
        "recent_files_listed_individually": "modified" in stdout.lower() or "last 7 days" in stdout.lower(),
        "parsed_total_files": total_files,
        "parsed_total_folders": total_folders,
        "parsed_size_lines": parsed_sizes,
        "parsed_extension_lines": parsed_exts,
    }
    return checks


def evaluate_csv_summary(stdout: str, expected: dict[str, Any]) -> dict[str, Any]:
    lower = stdout.lower()
    common_values_found = (
        "top 5 values" in lower
        or "top values" in lower
        or "most common values" in lower
        or "most common" in lower
    )

    checks = {
        "reports_row_count": find_int(r"number\s+of\s+rows\s*:\s*(\d+)", stdout) == expected["expected_rows"],
        "reports_column_names": all(col in stdout for col in expected["expected_columns"]),
        "mentions_numeric_columns": all(col in stdout for col in expected["expected_numeric_columns"]),
        "mentions_text_columns": all(col in stdout for col in expected["expected_text_columns"]),
        "mentions_min_max_average": all(token in lower for token in ["min", "max", "avg"]),
        "mentions_common_values": common_values_found,
    }
    return checks


def evaluate_log_parser(stdout: str, expected: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "reports_total_lines": find_int(r"total\s+lines\s*:\s*(\d+)", stdout) == expected["expected_total_lines"],
        "reports_info_count": find_int(r"info\s+messages\s*:\s*(\d+)", stdout) == expected["expected_info"],
        "reports_warning_count": find_int(r"warning\s+messages\s*:\s*(\d+)", stdout) == expected["expected_warning"],
        "reports_error_count": find_int(r"error\s+messages\s*:\s*(\d+)", stdout) == expected["expected_error"],
        "reports_earliest_timestamp": expected["expected_earliest"] in stdout,
        "reports_latest_timestamp": expected["expected_latest"] in stdout,
        "reports_common_error": expected["expected_top_error"].lower() in stdout.lower(),
    }
    return checks


def evaluate_stdout(stdout: str, task: str, expected: dict[str, Any]) -> dict[str, Any]:
    if task == "folder_scan":
        return evaluate_folder_scan(stdout, expected)
    if task == "csv_summary":
        return evaluate_csv_summary(stdout, expected)
    if task == "log_parser":
        return evaluate_log_parser(stdout, expected)
    raise ValueError(f"Unsupported task: {task}")


def determine_execution_status(
    extraction_mode: str,
    syntax_valid: bool,
    runtime: dict[str, Any] | None,
    features: dict[str, Any],
) -> str:
    if extraction_mode == "none":
        return "extraction_failed"
    if not syntax_valid:
        return "syntax_error"
    if runtime is None:
        return "runtime_not_attempted"
    if runtime.get("timed_out"):
        return "timeout"
    if runtime.get("returncode") not in (0, None):
        return "runtime_error"
    if features.get("reads_stdin"):
        return "contract_violation"
    if features.get("uses_input_prompt"):
        return "contract_violation"
    return "ok"


def build_score(
    execution_status: str,
    stdout_checks: dict[str, Any] | None,
) -> dict[str, Any]:
    if execution_status != "ok":
        return {
            "checks": {},
            "passed_checks": 0,
            "total_checks": 0,
            "score_percent": 0.0,
            "hard_failure": True,
        }

    assert stdout_checks is not None
    bool_checks = {k: v for k, v in stdout_checks.items() if isinstance(v, bool)}
    passed = sum(1 for v in bool_checks.values() if v)
    total = len(bool_checks)
    score = round((passed / total) * 100.0, 2) if total else 0.0

    return {
        "checks": stdout_checks,
        "passed_checks": passed,
        "total_checks": total,
        "score_percent": score,
        "hard_failure": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--task", required=True, choices=["folder_scan", "csv_summary", "log_parser"])
    parser.add_argument("--save-code", default="")
    parser.add_argument("--save-report", default="")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    raw_text = read_text(input_path)

    code, extraction_mode = extract_code_block(raw_text)
    syntax_valid, syntax_error = syntax_check(code) if code else (False, "No code extracted")
    features = detect_features(code) if code else {}

    runtime: dict[str, Any] | None = None
    stdout_checks: dict[str, Any] | None = None
    expected: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="jarri_eval_") as tmp:
        tmpdir = Path(tmp)

        if code and syntax_valid:
            candidate_path = write_candidate(tmpdir, code)
            expected = build_fixture(tmpdir, args.task)
            runtime = run_candidate(candidate_path, args.task, expected)

            if args.save_code:
                Path(args.save_code).write_text(code, encoding="utf-8")

            if runtime["returncode"] == 0 and not runtime.get("timed_out"):
                stdout_checks = evaluate_stdout(runtime["stdout"], args.task, expected)

    execution_status = determine_execution_status(extraction_mode, syntax_valid, runtime, features)
    score = build_score(execution_status, stdout_checks)

    artifact_usability = (
        "unusable" if execution_status != "ok"
        else "usable" if score["score_percent"] >= 80.0
        else "partial"
    )

    report = {
        "success": True,
        "input_file": str(input_path),
        "task": args.task,
        "extraction_mode": extraction_mode,
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "features": features,
        "runtime": runtime or {
            "command": [],
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        },
        "execution_status": execution_status,
        "artifact_usability": artifact_usability,
        "stdout_checks": stdout_checks,
        "score": score,
        "expected_fixture": expected,
    }

    if args.save_report:
        Path(args.save_report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
