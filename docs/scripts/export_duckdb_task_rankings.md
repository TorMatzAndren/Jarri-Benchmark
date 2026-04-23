Title: export_duckdb_task_rankings.py
ID: script-export-duckdb-task-rankings
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:duckdb-export
@scope:task-ranking
@scope:ui-export
@entity:./scripts/export/export_duckdb_task_rankings.py
@script:./scripts/export/export_duckdb_task_rankings.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_task_rankings.json

[summary]
export_duckdb_task_rankings.py reads per-model, per-task, per-TDP ranking rows from the benchmark DuckDB database and exports them as a JSON payload for the benchmark UI. It joins ranking rows with joined_model_task_tdp to attach benchmark_count, sanitizes NaN and Infinity values into null, sorts rows primarily by task and correctness, and writes the result to duckdb_task_rankings.json.

[purpose]
This script exists to produce a task-centric ranking export from DuckDB so the UI and downstream scripts can inspect how models performed on each task across TDP levels. It is a read-only export step, not a benchmark runner and not a database importer.

[role]
active
exporter
duckdb-reader
ui-data-builder
task-ranking-surface

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- DB_PATH = ./benchmarks/_db/benchmark.duckdb
- OUT_PATH = ./benchmark_ui/data/duckdb_task_rankings.json

Database dependency:
- DuckDB database at ./benchmarks/_db/benchmark.duckdb

Expected DuckDB relations used:
- v_task_model_ranking
- joined_model_task_tdp

Expected fields read from v_task_model_ranking:
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

Expected field read from joined_model_task_tdp:
- rows

Join behavior:
- LEFT JOIN joined_model_task_tdp AS j
  ON j.model = r.model
 AND j.task_id = r.task_id
 AND j.task_family = r.task_family
 AND j.tdp_level = r.tdp_level

Derived output field from join:
- benchmark_count = j.rows

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_task_rankings.json

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

stdout behavior:
- prints the output JSON path on success

[ordering]
Rows are ordered in SQL by:
1. r.task_id ascending
2. r.fully_correct_rate descending
3. r.pipeline_usable_rate descending
4. r.avg_score_percent descending
5. r.model ascending
6. r.tdp_level ascending

This means the output is task-first, then best-performing rows within each task float to the top.

[functions]
utc_now_iso()
- returns current UTC timestamp in ISO format

sanitize_value(value)
- converts NaN and Infinity float values to None
- leaves all other values unchanged

sanitize_row(row)
- sanitizes every field in a row dict

main()
- opens benchmark.duckdb in read-only mode
- executes the ranking query
- converts query results into dict rows
- sanitizes the rows
- writes the payload to duckdb_task_rankings.json
- prints the output path
- returns 0

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_task_rankings.json
- side_effects:
  - no benchmark mutation
  - no DuckDB mutation
  - deterministic overwrite for a fixed DB state

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
python3 ./scripts/export/export_duckdb_task_rankings.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_task_rankings.json
- output file exists
- output file is valid JSON
- payload has keys:
  - generated_at_utc
  - source
  - rows

Quick validation:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_task_rankings.json').expanduser(); d=json.loads(p.read_text()); print(type(d.get('rows')).__name__, len(d.get('rows', [])))"

DuckDB validation:
python3 -c "import duckdb, pathlib; db=pathlib.Path('./benchmarks/_db/benchmark.duckdb').expanduser(); con=duckdb.connect(str(db), read_only=True); print(con.execute('select count(*) from v_task_model_ranking').fetchone()[0]); con.close()"

Ordering sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_task_rankings.json').expanduser(); rows=json.loads(p.read_text())['rows']; print(rows[0]['task_id'] if rows else None)"

Join sanity check:
- confirm benchmark_count appears where joined_model_task_tdp has matching rows
- accept null benchmark_count when no matching joined row exists because the join is LEFT JOIN

Sanitization sanity check:
- inspect output for raw NaN or Infinity values
- expected result is JSON null instead

[failure_modes]
- benchmark.duckdb missing: connection/open failure
- duckdb module missing: import failure
- v_task_model_ranking missing: SQL execution failure
- joined_model_task_tdp missing: SQL execution failure
- schema drift in either relation: SQL execution failure
- output parent directory missing: write failure unless parent already exists
- NaN or Infinity in source rows: converted to null by sanitize_value
- empty result set: valid output with rows = []

[notes]
This script is very close in structure to export_duckdb_model_task_tdp.py, but it is not the same export.

The difference in emphasis is:
- export_duckdb_task_rankings.py orders output by task and ranking logic
- export_duckdb_model_task_tdp.py exports a model-task-TDP surface with additional joined failure distributions

This script lives directly under ./, so its document belongs under:
- ./docs/scripts/export_duckdb_task_rankings.md
