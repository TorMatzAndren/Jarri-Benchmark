Title: export_duckdb_model_rankings.py
ID: script-export-duckdb-model-rankings
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:duckdb-export
@scope:model-ranking
@scope:ui-export
@entity:./scripts/export/export_duckdb_model_rankings.py
@script:./scripts/export/export_duckdb_model_rankings.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_model_rankings.json

[summary]
export_duckdb_model_rankings.py reads the canonical benchmark DuckDB database in read-only mode, joins model-level summary metrics with a model rollup built from normalized benchmark rows, sanitizes NaN and infinite numeric values, and writes a model-ranking JSON payload for the benchmark UI. It is a read-only export script and depends on the presence of the normalized_runs table and v_model_summary view inside the benchmark DuckDB database.

[purpose]
This script exists to produce a compact model-level ranking surface for UI and downstream inspection, combining correctness, usability, failure, score, energy, speed, hardware diversity, and runtime-status context into one exported JSON file.

[role]
active
exporter
duckdb-reader
ui-data-builder

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- DB_PATH = ./benchmarks/_db/benchmark.duckdb
- OUT_PATH = ./benchmark_ui/data/duckdb_model_rankings.json

Database dependency:
- DuckDB database at ./benchmarks/_db/benchmark.duckdb

Expected DuckDB objects:
- table or relation: normalized_runs
- view or relation: v_model_summary

Expected normalized_runs fields used in the SQL:
- model
- task_id
- gpu_name
- runtime_residency_status
- canonical_runtime

Expected v_model_summary fields used in the SQL:
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

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_model_rankings.json

Output payload structure:
- generated_at_utc
- source
- rows

Each row contains:
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
- benchmark_count
- distinct_task_count
- distinct_gpu_count
- gpu_names
- runtime_statuses

[sql_behavior]
The script runs one SQL query with two parts:

1. model_rollup CTE from normalized_runs
   - groups by model
   - counts total benchmark rows
   - counts distinct tasks
   - counts distinct GPUs
   - concatenates distinct GPU names
   - concatenates distinct runtime statuses, preferring:
     - runtime_residency_status
     - canonical_runtime as fallback via COALESCE

2. final SELECT from v_model_summary
   - selects model-level summary fields from v_model_summary
   - LEFT JOINs model_rollup on model
   - orders rows by:
     - fully_correct_rate DESC
     - pipeline_usable_rate DESC
     - avg_score_percent DESC
     - model ASC

This means the ranking is primarily correctness-first, then pipeline usability, then average score.

[sanitization]
sanitize_value(value)
- converts NaN to None
- converts positive/negative infinity to None
- leaves all other values unchanged

sanitize_row(row)
- applies sanitize_value to every field in a row dict

This is important because raw floating-point non-finite values are not safe JSON values for downstream consumers.

[functions]
utc_now_iso()
- returns UTC ISO timestamp

sanitize_value(value)
- normalizes non-finite floats to None

sanitize_row(row)
- sanitizes a whole result row

main()
- opens DuckDB in read-only mode
- executes the ranking query
- converts results to dict rows
- sanitizes each row
- closes the connection
- writes the JSON payload
- prints the output path

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_model_rankings.json
- side_effects:
  - no mutation of database
  - no mutation of upstream benchmark artifacts
  - deterministic overwrite of one UI JSON output given the same DB contents

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
python3 ./scripts/export/export_duckdb_model_rankings.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_model_rankings.json
- output file exists and is valid JSON
- output contains:
  - generated_at_utc
  - source
  - rows

Validation checks:
- confirm rows are ordered by:
  - fully_correct_rate descending
  - pipeline_usable_rate descending
  - avg_score_percent descending
  - model ascending
- confirm source equals ./benchmarks/_db/benchmark.duckdb
- confirm non-finite values are emitted as null, not NaN or Infinity
- confirm each row includes benchmark_count and distinct_task_count when rollup data exists

Quick sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_model_rankings.json').expanduser(); d=json.loads(p.read_text()); print(len(d.get('rows', [])))"

Database sanity check:
python3 -c "import duckdb, pathlib; db=pathlib.Path('./benchmarks/_db/benchmark.duckdb').expanduser(); con=duckdb.connect(str(db), read_only=True); print(con.execute('select count(*) from v_model_summary').fetchone()[0]); con.close()"

[failure_modes]
- benchmark.duckdb missing: connection/open failure
- duckdb module missing: import failure
- normalized_runs missing: SQL execution failure
- v_model_summary missing: SQL execution failure
- output directory missing: write failure unless parent already exists
- nonstandard schema in normalized_runs or v_model_summary: SQL execution failure
- null-heavy data may produce sparse but still valid rows

[notes]
This script is read-only against DuckDB and writes only one UI export artifact.

It lives directly under ./, so its document belongs under:
- ./docs/scripts/export_duckdb_model_rankings.md

It is part of the DuckDB/UI export layer rather than the benchmark runtime or evaluator layer.
