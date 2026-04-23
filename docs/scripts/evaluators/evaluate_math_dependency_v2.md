Title: evaluate_math_dependency_v2.py
ID: script-evaluate-math-dependency-v2
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:math-evaluation
@scope:deterministic-evaluation
@scope:failure-taxonomy
@entity:./benchmark/evaluators/evaluate_math_dependency_v2.py
@script:./benchmark/evaluators/evaluate_math_dependency_v2.py
@semantic:math-dependency-evaluator
@capability:evaluate-math-dependency-v1-answers-against-a-deterministic-expected-output
@state:documented
@truth:script-behavior
@risk:file-name-version-mismatch-can-confuse-maintainers
@risk:strict-output-format-requirements-create-format-hard-failures
@risk:precision-and-rounding-policy-is hardcoded
@output:optional-report-json-path

[summary]
evaluate_math_dependency_v2.py is the active deterministic evaluator used by benchmark_run.py for the math task family, specifically for task id `math_dependency_v1`, even though the script filename itself still carries a `_v2` suffix and the evaluator version is `math_dependency_eval_v3`. It computes the expected arithmetic chain internally, parses a required sectioned output format from the model answer, scores exact totals, filtered percentages, rounding, and final dependency logic, and emits a normalized evaluator report with benchmark failure fields. This script is active, authoritative, and part of the current benchmark truth path.

[purpose]
This script exists to evaluate a constrained math dependency task where the model must transform a fixed set of values into initial percentages, remove the smallest value, recompute filtered percentages, and produce a final dependency-based score. It solves both scoring and failure taxonomy production for this math benchmark task.

[canonical_role]
authoritative
active
runtime-critical
evaluator-boundary

[authority_boundary]
This script is allowed to:
- read one model answer file
- compute the expected correct math result internally
- parse a strict sectioned text output format
- score exact totals, removals, percentages, rounding, and final score
- assign execution_status, failure_type, failure_stage, failure_subtype, success, usability, and quality class
- emit a structured report JSON

This script is not allowed to:
- orchestrate benchmark runs
- aggregate across runs
- normalize ledger rows globally
- evaluate other math tasks outside its hardcoded dependency problem
- define benchmark manifests

[inputs]
CLI positional arguments:
- input_file

CLI optional options:
- --save-report

Environment assumptions:
- input file exists and is readable
- model output is expected as plain text with exact section markers and line formats

Hardcoded task constants:
- task_id: math_dependency_v1
- task_family: math
- values:
  - A = 120
  - B = 80
  - C = 150
  - D = 50

Required output sections:
- === INITIAL ===
- === FILTERED ===
- === FINAL ===

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
2. Read the answer text file.
3. Compute the expected correct totals, filtered percentages, removed label, and final score from the hardcoded values.
4. Split answer text into lines and detect whether the required sections exist.
5. Locate section positions and validate section order.
6. Parse:
   - initial total
   - filtered total
   - final score
   - initial percentages for A/B/C/D
   - filtered percentages for A/B/C after removing the smallest label
7. Build boolean checks for presence, exactness, ordering, approximate numeric correctness, and removal correctness.
8. Build failure_subtype and task_failures entries for all detected mismatches.
9. Convert failure_subtypes into failure_stage and failure_type.
10. Compute score, success, usability, and quality class.
11. Write the report JSON if requested and print it to stdout.

[dependencies]
Python standard library modules:
- argparse
- json
- re
- decimal
- pathlib
- typing

External tools:
- none beyond Python itself

Runtime assumptions:
- answer is a plain text structured report rather than JSON
- percentage tolerance is fixed through approx_equal with a default tolerance of 0.02
- half-up rounding to two decimals is the canonical evaluator policy

[callers]
Known direct caller:
- ./benchmark/cli/benchmark_run.py uses this for task_family == "math"

Possible manual usage:
- direct operator evaluation of one math answer file

Call relationship role:
- canonical evaluator for the current math benchmark task

[verification]
Canonical command:
python3 ./benchmark/evaluators/evaluate_math_dependency_v2.py <answer.txt> --save-report <report.json>

Expected success signals:
- report JSON is printed
- task_id in report is math_dependency_v1
- evaluator_version in report is math_dependency_eval_v3
- success is true only for fully correct output with score_percent 100.0

Quick sanity checks:
- confirm file name is _v2 while evaluator_version is v3 and task_id is math_dependency_v1
- verify missing required sections produce execution_status = format_violation and hard_failure = true
- verify wrong arithmetic totals produce arithmetic_error semantics
- verify wrong final dependency score produces dependency_error
- verify near-but-not-exact percentage deviations produce percentage_mismatch or rounding_error depending on delta
- verify parsed smallest label removal is enforced through removed_smallest_value

[failure_modes]
- missing section headers: hard failure with format-oriented semantics
- invalid section order: hard failure with format-oriented semantics
- missing totals or percentages: parse_failure-oriented semantics
- wrong initial or filtered totals: arithmetic_error
- smallest value not removed: logic_error
- wrong final score: dependency_error
- wrong percentages: precision_error
- hardcoded task mismatch risk: evaluator only knows this one fixed problem and is not generic

[notes]
This script is active and should not be deprecated. benchmark_run.py directly calls it for the math task family.

There is an important naming/version mismatch to preserve explicitly:
- file path name: evaluate_math_dependency_v2.py
- evaluator version: math_dependency_eval_v3
- task id evaluated: math_dependency_v1

That mismatch is real and should remain documented so future cleanup does not break the active routing.

This evaluator is strict-format and deterministic by design. It does not try to infer intent from loosely phrased output; it requires a structured sectioned answer and then measures exact or near-exact correctness against internally computed expected values.

This script is both a scorer and a failure-schema producer for the current math benchmark task.
