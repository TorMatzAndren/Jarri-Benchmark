Title: run_ollama_prompt.py
ID: script-run-ollama-prompt
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:llm-execution
@scope:ollama-integration
@scope:runtime-metrics
@scope:probe-capture
@entity:./scripts/benchmark/run_ollama_prompt.py
@script:./scripts/benchmark/run_ollama_prompt.py
@semantic:single-prompt-execution-adapter
@capability:execute-one-ollama-prompt-and-return-structured-json-with-metrics-and-probes
@state:documented
@truth:script-behavior
@risk:depends-on-ollama-api-and-cli-output-format
@risk:depends-on-local-ollama-availability
@risk:downstream-scripts-depend-on-its-json-shape

[summary]
run_ollama_prompt.py is the canonical single-prompt execution adapter for the Jarri benchmark system. It sends a non-streaming request to the Ollama API, captures response data and runtime metrics, probes GPU and CPU residency via ollama ps before and after execution, and emits a structured JSON document describing the run. It is used as the lowest-level execution bridge by benchmark_run.py and related active benchmark scripts.

[purpose]
This script exists to provide a deterministic, structured boundary between higher-level benchmark orchestration and the Ollama runtime. It standardizes prompt execution, output extraction, and runtime metric capture into one JSON-only execution surface.

[canonical_role]
active
authoritative
runtime-helper
execution-bridge

[authority_boundary]
This script is allowed to:
- send HTTP POST requests to the Ollama /api/generate endpoint
- read prompt text from CLI or file
- capture ollama ps output before and after execution
- extract final_answer and thinking_trace from the response
- compute runtime and token metrics
- optionally write debug artifacts to ./llm_debug_runs
- emit structured JSON to stdout

This script is not allowed to:
- iterate over multiple tasks or experiments
- evaluate outputs
- aggregate results across runs
- write canonical benchmark ledger entries directly

[inputs]
CLI options:
- --model
- --prompt
- --prompt-file
- --think
- --keep-alive
- --write-debug-artifact

Input constraints:
- exactly one of --prompt or --prompt-file must be provided
- prompt-file must exist if specified
- --model is required

Environment assumptions:
- Ollama server is reachable at http://127.0.0.1:11434
- ollama CLI is available for ps probe capture
- . exists or can be created

Files read:
- prompt file when --prompt-file is used

Files written:
- optional debug JSON under ./llm_debug_runs

[outputs]
Primary output:
- JSON printed to stdout

Top-level output fields:
- success
- model
- started_utc
- completed_utc
- duration_seconds
- final_answer
- thinking_trace
- metrics
- probes
- debug_artifact_path
- error

Metrics fields include:
- prompt_tokens
- response_tokens
- tokens_per_second
- cold_start
- timing-related fields returned from Ollama

Probe fields include:
- ollama_ps_before
- ollama_ps_after

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - debug artifacts are timestamped and do not overwrite each other
- statefulness:
  - optional debug artifact creation only

[execution_flow]
1. Parse CLI arguments.
2. Validate prompt input mode.
3. Load prompt text from inline input or file.
4. Capture ollama ps snapshot before execution.
5. Send POST request to the Ollama API.
6. Capture response or failure state.
7. Capture ollama ps snapshot after execution.
8. Extract final_answer and thinking_trace.
9. Compute runtime, token, and cold-start metrics.
10. Optionally write a debug artifact.
11. Emit structured JSON to stdout.
12. Exit with status 0 on success and 1 on failure.

[metrics_model]
Derived from Ollama response fields:
- eval_count -> response_tokens
- prompt_eval_count -> prompt_tokens
- eval_duration -> tokens_per_second
- load_duration -> cold_start heuristic

Cold start rule:
- load_seconds > 1.0 implies cold_start = true

[probe_model]
Uses:
- ollama ps

Extracts processor split patterns such as:
- X% GPU
- X% CPU
- X%/Y% CPU/GPU

Stored in:
- probes.ollama_ps_before
- probes.ollama_ps_after

[dependencies]
Python standard library:
- argparse
- json
- re
- urllib.request
- datetime
- pathlib
- typing

External dependencies:
- Ollama HTTP API
- ollama CLI

[callers]
Confirmed active caller:
- ./benchmark/cli/benchmark_run.py

Possible direct operator usage:
- can be run manually for single-prompt execution and structured inspection

Call relationship role:
- lowest-level benchmark prompt execution adapter

[verification]
Canonical command:
python3 ./scripts/benchmark/run_ollama_prompt.py --model qwen3:8b --prompt "Say hello"

Expected success signals:
- JSON output printed to stdout
- success is true
- final_answer is populated
- metrics are present
- probes are present

Failure checks:
- missing prompt input -> error JSON or non-success result
- both prompt and prompt-file -> error JSON or non-success result
- invalid model or Ollama unavailable -> success false with error information

[failure_modes]
- Ollama API unavailable -> exception captured, success false
- prompt file missing -> early failure
- malformed Ollama response -> partial or missing metrics
- ollama ps format change -> processor split extraction degradation
- downstream schema dependency drift -> higher-level scripts may break if JSON shape changes

[notes]
This script is the lowest-level runtime execution unit in the active benchmark system. It should remain stable, predictable, and JSON-only in output behavior because multiple higher-level active scripts depend on its structure.

This script should be documented only against the active repo runtime surface. Historical bootstrap and deprecated wrapper lineage belongs in deprecated documentation rather than in active caller lists.
