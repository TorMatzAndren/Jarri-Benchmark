Title: run_llm_task_sweep_once.sh
ID: script-run-llm-task-sweep-once
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
@scope:single-sweep-orchestration
@scope:gpu-residency-validation
@scope:tdp-token-dispatch
@entity:./scripts/benchmark/run_llm_task_sweep_once.sh
@script:./scripts/benchmark/run_llm_task_sweep_once.sh
@semantic:single-run-benchmark-wrapper
@capability:validate-runtime-residency-and-dispatch-one-model-experiment-run-across-a-default-tdp-token-ladder-or-supplied-token-list
@state:documented
@truth:script-behavior
@risk:depends-on-validate_ollama_gpu_residency.py
@risk:depends-on-benchmark_run.py
@risk:default-tdp-token-ladder-is-policy-not-hardware-truth
@risk:assumes-python3-is-runnable-in-the-current-shell-environment
@input:model-name
@input:experiment-id
@input:run-index
@input:optional-tdp-token-list
@output:delegated-benchmark-artifacts-produced-by-benchmark_run.py

[summary]
run_llm_task_sweep_once.sh is the canonical single-sweep wrapper in the active Jarri benchmark execution chain. It does not perform evaluation or ledger construction itself. Instead it validates that the requested Ollama model is fully GPU resident, chooses either a caller-supplied TDP token list or the current default TDP token ladder, fixes the current measurement parameters, and delegates one model / one experiment / one run-index sweep into benchmark_run.py.

[purpose]
This script exists to freeze one stable benchmark invocation shape between the higher-level repeat/sweep wrappers and the real execution spine in benchmark_run.py. It prevents each caller from inventing its own runtime validation behavior, TDP-token dispatch shape, or measurement settings.

[canonical_role]
active
authoritative-wrapper
single-sweep-entrypoint
execution-chain-bridge

[authority_boundary]
This script is allowed to:
- require model, experiment id, and run index
- accept an optional TDP token CSV
- bind model, experiment id, run index, and selected TDP token list
- define the active default TDP token ladder when no override is supplied
- define the active benchmark-side power sampling settings
- validate full GPU residency before execution
- delegate benchmark execution into benchmark_run.py

This script is not allowed to:
- talk to Ollama directly for benchmark prompts
- evaluate answers
- build ledger rows itself
- aggregate results
- rebuild downstream analysis surfaces
- define benchmark manifests
- resolve percent-to-watt values itself
- inspect GPU driver power limits itself

[inputs]
CLI positional arguments:
- model
- experiment_id
- run_index
- optional tdp_token_csv

Resolved script dependencies:
- ./scripts/benchmark/validate_ollama_gpu_residency.py
- ./benchmark/cli/benchmark_run.py

Default TDP token ladder when no override is supplied:
- 41
- 50
- 60
- 70
- 80
- 90
- 100
- 112

Current TDP token contract:
- bare numeric token -> percent token downstream
- token ending in w or W -> explicit watt token downstream

Hardcoded measurement settings:
- power sample interval = 0.2
- idle baseline duration = 3.0

Environment assumptions:
- HOME is set
- python3 is available
- the validator script is runnable
- benchmark_run.py is runnable
- the requested model is present in Ollama
- Ollama processor split validation is meaningful for the active runtime

Files read indirectly:
- whatever files are read by validate_ollama_gpu_residency.py
- whatever files are read by benchmark_run.py

[outputs]
Direct stdout behavior:
- prints a run banner with:
  - model
  - experiment
  - run index
  - selected TDP token list

Direct stderr behavior:
- usage text on wrong argument count
- delegated Python failures surface normally

Direct file outputs:
- none

Indirect outputs:
- runtime residency verification artifact written by validate_ollama_gpu_residency.py
- benchmark artifacts and ledger rows written by benchmark_run.py

Primary indirect benchmark outputs include:
- ./benchmarks/<experiment_id>/results/*.json
- ./benchmarks/<experiment_id>/answers/*.txt
- ./benchmarks/<experiment_id>/reports/*_report.json
- ./benchmarks/<experiment_id>/candidates/*.py for coding tasks
- ./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl

[idempotency]
- safe_to_rerun: conditionally
- overwrite_behavior:
  - this wrapper itself writes no canonical output file
  - delegated benchmark_run.py may overwrite per-run artifacts for the same run stem
  - delegated benchmark_run.py appends ledger rows
- statefulness:
  - indirect only through delegated validator and benchmark runner

Important consequence:
Re-running the same model / experiment / run-index through this wrapper is not a no-op. It replays the delegated execution path and can append duplicate semantic runs into the experiment ledger.

[execution_flow]
1. Enable strict shell mode with set -euo pipefail.
2. Require three or four positional arguments.
3. Bind:
   - MODEL
   - EXPERIMENT_ID
   - RUN_INDEX
   - optional PASSTHROUGH_TDP_CSV
4. Resolve PROJECT_ROOT relative to the script location.
5. Resolve RUNNER as ${PROJECT_ROOT}/benchmark/cli/benchmark_run.py.
6. Resolve VALIDATOR as ${PROJECT_ROOT}/validate_ollama_gpu_residency.py.
7. Define the default TDP token ladder as:
   - 41 50 60 70 80 90 100 112
8. If a passthrough TDP CSV is supplied, use it.
9. Otherwise convert the default token ladder into a comma-separated value string.
10. Define:
   - POWER_SAMPLE_INTERVAL=0.2
   - IDLE_BASELINE_DURATION=3.0
11. Print the single-sweep banner.
12. Run the GPU residency validator:
    python3 "${VALIDATOR}" "${MODEL}" --warm --checks 3 --sleep-seconds 1.0 --require "100% GPU"
13. If validation fails, abort immediately because strict mode is enabled.
14. If validation succeeds, delegate to benchmark_run.py with:
    - model
    - experiment id
    - --run-index
    - --tdp-levels
    - --power-sample-interval
    - --idle-baseline-duration
15. Allow benchmark_run.py to execute the full task manifest for that experiment across the selected TDP token list.

[dependencies]
Shell/runtime:
- bash
- strict shell mode support

Direct Python entrypoints:
- ./scripts/benchmark/validate_ollama_gpu_residency.py
- ./benchmark/cli/benchmark_run.py

External runtime dependency:
- python3

Behavioral dependency:
- validate_ollama_gpu_residency.py must reject non-full-GPU residency correctly
- benchmark_run.py must accept the delegated argument shape used here
- benchmark_run.py must validate and dispatch the TDP token list
- set_gpu_power_limit_linux.sh must perform final hardware power-limit resolution downstream

[callers]
Confirmed active caller:
- ./scripts/benchmark/run_llm_task_sweep_repeated.sh

Likely direct operator usage:
- can be called manually for one model / one experiment / one run-index sweep

Call relationship role:
- wrapper directly above benchmark_run.py
- wrapper directly below run_llm_task_sweep_repeated.sh

[tdp_token_contract]
This script owns the default token ladder, not final GPU power truth.

Current default token ladder:
- 41,50,60,70,80,90,100,112

Important interpretation:
- these are request tokens
- bare numeric tokens are resolved downstream as percent tokens
- explicit watt tokens can be supplied by callers with w/W suffix
- final percent-to-watt resolution happens inside the Linux GPU power helper

This means:
- the default ladder is a benchmark policy surface
- it is not a universal watt map
- the same percent token may resolve differently on different GPUs

[verification]
Canonical command:
bash ./scripts/benchmark/run_llm_task_sweep_once.sh qwen3:8b fact_prose_v2 1

Example with explicit TDP token override:
bash ./scripts/benchmark/run_llm_task_sweep_once.sh qwen3:8b fact_prose_v2 1 80,100,112

Example with explicit watt tokens:
bash ./scripts/benchmark/run_llm_task_sweep_once.sh qwen3:8b fact_prose_v2 1 144w,168w

Expected success signals:
- the wrapper prints the single-sweep banner
- GPU residency validation runs before benchmark execution
- benchmark_run.py starts and prints its own execution banners
- experiment artifacts appear under the requested benchmark directory
- llm_benchmark_runs.jsonl receives new rows for the requested run index

Quick sanity checks:
- verify wrong argument count prints usage and exits 1
- verify a non-GPU-resident model is rejected before benchmark execution
- verify the delegated benchmark_run.py command receives:
  - the requested model
  - the requested experiment id
  - the supplied run index
  - the selected TDP token list
  - the fixed power sampling settings
- verify the wrapper does not invent its own artifact-writing layer
- verify the wrapper does not claim to resolve GPU watts itself

[failure_modes]
- wrong argument count
- missing or broken python3
- missing or broken validate_ollama_gpu_residency.py
- missing or broken benchmark_run.py
- malformed TDP token list passed downstream
- requested model fails GPU residency validation
- benchmark_run.py exits nonzero during delegated execution
- active runtime changes and "100% GPU" is no longer the correct residency signature

[notes]
This script is important because it freezes the currently canonical single-sweep shape without duplicating the logic of benchmark_run.py.

Important current truths frozen here:
- full GPU residency is required before benchmark execution begins
- the active default TDP token ladder is:
  - 41,50,60,70,80,90,100,112
- the active fixed measurement settings are:
  - power sample interval 0.2
  - idle baseline duration 3.0
- this file is not the benchmark engine; benchmark_run.py is
- TDP tokens are passed downward and resolved later by the runtime chain

This script should stay small. Its purpose is not to grow into a second runtime spine, but to standardize one delegated sweep shape cleanly and explicitly.
