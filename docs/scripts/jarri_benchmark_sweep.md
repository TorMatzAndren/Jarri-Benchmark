Title: jarri_benchmark_sweep.sh
ID: script-jarri-benchmark-sweep
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-23
Revision: 3

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:benchmark-execution
@scope:sweep-orchestration
@scope:multi-model-execution
@scope:multi-experiment-execution
@scope:repeat-run-orchestration
@scope:tdp-token-pass-through
@entity:./scripts/benchmark/jarri_benchmark_sweep.sh
@script:./scripts/benchmark/jarri_benchmark_sweep.sh
@semantic:top-level-benchmark-sweep-entrypoint
@capability:run-repeated-benchmark-sweeps-across-selected-models-and-experiments-by-delegating-to-run_llm_task_sweep_repeated.sh
@state:documented
@truth:script-behavior
@risk:depends-on-run_llm_task_sweep_repeated.sh-and-valid-model-experiment-arguments
@risk:default-experiment-set-is-hardcoded-and-must-be-updated-intentionally
@risk:re-running-the-same-sweep-can-append-duplicate-semantic-runs-through-downstream-ledger-writes
@risk:tdp-token-interpretation-happens-downstream
@input:repeat-count
@input:model-list
@input:optional-experiment-list
@input:optional-tdp-token-list
@output:delegated-benchmark-artifacts-under-home-jarri-benchmarks

[summary]
jarri_benchmark_sweep.sh is the current top-level human entrypoint for repeated benchmark execution across multiple models and multiple benchmark experiment families. It parses a repeat count, a comma-separated model list, an optional comma-separated experiment list, and an optional comma-separated TDP token list. It then delegates each model / experiment combination into run_llm_task_sweep_repeated.sh.

It is a sweep orchestrator only. It does not execute benchmark logic itself, does not evaluate answers, does not resolve GPU power limits, and does not rebuild post-run analysis.

[purpose]
This script exists to give the operator one stable outer CLI for broad benchmark sweeps. It centralizes the default experiment set and the loop structure for model-by-model and experiment-by-experiment repeated execution, so the sweep shape does not have to be rebuilt manually at the shell each time.

[canonical_role]
active
authoritative-wrapper
top-level-sweep-entrypoint
operator-facing-execution-layer

[authority_boundary]
This script is allowed to:
- parse --repeats
- parse --models
- parse optional --experiments
- parse optional --tdp-levels
- define the default experiment set when --experiments is omitted
- validate that the repeated-sweep delegate exists and is executable
- iterate across all requested model / experiment combinations
- delegate each combination into run_llm_task_sweep_repeated.sh
- pass a TDP token list downward when supplied

This script is not allowed to:
- run Ollama prompts directly
- validate GPU residency directly
- evaluate benchmark answers
- write benchmark ledgers directly
- normalize ledgers
- resolve percent-to-watt GPU power values
- rebuild failure or joined analysis
- import anything into DuckDB
- export UI or ranking surfaces

[inputs]
Required CLI arguments:
- --repeats <n>
- --models <model1,model2,...>

Optional CLI arguments:
- --experiments <exp1,exp2,...>
- --tdp-levels <token1,token2,...>

Default experiment set when --experiments is omitted:
- coding_measurement_v3
- math_measurement_v1
- knowledge_measurement_v2
- language_measurement_v2
- fact_prose_v2

TDP token behavior:
- if --tdp-levels is omitted, the lower single-sweep wrapper supplies its default token ladder
- if --tdp-levels is supplied, this script passes the token list through unchanged
- final token validation and hardware interpretation happen downstream

Resolved runtime dependency:
- ./scripts/benchmark/run_llm_task_sweep_repeated.sh

Environment assumptions:
- HOME is set
- bash is available
- the repeated-sweep delegate exists and is executable
- comma-separated model, experiment, and TDP-token lists are supplied in shell-safe form

Files read directly:
- ./scripts/benchmark/run_llm_task_sweep_repeated.sh existence and executability only

Files read indirectly:
- whatever run_llm_task_sweep_repeated.sh, run_llm_task_sweep_once.sh, benchmark_run.py, and downstream evaluators read

[outputs]
Direct stdout behavior:
- prints a sweep banner showing:
  - repeat count
  - model list
  - experiment list
  - TDP token list when supplied

Direct stderr behavior:
- prints usage text for unknown arguments or missing required arguments
- prints an explicit error if the repeated-sweep delegate is missing or not executable
- downstream failures surface normally

Direct file outputs:
- none

Indirect outputs:
- all benchmark artifacts produced through the delegated chain

Primary indirect outputs include:
- ./benchmarks/<experiment_id>/results/*.json
- ./benchmarks/<experiment_id>/answers/*.txt
- ./benchmarks/<experiment_id>/reports/*_report.json
- ./benchmarks/<experiment_id>/candidates/*.py for coding tasks
- ./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl

[idempotency]
- safe_to_rerun: conditionally
- overwrite_behavior:
  - this wrapper itself writes no persistent benchmark artifacts
  - downstream execution may overwrite per-run artifacts for the same run stem
  - downstream execution appends ledger rows
- statefulness:
  - indirect only through delegated benchmark execution

Important consequence:
Re-running the same sweep with the same models, experiments, repeat count, and TDP tokens can create duplicate semantic benchmark rows in downstream llm_benchmark_runs.jsonl ledgers unless those ledgers are cleaned or filtered later.

[execution_flow]
1. Enable strict shell mode with set -euo pipefail.
2. Resolve PROJECT_ROOT relative to the script location.
3. Resolve REPEATED_SCRIPT as ${PROJECT_ROOT}/run_llm_task_sweep_repeated.sh.
4. Define the default experiment set:
   - coding_measurement_v3
   - math_measurement_v1
   - knowledge_measurement_v2
   - language_measurement_v2
   - fact_prose_v2
5. Parse CLI arguments:
   - --repeats
   - --models
   - --experiments
   - --tdp-levels
6. Reject unknown arguments.
7. Require both --repeats and --models to be provided.
8. Abort if REPEATED_SCRIPT is missing or not executable.
9. Split the comma-separated model list into a shell array.
10. Split the comma-separated experiment list into a shell array if provided.
11. Otherwise use the hardcoded default experiment array.
12. Print the sweep banner.
13. For each model:
    13.1 for each experiment:
         13.1.1 call run_llm_task_sweep_repeated.sh with:
                - model
                - experiment
                - repeats
                - optional TDP token CSV if supplied
14. Exit successfully only if every delegated call succeeds.

[dependencies]
Shell/runtime:
- bash
- strict shell mode support

Direct runtime dependency:
- ./scripts/benchmark/run_llm_task_sweep_repeated.sh

Behavioral dependency:
- run_llm_task_sweep_repeated.sh must accept positional arguments in this order:
  - model
  - experiment_id
  - repeats
  - optional TDP token CSV

[callers]
Observed role:
- intended direct operator entrypoint from the shell
- invoked by run_me.sh when sweep mode is enabled

Downstream relationship:
- directly delegates into ./scripts/benchmark/run_llm_task_sweep_repeated.sh

Call relationship role:
- top wrapper above run_llm_task_sweep_repeated.sh
- outer human-facing CLI layer above the benchmark execution chain

[tdp_token_contract]
This script does not own the final GPU power contract.

Current pass-through contract:
- bare numeric tokens are intended downstream as percent tokens
  - examples:
    - 41
    - 80
    - 100
    - 112
- tokens ending in w or W are intended downstream as explicit watt tokens
  - examples:
    - 144w
    - 168w
    - 270W

Important current truth:
- this script does not convert TDP tokens into watts
- this script does not validate driver power limits
- this script does not inspect GPU hardware
- final token interpretation is delegated downward into benchmark_run.py and set_gpu_power_limit_linux.sh

[verification]
Canonical command:
bash ./scripts/benchmark/jarri_benchmark_sweep.sh --repeats 2 --models qwen3:8b,mistral:7b

Example with explicit experiment list:
bash ./scripts/benchmark/jarri_benchmark_sweep.sh --repeats 1 --models qwen3:8b --experiments coding_measurement_v3,math_measurement_v1

Example with explicit TDP token list:
bash ./scripts/benchmark/jarri_benchmark_sweep.sh --repeats 1 --models qwen3:8b --tdp-levels 80,100,112

Example with explicit watt tokens:
bash ./scripts/benchmark/jarri_benchmark_sweep.sh --repeats 1 --models qwen3:8b --tdp-levels 144w,168w

Expected success signals:
- the sweep banner prints the expected repeat count, models, experiments, and TDP tokens when supplied
- every requested model / experiment combination is reached
- run_llm_task_sweep_repeated.sh is invoked for each combination
- downstream benchmark artifacts appear under the corresponding experiment directories

Quick sanity checks:
- verify missing --repeats causes usage failure
- verify missing --models causes usage failure
- verify unknown arguments cause immediate rejection
- verify omitted --experiments uses the hardcoded five-family default
- verify ./scripts/benchmark/run_llm_task_sweep_repeated.sh is executable
- verify this wrapper does not claim to perform benchmark evaluation or analysis rebuilding itself
- verify this wrapper does not claim to resolve GPU power limits itself

[failure_modes]
- missing --repeats
- missing --models
- unknown CLI argument
- malformed comma-separated model list
- malformed comma-separated experiment list
- malformed TDP token list passed downstream
- repeated delegate script missing
- repeated delegate script not executable
- downstream repeated-sweep failure on any invoked combination
- hardcoded default experiment set becoming stale relative to the benchmark tree

[notes]
This script is the current outer execution wrapper, not the benchmark runtime spine itself.

Important current truths frozen here:
- the intended human CLI shape is centered here, not in benchmark_run.py
- benchmark_run.py is a lower execution layer
- run_llm_task_sweep_repeated.sh is the repetition layer
- run_llm_task_sweep_once.sh is the single-sweep wrapper
- TDP-token interpretation is downstream, not owned here
- this file does not perform post-run canonicalization or export rebuilding

This script should remain a narrow orchestration entrypoint rather than accumulate benchmark-engine logic.
