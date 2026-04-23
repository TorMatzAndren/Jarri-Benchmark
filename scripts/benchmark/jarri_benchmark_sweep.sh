#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPEATED_SCRIPT="${PROJECT_ROOT}/scripts/benchmark/run_llm_task_sweep_repeated.sh"

REPEATS=""
MODELS_CSV=""
EXPERIMENTS_CSV=""
TDP_LEVELS_CSV=""

DEFAULT_EXPERIMENTS=(
  coding_measurement_v3
  math_measurement_v1
  knowledge_measurement_v2
  language_measurement_v2
  fact_prose_v2
)

usage() {
  echo "Usage:"
  echo "  bash scripts/benchmark/jarri_benchmark_sweep.sh --repeats <n> --models <model1,model2,...> [--experiments <...>] [--tdp-levels <...>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repeats) REPEATS="$2"; shift 2 ;;
    --models) MODELS_CSV="$2"; shift 2 ;;
    --experiments) EXPERIMENTS_CSV="$2"; shift 2 ;;
    --tdp-levels) TDP_LEVELS_CSV="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$REPEATS" || -z "$MODELS_CSV" ]] && usage
[[ ! -x "$REPEATED_SCRIPT" ]] && { echo "Missing repeated script"; exit 1; }

IFS=',' read -ra MODELS <<< "$MODELS_CSV"

if [[ -n "$EXPERIMENTS_CSV" ]]; then
  IFS=',' read -ra EXPERIMENTS <<< "$EXPERIMENTS_CSV"
else
  EXPERIMENTS=("${DEFAULT_EXPERIMENTS[@]}")
fi

echo "Sweep:"
echo "  repeats: $REPEATS"
echo "  models:  ${MODELS[*]}"
echo "  exps:    ${EXPERIMENTS[*]}"
echo "  tdp:     ${TDP_LEVELS_CSV:-default}"

for model in "${MODELS[@]}"; do
  for exp in "${EXPERIMENTS[@]}"; do
    if [[ -n "$TDP_LEVELS_CSV" ]]; then
      bash "$REPEATED_SCRIPT" "$model" "$exp" "$REPEATS" "$TDP_LEVELS_CSV"
    else
      bash "$REPEATED_SCRIPT" "$model" "$exp" "$REPEATS"
    fi
  done
done
