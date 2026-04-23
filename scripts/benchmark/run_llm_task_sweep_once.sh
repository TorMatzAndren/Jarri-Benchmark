#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

VALIDATOR="${PROJECT_ROOT}/scripts/benchmark/validate_ollama_gpu_residency.py"
RUNNER="${PROJECT_ROOT}/benchmark/cli/benchmark_run.py"

[[ $# -lt 3 ]] && { echo "Usage: model experiment run_index [tdp]"; exit 1; }

MODEL="$1"
EXPERIMENT="$2"
RUN_INDEX="$3"
TDP="${4:-}"

DEFAULT_TDP="41,50,60,70,80,90,100,112"

if [[ -z "$TDP" ]]; then
  TDP="$DEFAULT_TDP"
fi

echo "Single sweep:"
echo "  model: $MODEL"
echo "  exp:   $EXPERIMENT"
echo "  run:   $RUN_INDEX"
echo "  tdp:   $TDP"

python3 "$VALIDATOR" "$MODEL" --warm --checks 3 --sleep-seconds 1.0 --require "100% GPU"

python3 "$RUNNER" \
  "$MODEL" \
  "$EXPERIMENT" \
  --run-index "$RUN_INDEX" \
  --tdp-levels "$TDP" \
  --power-sample-interval 0.2 \
  --idle-baseline-duration 3.0
