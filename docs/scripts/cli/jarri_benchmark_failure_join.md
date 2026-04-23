Title: jarri_benchmark_failure_join.py
ID: script-jarri-benchmark-failure-join
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:failure-energy-join
@scope:joined-analysis
@scope:grouped-summary-views
@entity:./benchmark/cli/jarri_benchmark_failure_join.py
@script:./benchmark/cli/jarri_benchmark_failure_join.py
@semantic:canonical-failure-energy-joiner
@capability:join-normalized-run-exports-with-failure-records-and-produce-joined-analysis-surfaces
@state:documented
@truth:script-behavior
@risk:join-depends-on-report-path-identity
@risk:unmatched-rows-can-silently-grow-if-upstream-paths-drift
@risk:joined-fields-overwrite-normalized-row-fields
@output:joined-failure-energy-output-directory

[summary]
jarri_benchmark_failure_join.py is the canonical join stage that merges normalized benchmark rows with failure taxonomy records. It uses evaluation report path identity as the join key, enriches normalized rows with failure-stage and usability metadata, and emits joined grouped summaries over performance, usability, failures, and energy. This script is active and authoritative in the current benchmark analysis chain.

[purpose]
This script exists to combine two previously separate analysis surfaces: normalized run exports from jarri_benchmark_export.py and failure records from jarri_benchmark_failure_aggregate.py. It solves the final analysis step needed to reason about score, energy, runtime validity, failure type, and usability in one joined view.

[canonical_role]
authoritative
active
analysis-critical
final-join-stage

[authority_boundary]
This script is allowed to:
- load normalized benchmark row exports from analysis directories
- load failure_records.json from the failure aggregation stage
- match normalized rows to failure records by report path
- enrich normalized rows with joined failure metadata
- compute grouped summaries across joined rows
- emit joined row and unmatched-row outputs

This script is not allowed to:
- execute benchmarks
- normalize raw benchmark ledgers
- infer benchmark scores from raw evaluator logic
- rewrite normalized rows or failure records in place
- mutate source files

[inputs]
CLI required options:
- --analysis-root
- --failure-records
- --output-dir

Environment assumptions:
- analysis-root contains per-experiment normalized_runs.json files
- failure-records points to failure_records.json emitted by jarri_benchmark_failure_aggregate.py
- evaluation_report_path values in normalized rows correspond to report_path values in failure records after normalization

Files read:
- <analysis-root>/*/normalized_runs.json
- failure_records.json

Files written:
- <output-dir>/joined_failure_energy_summary.json
- <output-dir>/joined_failure_energy_by_model.json
- <output-dir>/joined_failure_energy_by_task.json
- <output-dir>/joined_failure_energy_by_tdp.json
- <output-dir>/joined_failure_energy_by_model_task_tdp.json
- <output-dir>/joined_failure_energy_rows.json
- <output-dir>/joined_failure_energy_unmatched.json

[outputs]
Primary outputs:
- joined_failure_energy_summary.json
- joined_failure_energy_by_model.json
- joined_failure_energy_by_task.json
- joined_failure_energy_by_tdp.json
- joined_failure_energy_by_model_task_tdp.json
- joined_failure_energy_rows.json
- joined_failure_energy_unmatched.json

joined_failure_energy_rows.json contains:
- generated_at_utc
- exporter_version
- row_count
- rows

joined_failure_energy_unmatched.json contains:
- generated_at_utc
- exporter_version
- row_count
- rows

Grouped summary outputs contain:
- generated_at_utc
- exporter_version
- grouped summary objects derived from summarize_group()

stdout behavior:
- prints a JSON success payload including row counts and written files

stderr behavior:
- normal Python exceptions surface for bad inputs or broken files

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: rewrites all output files in the target output directory
- statefulness: none beyond writing fresh joined outputs

[execution_flow]
1. Parse CLI arguments.
2. Resolve analysis_root, failure_records_path, and output_dir.
3. Load failure_records.json and build a lookup index keyed by normalized report_path.
4. Discover all <analysis-root>/*/normalized_runs.json files.
5. Load each normalized_runs.json payload.
6. For each row in each normalized file:
   6.1 attach analysis source metadata
   6.2 normalize evaluation_report_path
   6.3 attempt join against the failure record index
   6.4 if matched, copy failure fields into the joined row
   6.5 if unmatched, mark the row as unmatched and add it to unmatched_rows
7. Build overall summary over all joined rows.
8. Build grouped summaries by:
   - model
   - task_id
   - power_limit_percent
   - model + task_id + power_limit_percent
9. Write joined row, unmatched row, and grouped summary outputs.
10. Print JSON success payload and exit.

[join-key]
The join key is path identity:
- normalized row field: evaluation_report_path
- failure record field: report_path

Both sides are normalized through normalize_path():
- expanduser()
- resolve()
- cast to string

This means the join is path-based, not run-signature-based, task-based, or model-based.

[normalized-run-collection]
Normalized rows are collected from:
- <analysis-root>/*/normalized_runs.json

For each normalized_runs.json:
- the parent directory name becomes _analysis_experiment_id
- the normalized file path becomes _analysis_source_path

Only list payloads are accepted.
Non-dict rows inside those lists are skipped.

[joined-field-overwrite-behavior]
When a failure match is found, the script overwrites or injects:
- failure_stage
- failure_type
- failure_subtypes
- quality_class
- artifact_usability
- confidence_classification
- usable_output
- pipeline_usable
- hard_failure
- parse_valid
- runtime_valid
- fully_correct
- task_failure_keys

Additional join metadata:
- joined_report_path
- failure_join_found

This means joined failure truth takes precedence over preexisting normalized row values for those fields.

[unmatched-row-behavior]
If no failure record is found for a normalized row:
- failure_stage = unmatched
- failure_type = unmatched
- failure_subtypes = []
- quality_class = unmatched
- artifact_usability = unmatched
- confidence_classification = unmatched
- usable_output = None
- pipeline_usable = None
- hard_failure = None
- parse_valid = None
- runtime_valid = None
- fully_correct = None
- task_failure_keys = []

The row is added to unmatched_rows.

[summarization]
summarize_group() computes:
- rows
- unique models
- unique task_ids
- unique task_families
- unique tdp_levels
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution
- quality_class_distribution
- artifact_usability_distribution
- confidence_classification_distribution
- success_rate
- energy_valid_rate
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_score_percent
- min_score_percent
- max_score_percent
- avg_energy_j
- min_energy_j
- max_energy_j
- avg_score_per_wh_strict
- avg_tokens_per_second

Rate logic:
- bool_rate() treats truthiness directly
- unmatched None values therefore do not count as true

[grouping]
Supported grouped outputs:
- by model
- by task
- by TDP
- by model/task/TDP combination

Grouping helpers:
- group_by_key()
- group_by_combo()

Unknown or blank values are grouped under:
- "unknown"

[dependencies]
Python standard library modules:
- argparse
- json
- collections.Counter
- collections.defaultdict
- datetime
- pathlib
- typing

External tools:
- none

Upstream dependencies:
- ./benchmark/cli/jarri_benchmark_export.py
- ./benchmark/cli/jarri_benchmark_failure_aggregate.py

Likely orchestration caller:
- ./scripts/export/rebuild_failure_join_chain.sh

[callers]
Known direct caller:
- ./scripts/export/rebuild_failure_join_chain.sh

Likely manual usage:
- operator performing end-to-end joined analysis rebuilds

Call relationship role:
- final canonical join stage after normalized export and failure aggregation

[verification]
Canonical command:
python3 ./benchmark/cli/jarri_benchmark_failure_join.py \
  --analysis-root ./benchmarks/_analysis \
  --failure-records ./benchmarks/_analysis_failures/failure_records.json \
  --output-dir ./benchmarks/_analysis_joined

Expected success signals:
- output directory is created
- all seven JSON files are written
- joined_failure_energy_rows.json row_count equals joined_rows_total
- joined_failure_energy_unmatched.json row_count equals unmatched_rows_total
- summary output contains failure_exporter_version
- stdout prints success: true

Quick sanity checks:
- verify normalized_rows_total == joined_rows_total
- verify unmatched_rows_total is small or zero in a healthy canonical rebuild
- verify joined_report_path values look normalized and absolute
- verify by_model, by_task, and by_tdp group counts are plausible
- verify joined rows carry both energy/performance fields and failure taxonomy fields

[failure_modes]
- missing or unreadable failure_records.json: load failure
- malformed failure_records payload: build_failure_index may silently produce sparse index
- missing normalized_runs.json files: joined result may be empty
- report path drift between normalized rows and failure records: unmatched rows increase
- analysis-root contains malformed normalized payloads: non-list payloads are skipped entirely
- field overwrite collisions: joined failure fields may replace older row values that differ
- path normalization surprises: symlink or relocation changes can break joins

[notes]
This script is the canonical bridge that turns separate export and failure-analysis products into one unified analysis surface.

Important current truths frozen here:
- the join key is report path identity, not content hash or run signature
- unmatched rows are explicitly preserved and exported rather than dropped
- grouped summaries intentionally mix performance, energy, and failure semantics in one surface
- normalized row count and joined row count should match because every normalized row is carried forward whether matched or unmatched

This script should remain in the main tree and is one of the highest-priority benchmark analysis documents.
