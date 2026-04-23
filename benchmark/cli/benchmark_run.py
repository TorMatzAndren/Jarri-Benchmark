#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JARRI_DIR = Path(__file__).resolve().parents[2]
BENCHMARKS_DIR = JARRI_DIR / "benchmarks"
SCRIPTS_BENCHMARK_DIR = JARRI_DIR / "scripts" / "benchmark"
EVALUATORS_DIR = JARRI_DIR / "benchmark" / "evaluators"

TDP_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?(?:[Ww])?$")
APPLIED_WATTS_RE = re.compile(r"Confirmed applied GPU power limit:\s*([0-9]+(?:\.[0-9]+)?)\s*W", re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_checked(cmd: list[str], stdout_path: Path | None = None) -> subprocess.CompletedProcess:
    if stdout_path is None:
        return subprocess.run(cmd, text=True, capture_output=True, check=True)

    with stdout_path.open("w", encoding="utf-8") as handle:
        return subprocess.run(cmd, text=True, stdout=handle, stderr=subprocess.PIPE, check=True)


def safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "yes", "1"}:
            return True
        if low in {"false", "no", "0"}:
            return False
    return None


def is_percent_tdp_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", token.strip()))


def is_watts_tdp_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?[Ww]", token.strip()))


def normalize_tdp_token(token: str) -> str:
    normalized = token.strip()
    if not normalized:
        raise ValueError("Empty TDP token is not allowed.")
    if not TDP_TOKEN_RE.fullmatch(normalized):
        raise ValueError(
            f"Unsupported TDP token: {token!r}. "
            "Use bare numeric percent values like 80 or 112, or watts like 144w."
        )
    return normalized


def extract_percent_from_tdp_token(token: str) -> float | None:
    normalized = normalize_tdp_token(token)
    if is_percent_tdp_token(normalized):
        return float(normalized)
    return None


def extract_explicit_watts_from_tdp_token(token: str) -> float | None:
    normalized = normalize_tdp_token(token)
    if is_watts_tdp_token(normalized):
        return float(normalized[:-1])
    return None


def set_power_limit(tdp_token: str, model: str, run_index: int) -> dict[str, Any]:
    normalized_token = normalize_tdp_token(tdp_token)
    percent_value = extract_percent_from_tdp_token(normalized_token)
    explicit_watts = extract_explicit_watts_from_tdp_token(normalized_token)

    print()
    print("============================================================")
    print(f"Model: {model}")
    if percent_value is not None:
        percent_display = int(percent_value) if percent_value.is_integer() else percent_value
        print(f"TDP:   {percent_display}%")
    else:
        print(f"TDP:   {normalized_token}")
    print(f"Run:   {run_index}")
    print("============================================================")

    result = subprocess.run(
        [str(JARRI_DIR / "set_gpu_power_limit_linux.sh"), normalized_token],
        check=True,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")

    applied_watts = None
    match = APPLIED_WATTS_RE.search(result.stdout or "")
    if match:
        applied_watts = safe_float(match.group(1))

    time.sleep(2)

    return {
        "power_limit_request": normalized_token,
        "power_limit_mode": "percent" if percent_value is not None else "watts",
        "power_limit_percent": percent_value,
        "power_limit_explicit_watts": explicit_watts,
        "power_limit_applied_watts": applied_watts,
        "power_limit_helper_stdout": result.stdout,
    }


def model_safe_name(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def load_manifest(experiment_id: str) -> dict[str, Any]:
    manifest_path = BENCHMARKS_DIR / experiment_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def get_gpu_snapshot() -> dict[str, Any]:
    query = ",".join(
        [
            "index",
            "name",
            "uuid",
            "driver_version",
            "temperature.gpu",
            "utilization.gpu",
            "memory.used",
            "memory.total",
            "power.draw",
            "power.limit",
        ]
    )
    req = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(req, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"available": False, "error": result.stderr.strip() or result.stdout.strip()}

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return {"available": False, "error": "No GPU data returned."}

    parts = [part.strip() for part in lines[0].split(",")]
    if len(parts) != 10:
        return {"available": False, "error": f"Unexpected GPU output: {lines[0]}"}

    memory_used_mb = safe_int(parts[6]) or 0
    memory_total_mb = safe_int(parts[7]) or 0
    power_draw_w = safe_float(parts[8]) or 0.0
    power_limit_w = safe_float(parts[9]) or 0.0
    gpu_util_percent = safe_int(parts[5]) or 0
    temperature_c = safe_int(parts[4]) or 0
    memory_used_percent = round((memory_used_mb / memory_total_mb) * 100, 2) if memory_total_mb > 0 else 0.0

    return {
        "available": True,
        "index": safe_int(parts[0]) or 0,
        "name": parts[1],
        "uuid": parts[2],
        "driver_version": parts[3],
        "temperature_c": temperature_c,
        "gpu_util_percent": gpu_util_percent,
        "memory_used_mb": memory_used_mb,
        "memory_total_mb": memory_total_mb,
        "memory_used_percent": memory_used_percent,
        "power_draw_w": power_draw_w,
        "power_limit_w": power_limit_w,
    }


def detect_gpu_info() -> dict[str, Any]:
    snapshot = get_gpu_snapshot()
    if not snapshot.get("available"):
        return {
            "gpu_name": "unknown",
            "gpu_uuid": "",
            "gpu_driver_version": "",
            "gpu_memory_total_mb": None,
            "gpu_index": None,
        }
    return {
        "gpu_name": snapshot.get("name", "unknown"),
        "gpu_uuid": snapshot.get("uuid", ""),
        "gpu_driver_version": snapshot.get("driver_version", ""),
        "gpu_memory_total_mb": snapshot.get("memory_total_mb"),
        "gpu_index": snapshot.get("index"),
    }


class ContinuousGpuSampler:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def capture_now(self, t: float | None = None) -> None:
        snapshot = get_gpu_snapshot()
        self.samples.append(
            {
                "t": float(time.perf_counter() if t is None else t),
                "available": bool(snapshot.get("available", False)),
                "power_draw_w": snapshot.get("power_draw_w"),
                "gpu_util_percent": snapshot.get("gpu_util_percent"),
                "memory_used_mb": snapshot.get("memory_used_mb"),
            }
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            t = time.perf_counter()
            snapshot = get_gpu_snapshot()
            self.samples.append(
                {
                    "t": t,
                    "available": bool(snapshot.get("available", False)),
                    "power_draw_w": snapshot.get("power_draw_w"),
                    "gpu_util_percent": snapshot.get("gpu_util_percent"),
                    "memory_used_mb": snapshot.get("memory_used_mb"),
                }
            )
            time.sleep(self.interval_seconds)

    def summarize_window(self, start_t: float, end_t: float, idle_baseline_w: float) -> dict[str, Any]:
        valid = [
            sample for sample in self.samples
            if sample["t"] >= start_t
            and sample["t"] <= end_t
            and sample.get("available")
            and isinstance(sample.get("power_draw_w"), (float, int))
        ]

        if len(valid) < 2:
            return {
                "sample_count": len(valid),
                "avg_power_w": None,
                "peak_power_w": None,
                "avg_gpu_util_percent": None,
                "peak_gpu_util_percent": None,
                "energy_joules_llm_only": None,
                "energy_wh_llm_only": None,
                "baseline_clamp_events": 0,
            }

        powers = [float(sample["power_draw_w"]) for sample in valid]
        utils = [
            float(sample["gpu_util_percent"])
            for sample in valid
            if isinstance(sample.get("gpu_util_percent"), (float, int))
        ]

        energy_joules = 0.0
        clamp_events = 0

        for a, b in zip(valid[:-1], valid[1:]):
            dt = max(0.0, float(b["t"]) - float(a["t"]))
            power_a = float(a["power_draw_w"])
            power_b = float(b["power_draw_w"])
            avg_segment_power = (power_a + power_b) / 2.0
            net_power = avg_segment_power - idle_baseline_w
            if net_power < 0.0:
                net_power = 0.0
                clamp_events += 1
            energy_joules += net_power * dt

        energy_wh = energy_joules / 3600.0

        return {
            "sample_count": len(valid),
            "avg_power_w": round(sum(powers) / len(powers), 2),
            "peak_power_w": round(max(powers), 2),
            "avg_gpu_util_percent": round(sum(utils) / len(utils), 2) if utils else None,
            "peak_gpu_util_percent": round(max(utils), 2) if utils else None,
            "energy_joules_llm_only": round(energy_joules, 2),
            "energy_wh_llm_only": round(energy_wh, 6),
            "baseline_clamp_events": clamp_events,
        }


def sample_idle_baseline(interval_seconds: float, duration_seconds: float) -> dict[str, Any]:
    samples: list[float] = []
    start = time.perf_counter()

    while (time.perf_counter() - start) < duration_seconds:
        snapshot = get_gpu_snapshot()
        if snapshot.get("available") and isinstance(snapshot.get("power_draw_w"), (float, int)):
            samples.append(float(snapshot["power_draw_w"]))
        time.sleep(interval_seconds)

    if not samples:
        return {
            "sample_count": 0,
            "idle_baseline_w": None,
            "reason": "no_gpu_samples",
        }

    avg_power = sum(samples) / len(samples)
    return {
        "sample_count": len(samples),
        "idle_baseline_w": round(avg_power, 2),
        "reason": "initial_loop_baseline_average",
    }


def classify_runtime_mode(
    ollama_processor_split: str | None,
    avg_gpu_util_percent: float | None,
    avg_power_w: float | None,
    tokens_per_second: float | None,
) -> dict[str, Any]:
    mode = "unknown"
    hybrid_warning = True
    fair_comparison_eligible = False

    split = (ollama_processor_split or "").lower()

    cpu_gpu_match = re.search(r"(\d+)%/(\d+)%\s+cpu/gpu", split)
    gpu_match = re.search(r"(\d+)%\s+gpu", split)
    cpu_match = re.search(r"(\d+)%\s+cpu", split)

    if cpu_gpu_match:
        cpu_pct = int(cpu_gpu_match.group(1))
        gpu_pct = int(cpu_gpu_match.group(2))
        if cpu_pct == 0 and gpu_pct > 0:
            mode = "full_gpu"
        elif cpu_pct > 0 and gpu_pct > 0:
            mode = "hybrid_cpu_gpu"
        elif gpu_pct == 0 and cpu_pct > 0:
            mode = "cpu_only"
    elif gpu_match and "cpu/gpu" not in split:
        mode = "full_gpu"
    elif cpu_match and "cpu/gpu" not in split:
        mode = "cpu_only"
    else:
        util = avg_gpu_util_percent or 0.0
        power = avg_power_w or 0.0
        tps = tokens_per_second or 0.0
        if util < 10 and power < 25:
            mode = "cpu_only"
        elif util >= 10 and power >= 25:
            mode = "full_gpu" if tps >= 1.0 else "hybrid_cpu_gpu"
        else:
            mode = "hybrid_cpu_gpu"

    hybrid_warning = mode != "full_gpu"
    fair_comparison_eligible = mode == "full_gpu"

    return {
        "gpu_residency_mode": mode,
        "ollama_processor_split": ollama_processor_split,
        "nvidia_avg_power_w": avg_power_w,
        "nvidia_avg_util_percent": avg_gpu_util_percent,
        "tokens_per_second_observed": tokens_per_second,
        "hybrid_warning": hybrid_warning,
        "fair_comparison_eligible": fair_comparison_eligible,
    }


def classify_energy_confidence(
    duration_seconds: float | None,
    gpu_power_sample_count: int | None,
    gpu_avg_power_w: float | None,
    idle_gpu_watts_discounted: float | None,
    gpu_residency_mode: str | None,
    fair_comparison_eligible: bool | None,
) -> dict[str, Any]:
    sample_count = int(gpu_power_sample_count or 0)
    avg_power = float(gpu_avg_power_w or 0.0)
    idle_power = float(idle_gpu_watts_discounted or 0.0)
    duration = float(duration_seconds or 0.0)
    power_delta = avg_power - idle_power

    if not fair_comparison_eligible or gpu_residency_mode != "full_gpu":
        return {
            "energy_confidence_class": "insufficient",
            "energy_comparison_eligible": False,
            "energy_valid": False,
            "energy_validity": "invalid_not_full_gpu",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "runtime_not_full_gpu_or_not_fair_comparison_eligible",
        }

    if duration <= 0.0:
        return {
            "energy_confidence_class": "insufficient",
            "energy_comparison_eligible": False,
            "energy_valid": False,
            "energy_validity": "invalid_missing_duration",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "missing_or_zero_duration",
        }

    if sample_count < 3:
        return {
            "energy_confidence_class": "insufficient",
            "energy_comparison_eligible": False,
            "energy_valid": False,
            "energy_validity": "invalid_low_sample_count",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "too_few_power_samples_for_comparison",
        }

    if power_delta <= 0.0:
        return {
            "energy_confidence_class": "insufficient",
            "energy_comparison_eligible": False,
            "energy_valid": False,
            "energy_validity": "invalid_no_signal",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "no_meaningful_power_signal_above_idle",
        }

    if sample_count >= 10:
        return {
            "energy_confidence_class": "high",
            "energy_comparison_eligible": True,
            "energy_valid": True,
            "energy_validity": "valid",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "strong_sample_support",
        }

    if sample_count >= 5:
        return {
            "energy_confidence_class": "medium",
            "energy_comparison_eligible": True,
            "energy_valid": True,
            "energy_validity": "valid",
            "energy_measurement_version": "run_sliced_v1",
            "energy_confidence_reason": "moderate_sample_support",
        }

    return {
        "energy_confidence_class": "low",
        "energy_comparison_eligible": True,
        "energy_valid": True,
        "energy_validity": "valid",
        "energy_measurement_version": "run_sliced_v1",
        "energy_confidence_reason": "sparse_but_usable_power_samples",
    }


def run_ollama_prompt(
    model: str,
    prompt_file: Path,
    result_json: Path,
    keep_alive: str,
    think: bool,
    write_debug_artifact: bool,
) -> dict[str, Any]:
    cmd = [
        str(SCRIPTS_BENCHMARK_DIR / "run_ollama_prompt.py"),
        "--model",
        model,
        "--prompt-file",
        str(prompt_file),
        "--keep-alive",
        keep_alive,
    ]

    if think:
        cmd.append("--think")

    if write_debug_artifact:
        cmd.append("--write-debug-artifact")

    run_checked(cmd, stdout_path=result_json)
    return json.loads(result_json.read_text(encoding="utf-8"))


def write_answer_text(runner_doc: dict[str, Any], answer_txt: Path) -> str:
    final_answer = runner_doc.get("final_answer", "")
    answer_txt.write_text(final_answer + ("" if final_answer.endswith("\n") else "\n"), encoding="utf-8")
    return final_answer


def evaluate_coding(answer_txt: Path, task_name: str, candidate_py: Path, report_json: Path) -> dict[str, Any]:
    task_name = (task_name or "").strip()

    if task_name == "coding_fs_strict_v3":
        subprocess.run(
            [
                str(EVALUATORS_DIR / "evaluate_coding_fs_strict_v2.py"),
                str(answer_txt),
                "--save-code",
                str(candidate_py),
                "--save-report",
                str(report_json),
            ],
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
        )
        return json.loads(report_json.read_text(encoding="utf-8"))

    generic_task_map = {
        "folder_scan": "folder_scan",
        "csv_summary": "csv_summary",
        "log_parser": "log_parser",
    }

    generic_task = generic_task_map.get(task_name)
    if generic_task is None:
        raise ValueError(f"Unsupported coding task_name: {task_name}")

    subprocess.run(
        [
            str(SCRIPTS_BENCHMARK_DIR / "evaluate_benchmark_python.py"),
            str(answer_txt),
            "--task",
            generic_task,
            "--save-code",
            str(candidate_py),
            "--save-report",
            str(report_json),
        ],
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(report_json.read_text(encoding="utf-8"))


def evaluate_fact_prose(answer_txt: Path, task_id: str, ground_truth_file: Path, report_json: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(SCRIPTS_BENCHMARK_DIR / "evaluate_benchmark_task.py"),
            str(answer_txt),
            "--task-id",
            task_id,
            "--ground-truth",
            str(ground_truth_file),
            "--save-report",
            str(report_json),
        ],
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(report_json.read_text(encoding="utf-8"))


def evaluate_math(answer_txt: Path, report_json: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(EVALUATORS_DIR / "evaluate_math_dependency_v2.py"),
            str(answer_txt),
            "--save-report",
            str(report_json),
        ],
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(report_json.read_text(encoding="utf-8"))


def evaluate_knowledge(answer_txt: Path, report_json: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(EVALUATORS_DIR / "evaluate_logic_consistency_v2.py"),
            str(answer_txt),
            "--save-report",
            str(report_json),
        ],
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(report_json.read_text(encoding="utf-8"))


def evaluate_language(answer_txt: Path, report_json: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(EVALUATORS_DIR / "evaluate_constrained_rewrite_v2.py"),
            str(answer_txt),
            "--save-report",
            str(report_json),
        ],
        check=True,
        text=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(report_json.read_text(encoding="utf-8"))


def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def deep_get(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def extract_score_percent(report: dict[str, Any]) -> float | None:
    candidates = [
        deep_get(report, "score", "score_percent"),
        report.get("score_percent"),
        report.get("scientific_score_percent"),
        deep_get(report, "summary", "score_percent"),
        deep_get(report, "result", "score_percent"),
    ]
    for value in candidates:
        f = safe_float(value)
        if f is not None:
            return round(f, 6)
    return None


def extract_passed_checks(report: dict[str, Any]) -> int | None:
    candidates = [
        deep_get(report, "score", "passed_checks"),
        report.get("passed_checks"),
        deep_get(report, "summary", "passed_checks"),
    ]
    for value in candidates:
        i = safe_int(value)
        if i is not None:
            return i
    return None


def extract_total_checks(report: dict[str, Any]) -> int | None:
    candidates = [
        deep_get(report, "score", "total_checks"),
        report.get("total_checks"),
        deep_get(report, "summary", "total_checks"),
    ]
    for value in candidates:
        i = safe_int(value)
        if i is not None:
            return i
    return None


def extract_usable(report: dict[str, Any]) -> bool | None:
    for candidate in [
        report.get("usable"),
        report.get("artifact_usability"),
        deep_get(report, "summary", "usable"),
    ]:
        b = boolish(candidate)
        if b is not None:
            return b
    return None


def extract_hard_failure(report: dict[str, Any], runner: dict[str, Any]) -> bool:
    for candidate in [
        report.get("hard_failure"),
        deep_get(report, "summary", "hard_failure"),
    ]:
        b = boolish(candidate)
        if b is not None:
            return b
    return not bool(runner.get("success", False))


def extract_execution_status(report: dict[str, Any], runner: dict[str, Any]) -> str:
    for candidate in [
        report.get("execution_status"),
        report.get("status"),
        deep_get(report, "summary", "execution_status"),
    ]:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "success" if runner.get("success") else "failed"


def extract_artifact_usability(report: dict[str, Any]) -> Any:
    for candidate in [
        report.get("artifact_usability"),
        report.get("usable"),
        deep_get(report, "summary", "artifact_usability"),
    ]:
        if candidate is not None:
            return candidate
    return None


def compute_common_metrics(
    *,
    runner: dict[str, Any],
    report: dict[str, Any],
    task_energy: dict[str, Any],
    runtime_classification: dict[str, Any],
    idle_gpu_watts: float,
) -> dict[str, Any]:
    metrics = runner.get("metrics", {})
    energy_flags = classify_energy_confidence(
        duration_seconds=runner.get("duration_seconds"),
        gpu_power_sample_count=task_energy.get("sample_count"),
        gpu_avg_power_w=task_energy.get("avg_power_w"),
        idle_gpu_watts_discounted=idle_gpu_watts,
        gpu_residency_mode=runtime_classification.get("gpu_residency_mode"),
        fair_comparison_eligible=runtime_classification.get("fair_comparison_eligible"),
    )

    llm_energy_joules = task_energy.get("energy_joules_llm_only")
    llm_energy_wh = task_energy.get("energy_wh_llm_only")
    llm_energy_kwh = round(llm_energy_wh / 1000.0, 9) if isinstance(llm_energy_wh, float) else None

    response_tokens = metrics.get("response_tokens")
    llm_joules_per_output_token = None
    llm_wh_per_1000_output_tokens = None
    output_tokens_per_joule = None

    if (
        isinstance(llm_energy_joules, (float, int))
        and float(llm_energy_joules) > 0.0
        and isinstance(response_tokens, int)
        and response_tokens > 0
    ):
        llm_energy_joules = float(llm_energy_joules)
        llm_joules_per_output_token = round(llm_energy_joules / response_tokens, 6)
        llm_wh_per_1000_output_tokens = round((llm_energy_joules / response_tokens) * 1000.0 / 3600.0, 6)
        output_tokens_per_joule = round(response_tokens / llm_energy_joules, 6)

    scientific_score_percent = extract_score_percent(report)
    score_per_second_strict = None
    score_per_wh_strict = None

    duration_seconds = safe_float(runner.get("duration_seconds"))
    if scientific_score_percent is not None and duration_seconds and duration_seconds > 0:
        score_per_second_strict = round(scientific_score_percent / duration_seconds, 6)

    if scientific_score_percent is not None and isinstance(llm_energy_wh, (float, int)) and float(llm_energy_wh) > 0:
        score_per_wh_strict = round(scientific_score_percent / float(llm_energy_wh), 6)

    usable = extract_usable(report)
    hard_failure = extract_hard_failure(report, runner)
    execution_status = extract_execution_status(report, runner)
    artifact_usability = extract_artifact_usability(report)

    return {
        "metrics": metrics,
        "energy_flags": energy_flags,
        "llm_energy_joules": round_or_none(safe_float(llm_energy_joules), 2),
        "llm_energy_wh": round_or_none(safe_float(llm_energy_wh), 6),
        "llm_energy_kwh": llm_energy_kwh,
        "llm_joules_per_output_token": llm_joules_per_output_token,
        "llm_wh_per_1000_output_tokens": llm_wh_per_1000_output_tokens,
        "output_tokens_per_joule": output_tokens_per_joule,
        "scientific_score_percent": scientific_score_percent,
        "score_per_second_strict": score_per_second_strict,
        "score_per_wh_strict": score_per_wh_strict,
        "usable": usable,
        "hard_failure": hard_failure,
        "execution_status": execution_status,
        "artifact_usability": artifact_usability,
        "evaluation_score_percent": extract_score_percent(report),
        "evaluation_passed_checks": extract_passed_checks(report),
        "evaluation_total_checks": extract_total_checks(report),
    }


def build_coding_ledger_entry(
    *,
    experiment_id: str,
    model: str,
    task_id: str,
    task_family: str,
    prompt_file: Path,
    power_limit_request: str,
    power_limit_percent: float | None,
    power_limit_mode: str,
    power_limit_explicit_watts: float | None,
    power_limit_applied_watts: float | None,
    run_index: int,
    runner: dict[str, Any],
    report: dict[str, Any],
    result_json: Path,
    report_json: Path,
    task_energy: dict[str, Any],
    runtime_classification: dict[str, Any],
    gpu_info: dict[str, Any],
    idle_gpu_watts: float,
) -> dict[str, Any]:
    prompt_text = prompt_file.read_text(encoding="utf-8", errors="replace")
    common = compute_common_metrics(
        runner=runner,
        report=report,
        task_energy=task_energy,
        runtime_classification=runtime_classification,
        idle_gpu_watts=idle_gpu_watts,
    )
    metrics = common["metrics"]
    energy_flags = common["energy_flags"]

    return {
        "experiment_id": experiment_id,
        "timestamp_utc": utc_now_iso(),
        "model": model,
        "task_id": task_id,
        "task_family": task_family,
        "prompt_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "prompt_file": str(prompt_file),
        "power_limit_request": power_limit_request,
        "power_limit_mode": power_limit_mode,
        "power_limit_percent": power_limit_percent,
        "power_limit_explicit_watts": power_limit_explicit_watts,
        "power_limit_applied_watts": power_limit_applied_watts,
        "run_index": run_index,
        "keep_alive": runner.get("keep_alive", "5m"),
        "duration_seconds": runner.get("duration_seconds"),
        "prompt_tokens": metrics.get("prompt_tokens"),
        "response_tokens": metrics.get("response_tokens"),
        "tokens_per_second": metrics.get("tokens_per_second"),
        "cold_start": metrics.get("cold_start"),
        "gpu_name": gpu_info["gpu_name"],
        "gpu_uuid": gpu_info["gpu_uuid"],
        "gpu_driver_version": gpu_info["gpu_driver_version"],
        "gpu_memory_total_mb": gpu_info["gpu_memory_total_mb"],
        "gpu_index": gpu_info["gpu_index"],
        "gpu_avg_power_w": task_energy.get("avg_power_w"),
        "gpu_peak_power_w": task_energy.get("peak_power_w"),
        "gpu_avg_util_percent": task_energy.get("avg_gpu_util_percent"),
        "gpu_peak_util_percent": task_energy.get("peak_gpu_util_percent"),
        "gpu_power_sample_count": task_energy.get("sample_count"),
        "idle_gpu_watts_discounted": idle_gpu_watts,
        "baseline_clamp_events": task_energy.get("baseline_clamp_events"),
        "llm_energy_joules": common["llm_energy_joules"],
        "llm_energy_wh": common["llm_energy_wh"],
        "llm_energy_kwh": common["llm_energy_kwh"],
        "llm_joules_per_output_token": common["llm_joules_per_output_token"],
        "llm_wh_per_1000_output_tokens": common["llm_wh_per_1000_output_tokens"],
        "output_tokens_per_joule": common["output_tokens_per_joule"],
        "answer_risk": "medium",
        "evaluation_type": "code_v3",
        "evaluation_score_percent": common["evaluation_score_percent"],
        "evaluation_passed_checks": common["evaluation_passed_checks"],
        "evaluation_total_checks": common["evaluation_total_checks"],
        "evaluation_report_path": str(report_json),
        "runner_json_path": str(result_json),
        "execution_status": common["execution_status"],
        "artifact_usability": common["artifact_usability"],
        "gpu_residency_mode": runtime_classification.get("gpu_residency_mode"),
        "ollama_processor_split": runtime_classification.get("ollama_processor_split"),
        "hybrid_warning": runtime_classification.get("hybrid_warning"),
        "fair_comparison_eligible": runtime_classification.get("fair_comparison_eligible"),
        "energy_confidence_class": energy_flags["energy_confidence_class"],
        "energy_comparison_eligible": energy_flags["energy_comparison_eligible"],
        "energy_valid": energy_flags["energy_valid"],
        "energy_validity": energy_flags["energy_validity"],
        "energy_measurement_version": energy_flags["energy_measurement_version"],
        "energy_confidence_reason": energy_flags["energy_confidence_reason"],
        "success": runner.get("success"),
        "error": runner.get("error", ""),
        "final_answer_chars": len(runner.get("final_answer", "")),
        "thinking_trace_chars": len(runner.get("thinking_trace", "")),
        "scientific_score_percent": common["scientific_score_percent"],
        "score_per_second_strict": common["score_per_second_strict"],
        "score_per_wh_strict": common["score_per_wh_strict"],
        "usable": common["usable"],
        "hard_failure": common["hard_failure"],
    }


def build_fact_prose_ledger_entry(
    *,
    experiment_id: str,
    model: str,
    task_id: str,
    task_family: str,
    prompt_file: Path,
    power_limit_request: str,
    power_limit_percent: float | None,
    power_limit_mode: str,
    power_limit_explicit_watts: float | None,
    power_limit_applied_watts: float | None,
    run_index: int,
    runner: dict[str, Any],
    report: dict[str, Any],
    result_json: Path,
    report_json: Path,
    task_energy: dict[str, Any],
    runtime_classification: dict[str, Any],
    gpu_info: dict[str, Any],
    idle_gpu_watts: float,
) -> dict[str, Any]:
    prompt_text = prompt_file.read_text(encoding="utf-8", errors="replace")
    common = compute_common_metrics(
        runner=runner,
        report=report,
        task_energy=task_energy,
        runtime_classification=runtime_classification,
        idle_gpu_watts=idle_gpu_watts,
    )
    metrics = common["metrics"]
    energy_flags = common["energy_flags"]

    return {
        "experiment_id": experiment_id,
        "timestamp_utc": utc_now_iso(),
        "model": model,
        "task_id": task_id,
        "task_family": task_family,
        "prompt_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "prompt_file": str(prompt_file),
        "power_limit_request": power_limit_request,
        "power_limit_mode": power_limit_mode,
        "power_limit_percent": power_limit_percent,
        "power_limit_explicit_watts": power_limit_explicit_watts,
        "power_limit_applied_watts": power_limit_applied_watts,
        "run_index": run_index,
        "keep_alive": runner.get("keep_alive", "5m"),
        "duration_seconds": runner.get("duration_seconds"),
        "prompt_tokens": metrics.get("prompt_tokens"),
        "response_tokens": metrics.get("response_tokens"),
        "tokens_per_second": metrics.get("tokens_per_second"),
        "cold_start": metrics.get("cold_start"),
        "gpu_name": gpu_info["gpu_name"],
        "gpu_uuid": gpu_info["gpu_uuid"],
        "gpu_driver_version": gpu_info["gpu_driver_version"],
        "gpu_memory_total_mb": gpu_info["gpu_memory_total_mb"],
        "gpu_index": gpu_info["gpu_index"],
        "gpu_avg_power_w": task_energy.get("avg_power_w"),
        "gpu_peak_power_w": task_energy.get("peak_power_w"),
        "gpu_avg_util_percent": task_energy.get("avg_gpu_util_percent"),
        "gpu_peak_util_percent": task_energy.get("peak_gpu_util_percent"),
        "gpu_power_sample_count": task_energy.get("sample_count"),
        "idle_gpu_watts_discounted": idle_gpu_watts,
        "baseline_clamp_events": task_energy.get("baseline_clamp_events"),
        "llm_energy_joules": common["llm_energy_joules"],
        "llm_energy_wh": common["llm_energy_wh"],
        "llm_energy_kwh": common["llm_energy_kwh"],
        "llm_joules_per_output_token": common["llm_joules_per_output_token"],
        "llm_wh_per_1000_output_tokens": common["llm_wh_per_1000_output_tokens"],
        "output_tokens_per_joule": common["output_tokens_per_joule"],
        "answer_risk": "medium",
        "evaluation_type": f"{task_family}_v1",
        "evaluation_score_percent": common["evaluation_score_percent"],
        "evaluation_passed_checks": common["evaluation_passed_checks"],
        "evaluation_total_checks": common["evaluation_total_checks"],
        "evaluation_report_path": str(report_json),
        "runner_json_path": str(result_json),
        "execution_status": common["execution_status"],
        "artifact_usability": common["artifact_usability"],
        "gpu_residency_mode": runtime_classification.get("gpu_residency_mode"),
        "ollama_processor_split": runtime_classification.get("ollama_processor_split"),
        "hybrid_warning": runtime_classification.get("hybrid_warning"),
        "fair_comparison_eligible": runtime_classification.get("fair_comparison_eligible"),
        "energy_confidence_class": energy_flags["energy_confidence_class"],
        "energy_comparison_eligible": energy_flags["energy_comparison_eligible"],
        "energy_valid": energy_flags["energy_valid"],
        "energy_validity": energy_flags["energy_validity"],
        "energy_measurement_version": energy_flags["energy_measurement_version"],
        "energy_confidence_reason": energy_flags["energy_confidence_reason"],
        "success": runner.get("success"),
        "error": runner.get("error", ""),
        "final_answer_chars": len(runner.get("final_answer", "")),
        "thinking_trace_chars": len(runner.get("thinking_trace", "")),
        "scientific_score_percent": common["scientific_score_percent"],
        "score_per_second_strict": common["score_per_second_strict"],
        "score_per_wh_strict": common["score_per_wh_strict"],
        "usable": common["usable"],
        "hard_failure": common["hard_failure"],
    }


def ensure_dirs(base_dir: Path, task_family: str) -> dict[str, Path]:
    dirs = {
        "results": base_dir / "results",
        "answers": base_dir / "answers",
        "reports": base_dir / "reports",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    if task_family == "coding":
        dirs["candidates"] = base_dir / "candidates"
        dirs["candidates"].mkdir(parents=True, exist_ok=True)

    return dirs


def normalize_task_family(task_family: str) -> str:
    raw = (task_family or "").strip().lower()
    mapping = {
        "factual": "fact",
        "fact": "fact",
        "prose": "prose",
        "coding": "coding",
        "code": "coding",
        "math": "math",
        "knowledge": "knowledge",
        "logic": "knowledge",
        "language": "language",
    }
    normalized = mapping.get(raw)
    if normalized is None:
        raise ValueError(f"Unsupported task_family: {task_family}")
    return normalized


def parse_tdp_levels(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError("No TDP levels supplied.")

    normalized = [normalize_tdp_token(part) for part in parts]
    return normalized


def run_experiment(
    *,
    model: str,
    experiment_id: str,
    run_index: int,
    tdp_levels: list[str],
    keep_alive: str,
    think: bool,
    write_debug_artifact: bool,
    power_sample_interval: float,
    idle_baseline_duration: float,
) -> int:
    manifest = load_manifest(experiment_id)
    base_dir = BENCHMARKS_DIR / experiment_id
    ledger_path = base_dir / "llm_benchmark_runs.jsonl"
    tasks = manifest.get("tasks", [])
    if not tasks:
        raise ValueError(f"No tasks found in manifest: {base_dir / 'manifest.json'}")

    model_safe = model_safe_name(model)

    for tdp_token in tdp_levels:
        power_limit_info = set_power_limit(tdp_token, model, run_index)

        gpu_info = detect_gpu_info()
        idle_baseline = sample_idle_baseline(
            interval_seconds=power_sample_interval,
            duration_seconds=idle_baseline_duration,
        )
        idle_gpu_watts = safe_float(idle_baseline.get("idle_baseline_w")) or 0.0

        run_stem_tdp = str(power_limit_info["power_limit_request"]).replace("%", "pct").replace(".", "_")

        sampler = ContinuousGpuSampler(interval_seconds=power_sample_interval)
        sampler.start()

        try:
            for task in tasks:
                task_id = task["task_id"]
                task_family = normalize_task_family(task["task_family"])
                task_name = task["task_name"]
                prompt_file = base_dir / task["prompt_file"]

                if not prompt_file.exists():
                    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

                dirs = ensure_dirs(base_dir, task_family)

                run_stem = f"{run_stem_tdp}_{model_safe}_{task_id}_run{run_index}"
                result_json = dirs["results"] / f"{run_stem}.json"
                answer_txt = dirs["answers"] / f"{run_stem}.txt"
                report_json = dirs["reports"] / f"{run_stem}_report.json"

                print()
                print(f"--- Running {task_id} ({task_name}) ---")

                task_start_t = time.perf_counter()
                sampler.capture_now(task_start_t)

                runner = run_ollama_prompt(
                    model=model,
                    prompt_file=prompt_file,
                    result_json=result_json,
                    keep_alive=keep_alive,
                    think=think,
                    write_debug_artifact=write_debug_artifact,
                )

                task_end_t = time.perf_counter()
                sampler.capture_now(task_end_t)

                write_answer_text(runner, answer_txt)

                task_energy = sampler.summarize_window(
                    start_t=task_start_t,
                    end_t=task_end_t,
                    idle_baseline_w=idle_gpu_watts,
                )

                processor_split = (
                    runner.get("probes", {})
                    .get("ollama_ps_after", {})
                    .get("processor_split")
                )
                runtime_classification = classify_runtime_mode(
                    ollama_processor_split=processor_split,
                    avg_gpu_util_percent=task_energy.get("avg_gpu_util_percent"),
                    avg_power_w=task_energy.get("avg_power_w"),
                    tokens_per_second=runner.get("metrics", {}).get("tokens_per_second"),
                )

                if task_family == "coding":
                    candidate_py = dirs["candidates"] / f"{run_stem}.py"
                    report = evaluate_coding(answer_txt, task_name, candidate_py, report_json)
                    entry = build_coding_ledger_entry(
                        experiment_id=experiment_id,
                        model=model,
                        task_id=task_id,
                        task_family=task_family,
                        prompt_file=prompt_file,
                        power_limit_request=power_limit_info["power_limit_request"],
                        power_limit_percent=power_limit_info["power_limit_percent"],
                        power_limit_mode=power_limit_info["power_limit_mode"],
                        power_limit_explicit_watts=power_limit_info["power_limit_explicit_watts"],
                        power_limit_applied_watts=power_limit_info["power_limit_applied_watts"],
                        run_index=run_index,
                        runner=runner,
                        report=report,
                        result_json=result_json,
                        report_json=report_json,
                        task_energy=task_energy,
                        runtime_classification=runtime_classification,
                        gpu_info=gpu_info,
                        idle_gpu_watts=idle_gpu_watts,
                    )
                    print("Saved:")
                    print(f"  result:    {result_json}")
                    print(f"  answer:    {answer_txt}")
                    print(f"  candidate: {candidate_py}")
                    print(f"  report:    {report_json}")

                elif task_family in {"fact", "prose"}:
                    gt_rel = task.get("ground_truth_file")
                    if not gt_rel:
                        raise ValueError(f"Missing ground_truth_file for task: {task_id}")
                    ground_truth_file = base_dir / gt_rel
                    if not ground_truth_file.exists():
                        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_file}")

                    report = evaluate_fact_prose(answer_txt, task_id, ground_truth_file, report_json)
                    entry = build_fact_prose_ledger_entry(
                        experiment_id=experiment_id,
                        model=model,
                        task_id=task_id,
                        task_family=task_family,
                        prompt_file=prompt_file,
                        power_limit_request=power_limit_info["power_limit_request"],
                        power_limit_percent=power_limit_info["power_limit_percent"],
                        power_limit_mode=power_limit_info["power_limit_mode"],
                        power_limit_explicit_watts=power_limit_info["power_limit_explicit_watts"],
                        power_limit_applied_watts=power_limit_info["power_limit_applied_watts"],
                        run_index=run_index,
                        runner=runner,
                        report=report,
                        result_json=result_json,
                        report_json=report_json,
                        task_energy=task_energy,
                        runtime_classification=runtime_classification,
                        gpu_info=gpu_info,
                        idle_gpu_watts=idle_gpu_watts,
                    )
                    print("Saved:")
                    print(f"  result: {result_json}")
                    print(f"  answer: {answer_txt}")
                    print(f"  report: {report_json}")

                elif task_family == "math":
                    report = evaluate_math(answer_txt, report_json)
                    entry = build_fact_prose_ledger_entry(
                        experiment_id=experiment_id,
                        model=model,
                        task_id=task_id,
                        task_family=task_family,
                        prompt_file=prompt_file,
                        power_limit_request=power_limit_info["power_limit_request"],
                        power_limit_percent=power_limit_info["power_limit_percent"],
                        power_limit_mode=power_limit_info["power_limit_mode"],
                        power_limit_explicit_watts=power_limit_info["power_limit_explicit_watts"],
                        power_limit_applied_watts=power_limit_info["power_limit_applied_watts"],
                        run_index=run_index,
                        runner=runner,
                        report=report,
                        result_json=result_json,
                        report_json=report_json,
                        task_energy=task_energy,
                        runtime_classification=runtime_classification,
                        gpu_info=gpu_info,
                        idle_gpu_watts=idle_gpu_watts,
                    )
                    print("Saved:")
                    print(f"  result: {result_json}")
                    print(f"  answer: {answer_txt}")
                    print(f"  report: {report_json}")

                elif task_family == "knowledge":
                    report = evaluate_knowledge(answer_txt, report_json)
                    entry = build_fact_prose_ledger_entry(
                        experiment_id=experiment_id,
                        model=model,
                        task_id=task_id,
                        task_family=task_family,
                        prompt_file=prompt_file,
                        power_limit_request=power_limit_info["power_limit_request"],
                        power_limit_percent=power_limit_info["power_limit_percent"],
                        power_limit_mode=power_limit_info["power_limit_mode"],
                        power_limit_explicit_watts=power_limit_info["power_limit_explicit_watts"],
                        power_limit_applied_watts=power_limit_info["power_limit_applied_watts"],
                        run_index=run_index,
                        runner=runner,
                        report=report,
                        result_json=result_json,
                        report_json=report_json,
                        task_energy=task_energy,
                        runtime_classification=runtime_classification,
                        gpu_info=gpu_info,
                        idle_gpu_watts=idle_gpu_watts,
                    )
                    print("Saved:")
                    print(f"  result: {result_json}")
                    print(f"  answer: {answer_txt}")
                    print(f"  report: {report_json}")

                elif task_family == "language":
                    report = evaluate_language(answer_txt, report_json)
                    entry = build_fact_prose_ledger_entry(
                        experiment_id=experiment_id,
                        model=model,
                        task_id=task_id,
                        task_family=task_family,
                        prompt_file=prompt_file,
                        power_limit_request=power_limit_info["power_limit_request"],
                        power_limit_percent=power_limit_info["power_limit_percent"],
                        power_limit_mode=power_limit_info["power_limit_mode"],
                        power_limit_explicit_watts=power_limit_info["power_limit_explicit_watts"],
                        power_limit_applied_watts=power_limit_info["power_limit_applied_watts"],
                        run_index=run_index,
                        runner=runner,
                        report=report,
                        result_json=result_json,
                        report_json=report_json,
                        task_energy=task_energy,
                        runtime_classification=runtime_classification,
                        gpu_info=gpu_info,
                        idle_gpu_watts=idle_gpu_watts,
                    )
                    print("Saved:")
                    print(f"  result: {result_json}")
                    print(f"  answer: {answer_txt}")
                    print(f"  report: {report_json}")

                else:
                    raise ValueError(f"Unsupported task_family: {task_family}")

                append_jsonl(ledger_path, entry)

        finally:
            sampler.stop()

    print()
    print(f"Done: {model}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Jarri LLM benchmark experiment.")
    parser.add_argument("model", help="Ollama model name, e.g. qwen3:8b")
    parser.add_argument("experiment_id", help="Benchmark experiment directory name under ./benchmarks")
    parser.add_argument("--run-index", type=int, required=True, help="Run index for this sweep pass")
    parser.add_argument(
        "--tdp-levels",
        default="41",
        help="Comma-separated TDP tokens, e.g. 41,50,80,100,112 or 144w,168w",
    )
    parser.add_argument("--keep-alive", default="5m")
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--write-debug-artifact", action="store_true")
    parser.add_argument("--power-sample-interval", type=float, default=0.2)
    parser.add_argument("--idle-baseline-duration", type=float, default=3.0)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    return run_experiment(
        model=args.model,
        experiment_id=args.experiment_id,
        run_index=args.run_index,
        tdp_levels=parse_tdp_levels(args.tdp_levels),
        keep_alive=args.keep_alive,
        think=args.think,
        write_debug_artifact=args.write_debug_artifact,
        power_sample_interval=args.power_sample_interval,
        idle_baseline_duration=args.idle_baseline_duration,
    )


if __name__ == "__main__":
    raise SystemExit(main())
