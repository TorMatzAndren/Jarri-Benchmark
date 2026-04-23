Title: run_llm_task_sweep_repeated.sh
ID: script-run-llm-task-sweep-repeated
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-23
Revision: 4

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:benchmark-execution
@scope:repeat-run-looping
@scope:single-model-single-experiment-repetition
@scope:tdp-token-pass-through
@entity:./scripts/benchmark/run_llm_task_sweep_repeated.sh
@script:./scripts/benchmark/run_llm_task_sweep_repeated.sh
@semantic:repeat-wrapper-for-single-model-single-experiment-benchmark-execution
@capability:repeat-one-model-and-one-experiment-for-n-runs-by-delegating-into-run_llm_task_sweep_once.sh
@state:documented
@truth:script-behavior
@risk:depends-on-run_llm_task_sweep_once.sh-being-present-and-executable
@risk:inherits-runtime-and-benchmark-failures-from-the-single-run-wrapper
@risk:does-not-validate-repeat-count-beyond-shell-argument-count-and-seq-behavior
@risk:tdp-token-interpretation-happens-downstream
@input:model-name
@input:experiment-id
@input:repeat-count
@input:optional-tdp-token-list
@output:delegated-benchmark-artifacts-produced-by-run_llm_task_sweep_once.sh

[summary]
run_llm_task_sweep_repeated.sh is the canonical repeat-loop wrapper for one model and one benchmark experiment. It does not execute benchmark logic itself. Instead it validates that run_llm_task_sweep_once.sh exists and is executable, loops deterministically from run index 1 through the requested repeat count, and delegates each pass into the single-sweep wrapper.

If a TDP token list is supplied by the caller, it passes that list through to the single-sweep wrapper unchanged.

[purpose]
This script exists to provide a stable repetition layer between the top-level sweep entrypoint and the single-sweep benchmark wrapper. It prevents callers from inventing their own run-index loop behavior and keeps repeated benchmark execution for one model / one experiment consistent.

[canonical_role]
active
authoritative-wrapper
repeat-loop
mid-layer-execution-bridge

[authority_boundary]
This script is allowed to:
- require model, experiment id, and repeat count
- accept an optional TDP token CSV
- bind model, experiment id, repeat count, and optional token list
- resolve the canonical single-sweep wrapper path
- verify that the single-sweep wrapper is executable
- loop from run index 1 through the requested repeat count
- delegate each run into run_llm_task_sweep_once.sh
- pass the optional TDP token list downward unchanged

This script is not allowed to:
- choose benchmark tasks itself
- resolve TDP tokens itself
- validate GPU residency itself
- run Ollama prompts itself
- evaluate answers
- write benchmark ledgers directly
- rebuild downstream analysis surfaces

[inputs]
CLI positional arguments:
- model
- experiment_id
- repeats
- optional tdp_token_csv

Resolved runtime dependency:
- ./scripts/benchmark/run_llm_task_sweep_once.sh

Environment assumptions:
- HOME is set
- bash is available
- seq is available
- the delegated single-sweep wrapper exists and is executable

Files read directly:
- ./scripts/benchmark/run_llm_task_sweep_once.sh existence and executability only

Files read indirectly:
- whatever run_llm_task_sweep_once.sh reads
- whatever benchmark_run.py and downstream evaluators read through that delegated path

[outputs]
Direct stdout behavior:
- prints a repetition banner for each run showing:
  - model
  - experiment
  - run index as current/total

Direct stderr behavior:
- usage text on wrong argument count
- explicit error if the delegated single-sweep wrapper is missing or not executable
- delegated failures surface normally

Direct file outputs:
- none

Indirect outputs:
- all benchmark artifacts produced by run_llm_task_sweep_once.sh for each delegated run index

Primary indirect outputs include:
- ./benchmarks/<experiment_id>/results/*.json
- ./benchmarks/<experiment_id>/answers/*.txt
- ./benchmarks/<experiment_id>/reports/*_report.json
- ./benchmarks/<experiment_id>/candidates/*.py for coding tasks
- ./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl

[idempotency]
- safe_to_rerun: no, not as a no-op
- overwrite_behavior:
  - this wrapper itself writes no persistent benchmark artifacts
  - delegated wrappers may overwrite per-run artifacts for the same run stem
  - delegated wrappers append ledger rows
- statefulness:
  - indirect only through delegated benchmark execution

Important consequence:
Re-running this script with the same model, experiment, repeat count, and TDP token list will replay benchmark execution from run index 1 upward and can append duplicate semantic runs into the experiment ledger.

[execution_flow]
1. Enable strict shell mode with set -euo pipefail.
2. Require three or four positional arguments.
3. Bind:
   - MODEL
   - EXPERIMENT_ID
   - REPEATS
   - optional TDP_LEVELS_CSV
4. Resolve PROJECT_ROOT relative to the script location.
5. Resolve ONCE_SCRIPT as ${PROJECT_ROOT}/run_llm_task_sweep_once.sh.
6. Abort if ONCE_SCRIPT is missing or not executable.
7. Loop from run index 1 through REPEATS using seq.
8. For each run index:
   8.1 print the repetition banner
   8.2 delegate to ONCE_SCRIPT with:
       - model
       - experiment id
       - current run index
       - optional TDP token CSV if supplied
9. Exit successfully only if every delegated run succeeds.

[dependencies]
Shell/runtime:
- bash
- seq
- strict shell mode support

Direct runtime dependency:
- ./scripts/benchmark/run_llm_task_sweep_once.sh

Behavioral dependency:
- run_llm_task_sweep_once.sh must accept positional arguments in this order:
  - model
  - experiment_id
  - run_index
  - optional TDP token CSV

[callers]
Confirmed active caller:
- ./scripts/benchmark/jarri_benchmark_sweep.sh

Likely direct operator usage:
- can be called manually for repeated execution of one model and one experiment

Call relationship role:
- wrapper directly above run_llm_task_sweep_once.sh
- wrapper directly below jarri_benchmark_sweep.sh

[tdp_token_contract]
This script does not choose the default TDP token ladder and does not resolve tokens.

Current behavior:
- if a fourth positional argument is provided, it is passed to run_llm_task_sweep_once.sh unchanged
- if no fourth argument is provided, run_llm_task_sweep_once.sh uses its default TDP token ladder

Important current truth:
- this file does not inspect GPU hardware
- this file does not convert percentages to watts
- this file only preserves caller intent across repeated runs

[verification]
Canonical command:
bash ./scripts/benchmark/run_llm_task_sweep_repeated.sh qwen3:8b fact_prose_v2 2

Example with explicit TDP token list:
bash ./scripts/benchmark/run_llm_task_sweep_repeated.sh qwen3:8b fact_prose_v2 2 80,100,112

Example with explicit watt tokens:
bash ./scripts/benchmark/run_llm_task_sweep_repeated.sh qwen3:8b fact_prose_v2 2 144w,168w

Expected success signals:
- two repetition banners are printed
- run_llm_task_sweep_once.sh is invoked twice
- delegated benchmark execution occurs for run indices 1 and 2
- benchmark artifacts appear under the requested experiment directory
- llm_benchmark_runs.jsonl receives rows for both delegated run indices

Quick sanity checks:
- verify wrong argument count prints usage and exits 1
- verify the script aborts if ./scripts/benchmark/run_llm_task_sweep_once.sh is not executable
- verify run index progression starts at 1
- verify run index progression ends at the requested repeat count
- verify a supplied TDP token CSV is passed downward
- verify the wrapper does not invent any separate artifact-writing layer of its own

[failure_modes]
- wrong argument count
- missing delegated single-sweep wrapper
- delegated single-sweep wrapper not executable
- non-numeric repeat count causing seq failure
- repeat count of zero or invalid shell-seq behavior producing no delegated runs
- malformed TDP token list passed downstream
- delegated benchmark execution failure on any run, causing immediate abort due to strict shell mode

[notes]
This script is intentionally small. Its job is only to freeze the repetition behavior for one model and one experiment.

Important current truths frozen here:
- this file does not execute benchmark logic itself
- this file does not validate GPU residency itself
- this file does not choose the default TDP token ladder itself
- this file does not resolve TDP tokens itself
- all real benchmark execution is delegated downward into run_llm_task_sweep_once.sh and then benchmark_run.py

This script should remain a narrow orchestration layer rather than grow into another runtime spine.
