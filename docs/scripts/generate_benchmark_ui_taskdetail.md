Title: generate_benchmark_ui_taskdetail.py
ID: script-generate-benchmark-ui-taskdetail
Date: 2026-04-22
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-22
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:benchmark-ui
@scope:task-detail
@scope:joined-analysis
@scope:failure-analysis
@scope:runtime-policy
@scope:ui-data-generation
@scope:model-task-tdp-detail
@entity:./scripts/ui/generate_benchmark_ui_taskdetail.py
@script:./scripts/ui/generate_benchmark_ui_taskdetail.py
@semantic:benchmark-ui-model-task-detail-builder
@capability:build-ui-ready-model-task-detail-rows-from-joined-and-failure-analysis-json
@state:documented
@truth:script-behavior
@risk:depends-on-joined-and-failure-json-shapes
@risk:task-axis-map-is-hand-maintained-and-can-drift-from-real-task-registry
@risk:group-expansion-assumes-upstream-joined-contracts-remain-stable
@output:./benchmark_ui/data/ui_model_task_taskdetail.json

[summary]
generate_benchmark_ui_taskdetail.py builds the detailed model-task surface consumed by the benchmark UI.

It reads already-synced joined and failure JSON surfaces, applies runtime-policy model exclusions, expands joined model-task-TDP groups into detailed rows, computes weighted summary metrics across TDP levels, derives dominant failure distributions, attaches representative failure examples, and writes ui_model_task_taskdetail.json.

This is a derived UI shaping layer, not a canonical benchmark truth producer.

[purpose]
This script exists to provide the frontend with a richer model-task breakdown than the higher-level model profile surface.

Instead of forcing the UI to reconstruct detail views from multiple upstream files, it precomputes:
- one row per model/task combination
- weighted summary metrics across TDP levels
- TDP-level subrows
- dominant failure stage/type/subtype summaries
- task-level failure distributions
- representative failure examples

That keeps the UI simpler and stabilizes the task-detail contract.

[canonical_role]
active
derived-ui-data-builder
post-analysis-transform
ui-surface-producer
not-source-truth

[authority_boundary]
This script is allowed to:
- read joined benchmark analysis JSON files
- read failure aggregate and failure record JSON files
- read the benchmark runtime policy and exclude models listed there
- map task ids to named capability axes
- expand joined model/task/TDP groups into detailed per-model/per-task rows
- compute weighted summary metrics across TDP rows
- derive dominant failure stage/type/subtype summaries
- attach representative failures from failure records
- write ui_model_task_taskdetail.json

This script is not allowed to:
- create joined analysis itself
- aggregate failure records directly from raw reports
- mutate benchmark ledgers
- modify runtime policy
- declare canonical benchmark truth beyond the provided inputs
- replace DuckDB import or downstream ranking export logic

[inputs]
Required files:
- ./benchmark_ui/data/joined/joined_failure_energy_by_model_task_tdp.json
- ./benchmark_ui/data/joined/joined_failure_energy_by_task.json
- ./benchmark_ui/data/failures/failure_by_task.json
- ./benchmark_ui/data/failures/failure_records.json
- ./benchmark_runtime_policy.json

Expected input assumptions:
- joined_failure_energy_by_model_task_tdp.json contains a top-level groups object
- joined_failure_energy_by_task.json contains a top-level groups object keyed by task id
- failure_by_task.json contains a top-level groups object keyed by task id
- failure_records.json contains either rows or records
- benchmark_runtime_policy.json contains canonical_runtime_policy.exclude_models

Primary internal mapping:
- TASK_AXIS_MAP assigns task ids to:
  - execution_reliability
  - constraint_precision
  - semantic_fidelity
  - dependency_chain_integrity
  - formal_reasoning_consistency
  - arithmetic_exactness

Files read:
- ./benchmark_ui/data/joined/joined_failure_energy_by_model_task_tdp.json
- ./benchmark_ui/data/joined/joined_failure_energy_by_task.json
- ./benchmark_ui/data/failures/failure_by_task.json
- ./benchmark_ui/data/failures/failure_records.json
- ./benchmark_runtime_policy.json

[outputs]
Primary output:
- ./benchmark_ui/data/ui_model_task_taskdetail.json

Output document structure:
- generated_at_utc
- policy_path
- excluded_models
- source_files
- rows

Each detailed row includes:
- model
- task_id
- task_family
- primary_axis
- summary
- dominant_failure_stage
- dominant_failure_type
- dominant_failure_subtypes
- task_level_failure_type_distribution
- tdp_rows
- representative_failures

Summary fields currently include:
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_tokens_per_second
- avg_score_per_wh_strict

Each tdp_rows entry currently includes:
- tdp_level
- rows
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_score_percent
- avg_energy_j
- avg_tokens_per_second
- avg_score_per_wh_strict
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution

Representative failure fields currently include:
- failure_stage
- failure_type
- failure_subtype
- quality_class
- artifact_usability
- score_percent
- report_path
- result_path

stdout behavior:
- prints the output path on success

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - overwrites ./benchmark_ui/data/ui_model_task_taskdetail.json
- statefulness:
  - no persistent mutation outside the output file

[execution_flow]
1. Load excluded model names from benchmark_runtime_policy.json.
2. Load joined_failure_energy_by_model_task_tdp.json.
3. Load joined_failure_energy_by_task.json.
4. Load failure_by_task.json.
5. Load failure_records.json.
6. Extract joined groups, task groups, failure task groups, and failure rows.
7. Build per_model_task_tdp by iterating joined groups:
   7.1 filter excluded models
   7.2 read task_ids and tdp_levels from each group
   7.3 append expanded TDP entries under each model/task key
8. For each model/task key:
   8.1 sort TDP rows by tdp_level
   8.2 resolve task-level joined and failure group context
   8.3 scan failure records for matching model/task rows
   8.4 keep up to eight representative failures
   8.5 aggregate stage/type/subtype distributions across TDP rows
   8.6 compute weighted summary metrics using row counts as weights
   8.7 derive dominant failure stage/type/subtypes
   8.8 attach task-level failure_type distribution
   8.9 append the detailed row
9. Sort detailed rows by model and task_id.
10. Write ui_model_task_taskdetail.json.
11. Print the output path.

[derived_logic]
Excluded model handling:
- models listed under canonical_runtime_policy.exclude_models are excluded before per-model/task expansion

Expansion model:
- the script expands each joined group into combinations of:
  - model
  - task_id
  - tdp_level
- each expanded row inherits the group-level rates and distributions from the upstream joined group

Weighted averaging:
- summary metrics are weighted by each TDP row's rows field
- weighted_average() returns 0.0 for zero total weight

Distribution shaping:
- top_k_distribution() converts dict distributions into sorted name/count rows
- dominant_failure_stage uses top 1 non-success stage
- dominant_failure_type uses top 1 non-success type
- dominant_failure_subtypes uses top 5 subtype rows
- task_level_failure_type_distribution uses failure_by_task.json rather than only the expanded TDP rows

Representative failures:
- representative failures are taken from failure_records.json where:
  - row.model == model
  - row.task_id or row.task == task_id
- limited to the first eight matched rows in scan order

Unmapped tasks:
- if a task id is missing from TASK_AXIS_MAP, primary_axis becomes unmapped

[data-contract_note]
This script currently reads only the synced joined and failure UI JSON surfaces plus runtime policy directly.

That means:
- it does not query DuckDB directly
- it does not recompute benchmark truth itself
- it depends on upstream rebuild and sync steps having already completed successfully

In the current chain, run_me.sh ensures this script runs after:
- rebuild_failure_join_chain.sh
- sync_benchmark_ui_data.sh
- DuckDB import

Even though this script does not currently read DuckDB directly, it belongs in the later UI-generation phase of the full canonical rebuild pipeline.

[dependencies]
Python standard library modules:
- json
- collections.defaultdict
- datetime
- pathlib
- typing

Data dependencies:
- joined benchmark analysis outputs
- failure aggregate outputs
- failure record outputs
- benchmark runtime policy file

Upstream producers likely include:
- ./benchmark/cli/jarri_benchmark_failure_join.py
- ./benchmark/cli/jarri_benchmark_failure_aggregate.py
- ./scripts/export/sync_benchmark_ui_data.sh
- ./run_me.sh

[callers]
Known caller:
- ./run_me.sh

Operational role:
- this script is part of the UI-generation phase after canonical analysis has already been rebuilt and synced

[verification]
Canonical command:
python3 ./scripts/ui/generate_benchmark_ui_taskdetail.py

Expected success signals:
- ./benchmark_ui/data/ui_model_task_taskdetail.json is written
- stdout prints that output path
- output JSON contains:
  - generated_at_utc
  - excluded_models
  - rows

Quick sanity checks:
- verify excluded models do not appear in rows
- verify each row has:
  - model
  - task_id
  - summary
  - tdp_rows
  - representative_failures
- verify tdp_rows are sorted by tdp_level
- verify representative_failures is capped at 8
- verify dominant failure sections are present even when sparse
- verify unmapped tasks, if any, use primary_axis unmapped

[failure_modes]
- missing input file: script aborts on file read
- malformed JSON in joined, failure, or policy files: JSON decode failure
- missing expected groups structure: falls back to empty dicts and may produce sparse output
- failure_records shape drift: representative_failures may become empty or partial
- joined group expansion assumptions may over-attribute group-level values to each model/task/TDP combination if upstream grouping contracts change
- task-axis drift: TASK_AXIS_MAP can become stale when task ids change or new tasks are introduced
- zero-row weighted averages collapse to 0.0, which can hide missing-signal situations

[notes]
This is a detailed UI-shaping script, not a canonical truth producer. It depends on upstream joined and failure analysis outputs already being correct.

Important current truths:
- task axes are still hand-mapped in TASK_AXIS_MAP
- excluded models are controlled by benchmark_runtime_policy.json
- representative failures are taken directly from failure_records.json
- output is intended for detailed benchmark UI views, not archival truth
- this script currently consumes synced joined/failure UI JSON, not DuckDB directly

This script belongs under ./docs/scripts/ because the script itself lives at ./, not under /benchmark/.
