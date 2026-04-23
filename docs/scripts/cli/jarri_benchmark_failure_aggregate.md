Title: jarri_benchmark_failure_aggregate.py
ID: script-jarri-benchmark-failure-aggregate
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:failure-taxonomy
@scope:report-aggregation
@scope:failure-analysis
@entity:./benchmark/cli/jarri_benchmark_failure_aggregate.py
@script:./benchmark/cli/jarri_benchmark_failure_aggregate.py
@semantic:canonical-failure-taxonomy-aggregator
@capability:collect-report-files-normalize-failure-records-and-export-failure-summary-surfaces
@state:documented
@truth:script-behavior
@risk:depends-on-report-schema-and-filename-conventions
@risk:metadata-inference-can-fall-back-to-unknown
@risk:report-schema-drift-can-silently-weaken-taxonomy-quality
@output:failure-analysis-output-directory

[summary]
jarri_benchmark_failure_aggregate.py is the canonical failure-taxonomy aggregation stage for benchmark report files. It discovers report JSON artifacts, normalizes each report into a failure record, infers missing metadata where needed, and emits summary distributions and grouped views over failure stages, failure types, subtypes, usability, and correctness. This script is active and authoritative in the current benchmark analysis chain.

[purpose]
This script exists to transform many per-run evaluator report files into a stable failure-analysis surface. It solves cross-report normalization and grouped failure summarization so that later analysis can reason about parse failures, runtime failures, semantic failures, pipeline usability, and fully-correct output rates at the system level.

[canonical_role]
authoritative
active
analysis-critical
primary-failure-record-builder

[authority_boundary]
This script is allowed to:
- discover *_report.json benchmark report files
- read evaluator reports and normalize them into stable failure records
- infer task family, run metadata, and correctness signals when fields are absent or incomplete
- summarize distributions and rates across all reports
- emit grouped failure-analysis JSON outputs

This script is not allowed to:
- execute benchmarks
- normalize raw llm_benchmark_runs.jsonl ledgers
- join failure records to normalized energy rows
- rank models by efficiency or performance directly
- rewrite or mutate source report files

[inputs]
CLI positional arguments:
- one or more input_paths, each being:
  - a benchmark directory
  - a reports directory
  - an individual *_report.json file

CLI required options:
- --output-dir

Environment assumptions:
- input paths exist or are at least intended to resolve into report files
- report JSON files are parseable objects
- report filenames often follow the canonical run stem format:
  <tdp>_<model_safe>_<task_id>_run<run_index>_report.json

Files read:
- evaluator report JSON files discovered from inputs

Files written:
- <output-dir>/failure_summary.json
- <output-dir>/failure_by_model.json
- <output-dir>/failure_by_task.json
- <output-dir>/failure_by_tdp.json
- <output-dir>/failure_by_task_family.json
- <output-dir>/failure_records.json

[outputs]
Primary outputs:
- failure_summary.json
- failure_by_model.json
- failure_by_task.json
- failure_by_tdp.json
- failure_by_task_family.json
- failure_records.json

failure_records.json contains:
- generated_at_utc
- exporter_version
- record_count
- records without embedded raw_report payloads

Summary/group outputs contain:
- generated_at_utc
- exporter_version
- grouped summaries built from summarize_records()

stdout behavior:
- prints a JSON success payload with counts and written file paths

stderr behavior:
- hard failure if no report files are found
- uncaught JSON/schema issues surface normally

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: rewrites all output JSON files in the target output directory
- statefulness: none beyond writing fresh aggregate outputs

[execution_flow]
1. Parse CLI arguments.
2. Discover all matching report files from the provided inputs.
3. Abort if no report files are found.
4. For each report file:
   4.1 load report JSON
   4.2 parse run metadata from filename and path
   4.3 infer task family if missing
   4.4 infer failure stage, failure type, and failure subtypes
   4.5 derive parse_valid, runtime_valid, usable_output, pipeline_usable, hard_failure, and fully_correct
   4.6 build a normalized failure record
5. Build overall summary payload.
6. Build grouped payloads by:
   - model
   - task_id
   - power_limit_percent
   - task_family
7. Build records payload without embedding raw_report bodies.
8. Write all output JSON files.
9. Print JSON success summary and exit.

[report-discovery]
Report discovery rules:
- file input: accepted only if name ends with *_report.json
- directory input named reports:
  - scans direct children matching *_report.json
- any other directory input:
  - recursively scans reports/*_report.json

Discovery behavior:
- duplicate paths are deduplicated
- nonexistent paths are ignored during directory scanning logic, but absence of all results becomes fatal later

[metadata-inference]
Filename regex:
- ^(?P<tdp>\d+?)_(?P<model_safe>.+?)_(?P<task_id>.+?)_run(?P<run_index>\d+?)_report$

Parsed metadata:
- power_limit_percent
- task_id if missing in report
- run_index

Experiment inference:
- derived from path segments after "benchmarks" if present

Task family inference priority:
1. explicit report task_family
2. task_id prefix:
   - fact_ -> fact
   - prose_ -> prose
   - coding_ -> coding
   - math_ -> math
   - logic_ -> knowledge
   - constrained_ -> language
3. experiment_id prefix:
   - coding_ -> coding
   - math_ -> math
   - knowledge_ -> knowledge
   - language_ -> language
   - fact_ -> fact_prose
4. fallback -> unknown

Failure inference:
- failure_stage from report if present
- else success if hard_failure == false and usable_output == true
- else unknown

- failure_type from report if present
- else success if hard_failure == false and usable_output == true
- else unknown

Failure subtypes:
- accepts list or scalar from failure_subtype
- normalizes to list[str]

[normalized-record-shape]
Each record contains:
- experiment_id
- report_path
- report_filename
- model
- model_safe
- task_id
- task_family
- power_limit_percent
- run_index
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
- score_percent
- passed_checks
- total_checks
- task_failure_keys
- raw_report

Important derived logic:
- parse_valid uses syntax_valid if present, else failure_stage != parse
- runtime_valid is true when execution_status == ok, or when stage is not runtime/parse and execution_status is blank
- fully_correct is true when:
  - score.score_percent >= 100, or
  - all score.checks are truthy, or
  - success == true and usable_output == true

[summaries-and-rates]
summarize_records() computes:
- total_runs
- unique models / experiments / task_ids / task_families / tdp_levels
- failure_stage_distribution
- failure_type_distribution
- failure_subtype_distribution
- quality_class_distribution
- artifact_usability_distribution
- confidence_classification_distribution
- task_failure_key_distribution
- success_ladder
- rates:
  - parse_failure_rate
  - runtime_failure_rate
  - constraint_failure_rate
  - semantic_failure_rate
  - usable_output_rate
  - pipeline_usable_rate
  - fully_correct_rate
  - hard_failure_rate

Success ladder fields:
- total_runs
- returned_output
- parse_valid
- runtime_valid
- usable_output
- pipeline_usable
- fully_correct
- hard_failures

[dependencies]
Python standard library modules:
- argparse
- json
- re
- collections.Counter
- collections.defaultdict
- datetime
- pathlib
- typing

External tools:
- none

Upstream dependencies:
- evaluator report JSON files emitted by benchmark evaluators

Downstream consumers:
- rebuild_failure_join_chain.sh
- jarri_benchmark_failure_join.py
- any UI or analysis layer reading failure_records.json or grouped failure outputs

[callers]
Known direct caller:
- ./scripts/export/rebuild_failure_join_chain.sh

Likely manual usage:
- operator targeting one benchmark directory, a reports directory, or individual reports

Call relationship role:
- canonical builder of normalized failure records before failure/energy join

[verification]
Canonical command:
python3 ./benchmark/cli/jarri_benchmark_failure_aggregate.py ./benchmarks/fact_prose_v2 --output-dir ./benchmarks/_analysis_failures

Expected success signals:
- output directory is created
- all six JSON files are written
- failure_records.json contains record_count and records
- summary/group files include exporter_version and generated_at_utc
- stdout prints success: true

Quick sanity checks:
- verify input_report_count matches the number of discovered *_report.json files
- verify failure_records.json record_count matches the number of built records
- verify task_failure_keys are extracted from report.task_failures keys
- verify task_family inference is correct for reports missing explicit family
- verify fully_correct does not exceed usable_output in obviously broken cases
- verify grouped files contain expected top-level groups object

[failure_modes]
- no report files found: SystemExit with explicit message
- invalid JSON report: uncaught failure during load_json/build_record
- malformed report schema: fields may degrade to unknown, empty, or false-like values
- filename pattern mismatch: power_limit_percent and run_index can remain null
- missing model/task metadata: grouped summaries may accumulate unknown buckets
- inconsistent evaluator schemas: subtype, correctness, and validity inference can weaken silently

[notes]
This script is the canonical failure-record constructor in the current benchmark chain.

Important current truths frozen here:
- failure aggregation begins from per-run report JSON files, not from raw JSONL ledgers
- filename parsing is still important for power_limit_percent and run_index recovery
- task family inference has both task_id-based and experiment_id-based fallback logic
- fully_correct is intentionally broader than only score_percent == 100 when checks or success/usable signals indicate full correctness
- failure_records.json strips raw_report bodies from the exported records payload

This script should remain in the main tree and is one of the highest-priority benchmark analysis documents.
