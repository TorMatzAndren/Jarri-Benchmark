Title: validate_ollama_gpu_residency.py
ID: script_validate_ollama_gpu_residency
Date: 2026-04-21
Author: Matz
Type: scripts
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

---

@role:scripts
@subsystem:benchmarking
@scope:benchmarking
@scope:runtime-validation
@scope:gpu-residency
@scope:ollama
@scope:inventory
@script:./scripts/benchmark/validate_ollama_gpu_residency.py
@status:active

[summary]
validate_ollama_gpu_residency.py verifies that an Ollama model is running with the required processor residency signature before canonical benchmark execution proceeds. It can optionally warm the model first, then repeatedly inspects `ollama ps`, records the observed model line, checks whether the required signature such as `100% GPU` is present, and writes a structured JSON validation record under the benchmark runtime residency inventory directory.

[purpose]
This script exists to block benchmark sweeps from running under invalid runtime conditions, especially hybrid CPU/GPU residency when the canonical sweep requires full GPU residency. It provides a deterministic preflight gate and leaves a machine-readable audit artifact showing exactly what was observed.

[inputs]
- positional argument: model
- optional flag: `--warm`
- optional flag: `--warm-prompt`
- optional flag: `--checks`
- optional flag: `--sleep-seconds`
- optional flag: `--require`

[outputs]
- writes a JSON report to:
  - `./benchmarks/_analysis_inventory/runtime_residency/<model_slug>.json`
- prints the output path to stdout
- returns exit code 0 when all checks satisfy the required processor signature
- returns nonzero when warmup fails or residency checks fail

[behaviour]
1. Resolve the project root as `.`.
2. Resolve the output directory as `./benchmarks/_analysis_inventory/runtime_residency`.
3. Parse runtime arguments.
4. Create the output directory if missing.
5. Optionally warm the model by calling:
   - `ollama run <model> <warm-prompt>`
6. If warmup fails:
   - write a JSON payload with status `warm_failed`
   - print the output path
   - exit with failure
7. Otherwise perform the requested number of checks.
8. For each check:
   - run `ollama ps`
   - find the line whose prefix matches the model name
   - test whether the required signature string is present in that line
   - store timestamp, return code, matched line, and stdout/stderr tails
9. Mark the full validation as `ok` only if every check contains the required signature.
10. Write the final JSON payload.
11. Print the output path.
12. Exit 0 on success, otherwise print a refusal message and exit 1.

[stored_report_shape]
The written JSON report includes:
- `generated_at_utc`
- `model`
- `required_processor_signature`
- `status`
- `warm_result`
- `checks`

Each per-check record includes:
- `index`
- `timestamp_utc`
- `returncode`
- `model_line`
- `matched_requirement`
- `stdout_tail`
- `stderr_tail`

[dependencies]
- Python 3
- local Ollama CLI
- `ollama run`
- `ollama ps`

[used_by]
- `./scripts/benchmark/run_llm_task_sweep_once.sh`

[failure_modes]
- Ollama warm run fails
- `ollama ps` does not show the model
- processor signature does not match the required value
- CLI execution errors prevent reliable inspection

[notes]
The validator is intentionally simple and string-based. It does not attempt to infer nuanced runtime states beyond the exact processor signature requirement supplied at invocation time.

