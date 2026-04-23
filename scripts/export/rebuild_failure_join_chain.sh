#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BENCH_ROOT="${PROJECT_ROOT}/benchmarks"
ANALYSIS_ROOT="${BENCH_ROOT}/_analysis"
FAIL_ROOT="${BENCH_ROOT}/_analysis_failures"
JOIN_ROOT="${BENCH_ROOT}/_analysis_joined"

EXPORTER="${PROJECT_ROOT}/benchmark/cli/jarri_benchmark_export.py"
FAILURE_AGGREGATE="${PROJECT_ROOT}/benchmark/cli/jarri_benchmark_failure_aggregate.py"
FAILURE_JOIN="${PROJECT_ROOT}/benchmark/cli/jarri_benchmark_failure_join.py"

DEFAULT_EXPERIMENTS=(
  coding_measurement_v3
  math_measurement_v1
  knowledge_measurement_v2
  language_measurement_v2
  fact_prose_v2
)

ACTIVE_EXPERIMENTS=()

REPORT_LIST_FILE="$(mktemp)"
trap 'rm -f "$REPORT_LIST_FILE"' EXIT

echo
echo "============================================================"
echo "STEP 0: rebuild canonical analysis exports"
echo "============================================================"

mkdir -p "$ANALYSIS_ROOT"
mkdir -p "$FAIL_ROOT"
mkdir -p "$JOIN_ROOT"

for exp in "${DEFAULT_EXPERIMENTS[@]}"; do
  exp_root="$BENCH_ROOT/$exp"

  if find "$exp_root" -maxdepth 1 -type f -name 'llm_benchmark_runs.jsonl' | grep -q .; then
    echo
    echo "===== EXPORTING $exp ====="
    python3 "$EXPORTER" \
      "$exp_root" \
      --output-dir "$ANALYSIS_ROOT/$exp"

    ACTIVE_EXPERIMENTS+=("$exp")
  else
    echo
    echo "===== SKIPPING $exp: no llm_benchmark_runs.jsonl ====="
  fi
done

if [ "${#ACTIVE_EXPERIMENTS[@]}" -eq 0 ]; then
  echo "ERROR: no benchmark ledgers found under ${BENCH_ROOT}" >&2
  echo "Run a sweep first, for example:" >&2
  echo "  bash ./run_me.sh --models llama3.1:8b --repeats 1 --experiments fact_prose_v2 --tdp-levels 80" >&2
  exit 1
fi

echo
echo "============================================================"
echo "STEP 1: collect ALL report.json files"
echo "============================================================"

find "$BENCH_ROOT" \
  -path "$BENCH_ROOT/_analysis" -prune -o \
  -path "$BENCH_ROOT/_analysis_failures" -prune -o \
  -path "$BENCH_ROOT/_analysis_joined" -prune -o \
  -path "$BENCH_ROOT/_db" -prune -o \
  -type f -name '*_report.json' -print \
  | sort > "$REPORT_LIST_FILE"

REPORT_COUNT="$(wc -l < "$REPORT_LIST_FILE" | tr -d ' ')"
echo "Found $REPORT_COUNT report files"

if [ "$REPORT_COUNT" -eq 0 ]; then
  echo "ERROR: no evaluator report files found under ${BENCH_ROOT}" >&2
  echo "A failure join cannot be rebuilt from ledgers alone." >&2
  exit 1
fi

echo
echo "============================================================"
echo "STEP 2: rebuild failure aggregate"
echo "============================================================"

python3 "$FAILURE_AGGREGATE" \
  --output-dir "$FAIL_ROOT" \
  $(cat "$REPORT_LIST_FILE")

if [ ! -f "$FAIL_ROOT/failure_records.json" ]; then
  echo "ERROR: failure aggregate did not produce ${FAIL_ROOT}/failure_records.json" >&2
  exit 1
fi

echo
echo "============================================================"
echo "STEP 3: verify canonical normalized analysis files exist"
echo "============================================================"

for exp in "${ACTIVE_EXPERIMENTS[@]}"; do
  path="$ANALYSIS_ROOT/$exp/normalized_runs.json"
  if [ -f "$path" ]; then
    echo "$path"
  else
    echo "Missing normalized runs file: $path" >&2
    exit 1
  fi
done

echo
echo "============================================================"
echo "STEP 4: rebuild joined failure+energy view"
echo "============================================================"

python3 "$FAILURE_JOIN" \
  --analysis-root "$ANALYSIS_ROOT" \
  --failure-records "$FAIL_ROOT/failure_records.json" \
  --output-dir "$JOIN_ROOT"

for required in \
  joined_failure_energy_summary.json \
  joined_failure_energy_by_model.json \
  joined_failure_energy_by_task.json \
  joined_failure_energy_by_tdp.json \
  joined_failure_energy_by_model_task_tdp.json \
  joined_failure_energy_rows.json \
  joined_failure_energy_unmatched.json
do
  if [ ! -f "$JOIN_ROOT/$required" ]; then
    echo "ERROR: join step did not produce ${JOIN_ROOT}/${required}" >&2
    exit 1
  fi
done

UNMATCHED_ROWS="$(jq -r '.row_count // 0' "$JOIN_ROOT/joined_failure_energy_unmatched.json")"

if [ "$UNMATCHED_ROWS" != "0" ]; then
  echo "ERROR: joined failure+energy view has unmatched rows: ${UNMATCHED_ROWS}" >&2
  echo "This usually means ledger rows exist without matching evaluator reports." >&2
  exit 1
fi

echo
echo "============================================================"
echo "STEP 5: sanity check"
echo "============================================================"

echo
echo "----- active experiments -----"
printf '%s\n' "${ACTIVE_EXPERIMENTS[@]}"

echo
echo "----- unmatched rows -----"
jq '.row_count' "$JOIN_ROOT/joined_failure_energy_unmatched.json"

echo
echo "----- summary snapshot -----"
jq '.summary | {
  rows,
  models,
  failure_stage_distribution,
  failure_type_distribution,
  usable_output_rate,
  pipeline_usable_rate,
  fully_correct_rate,
  hard_failure_rate,
  avg_score_percent,
  avg_energy_j
}' "$JOIN_ROOT/joined_failure_energy_summary.json"

echo
echo "Done."
