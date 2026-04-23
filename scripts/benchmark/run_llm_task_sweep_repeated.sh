#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ONCE_SCRIPT="${PROJECT_ROOT}/scripts/benchmark/run_llm_task_sweep_once.sh"

[[ $# -lt 3 ]] && { echo "Usage: model experiment repeats [tdp]"; exit 1; }

MODEL="$1"
EXPERIMENT="$2"
REPEATS="$3"
TDP="${4:-}"

[[ ! -x "$ONCE_SCRIPT" ]] && { echo "Missing once script"; exit 1; }

for ((i=1; i<=REPEATS; i++)); do
  echo "Run $i/$REPEATS :: $MODEL :: $EXPERIMENT"
  if [[ -n "$TDP" ]]; then
    bash "$ONCE_SCRIPT" "$MODEL" "$EXPERIMENT" "$i" "$TDP"
  else
    bash "$ONCE_SCRIPT" "$MODEL" "$EXPERIMENT" "$i"
  fi
done
