#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, UTC
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "benchmarks" / "_analysis_inventory" / "runtime_residency"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def find_model_line(ps_output: str, model: str) -> str | None:
    for line in ps_output.splitlines():
        if line.strip().startswith(model):
            return line.strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--warm-prompt", default="Return exactly: READY")
    parser.add_argument("--checks", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--require", default="100% GPU")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    warm_result = None
    if args.warm:
        warm = run_cmd(["ollama", "run", args.model, args.warm_prompt], check=False)
        warm_result = {
            "returncode": warm.returncode,
            "stdout": warm.stdout[-4000:],
            "stderr": warm.stderr[-4000:]
        }
        if warm.returncode != 0:
            payload = {
                "generated_at_utc": utc_now_iso(),
                "model": args.model,
                "status": "warm_failed",
                "warm_result": warm_result
            }
            out_path = OUT_DIR / f"{slugify(args.model)}.json"
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(str(out_path))
            return 1

    checks = []
    ok = True

    for index in range(args.checks):
        ps = run_cmd(["ollama", "ps"], check=False)
        model_line = find_model_line(ps.stdout, args.model)

        check_payload = {
            "index": index + 1,
            "timestamp_utc": utc_now_iso(),
            "returncode": ps.returncode,
            "model_line": model_line,
            "matched_requirement": bool(model_line and args.require in model_line),
            "stdout_tail": ps.stdout[-4000:],
            "stderr_tail": ps.stderr[-4000:]
        }
        checks.append(check_payload)

        if not model_line or args.require not in model_line:
            ok = False

        if index < args.checks - 1:
            time.sleep(args.sleep_seconds)

    payload = {
        "generated_at_utc": utc_now_iso(),
        "model": args.model,
        "required_processor_signature": args.require,
        "status": "ok" if ok else "rejected",
        "warm_result": warm_result,
        "checks": checks
    }

    out_path = OUT_DIR / f"{slugify(args.model)}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if ok:
        return 0

    print(str(out_path))
    print(f"ERROR: {args.model} is not fully GPU resident. Refusing canonical sweep.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
