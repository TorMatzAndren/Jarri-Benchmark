Title: benchmark_run.py
ID: script-benchmark-run
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
@scope:manifest-driven-runs
@scope:gpu-power-control
@scope:gpu-telemetry
@scope:energy-measurement
@scope:runtime-classification
@scope:evaluator-dispatch
@scope:canonical-ledger-production
@entity:./benchmark/cli/benchmark_run.py
@script:./benchmark/cli/benchmark_run.py
@semantic:canonical-benchmark-execution-spine
@capability:run-one-model-against-one-benchmark-experiment-across-one-or-more-tdp-levels-and-append-canonical-jsonl-ledger-rows
@state:documented
@truth:script-behavior
@risk:depends-on-manifest-shape-and-evaluator-contracts
@risk:depends-on-ollama-runtime-and-local-helper-scripts
@risk:depends-on-nvidia-smi-telemetry-quality
@risk:energy-validity-depends-on-full-gpu-detection-and-sampling-quality
@output:./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl

[summary]
benchmark_run.py is the canonical execution spine of the active Jarri benchmark runtime. It runs one selected model against one selected benchmark experiment, iterates through one or more requested TDP levels, executes every task declared in that experiment manifest, writes per-task result artifacts, evaluates outputs through the appropriate deterministic evaluator, computes GPU and energy measurements, classifies runtime residency, and appends canonical ledger rows into `./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl`.

This file is not the top-level human multi-model sweep interface. It is the execution engine that sits beneath the shell sweep wrappers.

[purpose]
This script exists to turn one benchmark experiment manifest plus one model plus one requested run index into a reproducible-enough canonical runtime pass with:
- prompt execution
- artifact generation
- evaluator routing
- GPU telemetry capture
- energy measurement
- runtime classification
- ledger-row production

It is the bridge between task manifests and the canonical benchmark ledgers that downstream export, failure, join, DuckDB, and UI stages consume.

[canonical_role]
authoritative
active
runtime-critical
primary-execution-spine

[system_position]
Human-facing orchestration currently lives above this file:
- `./scripts/benchmark/jarri_benchmark_sweep.sh`
- `./scripts/benchmark/run_llm_task_sweep_repeated.sh`
- `./scripts/benchmark/run_llm_task_sweep_once.sh`

This file sits below those wrappers and is responsible for the actual per-experiment benchmark execution.

It should be understood as:
- the real runtime engine
- the canonical producer of ledger truth
- the layer where task execution, evaluator dispatch, telemetry, and energy accounting actually happen

It should not be described as:
- the top-level multi-model human CLI
- the full post-processing pipeline
- the UI/export/analysis chain

[authority_boundary]
This script is allowed to:
- load benchmark manifests under `./benchmarks/<experiment_id>`
- validate requested TDP tokens against the supported token contract
- request GPU power-limit changes through `./set_gpu_power_limit_linux.sh`
- sample GPU state through `nvidia-smi`
- run prompts through `./scripts/benchmark/run_ollama_prompt.py`
- write result, answer, report, and candidate artifacts into experiment directories
- dispatch outputs into the correct evaluator based on task family and task name
- classify runtime mode from Ollama processor split and GPU telemetry
- classify energy confidence and energy validity
- append canonical ledger rows into `llm_benchmark_runs.jsonl`

This script is not allowed to:
- discover or rank models globally
- aggregate results across multiple experiments into joined analysis views
- build failure taxonomy across all reports
- import results into DuckDB
- produce benchmark UI exports
- replace the downstream export, failure, join, or DuckDB chain

[inputs]
CLI positional arguments:
- `model`
- `experiment_id`

CLI required options:
- `--run-index`

CLI optional options:
- `--tdp-levels`
- `--keep-alive`
- `--think`
- `--write-debug-artifact`
- `--power-sample-interval`
- `--idle-baseline-duration`

Resolved runtime inputs:
- `./benchmarks/<experiment_id>/manifest.json`
- prompt files referenced by the manifest
- ground-truth files for fact/prose tasks
- runner JSON produced by `run_ollama_prompt.py`
- evaluator report JSON produced by the selected evaluator
- GPU telemetry from `nvidia-smi`
- power-limit confirmation messages from `set_gpu_power_limit_linux.sh`

Environment assumptions:
- `.` exists
- the selected experiment directory exists under `./benchmarks`
- `manifest.json` exists and contains a non-empty `tasks` list
- `./scripts/benchmark/run_ollama_prompt.py` exists and runs
- `./set_gpu_power_limit_linux.sh` exists and runs
- `nvidia-smi` is available and returns parseable data
- evaluator scripts exist and are runnable
- the requested model is available to Ollama

[input_contract]
`experiment_id` must refer to a benchmark directory under:
- `./benchmarks/<experiment_id>`

The manifest must contain:
- `experiment_id`
- `tasks`

Each task is expected to contain:
- `task_id`
- `task_family`
- `task_name`
- `prompt_file`

Fact and prose tasks must also provide:
- `ground_truth_file`

`--tdp-levels` contract:
- comma-separated tokens
- bare numeric token -> percent
  - examples:
    - `41`
    - `80`
    - `100`
    - `112`
- token ending in `w` or `W` -> explicit watts
  - examples:
    - `144w`
    - `270W`

Interpretation rule:
- benchmark_run.py should treat these as runtime control tokens
- final percent-to-watt resolution is delegated to `set_gpu_power_limit_linux.sh`
- the helper resolves tokens against the active card and driver power surface

[files_read]
Always read:
- `./benchmarks/<experiment_id>/manifest.json`

Conditionally read:
- prompt file for each task
- ground-truth file for each fact/prose task
- runner JSON written by `run_ollama_prompt.py`
- evaluator report JSON written by the chosen evaluator

[files_written]
Per experiment:
- `results/<run_stem>.json`
- `answers/<run_stem>.txt`
- `reports/<run_stem>_report.json`
- `candidates/<run_stem>.py` for coding tasks
- `llm_benchmark_runs.jsonl`

Primary canonical output:
- `./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl`

[external_runtime_dependencies]
Shell/helper scripts:
- `./set_gpu_power_limit_linux.sh`
- `./scripts/benchmark/run_ollama_prompt.py`
- `./scripts/benchmark/evaluate_benchmark_python.py`
- `./scripts/benchmark/evaluate_benchmark_task.py`
- `./benchmark/evaluators/evaluate_coding_fs_strict_v2.py`
- `./benchmark/evaluators/evaluate_math_dependency_v2.py`
- `./benchmark/evaluators/evaluate_logic_consistency_v2.py`
- `./benchmark/evaluators/evaluate_constrained_rewrite_v2.py`

External tools:
- `nvidia-smi`

[outputs]
Primary canonical output:
- `./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl`

Per-task artifacts:
- `results/<run_stem>.json`
- `answers/<run_stem>.txt`
- `reports/<run_stem>_report.json`
- `candidates/<run_stem>.py` for coding tasks only

stdout behavior:
- prints model / TDP / run banners
- prints per-task execution banners
- prints saved artifact paths
- prints final completion message

Operational note:
The power-limit helper itself also prints confirmation messages and driver-power context. As a result, visible power-limit lines may appear both from the helper and from this script's own surrounding runtime output.

stderr behavior:
- uncaught subprocess and validation failures surface normally

[ledger_shape]
Ledger rows are appended as JSON objects to:
- `./benchmarks/<experiment_id>/llm_benchmark_runs.jsonl`

There are currently two ledger-builder paths:
- coding tasks use `build_coding_ledger_entry()`
- fact, prose, math, knowledge, and language tasks use `build_fact_prose_ledger_entry()`

This naming asymmetry is real current behavior and should be preserved in documentation until deliberately cleaned up.

Important ledger fields include:
- `experiment_id`
- `timestamp_utc`
- `model`
- `task_id`
- `task_family`
- `prompt_hash`
- `prompt_file`
- `power_limit_percent`
- `run_index`
- `duration_seconds`
- `prompt_tokens`
- `response_tokens`
- `tokens_per_second`
- `gpu_name`
- `gpu_uuid`
- `gpu_driver_version`
- `gpu_memory_total_mb`
- `gpu_index`
- `gpu_avg_power_w`
- `gpu_peak_power_w`
- `gpu_avg_util_percent`
- `gpu_peak_util_percent`
- `gpu_power_sample_count`
- `idle_gpu_watts_discounted`
- `baseline_clamp_events`
- `llm_energy_joules`
- `llm_energy_wh`
- `llm_energy_kwh`
- `llm_joules_per_output_token`
- `llm_wh_per_1000_output_tokens`
- `output_tokens_per_joule`
- `evaluation_type`
- `evaluation_score_percent`
- `evaluation_passed_checks`
- `evaluation_total_checks`
- `evaluation_report_path`
- `runner_json_path`
- `execution_status`
- `artifact_usability`
- `gpu_residency_mode`
- `ollama_processor_split`
- `hybrid_warning`
- `fair_comparison_eligible`
- `energy_confidence_class`
- `energy_comparison_eligible`
- `energy_valid`
- `energy_validity`
- `energy_measurement_version`
- `energy_confidence_reason`
- `success`
- `error`
- `final_answer_chars`
- `thinking_trace_chars`
- `scientific_score_percent`
- `score_per_second_strict`
- `score_per_wh_strict`
- `usable`
- `hard_failure`

[idempotency]
- safe_to_rerun: conditionally
- overwrite_behavior:
  - result, answer, report, and candidate files for the same run stem are overwritten
  - ledger rows are appended, not replaced
- statefulness:
  - mutates experiment artifact directories
  - appends persistent run history into `llm_benchmark_runs.jsonl`
  - changes GPU power limit during execution

Important consequence:
Re-running the same model / experiment / run-index combination can overwrite per-task artifacts while also appending additional semantic runs to the ledger. That means artifact files and ledger history do not behave the same way.

[execution_flow]
1. Parse CLI arguments.
2. Resolve and load `./benchmarks/<experiment_id>/manifest.json`.
3. Parse and validate requested TDP tokens.
4. Validate that the manifest contains tasks.
5. For each requested TDP token:
   5.1 request the corresponding GPU power limit through `set_gpu_power_limit_linux.sh`
   5.2 sleep briefly after the requested power-limit change
   5.3 detect current GPU identity and memory surface through `nvidia-smi`
   5.4 sample an idle baseline power window
   5.5 start `ContinuousGpuSampler`
6. For each task in the manifest:
   6.1 normalize `task_family`
   6.2 resolve prompt path
   6.3 create needed artifact directories
   6.4 derive the run stem and all artifact paths
   6.5 capture task start time in the sampler
   6.6 run `run_ollama_prompt.py`
   6.7 capture task end time in the sampler
   6.8 write `final_answer` into the answer text artifact
   6.9 summarize energy across the task execution window
   6.10 extract Ollama processor split from runner probe output
   6.11 classify runtime mode
   6.12 dispatch to the correct evaluator
   6.13 build the canonical ledger row
   6.14 append the ledger row to `llm_benchmark_runs.jsonl`
7. Stop the continuous sampler after the TDP pass finishes.
8. Continue to the next requested TDP token.
9. Print final completion message and return success.

[task-family_normalization]
Normalized family mapping:
- `factual` -> `fact`
- `fact` -> `fact`
- `prose` -> `prose`
- `coding` -> `coding`
- `code` -> `coding`
- `math` -> `math`
- `knowledge` -> `knowledge`
- `logic` -> `knowledge`
- `language` -> `language`

Unsupported task families raise a Python error and abort the run.

[evaluator_routing]
Coding task-name routing:
- `coding_fs_strict_v3` -> `./benchmark/evaluators/evaluate_coding_fs_strict_v2.py`
- `folder_scan` -> `./scripts/benchmark/evaluate_benchmark_python.py --task folder_scan`
- `csv_summary` -> `./scripts/benchmark/evaluate_benchmark_python.py --task csv_summary`
- `log_parser` -> `./scripts/benchmark/evaluate_benchmark_python.py --task log_parser`

Non-coding task-family routing:
- `fact` -> `./scripts/benchmark/evaluate_benchmark_task.py`
- `prose` -> `./scripts/benchmark/evaluate_benchmark_task.py`
- `math` -> `./benchmark/evaluators/evaluate_math_dependency_v2.py`
- `knowledge` -> `./benchmark/evaluators/evaluate_logic_consistency_v2.py`
- `language` -> `./benchmark/evaluators/evaluate_constrained_rewrite_v2.py`

Current frozen truth:
- `coding_fs_strict_v3` still routes into an evaluator file named `_v2`
- fact and prose still share `evaluate_benchmark_task.py`
- math, knowledge, and language each route through dedicated evaluator files

[tdp_model]
Current TDP control model:
- bare numeric tokens are percent inputs
- explicit `w` suffixed tokens are watt inputs
- percent tokens are resolved card-locally by `set_gpu_power_limit_linux.sh`
- the final authoritative GPU apply surface remains watt-based `nvidia-smi -pl`

Important current truth:
- TDP tokens are no longer documented as one universal fixed percent-to-watt map across all GPUs

[gpu_and_energy_model]
GPU telemetry source:
- `nvidia-smi`

Queried GPU fields include:
- index
- name
- uuid
- driver_version
- temperature.gpu
- utilization.gpu
- memory.used
- memory.total
- power.draw
- power.limit

Idle baseline model:
- an idle power window is sampled before each TDP pass
- baseline is later subtracted from sampled task power to estimate LLM-only energy

`ContinuousGpuSampler`:
- samples power, utilization, and memory during execution
- stores time-based GPU snapshots
- computes:
  - sample count
  - average power
  - peak power
  - average GPU util
  - peak GPU util
  - LLM-only joules
  - LLM-only Wh
  - baseline clamp events

Clamp rule:
- negative net-power segments after idle subtraction are clamped to zero
- clamp events are counted explicitly

[runtime_classification_model]
Runtime classification prefers the Ollama processor split when available.

Observed runtime outputs are interpreted into:
- `full_gpu`
- `hybrid_cpu_gpu`
- `cpu_only`
- `unknown`

Runtime classification emits:
- `gpu_residency_mode`
- `ollama_processor_split`
- `hybrid_warning`
- `fair_comparison_eligible`

Heuristic fallback:
If processor split is missing or ambiguous, the classifier falls back to:
- average GPU utilization
- average GPU power draw
- observed tokens per second

[energy_confidence_model]
Energy confidence is classified after runtime classification.

Energy validity requires:
- `gpu_residency_mode == full_gpu`
- `fair_comparison_eligible == true`
- non-zero duration
- enough GPU power samples
- meaningful signal above idle

Possible outputs include:
- `energy_confidence_class`
- `energy_comparison_eligible`
- `energy_valid`
- `energy_validity`
- `energy_measurement_version`
- `energy_confidence_reason`

Current energy measurement version:
- `run_sliced_v1`

General rule:
- non-full-GPU or weak-signal runs are not treated as fair canonical energy comparisons

[dependencies]
Python standard library modules:
- `argparse`
- `hashlib`
- `json`
- `subprocess`
- `threading`
- `time`
- `datetime`
- `pathlib`
- `typing`

External tools:
- `nvidia-smi`

Local runtime scripts:
- `./set_gpu_power_limit_linux.sh`
- `./scripts/benchmark/run_ollama_prompt.py`
- `./scripts/benchmark/evaluate_benchmark_python.py`
- `./scripts/benchmark/evaluate_benchmark_task.py`
- `./benchmark/evaluators/evaluate_coding_fs_strict_v2.py`
- `./benchmark/evaluators/evaluate_math_dependency_v2.py`
- `./benchmark/evaluators/evaluate_logic_consistency_v2.py`
- `./benchmark/evaluators/evaluate_constrained_rewrite_v2.py`

Internal helper structures:
- TDP-token parsing and validation logic
- `ContinuousGpuSampler`
- task-family normalization logic
- runtime classifier
- energy confidence classifier
- ledger builder helpers

[callers]
Confirmed active direct caller:
- `./scripts/benchmark/run_llm_task_sweep_once.sh`

Confirmed higher-level wrapper lineage:
- `./scripts/benchmark/run_llm_task_sweep_repeated.sh`
- `./scripts/benchmark/jarri_benchmark_sweep.sh`

Possible direct operator usage:
- operator can invoke `benchmark_run.py` directly for one model, one experiment, one run-index, and one chosen TDP token set

Known downstream consumers:
- `./benchmark/cli/jarri_benchmark_export.py`
- `./benchmark/cli/jarri_benchmark_failure_aggregate.py`
- `./benchmark/cli/jarri_benchmark_failure_join.py`
- `./scripts/benchmark/enforce_benchmark_runtime_policy.py`
- `./scripts/benchmark/import_benchmark_json_to_duckdb.py`
- any workflow reading `llm_benchmark_runs.jsonl`

Call relationship role:
- canonical producer of current benchmark ledger truth
- execution spine beneath the shell sweep wrappers
- not the top-level human multi-model entrypoint

[verification]
Canonical direct commands:
- `python3 ./benchmark/cli/benchmark_run.py qwen3:8b fact_prose_v2 --run-index 1 --tdp-levels 80`
- `python3 ./benchmark/cli/benchmark_run.py qwen3:8b fact_prose_v2 --run-index 1 --tdp-levels 112`
- `python3 ./benchmark/cli/benchmark_run.py qwen3:8b fact_prose_v2 --run-index 1 --tdp-levels 144w`

Expected success signals:
- results, answers, and reports are created under the experiment directory
- coding tasks also create candidate files
- `llm_benchmark_runs.jsonl` receives appended rows
- printed output shows task execution and save paths
- resulting report files are valid JSON
- resulting ledger rows contain runtime and energy fields

Direct validation checks:
- `python3 ./benchmark/cli/benchmark_run.py --help`
- run one experiment with one TDP token
- inspect the last ledger row in `llm_benchmark_runs.jsonl`
- verify saved artifact paths exist
- verify `gpu_residency_mode`, `energy_validity`, and evaluator fields are present in the row

Quick sanity checks:
- verify manifest exists and has tasks
- verify prompt files resolve correctly
- verify fact/prose tasks resolve ground truth
- verify `results/`, `answers/`, and `reports/` are populated
- verify coding tasks also populate `candidates/`
- verify each ledger row includes:
  - `experiment_id`
  - `model`
  - `task_id`
  - `task_family`
  - `evaluation_score_percent`
  - `execution_status`
  - `gpu_residency_mode`
  - `energy_validity`

[failure_modes]
Hard stop failures before or during execution:
- missing manifest -> `FileNotFoundError`
- empty task list -> `ValueError`
- malformed TDP token -> `ValueError`
- missing prompt file -> `FileNotFoundError`
- missing ground-truth file for fact/prose -> `FileNotFoundError`
- unsupported task family -> `ValueError`
- unsupported coding task name -> `ValueError`
- power helper subprocess failure -> abort
- evaluator subprocess failure -> abort
- prompt runner subprocess failure -> abort

Degraded or classification-quality failures:
- `nvidia-smi` unavailable or malformed -> GPU and energy surfaces degrade
- runtime classification can become uncertain if probe quality is weak
- energy comparison can be marked invalid when sample count is too low
- energy comparison can be marked invalid when no meaningful power signal exists above idle
- non-full-GPU execution invalidates canonical energy comparison

Historical/operational caveat:
- reruns append new ledger rows instead of replacing previous semantic runs
- per-task artifacts for the same run stem are overwritten
- ledger history and artifact overwriting must therefore be interpreted separately

[notes]
This file is one of the highest-priority benchmark documents because it describes the script that actually creates the canonical benchmark ledgers.

Important current truths frozen here:
- the active human sweep entrypoint is above this file, not inside it
- this script is the real runtime engine beneath the shell wrappers
- the canonical ledger format is JSONL under `llm_benchmark_runs.jsonl`, not SQLite
- coding currently uses a dedicated coding ledger builder while all non-coding families currently reuse `build_fact_prose_ledger_entry()`
- the power-control path is now mediated through the Linux-native helper
- downstream export, failure, join, DuckDB, and UI layers all depend on the ledger shape produced here

This document should stay tightly literal. If the runtime script changes, this document should be rewritten from observed behavior rather than patched from memory or inferred architecture.
