Title: import_benchmark_json_to_duckdb.py
ID: script-import-benchmark-json-to-duckdb
Date: 2026-04-22
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-22
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:duckdb-import
@scope:analysis-materialization
@scope:token-efficiency
@scope:sql-surface
@entity:./scripts/benchmark/import_benchmark_json_to_duckdb.py
@script:./scripts/benchmark/import_benchmark_json_to_duckdb.py
@semantic:canonical-json-to-duckdb-analysis-loader
@capability:load-canonical-benchmark-json-surfaces-into-duckdb-and-materialize-token-efficiency-views
@state:documented
@truth:script-behavior
@risk:depends-on-export-json-shape-stability
@risk:duckdb-type-coercion-can-fail-if-upstream-fields-drift
@risk:view-semantics-can-be-misread-without-understanding-output-token-cost-vs-score
@output:./benchmarks/_db/benchmark.duckdb

[summary]
import_benchmark_json_to_duckdb.py is the canonical bridge from exported benchmark JSON surfaces into DuckDB. It loads normalized and aggregate benchmark analysis outputs, materializes stable relational tables, and creates SQL views used by later ranking, UI, and inspection layers.

As of this revision, the DuckDB import layer explicitly materializes output-token-efficiency surfaces. That means the benchmark system can query token cost, score per output token, and joules per output token directly in SQL rather than recomputing them ad hoc in frontend code.

[purpose]
This script exists to turn the filesystem-based benchmark analysis outputs into a structured SQL surface. It gives the benchmark system a queryable truth layer for rankings, frontiers, token-efficiency inspection, model comparisons, and later UI export.

[canonical_role]
authoritative
active
sql-truth-bridge
analysis-materialization-spine

[authority_boundary]
This script is allowed to:
- load canonical normalized benchmark JSON exports
- load canonical aggregate benchmark JSON exports
- create or refresh DuckDB tables
- normalize field types during import
- create SQL views over imported benchmark tables
- materialize model-level and model-task-level token-efficiency surfaces

This script is not allowed to:
- execute benchmark runs
- evaluate answers
- rebuild failure taxonomy by itself
- define benchmark truth upstream of the exported JSON surfaces
- mutate original benchmark ledgers

[inputs]
Expected upstream JSON sources:
- ./benchmarks/_analysis/coding_measurement_v3/normalized_runs.json
- ./benchmarks/_analysis/fact_prose_v2/normalized_runs.json
- ./benchmarks/_analysis/knowledge_measurement_v2/normalized_runs.json
- ./benchmarks/_analysis/language_measurement_v2/normalized_runs.json
- ./benchmarks/_analysis/math_measurement_v1/normalized_runs.json
- corresponding aggregate_by_model_gpu_tdp_task.json files for the same experiment families

Environment assumptions:
- DuckDB Python package is available in the active benchmark environment
- upstream export files exist and are parseable JSON
- normalized and aggregate rows follow the canonical exporter shape

Files read:
- normalized_runs.json per experiment
- aggregate_by_model_gpu_tdp_task.json per experiment

Files written:
- ./benchmarks/_db/benchmark.duckdb

[outputs]
Primary durable output:
- ./benchmarks/_db/benchmark.duckdb

Core relations and views include:
- benchmark_runs
- benchmark_normalized_runs
- benchmark_aggregates
- normalized_run_token_surface
- model_task_token_efficiency
- model_token_efficiency

These views exist so downstream ranking and UI layers can query token-efficiency directly.

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: refreshes imported tables and recreates views from canonical JSON sources
- statefulness: persistent only in the DuckDB database file

[execution_flow]
1. Resolve the canonical benchmark analysis source files.
2. Load normalized benchmark rows from JSON.
3. Load aggregate benchmark rows from JSON.
4. Create or refresh DuckDB tables for normalized and aggregate data.
5. Coerce text, boolean, integer, and float fields into stable relational types.
6. Create SQL views over normalized runs.
7. Create SQL views over aggregate rows.
8. Materialize token-efficiency views used for later export and UI generation.
9. Print a compact success summary including row counts and created view names.

[token_efficiency_surfaces]
Canonical token-efficiency SQL surfaces now include:

normalized_run_token_surface
Per-run view exposing token-efficiency fields such as:
- output_tokens
- llm_joules_per_output_token
- output_tokens_per_joule
- score_per_output_token
- score_per_100_output_tokens

model_task_token_efficiency
Grouped view for one model on one task across configurations and repeats. Useful for:
- seeing whether one model bloats output specifically on certain task families
- comparing score-per-token task by task
- finding token-thrashing patterns

model_token_efficiency
Grouped view across each whole model. Useful for:
- model-level website ranking
- compact efficiency summaries
- exposing cases where a smaller model emits massively more tokens for worse results

Important interpretation note:
- output_tokens_per_joule is descriptive throughput
- score_per_100_output_tokens is usually the strongest “token waste vs useful work” metric
- joules_per_output_token is useful but should be read together with score

[type_handling]
This importer depends on stable type coercion from exported JSON.

Important current detail:
artifact_usability and similar string fields must be imported as strings, not JSON-typed objects. Prior conversion failures occurred when DuckDB tried to coerce plain strings into JSON unexpectedly. The importer must therefore treat these fields explicitly as text surfaces.

[dependencies]
Python runtime:
- duckdb
- json
- pathlib
- typing

Upstream producer:
- ./benchmark/cli/jarri_benchmark_export.py

Downstream consumers:
- generate_benchmark_ui_profiles.py
- DuckDB export scripts
- benchmark UI ranking surfaces
- ad hoc SQL inspection by operator

[callers]
Known direct caller:
- ./run_me.sh

Likely manual usage:
- operator refreshing DuckDB after analysis export rebuilds

Call relationship role:
- canonical import bridge from JSON filesystem truth into relational SQL truth

[verification]
Canonical command:
python3 ./scripts/benchmark/import_benchmark_json_to_duckdb.py

Expected success signals:
- benchmark.duckdb is created or refreshed
- success JSON reports normalized and aggregate row counts
- view list includes:
  - normalized_run_token_surface
  - model_task_token_efficiency
  - model_token_efficiency

Quick sanity checks:
- verify normalized run columns include:
  - artifact_usability
  - llm_joules_per_output_token
  - output_tokens
  - output_tokens_per_joule
  - score_per_output_token
  - score_per_100_output_tokens
- verify aggregate columns include:
  - avg_output_tokens
  - total_output_tokens
  - weighted_joules_per_output_token
  - weighted_output_tokens_per_joule
  - weighted_score_per_output_token
  - weighted_score_per_100_output_tokens
- run a sample query against model_token_efficiency and confirm qwen3:4b surfaces as token-expensive relative to qwen3:8b

[failure_modes]
- missing upstream normalized JSON files
- missing upstream aggregate JSON files
- malformed JSON input
- DuckDB package unavailable in the active environment
- type coercion failure from schema drift
- SQL view creation failure if expected columns are missing
- misleading interpretation if token throughput is shown without score context

[notes]
This script is now one of the key benchmark truth surfaces because it converts exported benchmark data into a stable query layer.

Important current truths frozen here:
- token-efficiency is now a first-class SQL surface
- output token count is the relevant token-cost dimension for this benchmark
- qwen3:4b-style token thrashing is expected to be visible through model_token_efficiency rather than hidden inside raw run logs
- frontend/UI layers should consume token-efficiency through DuckDB-backed exports or DuckDB-backed profile generation rather than recomputing it independently

This script should remain authoritative for relational benchmark truth until formally replaced.
