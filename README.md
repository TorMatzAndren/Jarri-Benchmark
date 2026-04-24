<p align="center">



  <img src="benchmark_ui/logo.png" width="200"/>


</p>





<h1 align="center">Jarri Benchmark</h1>

# Jarri Benchmark

Deterministic LLM efficiency analysis surface.

This repository contains a filesystem-backed benchmark UI for inspecting local LLM behavior across correctness, energy, token use, throughput, and failure structure.

It is not a generic leaderboard, not a benchmark theater layer, and not a vibes dashboard. It is a deterministic inspection surface over already-produced benchmark artifacts.

---

The current version requires Ollama as the execution layer, plus DuckDB and Pandas in the Python environment for the full rebuild and export chain.

---

## Quick start

## Python environment

Create a virtual environment and install dependencies:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Run the full canonical rebuild chain first:

    bash ./run_me.sh

If you want to run a fresh sweep first and then rebuild everything (example, requires qwen3:8b pulled through Ollama):

    bash ./run_me.sh --models qwen3:8b --repeats 1

Example with explicit experiments:

    bash ./run_me.sh --models qwen3:8b,mistral:7b --repeats 1 --experiments fact_prose_v2,math_measurement_v1

Example with explicit TDP levels:

    bash ./run_me.sh --models qwen3:8b --repeats 1 --experiments fact_prose_v2 --tdp-levels 41,50,60,70

After the data has been rebuilt, serve the UI:

    cd benchmark_ui
    python3 -m http.server 8000

Open it in the browser:

    http://localhost:8000

---

## What this is

Jarri Benchmark is a deterministic analysis surface for local LLM benchmarking.

It exposes benchmark evidence through a plain HTML/JavaScript UI backed by exported JSON surfaces. Those JSON files are derived from canonical benchmark ledgers, joined failure analysis, and DuckDB-backed ranking/export steps.

The goal is simple:

- show what models actually do
- show what they cost in energy
- show how many output tokens they waste
- show how they fail
- show which configurations are genuinely useful

---

## What this is not

This repository does not define benchmark truth by itself.

It does not:

- prompt models directly
- evaluate answers directly
- define benchmark manifests
- own the GPU control policy
- replace the upstream Jarri benchmark chain

It contains the release-facing execution, rebuild, export, and UI surface needed to inspect that chain.

---

## Core visible surfaces

The UI is built around a few concrete inspection surfaces:

- model comparison
- selected model detail
- task registry
- task ranking
- model × task surface
- model × TDP surface
- task drilldown
- failure surface
- Pareto frontier
- raw JSON browser

These surfaces are intended to remain operator-readable first. Fancy visualization is secondary to inspectable truth.

---

## Core metrics

The system currently surfaces metrics such as:

- average evaluator score
- average energy in joules
- tokens per second
- average output tokens
- average total tokens
- joules per output token
- output tokens per joule
- score per 100 output tokens
- score per output token
- score per Wh
- output-token waste relative to best visible row
- score-per-Wh relative to best visible row
- hard failure rate
- success rate

This is important: the system is not only measuring correctness. It is measuring correctness relative to cost and behavior.

---

## Why output tokens matter

Input prompts are mostly standardized. That makes output-token behavior highly informative.

A model that burns dramatically more output tokens to attempt the same task is often revealing one or more of these:

- weak task discipline
- rambling search behavior
- semantic uncertainty
- inefficient reasoning structure
- wasted energy for lower-quality output

This is why token use is treated as a first-class metric rather than hidden behind generic speed numbers.

---

## Reading the UI correctly

### Avg Score %

Average evaluator score for the slice. Higher is better.

### Avg Energy J

Average observed energy used by the slice. Lower is better.

### Tokens/s

Raw throughput. Useful, but not a truth metric on its own.

### Out Tokens

Average output tokens generated per task. Lower usually means less waste.

### OutTok vs Best

Relative output-token consumption compared with the best visible row.

- `1.00x` = best visible token efficiency
- higher values = more token waste

### Score/100tok

How much evaluator score is being bought per 100 output tokens. Higher is better.

### J/OutTok

How much energy is spent per output token. Lower is better.

### Score/Wh vs Best

Relative score-per-Wh compared with the best visible row.

- `1.00x` = best visible energy efficiency
- lower values = weaker score return for the same energy budget

### Hard Failure

How often the slice fails badly enough to be structurally unreliable.

### Success

How often the slice completed successfully under the exported contract.

---

## Data contract

The UI expects benchmark data under `benchmark_ui/data/`.

Minimum core surfaces:

    benchmark_ui/data/
      duckdb_model_rankings.json
      duckdb_task_rankings.json
      duckdb_model_task_tdp.json
      duckdb_pareto_frontiers.json
      duckdb_task_registry.json
      duckdb_failure_surfaces.json

Additional surfaces often present:

    benchmark_ui/data/
      data_index.json
      joined/
      failures/
      analysis/
      registries/
      verification/

If the required JSON artifacts do not exist, the UI has nothing truthful to display.

---

## Canonical pipeline position

This UI sits late in the Jarri benchmark chain.

Simplified truth path:

    benchmark/cli/benchmark_run.py
      -> llm_benchmark_runs.jsonl
      -> benchmark/cli/jarri_benchmark_export.py
      -> benchmark/cli/jarri_benchmark_failure_aggregate.py
      -> benchmark/cli/jarri_benchmark_failure_join.py
      -> scripts/export/sync_benchmark_ui_data.sh
      -> scripts/benchmark/import_benchmark_json_to_duckdb.py
      -> scripts/export/export_duckdb_*.py
      -> benchmark_ui/data/*.json
      -> benchmark_ui/index.html + app.js

The UI is downstream of canonical artifacts.

If upstream truth is wrong, the UI will faithfully expose wrong data.

---

## Current canonical entrypoint

The current top-level entrypoint is:

    bash ./run_me.sh

This can operate in two modes.

### 1. Rebuild only

Rebuilds policy, joined analysis, UI data, DuckDB import, and exported surfaces from existing benchmark artifacts.

    bash ./run_me.sh

### 2. Sweep + rebuild

Runs a benchmark sweep first, then executes the full rebuild/export chain.

    bash ./run_me.sh --models qwen3:8b --repeats 1

---

## Important runtime warning

`--tdp-levels` is a GPU power-limit request-token surface.

Current token forms:

- bare numeric tokens are interpreted downstream as percent requests
  - examples: `41`, `80`, `100`, `112`
- tokens ending in `w` or `W` are interpreted downstream as explicit watt requests
  - examples: `144w`, `168w`, `270W`

The current Linux benchmark chain resolves these requests through `set_gpu_power_limit_linux.sh`, which reads the active NVIDIA driver power-limit surface, converts percent tokens into card-local watt targets, clamps requests into the supported min/max range, applies the result through `nvidia-smi`, and confirms the applied value.

This matters.

A percent token is not a universal watt value. The same token may resolve differently on different GPUs because each card exposes its own power-limit range.

That means:

- the default TDP token ladder is a benchmark policy surface
- percent tokens are hardware-interpreted, not globally fixed
- explicit watt tokens are available when fixed power targets are needed
- cross-GPU comparisons must preserve the applied watt value and GPU identity

Do not assume that one machine’s TDP percentages mean the same absolute power draw on another without explicit verification.

---

## Repository structure

Typical visible structure:

    benchmark_ui/
      index.html
      app.js
      logo.png
      data/
        duckdb_model_rankings.json
        duckdb_task_rankings.json
        duckdb_model_task_tdp.json
        duckdb_pareto_frontiers.json
        duckdb_task_registry.json
        duckdb_failure_surfaces.json

The frontend is intentionally simple:

- plain HTML
- plain JavaScript
- exported JSON surfaces
- no fake backend
- no frontend framework dependency

---

## Design rules

This surface follows a few hard rules:

- deterministic artifacts before presentation
- raw JSON remains inspectable
- no invented rankings beyond exported truth
- efficiency must include energy and token behavior, not just score
- failure structure is evidence, not noise
- operator-readable tables matter more than flashy charting

---

## What is actually interesting here

The interesting part is not that models can be ranked.

The interesting part is that they can be ranked simultaneously by:

- correctness
- energy cost
- token waste
- score density
- failure topology
- Pareto usefulness

That is the real surface.

---

## Known limitations

Current limitations include:

- NVIDIA-specific Linux power-limit control through `nvidia-smi`
- hardware-specific interpretation of percent TDP tokens
- schema evolution risk if exporters drift
- no universal non-NVIDIA hardware abstraction yet
- UI truth depends fully on upstream artifact correctness

This system is strongest when the full Jarri chain is treated as truth-bound and verified end to end.

---

## Minimal verification

A basic smoke test:

    bash ./run_me.sh
    cd benchmark_ui
    python3 -m http.server 8000

Then verify that the following actually render:

- model comparison
- selected model detail
- task ranking
- failure surface
- Pareto frontier
- JSON browser

If the raw JSON browser looks wrong, trust that signal first.

---

## Open-source release posture

This project should be understood as:

a deterministic LLM efficiency analysis surface

not as:

- a generic benchmark toy
- a subjective leaderboard
- a marketing dashboard
- an AI-insights wrapper

It is an inspectable surface over concrete benchmark artifacts.

That distinction matters.

---

## License

This project is released under the MIT License.

See `LICENSE` for the full text.

### Attribution request

If you build on Jarri Benchmark, please keep visible credit to:

- Tor Matz Andrén
- https://jarri.systems
- http://www.gbsproductions.se
- https://github.com/TorMatzAndren

This is a request, not an additional legal restriction on top of the MIT License.
