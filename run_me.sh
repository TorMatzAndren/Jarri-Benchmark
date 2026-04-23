#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${PROJECT_ROOT}/venv/bin/python"

SWEEP_SCRIPT="${PROJECT_ROOT}/scripts/benchmark/jarri_benchmark_sweep.sh"
ENFORCE_POLICY="${PROJECT_ROOT}/scripts/benchmark/enforce_benchmark_runtime_policy.py"
REBUILD_CHAIN="${PROJECT_ROOT}/scripts/export/rebuild_failure_join_chain.sh"
SYNC_UI_DATA="${PROJECT_ROOT}/scripts/export/sync_benchmark_ui_data.sh"
IMPORT_DUCKDB="${PROJECT_ROOT}/scripts/benchmark/import_benchmark_json_to_duckdb.py"
GENERATE_UI_PROFILES="${PROJECT_ROOT}/scripts/ui/generate_benchmark_ui_profiles.py"
GENERATE_UI_TASKDETAIL="${PROJECT_ROOT}/scripts/ui/generate_benchmark_ui_taskdetail.py"
EXPORT_DUCKDB_MODEL_RANKINGS="${PROJECT_ROOT}/scripts/export/export_duckdb_model_rankings.py"
EXPORT_DUCKDB_TASK_RANKINGS="${PROJECT_ROOT}/scripts/export/export_duckdb_task_rankings.py"
EXPORT_DUCKDB_MODEL_TASK_TDP="${PROJECT_ROOT}/scripts/export/export_duckdb_model_task_tdp.py"
EXPORT_DUCKDB_PARETO="${PROJECT_ROOT}/scripts/export/export_duckdb_pareto_frontiers.py"
EXPORT_DUCKDB_TASK_REGISTRY="${PROJECT_ROOT}/scripts/export/export_duckdb_task_registry.py"
EXPORT_DUCKDB_FAILURE_SURFACES="${PROJECT_ROOT}/scripts/export/export_duckdb_failure_surfaces.py"

RUN_SWEEP="false"
MODELS_CSV=""
REPEATS=""
EXPERIMENTS_CSV=""
TDP_LEVELS_CSV=""

print_usage() {
  cat <<'USAGE'
Usage:
  bash ./run_me.sh [options]

Modes:
  1. Full sweep + full rebuild:
     bash ./run_me.sh --models qwen3:8b --repeats 10
     bash ./run_me.sh --models qwen3:8b,mistral:7b --repeats 3 --experiments fact_prose_v2,math_measurement_v1
     bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 41,50,60,70
     bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 80,100,112
     bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 144w,168w,192w

  2. Rebuild only from existing benchmark artifacts:
     bash ./run_me.sh

Notes:
  - Rebuild-only mode uses the active Python if one is already available, otherwise python3.
  - Sweep mode requires ./venv/bin/python so execution dependencies stay controlled.
  - If --models and --repeats are supplied, a benchmark sweep is run first.
  - If no sweep args are supplied, only the canonical rebuild/export chain runs.
  - --tdp-levels accepts comma-separated TDP tokens.
  - Bare numeric tokens are treated downstream as percent, e.g. 80, 100, 112.
  - Tokens ending in w/W are treated downstream as explicit watts, e.g. 144w.
USAGE
}

require_file() {
  local path="$1"
  if [ ! -e "$path" ]; then
    echo "ERROR: required path missing: $path" >&2
    exit 1
  fi
}

require_executable() {
  local path="$1"
  if [ ! -x "$path" ]; then
    echo "ERROR: required executable missing or not executable: $path" >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command missing: $cmd" >&2
    exit 1
  fi
}

choose_python() {
  if [ "${RUN_SWEEP}" = "true" ]; then
    require_executable "${VENV_PY}"
    PYTHON_BIN="${VENV_PY}"
    return
  fi

  if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
    return
  fi

  if [ -x "${VENV_PY}" ]; then
    PYTHON_BIN="${VENV_PY}"
    return
  fi

  require_command python3
  PYTHON_BIN="python3"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --models)
      MODELS_CSV="${2:-}"
      RUN_SWEEP="true"
      shift 2
      ;;
    --repeats)
      REPEATS="${2:-}"
      RUN_SWEEP="true"
      shift 2
      ;;
    --experiments)
      EXPERIMENTS_CSV="${2:-}"
      shift 2
      ;;
    --tdp-levels)
      TDP_LEVELS_CSV="${2:-}"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      echo >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

if [ "${RUN_SWEEP}" = "true" ]; then
  if [ -z "${MODELS_CSV}" ] || [ -z "${REPEATS}" ]; then
    echo "ERROR: --models and --repeats are both required when running a sweep." >&2
    exit 1
  fi
fi

choose_python

echo
echo "============================================================"
echo "Jarri benchmark main entrypoint"
echo "============================================================"
if [ "${RUN_SWEEP}" = "true" ]; then
  echo "Mode:        full sweep + canonical rebuild"
  echo "Models:      ${MODELS_CSV}"
  echo "Repeats:     ${REPEATS}"
  if [ -n "${EXPERIMENTS_CSV}" ]; then
    echo "Experiments: ${EXPERIMENTS_CSV}"
  else
    echo "Experiments: default sweep set"
  fi
  if [ -n "${TDP_LEVELS_CSV}" ]; then
    echo "TDP levels:  ${TDP_LEVELS_CSV}"
  else
    echo "TDP levels:  wrapper default"
  fi
else
  echo "Mode:        canonical rebuild only"
fi
echo "Python:      ${PYTHON_BIN}"
echo "Root:        ${PROJECT_ROOT}"
echo "============================================================"

require_file "${ENFORCE_POLICY}"
require_executable "${REBUILD_CHAIN}"
require_executable "${SYNC_UI_DATA}"
require_file "${IMPORT_DUCKDB}"
require_file "${GENERATE_UI_PROFILES}"
require_file "${GENERATE_UI_TASKDETAIL}"
require_file "${EXPORT_DUCKDB_MODEL_RANKINGS}"
require_file "${EXPORT_DUCKDB_TASK_RANKINGS}"
require_file "${EXPORT_DUCKDB_MODEL_TASK_TDP}"
require_file "${EXPORT_DUCKDB_PARETO}"
require_file "${EXPORT_DUCKDB_TASK_REGISTRY}"
require_file "${EXPORT_DUCKDB_FAILURE_SURFACES}"

if [ "${RUN_SWEEP}" = "true" ]; then
  require_executable "${SWEEP_SCRIPT}"

  SWEEP_CMD=(bash "${SWEEP_SCRIPT}" --models "${MODELS_CSV}" --repeats "${REPEATS}")

  if [ -n "${EXPERIMENTS_CSV}" ]; then
    SWEEP_CMD+=(--experiments "${EXPERIMENTS_CSV}")
  fi

  if [ -n "${TDP_LEVELS_CSV}" ]; then
    SWEEP_CMD+=(--tdp-levels "${TDP_LEVELS_CSV}")
  fi

  echo
  echo "[0/11] Running benchmark sweep"
  "${SWEEP_CMD[@]}"
fi

echo
echo "[1/11] Enforcing canonical runtime policy"
"${PYTHON_BIN}" "${ENFORCE_POLICY}"

echo
echo "[2/11] Rebuilding canonical benchmark analysis chain"
bash "${REBUILD_CHAIN}"

echo
echo "[3/11] Syncing benchmark UI data"
bash "${SYNC_UI_DATA}"

echo
echo "[4/11] Importing canonical JSON into DuckDB"
"${PYTHON_BIN}" "${IMPORT_DUCKDB}"

echo
echo "[5/11] Generating benchmark UI model profiles"
"${PYTHON_BIN}" "${GENERATE_UI_PROFILES}"

echo
echo "[6/11] Generating benchmark UI task detail surface"
"${PYTHON_BIN}" "${GENERATE_UI_TASKDETAIL}"

echo
echo "[7/11] Exporting DuckDB model rankings"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_MODEL_RANKINGS}"

echo
echo "[8/11] Exporting DuckDB task and model-task-TDP surfaces"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_TASK_RANKINGS}"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_MODEL_TASK_TDP}"

echo
echo "[9/11] Exporting DuckDB Pareto frontiers"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_PARETO}"

echo
echo "[10/11] Exporting task registry"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_TASK_REGISTRY}"

echo
echo "[11/11] Exporting failure surfaces"
"${PYTHON_BIN}" "${EXPORT_DUCKDB_FAILURE_SURFACES}"

echo
echo "============================================================"
echo "Jarri benchmark main entrypoint completed"
echo "============================================================"
