Title: export_duckdb_model_task_tdp.py
ID: script-export-duckdb-model-task-tdp
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:duckdb-export
@scope:model-task-tdp-ranking
@scope:ui-export
@entity:./scripts/export/export_duckdb_model_task_tdp.py
@script:./scripts/export/export_duckdb_model_task_tdp.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_model_task_tdp.json

[summary]
export_duckdb_model_task_tdp.py reads the canonical benchmark DuckDB database in read-only mode, joins task/model/TDP ranking rows with joined failure-and-energy rollup rows, sanitizes NaN and infinite numeric values, and writes a JSON export for the benchmark UI. It is a read-only export layer script that depends on two prebuilt DuckDB relations, v_task_model_ranking and joined_model_task_tdp.

[purpose]
This script exists to export a detailed comparison surface at the model + task + TDP level, so downstream UI and analysis layers can inspect correctness, usability, failure, runtime, energy, and distribution data for each benchmark configuration.

[role]
active
exporter
duckdb-reader
ui-data-builder

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- DB_PATH = ./benchmarks/_db/benchmark.duckdb
- OUT_PATH = ./benchmark_ui/data/duckdb_model_task_tdp.json

Database dependency:
- DuckDB database at ./benchmarks/_db/benchmark.duckdb

Expected DuckDB relations used:
- v_task_model_ranking
- joined_model_task_tdp

Expected v_task_model_ranking fields used in SQL:
- model
- task_id
- task_family
- tdp_level
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_score_per_wh_strict
- avg_tokens_per_second
- gpu_name
- gpu_architecture
- gpu_power_limit_w
- runtime_residency_status
- canonical_runtime
- observed_energy_j
- observed_tokens_per_second

Expected joined_model_task_tdp fields used in SQL:
- model
- task_id
- task_family
- tdp_level
- rows
- success_rate
- energy_valid_rate
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution
- artifact_usability_distribution
- quality_class_distribution
- confidence_classification_distribution

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_model_task_tdp.json

Output payload structure:
- generated_at_utc
- source
- rows

Each row contains:
- model
- task_id
- task_family
- tdp_level
- benchmark_count
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_score_per_wh_strict
- avg_tokens_per_second
- gpu_name
- gpu_architecture
- gpu_power_limit_w
- runtime_residency_status
- canonical_runtime
- observed_energy_j
- observed_tokens_per_second
- success_rate
- energy_valid_rate
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution
- artifact_usability_distribution
- quality_class_distribution
- confidence_classification_distribution

[sql_behavior]
The script runs one SQL query that:

1. Selects ranking fields from v_task_model_ranking as r
2. LEFT JOINs joined_model_task_tdp as j on:
   - model
   - task_id
   - task_family
   - tdp_level
3. Renames j.rows to benchmark_count
4. Orders results by:
   - r.model ASC
   - r.task_id ASC
   - r.tdp_level ASC

This means the exported table is stable and grouped by model first, then task, then TDP level.

[sanitization]
sanitize_value(value)
- converts NaN to None
- converts positive or negative infinity to None
- leaves all other values unchanged

sanitize_row(row)
- applies sanitize_value to every field in a row dict

This is necessary because JSON consumers should not receive non-finite float values.

[functions]
utc_now_iso()
- returns current UTC time in ISO format

sanitize_value(value)
- normalizes non-finite float values to None

sanitize_row(row)
- sanitizes one full row dict

main()
- opens DuckDB in read-only mode
- executes the export query
- maps rows to column-named dicts
- sanitizes each row
- closes the database connection
- writes the JSON payload
- prints the output path

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_model_task_tdp.json
- side_effects:
  - no database mutation
  - no benchmark artifact mutation
  - deterministic overwrite of one UI export file for a given DB state

[dependencies]
Python standard library:
- json
- math
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
python3 ./scripts/export/export_duckdb_model_task_tdp.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_model_task_tdp.json
- output file exists and is valid JSON
- payload contains:
  - generated_at_utc
  - source
  - rows

Validation checks:
- confirm source equals ./benchmarks/_db/benchmark.duckdb
- confirm rows are sorted by model, then task_id, then tdp_level
- confirm benchmark_count comes from joined_model_task_tdp.rows
- confirm failure distributions and quality distributions are carried through when present
- confirm NaN and Infinity are serialized as null

Quick sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_model_task_tdp.json').expanduser(); d=json.loads(p.read_text()); print(len(d.get('rows', [])))"

Database sanity check:
python3 -c "import duckdb, pathlib; db=pathlib.Path('./benchmarks/_db/benchmark.duckdb').expanduser(); con=duckdb.connect(str(db), read_only=True); print(con.execute('select count(*) from v_task_model_ranking').fetchone()[0]); print(con.execute('select count(*) from joined_model_task_tdp').fetchone()[0]); con.close()"

[failure_modes]
- benchmark.duckdb missing: connection/open failure
- duckdb module missing: import failure
- v_task_model_ranking missing: SQL execution failure
- joined_model_task_tdp missing: SQL execution failure
- schema drift in either relation: SQL execution failure
- output parent directory missing: write failure unless parent already exists
- sparse joined data: LEFT JOIN may produce null joined-side fields while still writing valid rows

[notes]
This script is part of the DuckDB-to-UI export layer, not the runtime benchmark executor layer.

It lives directly under ./, so its document belongs under:
- ./docs/scripts/export_duckdb_model_task_tdp.md

The exported row shape is intentionally richer than a simple ranking table because it carries both ranking metrics and joined failure taxonomy distributions for each model/task/TDP combination.
