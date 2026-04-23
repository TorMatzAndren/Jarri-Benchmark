#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_ROOT="${PROJECT_ROOT}"
UI_ROOT="${PROJECT_ROOT}/benchmark_ui"
DATA_ROOT="${UI_ROOT}/data"

EXPERIMENTS=(
  coding_measurement_v3
  fact_prose_v2
  knowledge_measurement_v2
  language_measurement_v2
  math_measurement_v1
)

mkdir -p "${DATA_ROOT}/joined"
mkdir -p "${DATA_ROOT}/failures"
mkdir -p "${DATA_ROOT}/analysis"

copy_required() {
  local src="$1"
  local dst="$2"

  if [ ! -f "${src}" ]; then
    echo "ERROR: required source missing: ${src}" >&2
    exit 1
  fi

  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
  echo "copied: ${src} -> ${dst}"
}

copy_optional() {
  local src="$1"
  local dst="$2"

  if [ -f "${src}" ]; then
    mkdir -p "$(dirname "${dst}")"
    cp "${src}" "${dst}"
    echo "copied: ${src} -> ${dst}"
  fi
}

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_joined/joined_failure_energy_by_model.json" \
  "${DATA_ROOT}/joined/joined_failure_energy_by_model.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_joined/joined_failure_energy_by_task.json" \
  "${DATA_ROOT}/joined/joined_failure_energy_by_task.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_joined/joined_failure_energy_by_tdp.json" \
  "${DATA_ROOT}/joined/joined_failure_energy_by_tdp.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_joined/joined_failure_energy_rows.json" \
  "${DATA_ROOT}/joined/joined_failure_energy_rows.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_joined/joined_failure_energy_by_model_task_tdp.json" \
  "${DATA_ROOT}/joined/joined_failure_energy_by_model_task_tdp.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_failures/failure_by_model.json" \
  "${DATA_ROOT}/failures/failure_by_model.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_failures/failure_by_task.json" \
  "${DATA_ROOT}/failures/failure_by_task.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_failures/failure_by_task_family.json" \
  "${DATA_ROOT}/failures/failure_by_task_family.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_failures/failure_by_tdp.json" \
  "${DATA_ROOT}/failures/failure_by_tdp.json"

copy_required \
  "${SRC_ROOT}/benchmarks/_analysis_failures/failure_records.json" \
  "${DATA_ROOT}/failures/failure_records.json"

for exp in "${EXPERIMENTS[@]}"; do
  copy_optional \
    "${SRC_ROOT}/benchmarks/_analysis/${exp}/benchmark_export.json" \
    "${DATA_ROOT}/analysis/${exp}/benchmark_export.json"

  copy_optional \
    "${SRC_ROOT}/benchmarks/_analysis/${exp}/normalized_runs.json" \
    "${DATA_ROOT}/analysis/${exp}/normalized_runs.json"

  copy_optional \
    "${SRC_ROOT}/benchmarks/_analysis/${exp}/aggregate_by_model_gpu_tdp_task.json" \
    "${DATA_ROOT}/analysis/${exp}/aggregate_by_model_gpu_tdp_task.json"
done

python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path("benchmark_ui/data")

sections: dict[str, object] = {
    "joined": [],
    "failures": [],
    "analysis": {},
}

for subdir in ["joined", "failures"]:
    d = root / subdir
    if d.exists():
        sections[subdir] = [
            str(p.relative_to(root))
            for p in sorted(d.glob("*.json"))
        ]

analysis_root = root / "analysis"
if analysis_root.exists():
    analysis = {}
    for exp_dir in sorted(p for p in analysis_root.iterdir() if p.is_dir()):
        files = [
            str(p.relative_to(root))
            for p in sorted(exp_dir.glob("*.json"))
        ]
        if files:
            analysis[exp_dir.name] = files
    sections["analysis"] = analysis

doc = {
    "generated_by": "sync_benchmark_ui_data.sh",
    "sections": sections,
}

(root / "data_index.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
PY

echo "wrote: ${DATA_ROOT}/data_index.json"
echo "benchmark UI data sync complete"
