Title: evaluate_logic_consistency_v2.py
ID: script-evaluate-logic-consistency-v2
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:knowledge-evaluation
@scope:logic-consistency
@scope:deterministic-evaluation
@scope:failure-taxonomy
@entity:./benchmark/evaluators/evaluate_logic_consistency_v2.py
@script:./benchmark/evaluators/evaluate_logic_consistency_v2.py
@semantic:logic-consistency-evaluator
@capability:evaluate-logic-consistency-v2-answers-against-a-fixed-contradiction-target
@state:documented
@truth:script-behavior
@risk:file-name-version-mismatch-can-confuse-maintainers
@risk:task-is-hardcoded-to-one-expected-contradiction-pair-set
@risk:strict-format-requirements-create-format-hard-failures
@output:optional-report-json-path

[summary]
evaluate_logic_consistency_v2.py is the active deterministic evaluator used by benchmark_run.py for the knowledge task family. It checks whether the answer correctly reports that the statement set is inconsistent, requires a specific contradiction pair set, enforces section markers, and emits a structured report with normalized benchmark failure fields. This script is active, authoritative, and part of the current benchmark truth path.

[purpose]
This script exists to evaluate a constrained logic-consistency task where the model must identify whether a statement set is consistent and enumerate the required contradiction pair or pairs. It provides deterministic scoring and failure taxonomy production for the knowledge benchmark task.

[canonical_role]
authoritative
active
runtime-critical
evaluator-boundary

[authority_boundary]
This script is allowed to:
- read one model answer file
- parse a required report-style text format
- validate the presence of required sections
- validate the consistency flag
- validate contradiction pair detection
- assign execution_status, failure_type, failure_stage, failure_subtype, success, usability, and quality class
- emit a structured report JSON

This script is not allowed to:
- orchestrate benchmark runs
- aggregate results across runs
- evaluate unrelated knowledge tasks
- define benchmark manifests

[inputs]
CLI positional arguments:
- input_file

CLI optional options:
- --save-report

Environment assumptions:
- input file exists and is readable
- answer is expected in a plain text report format

Hardcoded task constants:
- evaluator_version: logic_consistency_eval_v3
- task_id: logic_consistency_v2
- task_family: knowledge
- expected consistent flag: NO
- expected contradiction pair set: (3, 4)

Required sections:
- === ANALYSIS ===
- === CONTRADICTIONS ===

Files read:
- model answer file

Files optionally written:
- evaluator report JSON at --save-report

[outputs]
Structured evaluator report printed to stdout and optionally written to --save-report.

Report fields include:
- success
- evaluator_version
- task_id
- task_family
- execution_status
- failure_type
- failure_stage
- failure_subtype
- quality_class
- artifact_usability
- usable_output
- pipeline_usable
- hard_failure
- score
- expected
- task_metrics
- task_failures

stdout behavior:
- prints the report JSON

stderr behavior:
- argparse errors surface normally
- file read/write errors surface as Python exceptions

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: --save-report output is overwritten if provided
- statefulness: stateless relative to the answer input

[execution_flow]
1. Parse CLI arguments.
2. Read the answer text.
3. Detect whether required ANALYSIS and CONTRADICTIONS sections exist.
4. Parse the `Consistent: YES|NO` line.
5. Parse contradiction-pair lines matching `Statement X conflicts with Statement Y`.
6. Normalize contradiction pairs into sorted tuple form.
7. Compare parsed pairs against the expected fixed pair set.
8. Build boolean checks for section presence, consistency flag, required pair detection, exact pair set, and duplicate/symmetric mentions.
9. Build failure_subtype and task_failures payloads for missing sections, wrong consistency flag, missing pairs, extra pairs, exact mismatch, partial detection, and duplicate mentions.
10. Derive execution_status, hard_failure, score, failure_stage, failure_type, success, artifact usability, and task metrics.
11. Write the report JSON if requested and print it to stdout.

[dependencies]
Python standard library modules:
- argparse
- json
- re
- pathlib
- typing

External tools:
- none beyond Python itself

Runtime assumptions:
- answer format is plain text rather than JSON
- only one fixed expected contradiction set is valid for this task

[callers]
Known direct caller:
- ./benchmark/cli/benchmark_run.py uses this for task_family == knowledge

Possible manual usage:
- direct operator evaluation of one logic-consistency answer file

Call relationship role:
- canonical evaluator for the current knowledge benchmark task

[verification]
Canonical command:
python3 ./benchmark/evaluators/evaluate_logic_consistency_v2.py <answer.txt> --save-report <report.json>

Expected success signals:
- report JSON is printed
- task_id in report is logic_consistency_v2
- evaluator_version in report is logic_consistency_eval_v3
- success is true only when the output is fully correct and score_percent is 100.0

Quick sanity checks:
- confirm required sections missing produce execution_status = format_violation and hard_failure = true
- confirm wrong `Consistent:` flag yields incorrect_consistency_flag
- confirm missing (3,4) contradiction pair yields missing_required_pair and logic_error semantics
- confirm extra contradiction pairs yield extra_pair_detected and over_inference semantics
- confirm duplicate symmetric restatements are tracked via symmetric_duplicate_pair
- confirm exact correct answer yields failure_type = null, failure_stage = null, and success = true

[failure_modes]
- missing ANALYSIS section: format hard failure
- missing CONTRADICTIONS section: format hard failure
- missing consistency flag: format hard failure
- wrong consistency flag: semantic failure
- missing required pair: logic_error
- extra detected pair: over_inference
- exact pair set mismatch: semantic mismatch record
- partial overlap with expected pair set: partial_pair_detection
- symmetric duplicate pair mentions: semantic noise / duplication issue
- hardcoded single-task nature: script is not generic beyond this fixed contradiction problem

[notes]
This script is active and should not be deprecated. benchmark_run.py directly calls it for the knowledge task family.

There is another important naming/version mismatch to preserve:
- file path name: evaluate_logic_consistency_v2.py
- evaluator version: logic_consistency_eval_v3
- task id evaluated: logic_consistency_v2

That means the file naming lineage is older than the current evaluator versioning, and the docs must preserve that explicitly.

This evaluator is not a broad logical reasoner. It is a strict task-specific checker for one known contradiction target and one required contradiction pair set. It is both a scorer and a direct producer of benchmark failure taxonomy for this task.
