Title: jarri_benchmark_export.py
ID: script-jarri-benchmark-export
Date: 2026-04-22
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-22
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:normalized-export
@scope:aggregate-analysis
@scope:token-efficiency
@scope:energy-efficiency
@scope:summary-views
@scope:csv-export
@entity:./benchmark/cli/jarri_benchmark_export.py
@script:./benchmark/cli/jarri_benchmark_export.py
@semantic:canonical-benchmark-exporter
@capability:normalize-ledger-rows-aggregate-runs-and-produce-analysis-exports-including-output-token-efficiency-metrics
@state:documented
@truth:script-behavior
@risk:depends-on-ledger-schema-stability
@risk:derived-metrics-can-hide-missing-upstream-fields
@risk:filtering-can-exclude-rows-and-change-summary-meaning
@output:analysis-export-directory

[summary]
jarri_benchmark_export.py is the canonical exporter that transforms raw llm_benchmark_runs.jsonl ledgers into normalized rows, grouped aggregates, and summary selection views. It is the first downstream analysis stage after benchmark_run.py and establishes the normalized benchmark data surfaces consumed by later failure and join workflows.

As of this revision, the exporter explicitly preserves and derives output-token-efficiency metrics so the benchmark system can compare not only correctness, speed, and energy, but also how many output tokens a model needed to reach its result. This matters because input prompts are mostly standardized, while output length varies drastically between models and is itself a meaningful efficiency signal.

[purpose]
This script exists to convert heterogeneous JSONL benchmark ledger rows into a stable normalized analysis shape, compute aggregate statistics across repeated runs, and emit summary views that make model/task/TDP comparisons easier.

It also now serves as the first canonical place where output-token-efficiency is normalized and aggregated. That includes per-run and per-group visibility into:
- output token count
- joules per output token
- output tokens per joule
- score per output token
- score per 100 output tokens

[canonical_role]
authoritative
active
analysis-critical
primary-normalization-export

[authority_boundary]
This script is allowed to:
- discover llm_benchmark_runs.jsonl files from files or directories
- parse and validate JSONL rows
- normalize incomplete or variant row fields into a canonical export row shape
- filter rows by energy version, energy validity, model, task family, and minimum run index
- aggregate repeated runs by model / GPU / power limit / task / family
- compute token-efficiency and energy-efficiency derived metrics
- compute summary ranking views
- emit JSON and CSV analysis files

This script is not allowed to:
- execute benchmarks
- run model prompts
- evaluate model answers
- classify failure taxonomy from reports
- join normalized rows to failure records
- mutate original ledgers

[inputs]
CLI positional arguments:
- one or more inputs, each being:
  - a JSONL ledger file
  - a directory containing llm_benchmark_runs.jsonl files

CLI required options:
- --output-dir

CLI optional options:
- --energy-measurement-version
- --require-energy-measurement-version
- --require-energy-valid
- --require-models
- --require-task-families
- --min-run-index

Environment assumptions:
- input files exist and are readable
- JSONL rows are top-level JSON objects
- upstream ledgers generally follow the benchmark_run.py ledger shape

Files read:
- one or more llm_benchmark_runs.jsonl files

Files written:
- <output-dir>/benchmark_export.json
- <output-dir>/normalized_runs.json
- <output-dir>/aggregate_by_model_gpu_tdp_task.json
- <output-dir>/summary_views.json
- <output-dir>/normalized_runs.csv
- <output-dir>/aggregate_by_model_gpu_tdp_task.csv

[outputs]
Primary export products:
- benchmark_export.json
- normalized_runs.json
- aggregate_by_model_gpu_tdp_task.json
- summary_views.json
- normalized_runs.csv
- aggregate_by_model_gpu_tdp_task.csv

benchmark_export.json contains:
- exporter version
- canonical energy measurement version
- input files
- filtering metadata
- normalized row count
- aggregate row count
- summary metadata
- normalized rows
- aggregates
- summary views

stdout behavior:
- prints a JSON success summary including written files and counts

stderr behavior:
- parse and file errors surface normally as exceptions

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: rewrites all output files in the target output directory
- statefulness: no mutation of source ledgers

[execution_flow]
1. Parse CLI arguments.
2. Resolve and create the output directory.
3. Discover all llm_benchmark_runs.jsonl inputs from the given files/directories.
4. Parse every JSONL row through iter_jsonl_rows().
5. Normalize each row through normalize_row().
6. Derive per-run token and energy efficiency metrics.
7. Apply filters through row_passes_filters().
8. Sort the filtered normalized rows deterministically.
9. Aggregate rows by:
   - model
   - gpu_name
   - power_limit_percent
   - task_id
   - task_family
10. For each aggregate group, compute:
   - run count
   - success / usable / hard-failure / energy-valid rates
   - min / max / avg / median / stddev for key metrics
11. Build summary views.
12. Write all JSON and CSV outputs.
13. Print JSON success metadata and exit.

[normalization_rules]
Row normalization includes:
- safe coercion of numeric fields
- inferred total_tokens if missing
- inferred tokens_per_second if missing and duration exists
- inferred llm_energy_wh from llm_energy_joules
- inferred llm_energy_kwh from llm_energy_wh
- fallback from evaluation_score_percent to score_per_process
- fallback from scientific_score_percent to evaluation_score_percent
- usable_output falls back to usable if needed
- energy_valid defaults to false if absent

Canonical per-run token-efficiency fields now include:
- output_tokens
- llm_joules_per_output_token
- llm_wh_per_1000_output_tokens
- output_tokens_per_joule
- score_per_output_token
- score_per_100_output_tokens

Important metric meaning:
- output_tokens is the model’s emitted completion size and is the interesting token-cost metric because the prompt side is largely standardized
- score_per_output_token measures how much benchmark score was achieved per generated token
- score_per_100_output_tokens is the same concept but scaled into a more readable unit
- llm_joules_per_output_token measures energy cost per generated token
- output_tokens_per_joule measures how many output tokens the model emits per joule, which is descriptive rather than inherently “good”

[aggregation_model]
Grouping key:
- model
- gpu_name
- power_limit_percent
- task_id
- task_family

Metric families aggregated include:
- duration_seconds
- tokens_per_second
- output_tokens
- gpu_avg_power_w
- gpu_peak_power_w
- llm_energy_joules
- llm_energy_wh
- llm_joules_per_output_token
- llm_wh_per_1000_output_tokens
- output_tokens_per_joule
- score_per_output_token
- score_per_100_output_tokens
- evaluation_score_percent
- scientific_score_percent
- score_per_second_strict
- score_per_wh_strict

Aggregate stats per metric:
- min
- max
- avg
- median
- stddev

Energy-sensitive metrics are only aggregated across rows where energy_valid == true.

[summary_views]
summary_views.json contains:
- best_raw_score_per_model
- best_score_per_wh_per_model
- best_tokens_per_second_per_model
- lowest_failure_rate_per_model
- best_usable_rate_per_model
- top_configurations_overall

These summary views remain heuristic convenience surfaces. They are not the sole authority for token-efficiency comparison, which should instead be read from normalized and aggregate outputs directly or from downstream DuckDB views built on top of them.

[dependencies]
Python standard library modules:
- argparse
- csv
- json
- math
- statistics
- collections.defaultdict
- pathlib
- typing

External tools:
- none

Upstream dependency:
- llm_benchmark_runs.jsonl ledgers produced by benchmark_run.py or compatible canonical producers

Downstream consumers:
- rebuild_failure_join_chain.sh
- import_benchmark_json_to_duckdb.py
- benchmark UI data generation
- any UI or reporting layer consuming normalized/aggregate exports

[callers]
Known direct callers:
- ./scripts/export/rebuild_failure_join_chain.sh

Likely manual usage:
- operator exporting one experiment or a directory of experiments

Call relationship role:
- canonical normalization/export stage immediately downstream of benchmark_run.py

[verification]
Canonical command:
python3 ./benchmark/cli/jarri_benchmark_export.py ./benchmarks/fact_prose_v2 --output-dir ./benchmarks/_analysis/fact_prose_v2

Expected success signals:
- output directory is created
- all six output files are written
- normalized_runs.json is a JSON list
- aggregate_by_model_gpu_tdp_task.json is a JSON list
- summary_views.json contains the expected summary view keys
- stdout prints a JSON object with success: true

Quick sanity checks:
- verify normalized_runs.json rows include:
  - output_tokens
  - llm_joules_per_output_token
  - output_tokens_per_joule
  - score_per_output_token
  - score_per_100_output_tokens
- verify aggregate rows include:
  - avg_output_tokens
  - total_output_tokens
  - weighted_joules_per_output_token
  - weighted_output_tokens_per_joule
  - weighted_score_per_output_token
  - weighted_score_per_100_output_tokens
- verify rows_included + rows_excluded == input_rows_total

[failure_modes]
- missing input path: FileNotFoundError
- non-JSONL file passed as file input: ValueError
- no ledger files found: FileNotFoundError
- invalid JSON line in ledger: ValueError
- non-object JSON row: ValueError
- upstream schema drift: normalized values may become null or misleading rather than failing immediately
- aggressive filters: exports may be empty or heavily reduced
- derived token-efficiency metrics become null when score or output token fields are absent
- descriptive token-throughput metrics can be misread as quality metrics if presented without score context

[notes]
This script is the canonical bridge from raw runtime ledgers to stable exported analysis surfaces.

Important current truths frozen here:
- the canonical energy measurement version is still run_sliced_v1
- normalized row export is JSON-first, with CSV as a convenience surface
- aggregate grouping key is model + gpu_name + power_limit_percent + task_id + task_family
- score_per_wh_strict is only meaningful when energy_valid is true
- output-token-efficiency is now an explicit first-class comparison surface
- output token count is more interesting than prompt token count in this benchmark because prompts are mostly standardized

This script should remain in the main tree and is one of the highest-priority benchmark analysis documents.
