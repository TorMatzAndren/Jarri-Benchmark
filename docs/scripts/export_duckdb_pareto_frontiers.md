Title: export_duckdb_pareto_frontiers.py
ID: script-export-duckdb-pareto-frontiers
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:duckdb-export
@scope:pareto-analysis
@scope:ui-export
@entity:./scripts/export/export_duckdb_pareto_frontiers.py
@script:./scripts/export/export_duckdb_pareto_frontiers.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_pareto_frontiers.json

[summary]
export_duckdb_pareto_frontiers.py reads benchmark summary rows from DuckDB, computes Pareto frontiers using fully_correct_rate as the correctness axis and avg_energy_j as the energy axis, and writes a JSON export for the benchmark UI. It produces both a global model frontier and per-task frontiers, separating frontier rows from dominated rows.

[purpose]
This script exists to expose efficiency-versus-correctness tradeoff surfaces in a form that the UI can consume directly. It formalizes which rows are non-dominated under the rule that higher fully_correct_rate is better and lower avg_energy_j is better.

[role]
active
exporter
duckdb-reader
ui-data-builder
pareto-frontier-builder

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- DB_PATH = ./benchmarks/_db/benchmark.duckdb
- OUT_PATH = ./benchmark_ui/data/duckdb_pareto_frontiers.json

Database dependency:
- DuckDB database at ./benchmarks/_db/benchmark.duckdb

Expected DuckDB relations used:
- v_model_summary
- v_task_model_ranking

Expected v_model_summary fields used in SQL:
- model
- fully_correct_rate
- pipeline_usable_rate
- usable_output_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_tokens_per_second
- fully_correct_per_joule
- pipeline_usable_per_joule

Expected v_task_model_ranking fields used in SQL:
- model
- task_id
- task_family
- tdp_level
- fully_correct_rate
- pipeline_usable_rate
- usable_output_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_tokens_per_second
- gpu_name
- runtime_residency_status
- canonical_runtime

Filtering rules in SQL:
- only rows with fully_correct_rate IS NOT NULL
- only rows with avg_energy_j IS NOT NULL

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_pareto_frontiers.json

Output payload structure:
- generated_at_utc
- source
- definition
- global_model_frontier
- per_task_frontier

definition object fields:
- x_axis = avg_energy_j
- x_direction = lower_is_better
- y_axis = fully_correct_rate
- y_direction = higher_is_better
- rule = textual dominance definition

global_model_frontier fields:
- frontier
- dominated
- row_count

per_task_frontier structure:
- keyed by task_id
- each task entry contains:
  - frontier
  - dominated
  - row_count
  - task_family

[pareto_definition]
A row a dominates row b if:
- a.fully_correct_rate >= b.fully_correct_rate
- a.avg_energy_j <= b.avg_energy_j
- and at least one of those comparisons is strict

This means a row is non-dominated when no other row is at least as correct and at least as energy-efficient while being strictly better on one axis.

[functions]
utc_now_iso()
- returns current UTC time in ISO format

sanitize_value(value)
- converts NaN and Infinity float values to None
- leaves finite floats and non-floats unchanged

sanitize_row(row)
- sanitizes every field in a row dict

dominates(a, b)
- applies the script's two-axis dominance rule
- returns False if either row lacks fully_correct_rate or avg_energy_j

pareto_frontier(rows)
- compares every row against every other row
- splits rows into frontier and dominated lists
- sorts both lists by:
  - avg_energy_j ascending
  - fully_correct_rate descending

main()
- opens DuckDB in read-only mode
- loads model summary rows
- loads task ranking rows
- sanitizes all rows
- computes a global frontier over model rows
- groups task rows by task_id
- computes a frontier for each task group
- writes the JSON payload
- prints the output path

[algorithm_behavior]
Global frontier:
- computed over all rows returned from v_model_summary query

Per-task frontier:
- task rows are grouped by task_id only
- each task group may contain multiple models and TDP levels
- task_family is taken from the first row in each grouped task

Sorting:
- frontier rows and dominated rows are both sorted for stable output
- lower-energy rows appear first
- ties then prefer higher fully_correct_rate

[complexity]
The frontier computation is pairwise and effectively O(n^2) per frontier set.
That is acceptable for current benchmark UI export sizes, but this script is not designed for very large datasets without optimization.

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_pareto_frontiers.json
- side_effects:
  - no database mutation
  - no benchmark ledger mutation
  - deterministic overwrite of one UI export file for a given DB state

[dependencies]
Python standard library:
- json
- math
- collections.defaultdict
- datetime
- pathlib

Third-party dependency:
- duckdb

External runtime requirement:
- DuckDB Python package must be installed and importable

[references]
Observed references shown in investigation:
- ./all_scripts_now.txt
- ./doc_queue_export_ui_now.txt
- ./file_inventory_clean.txt
- ./run_me.sh
- ./undocumented_not_in_deprecated_now.txt
- ./undocumented_scripts_abs_now.txt
- ./undocumented_scripts_now.txt

Observed caller from shown references:
- ./run_me.sh

[validation]
Direct validation command:
python3 ./scripts/export/export_duckdb_pareto_frontiers.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_pareto_frontiers.json
- output file exists and is valid JSON
- payload contains:
  - definition
  - global_model_frontier
  - per_task_frontier

Validation checks:
- confirm source equals ./benchmarks/_db/benchmark.duckdb
- confirm definition axes match:
  - avg_energy_j
  - fully_correct_rate
- confirm every frontier row is non-dominated within its group
- confirm dominated rows have at least one dominating competitor within their group
- confirm rows with null correctness or null energy are excluded by SQL
- confirm NaN and Infinity are serialized as null if ever encountered before sanitization

Quick sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_pareto_frontiers.json').expanduser(); d=json.loads(p.read_text()); print(d['global_model_frontier']['row_count']); print(len(d['per_task_frontier']))"

Database sanity check:
python3 -c "import duckdb, pathlib; db=pathlib.Path('./benchmarks/_db/benchmark.duckdb').expanduser(); con=duckdb.connect(str(db), read_only=True); print(con.execute('select count(*) from v_model_summary where fully_correct_rate is not null and avg_energy_j is not null').fetchone()[0]); print(con.execute('select count(*) from v_task_model_ranking where fully_correct_rate is not null and avg_energy_j is not null').fetchone()[0]); con.close()"

[failure_modes]
- benchmark.duckdb missing: connection/open failure
- duckdb module missing: import failure
- v_model_summary missing: SQL execution failure
- v_task_model_ranking missing: SQL execution failure
- schema drift in either relation: SQL execution failure
- output parent directory missing: write failure unless parent already exists
- null correctness or energy values: rows are excluded from frontier computation by design
- large row counts: pairwise frontier computation may become slow

[notes]
This script is a read-only analysis export, not a benchmark runner and not a DuckDB importer.

It lives directly under ./, so its document belongs under:
- ./docs/scripts/export_duckdb_pareto_frontiers.md

The frontier logic is intentionally simple and explicit in Python rather than pushed fully into SQL, which makes the dominance rule easier to inspect and adjust later.
