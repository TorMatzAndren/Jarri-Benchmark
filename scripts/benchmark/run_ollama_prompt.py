#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
JARRI_DIR = Path(__file__).resolve().parents[2]
DEBUG_RUNS_DIR = JARRI_DIR / "llm_debug_runs"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def split_embedded_thinking(text: str) -> tuple[str, str]:
    marker = "</think>"
    if marker not in text:
        return "", text.strip()
    before, after = text.split(marker, 1)
    return before.strip(), after.strip()


def get_ollama_ps_snapshot() -> dict[str, Any]:
    import subprocess

    result = subprocess.run(["ollama", "ps"], capture_output=True, text=True, check=False)
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    split_text = None
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    if len(lines) >= 2:
        raw = lines[1]
        processor_match = re.search(r"(\d+%/\d+%\s+CPU/GPU|\d+%\s+GPU|\d+%\s+CPU)", raw)
        if processor_match:
            split_text = processor_match.group(1).strip()

    return {
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "processor_split": split_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one non-interactive Ollama prompt and emit structured JSON.")
    parser.add_argument("--model", required=True, help="Model name, e.g. qwen3:8b")
    parser.add_argument("--prompt", help="Prompt text")
    parser.add_argument("--prompt-file", help="Path to a UTF-8 text file containing the prompt")
    parser.add_argument("--think", action="store_true", help="Enable thinking output")
    parser.add_argument("--keep-alive", default="5m", help="Ollama keep_alive value")
    parser.add_argument("--write-debug-artifact", action="store_true", help="Write full debug JSON to ./llm_debug_runs")
    args = parser.parse_args()

    JARRI_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.prompt and not args.prompt_file:
        print(json.dumps({"success": False, "error": "Either --prompt or --prompt-file is required."}, indent=2))
        return 1

    if args.prompt and args.prompt_file:
        print(json.dumps({"success": False, "error": "Use either --prompt or --prompt-file, not both."}, indent=2))
        return 1

    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            print(json.dumps({"success": False, "error": f"Prompt file not found: {prompt_path}"}, indent=2))
            return 1
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        prompt = args.prompt or ""

    started_utc = utc_now_iso()
    ollama_ps_before = get_ollama_ps_snapshot()

    import time
    start_time = time.perf_counter()

    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "stream": False,
        "think": args.think,
        "keep_alive": args.keep_alive,
    }

    try:
        response = post_json(OLLAMA_URL, payload)
        success = True
        error = ""
    except Exception as exc:
        response = {}
        success = False
        error = str(exc)

    end_time = time.perf_counter()
    completed_utc = utc_now_iso()
    duration_seconds = round(end_time - start_time, 3)
    ollama_ps_after = get_ollama_ps_snapshot()

    final_answer = response.get("response", "")
    thinking_trace = response.get("thinking", "")
    if not thinking_trace:
        embedded_thinking, cleaned_answer = split_embedded_thinking(final_answer)
        if embedded_thinking:
            thinking_trace = embedded_thinking
            final_answer = cleaned_answer

    total_duration_ns = safe_int(response.get("total_duration"))
    load_duration_ns = safe_int(response.get("load_duration"))
    prompt_eval_count = safe_int(response.get("prompt_eval_count"))
    eval_count = safe_int(response.get("eval_count"))
    eval_duration_ns = safe_int(response.get("eval_duration"))
    prompt_eval_duration_ns = safe_int(response.get("prompt_eval_duration"))

    load_seconds = round(load_duration_ns / 1_000_000_000, 3) if isinstance(load_duration_ns, int) else None
    eval_seconds = round(eval_duration_ns / 1_000_000_000, 3) if isinstance(eval_duration_ns, int) else None
    prompt_eval_seconds = round(prompt_eval_duration_ns / 1_000_000_000, 3) if isinstance(prompt_eval_duration_ns, int) else None

    tokens_per_second = None
    if isinstance(eval_duration_ns, int) and eval_duration_ns > 0 and isinstance(eval_count, int):
        tokens_per_second = round(eval_count / (eval_duration_ns / 1_000_000_000), 2)

    cold_start = bool(isinstance(load_seconds, float) and load_seconds > 1.0)

    debug_artifact_path = None
    if args.write_debug_artifact:
        debug_artifact_name = f"{completed_utc.replace(':', '-').replace('+00:00', 'Z')}_{args.model.replace(':', '_')}.json"
        debug_artifact_path = DEBUG_RUNS_DIR / debug_artifact_name
        debug_document = {
            "success": success,
            "model": args.model,
            "prompt": prompt,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "duration_seconds": duration_seconds,
            "keep_alive": args.keep_alive,
            "think_enabled": args.think,
            "final_answer": final_answer,
            "thinking_trace": thinking_trace,
            "done": response.get("done", False),
            "done_reason": response.get("done_reason", ""),
            "metrics": {
                "prompt_tokens": prompt_eval_count,
                "response_tokens": eval_count,
                "prompt_eval_seconds": prompt_eval_seconds,
                "eval_seconds": eval_seconds,
                "load_seconds": load_seconds,
                "tokens_per_second": tokens_per_second,
                "cold_start": cold_start,
                "total_duration_ns": total_duration_ns,
                "load_duration_ns": load_duration_ns,
                "prompt_eval_duration_ns": prompt_eval_duration_ns,
                "eval_duration_ns": eval_duration_ns,
            },
            "ollama_ps_before": ollama_ps_before,
            "ollama_ps_after": ollama_ps_after,
            "error": error,
            "raw_response": response,
        }
        debug_artifact_path.write_text(json.dumps(debug_document, indent=2, ensure_ascii=False), encoding="utf-8")

    output_document = {
        "success": success,
        "model": args.model,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "duration_seconds": duration_seconds,
        "final_answer": final_answer,
        "thinking_trace": thinking_trace,
        "metrics": {
            "prompt_tokens": prompt_eval_count,
            "response_tokens": eval_count,
            "tokens_per_second": tokens_per_second,
            "cold_start": cold_start,
            "prompt_eval_seconds": prompt_eval_seconds,
            "eval_seconds": eval_seconds,
            "load_seconds": load_seconds,
            "total_duration_ns": total_duration_ns,
            "load_duration_ns": load_duration_ns,
            "prompt_eval_duration_ns": prompt_eval_duration_ns,
            "eval_duration_ns": eval_duration_ns,
        },
        "probes": {
            "ollama_ps_before": ollama_ps_before,
            "ollama_ps_after": ollama_ps_after,
        },
        "debug_artifact_path": str(debug_artifact_path) if debug_artifact_path else None,
        "error": error,
    }

    print(json.dumps(output_document, indent=2, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
