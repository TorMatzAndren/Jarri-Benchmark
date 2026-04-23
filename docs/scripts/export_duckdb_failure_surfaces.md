Title: export_duckdb_failure_surfaces.py
ID: script-export-duckdb-failure-surfaces
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:failure-analysis
@scope:ui-export
@scope:failure-surface-aggregation
@entity:./scripts/export/export_duckdb_failure_surfaces.py
@script:./scripts/export/export_duckdb_failure_surfaces.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_failure_surfaces.json

[summary]
export_duckdb_failure_surfaces.py reads benchmark UI failure records together with task ranking rows, groups failures by model and task, computes failure-stage, failure-type, and failure-subtype distributions, attaches benchmark-count context from the task rankings dataset, and writes a condensed failure-surface JSON for UI or downstream analytical use. It is an export/aggregation script, not a runtime mutator.

[purpose]
This script exists to transform raw failure records into a compact per-model/per-task surface that shows where failures cluster, how common each failure mode is, and how those failures compare against the number of benchmarked rows seen for the same model/task pair.

[role]
active
exporter
aggregation
ui-data-builder

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- DATA_DIR = ./benchmark_ui/data
- FAILURE_RECORDS_PATH = ./benchmark_ui/data/failures/failure_records.json
- TASK_RANKINGS_PATH = ./benchmark_ui/data/duckdb_task_rankings.json
- OUT_PATH = ./benchmark_ui/data/duckdb_failure_surfaces.json

Expected failure-record payload shapes:
- list of records
- dict with "records"
- dict with "rows"
- dict with "failure_records"

Expected failure-record fields used:
- model or model_name
- task_id or task or benchmark_task_id
- failure_stage or stage
- failure_type or type
- failure_subtype or subtype or failure_subtypes
- score_percent
- quality_class
- artifact_usability
- pipeline_usable
- hard_failure

Expected task-ranking payload shape:
- dict with "rows"

Expected task-ranking fields used:
- model
- task_id
- benchmark_count
- task_family

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_failure_surfaces.json

Output payload structure:
- generated_at_utc
- source_failure_records
- source_task_rankings
- rows

Each output row contains:
- model
- task_id
- task_family
- benchmark_count
- failure_record_count
- failure_record_rate_vs_benchmarks
- dominant_failure_stage
- dominant_failure_type
- dominant_failure_subtype
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution
- representative_failures

Representative failures are capped at:
- 8 per model/task group

Dominant distributions are truncated to:
- top 5 stages
- top 5 types
- top 8 subtypes

[behavior]
The script:
1. Loads failure_records.json.
2. Loads duckdb_task_rankings.json.
3. Normalizes the failure payload into a plain record list.
4. Reads task ranking rows and builds:
   - benchmark_counts keyed by (model, task_id)
   - task_meta keyed by (model, task_id)
5. Groups failure records by (model, task_id).
6. For each group:
   - counts total failures
   - looks up benchmark_count
   - counts failure stages
   - counts failure types
   - counts normalized subtypes
   - collects up to 8 representative failures
7. Computes failure_record_rate_vs_benchmarks when benchmark_count is nonzero.
8. Builds the final payload.
9. Writes duckdb_failure_surfaces.json.
10. Prints the output path.

[normalization_rules]
normalize_records(payload)
- accepts several known payload shapes
- returns a list of failure records
- returns an empty list for unknown structures

get_first(record, keys, default)
- returns the first non-null value among alternate field names

normalize_subtypes(value)
- None -> []
- list -> stringified non-null entries
- comma-delimited string -> split and trim
- simple string -> one-item list
- other values -> stringified one-item list

counter_to_rows(counter, total)
- converts Counter values into rows with:
  - name
  - count
  - rate
- sorts by most_common() order

[grouping_model]
Primary grouping key:
- (model, task_id)

Task-ranking context key:
- (model, task_id)

This means:
- benchmark counts are aligned against the exact same model/task pair
- task_family is pulled from duckdb_task_rankings.json rather than failure records directly

[output_semantics]
benchmark_count
- number of benchmark rows known from task rankings for the same model/task pair

failure_record_count
- number of failure records found for that same model/task pair

failure_record_rate_vs_benchmarks
- failure_record_count / benchmark_count
- None if benchmark_count is zero

dominant_* fields
- truncated views for UI-friendly summaries

full *_distribution fields
- complete ordered distributions for the grouped failure set

representative_failures
- sampled first-seen failure rows, capped at 8
- includes stage/type/subtype plus selected severity/usability fields

[functions]
utc_now_iso()
- returns UTC ISO timestamp

load_json(path)
- reads JSON from disk

normalize_records(payload)
- normalizes supported input payload shapes into a list of dict records

get_first(record, keys, default)
- resolves alternate field names

normalize_subtypes(value)
- normalizes subtype representations into list[str]

counter_to_rows(counter, total)
- converts a Counter into structured count/rate rows

main()
- orchestrates the full export and writes the final JSON

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_failure_surfaces.json
- side_effects:
  - no mutation of source inputs
  - no external commands
  - deterministic overwrite of one output file given identical inputs

[dependencies]
Python standard library only:
- json
- collections.Counter
- collections.defaultdict
- datetime
- pathlib

No subprocess usage.
No network usage.
No database connection despite the duckdb-oriented filename.

[references]
Observed references shown in investigation:
- ./all_scripts_now.txt
- ./benchmarks/_analysis_inventory/benchmark_producer_discovery.json
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
python3 ./scripts/export/export_duckdb_failure_surfaces.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_failure_surfaces.json
- output file exists and is valid JSON
- output contains:
  - generated_at_utc
  - source_failure_records
  - source_task_rankings
  - rows

Validation checks:
- confirm rows are grouped by model/task_id
- confirm benchmark_count is populated where task rankings contain matching rows
- confirm failure_record_rate_vs_benchmarks is None only when benchmark_count == 0
- confirm dominant_failure_stage/type/subtype are truncated summaries
- confirm representative_failures never exceeds 8 items per row

Quick sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_failure_surfaces.json').expanduser(); d=json.loads(p.read_text()); print(len(d.get('rows', [])))"

[failure_modes]
- missing failure_records.json: hard failure on load
- missing duckdb_task_rankings.json: hard failure on load
- malformed JSON in either input: hard failure on parse
- unexpected payload shape: script may emit zero rows or rows missing contextual counts
- task_rankings rows without matching failure records contribute no output rows
- failure records without matching task rankings get benchmark_count = 0 and task_family = None

[notes]
Despite the name, this script does not query DuckDB directly. It reads already-exported JSON artifacts and produces a derived JSON summary.

This script lives directly under ./, so its document belongs under:
- ./docs/scripts/export_duckdb_failure_surfaces.md
