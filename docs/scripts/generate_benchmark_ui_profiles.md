Title: generate_benchmark_ui_profiles.py
ID: script-generate-benchmark-ui-profiles
Date: 2026-04-22
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-22
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:benchmark-ui
@scope:model-profiles
@scope:joined-analysis
@scope:runtime-policy
@scope:duckdb-consumption
@scope:token-efficiency
@scope:ui-data-generation
@entity:./scripts/ui/generate_benchmark_ui_profiles.py
@script:./scripts/ui/generate_benchmark_ui_profiles.py
@semantic:benchmark-ui-model-profile-builder
@capability:build-ui-ready-model-profiles-from-joined-benchmark-analysis-runtime-policy-and-duckdb-token-efficiency-surfaces
@state:documented
@truth:script-behavior
@risk:depends-on-joined-json-shapes-policy-schema-and-duckdb-view-contracts
@risk:task-axis-map-is-hand-maintained-and-can-drift-from-real-task-registry
@risk:run-order-matters-because-duckdb-must-exist-before-this-script-runs
@output:./benchmark_ui/data/ui_model_profiles.json

[summary]
generate_benchmark_ui_profiles.py builds UI-ready per-model benchmark profiles from three upstream truth surfaces:

- joined model-level failure and energy summaries
- joined task-level failure and energy summaries
- DuckDB token-efficiency views

It also reads the runtime policy so excluded models are filtered out before profile generation.

The script’s job is not to create new benchmark truth. Its job is to reshape already-produced benchmark truth into a UI-oriented model profile surface. That surface now includes not only reliability, score, and energy metrics, but also token-efficiency metrics such as average output tokens, score per output token, score per 100 output tokens, and joules per output token.

[purpose]
This script exists to convert lower-level benchmark analysis surfaces into a higher-level UI abstraction centered on models.

Instead of forcing the website to derive everything from raw joined tables or ad hoc frontend logic, it assembles a compact model profile document that can drive cards, overview panels, and ranking surfaces.

Its current role is to combine:
- model-level benchmark outcome summaries
- per-task axis folding
- dominant failure modes
- DuckDB-derived token-efficiency metrics

This is especially important because output token cost is now considered a meaningful benchmark dimension. Smaller or weaker models can sometimes emit dramatically more output tokens while still scoring worse, and that behavior should be visible in the UI rather than buried in raw logs.

[canonical_role]
active
derived-ui-data-builder
post-analysis-transform
not-source-truth

[authority_boundary]
This script is allowed to:
- read joined benchmark analysis JSON files from benchmark_ui/data/joined
- read the benchmark runtime policy and exclude models listed there
- open the canonical DuckDB database in read-only mode
- query model_token_efficiency from DuckDB
- map task ids into named capability axes
- compute weighted averages across task-group evidence
- derive dominant failure types per axis
- assemble model summary/profile structures for UI use
- write ui_model_profiles.json

This script is not allowed to:
- generate joined analysis itself
- import benchmark JSON into DuckDB
- aggregate failure records directly from raw report files
- modify benchmark ledgers
- change runtime policy
- define canonical benchmark truth upstream of the provided inputs

[inputs]
Required files:
- ./benchmark_ui/data/joined/joined_failure_energy_by_model.json
- ./benchmark_ui/data/joined/joined_failure_energy_by_task.json
- ./benchmark_runtime_policy.json
- ./benchmarks/_db/benchmark.duckdb

Expected input assumptions:
- joined_failure_energy_by_model.json contains a top-level "groups" object keyed by model
- joined_failure_energy_by_task.json contains a top-level "groups" object keyed by task id
- benchmark_runtime_policy.json contains canonical_runtime_policy.exclude_models
- benchmark.duckdb exists and has a model_token_efficiency view
- task ids present in joined task groups are stable enough to map via TASK_AXIS_MAP

Primary internal mapping:
- TASK_AXIS_MAP assigns task ids to primary axes such as:
  - execution_reliability
  - constraint_precision
  - semantic_fidelity
  - dependency_chain_integrity
  - formal_reasoning_consistency
  - arithmetic_exactness

Files read:
- ./benchmark_ui/data/joined/joined_failure_energy_by_model.json
- ./benchmark_ui/data/joined/joined_failure_energy_by_task.json
- ./benchmark_runtime_policy.json
- ./benchmarks/_db/benchmark.duckdb

DuckDB view read:
- model_token_efficiency

DuckDB columns expected:
- model
- configuration_rows
- avg_score_percent
- avg_output_tokens
- avg_score_per_output_token
- avg_score_per_100_output_tokens
- avg_joules_per_output_token
- avg_output_tokens_per_joule

[outputs]
Primary output:
- ./benchmark_ui/data/ui_model_profiles.json

Output document structure:
- generated_at_utc
- policy_path
- duckdb_path
- excluded_models
- source_files
- models

Each model entry includes:
- name
- summary
- axes
- top_failures

Model summary fields:
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- hard_failure_rate
- avg_energy_j
- avg_score_percent
- score_per_wh_strict
- avg_tokens_per_second
- avg_output_tokens
- avg_score_per_output_token
- avg_score_per_100_output_tokens
- avg_joules_per_output_token
- avg_output_tokens_per_joule
- token_efficiency_configuration_rows

Per-axis fields:
- usable_output_rate
- pipeline_usable_rate
- fully_correct_rate
- avg_energy_j
- capability_per_joule
- pipeline_capability_per_joule
- dominant_failure

stdout behavior:
- prints the output path on success

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - overwrites ./benchmark_ui/data/ui_model_profiles.json
- statefulness:
  - no persistent mutation outside the output file

[execution_flow]
1. Load excluded model names from benchmark_runtime_policy.json.
2. Load joined_failure_energy_by_model.json.
3. Load joined_failure_energy_by_task.json.
4. Open benchmark.duckdb in read-only mode.
5. Query model_token_efficiency and build a per-model token-efficiency lookup.
6. Extract task groups and model groups from joined JSON inputs.
7. For each task group:
   7.1 read row count
   7.2 filter out excluded models
   7.3 map task id to primary axis via TASK_AXIS_MAP, or use "unmapped"
   7.4 determine top failure type for the task group excluding "success"
   7.5 accumulate weighted fully-correct, usable, pipeline-usable, and energy values per model per axis
   7.6 accumulate per-axis failure counts per model
   7.7 collect top per-task failure records per model
8. For each model group not excluded:
   8.1 copy model-level joined summary metrics
   8.2 merge in DuckDB token-efficiency metrics for that model
   8.3 discover the model’s primary axes from accumulated entries
   8.4 compute weighted averages for each axis
   8.5 derive dominant failure per axis
   8.6 compute capability_per_joule and pipeline_capability_per_joule
   8.7 trim top_failures to the eight highest-count entries
   8.8 append the assembled profile
9. Sort profiles using:
   - fully_correct_rate descending
   - avg_score_per_100_output_tokens descending
   - hard_failure_rate ascending
10. Write ui_model_profiles.json.
11. Print output path.

[derived_logic]
Excluded model handling:
- models listed under canonical_runtime_policy.exclude_models are removed both from task-level folding and final model output
- DuckDB token-efficiency rows for excluded models are also ignored

Weighted averaging:
- per-axis rates and energy are weighted by task-group row counts
- weighted_average() returns 0.0 for zero total weight

Failure typing:
- pick_top_failure_type() selects the most frequent non-success failure_type in a group
- dominant per-axis failure is selected from accumulated task failure counts for that axis

Capability-per-joule metrics:
- capability_per_joule = fully_correct_rate / avg_energy_j
- pipeline_capability_per_joule = pipeline_usable_rate / avg_energy_j
- safe_div() returns 0.0 when denominator is zero

Token-efficiency integration:
- token-efficiency is not recomputed from joined JSON
- it is pulled from DuckDB’s model_token_efficiency view
- this avoids duplicating token-efficiency derivation logic in multiple places

Important token metrics:
- avg_output_tokens describes how many output tokens a model typically emits
- avg_score_per_output_token describes useful benchmark score produced per generated token
- avg_score_per_100_output_tokens is the same idea in a more readable scale for UI display
- avg_joules_per_output_token describes energy cost per generated token
- avg_output_tokens_per_joule is descriptive throughput, not inherently a quality metric

Unmapped tasks:
- if a task id is missing from TASK_AXIS_MAP, it is grouped under axis name "unmapped"

[dependencies]
Python standard library modules:
- json
- collections.defaultdict
- datetime
- pathlib
- typing

External Python dependency:
- duckdb

Data dependencies:
- joined failure-energy aggregates already produced upstream
- benchmark runtime policy file
- benchmark DuckDB already imported upstream

Upstream producers include:
- ./benchmark/cli/jarri_benchmark_failure_join.py
- ./scripts/export/sync_benchmark_ui_data.sh
- ./scripts/benchmark/import_benchmark_json_to_duckdb.py

[callers]
Known caller:
- ./run_me.sh

Runtime ordering requirement:
- this script must run after import_benchmark_json_to_duckdb.py
- if run_me.sh executes this script before DuckDB import, token-efficiency surfaces can be missing or stale

Referenced source files:
- benchmark_ui/data/joined/joined_failure_energy_by_model.json
- benchmark_ui/data/joined/joined_failure_energy_by_task.json
- benchmarks/_db/benchmark.duckdb

[verification]
Canonical command:
python3 ./scripts/ui/generate_benchmark_ui_profiles.py

Expected success signals:
- ./benchmark_ui/data/ui_model_profiles.json is written
- stdout prints that output path
- output JSON contains:
  - generated_at_utc
  - excluded_models
  - duckdb_path
  - models

Quick sanity checks:
- verify excluded models are absent from the output models list
- verify each model entry has:
  - name
  - summary
  - axes
  - top_failures
- verify summary now includes:
  - avg_output_tokens
  - avg_score_per_output_token
  - avg_score_per_100_output_tokens
  - avg_joules_per_output_token
  - avg_output_tokens_per_joule
- verify top_failures is capped at 8 entries
- verify profiles are sorted by fully_correct_rate, then score-per-100-output-tokens, then hard-failure pressure
- verify qwen3:4b-like token bloat is visible in avg_output_tokens and score-per-100-output-tokens
- verify unmapped tasks, if any, land under axis "unmapped"

[failure_modes]
- missing joined input file: script aborts on file read
- missing policy file: script aborts on file read
- missing DuckDB database: FileNotFoundError
- missing or broken model_token_efficiency view: DuckDB query failure
- malformed JSON in joined or policy files: JSON decode failure
- missing expected "groups" structure: falls back to empty dicts and may produce sparse output
- task-axis drift: TASK_AXIS_MAP can become stale when task ids change or new tasks are introduced
- denominator-zero capability metrics: safely collapse to 0.0, which can hide missing-signal situations
- stale DuckDB contents: UI can show old token-efficiency metrics if import_benchmark_json_to_duckdb.py has not run first
- inconsistent upstream aggregation shapes: can produce empty or misleading UI profiles if contracts drift

[notes]
This is a UI-shaping script, not a canonical benchmark truth producer. Its correctness depends entirely on the integrity of upstream joined analysis, runtime policy, and DuckDB token-efficiency views.

Important current truths:
- the axis model is explicitly hand-authored in TASK_AXIS_MAP
- excluded models are controlled by benchmark_runtime_policy.json
- token-efficiency is now sourced from DuckDB, not recomputed locally
- output token count is a first-class UI-visible benchmark metric
- this script now depends on correct run ordering in run_me.sh

This script belongs under ./docs/scripts/ because the script itself lives at ./, not under /benchmark/.
