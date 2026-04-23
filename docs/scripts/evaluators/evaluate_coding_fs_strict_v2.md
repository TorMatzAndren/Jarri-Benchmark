Title: evaluate_coding_fs_strict_v2.py
ID: script-evaluate-coding-fs-strict-v2
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:coding-evaluation
@scope:strict-filesystem-evaluation
@scope:deterministic-evaluation
@scope:failure-taxonomy
@entity:./benchmark/evaluators/evaluate_coding_fs_strict_v2.py
@script:./benchmark/evaluators/evaluate_coding_fs_strict_v2.py
@semantic:strict-coding-filesystem-evaluator
@capability:evaluate-coding-fs-strict-v3-answers-against-a-deterministic-filesystem-fixture
@state:documented
@truth:script-behavior
@risk:script-name-version-mismatch-can-confuse-maintainers
@risk:stdout-format-parsing-is-strict-and brittle by design
@risk:executes generated code locally in temp fixture with timeout
@output:optional-report-json-and-optional-saved-code-path

[summary]
evaluate_coding_fs_strict_v2.py is the active deterministic evaluator used for the benchmark task `coding_fs_strict_v3`, despite the file itself still carrying a `_v2` name. It extracts Python code from model output, builds a controlled filesystem fixture, runs the candidate code, parses a required stdout format, scores exact semantic and ordering correctness, and emits a benchmark report with normalized failure fields. This script is active, authoritative, and part of the current benchmark truth path.

[purpose]
This script exists to evaluate the strict filesystem coding benchmark task where the model must inspect a directory tree and print an exact structured summary. It solves both task scoring and failure taxonomy generation for the `coding_fs_strict_v3` benchmark task.

[canonical_role]
authoritative
active
runtime-critical
evaluator-boundary

[authority_boundary]
This script is allowed to:
- read a model answer file
- extract Python code from markdown or raw text
- syntax-check candidate code
- build a deterministic filesystem fixture
- execute the candidate with timeout
- parse stdout into required benchmark sections
- compute exact and partial correctness checks
- assign execution_status, failure_type, failure_stage, failure_subtype, quality_class, usability, and success

This script is not allowed to:
- orchestrate full benchmark experiments
- aggregate runs
- normalize benchmark ledgers globally
- evaluate unrelated coding tasks like csv_summary or log_parser
- define benchmark manifests

[inputs]
CLI positional arguments:
- input_file

CLI optional options:
- --save-code
- --save-report

Environment assumptions:
- extracted candidate code can be executed locally
- temp directory creation works
- filesystem and subprocess execution are available
- candidate program is expected to accept one path argument

Files read:
- model answer input file

Files optionally written:
- extracted code at --save-code
- evaluator report JSON at --save-report

Temporary artifacts:
- candidate.py in a temp directory
- a deterministic filesystem tree fixture in that same temp directory

[outputs]
Structured evaluator report printed to stdout and optionally written to --save-report.

Report fields include:
- success
- evaluator_version
- task_id
- task_family
- extraction_mode
- syntax_valid
- syntax_error
- runtime
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
- expected_fixture
- task_metrics
- task_failures

stdout behavior:
- prints the report JSON

stderr behavior:
- argparse errors surface normally
- generated candidate runtime errors are captured into structured runtime output
- timeout is captured structurally rather than crashing the evaluator

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: --save-code and --save-report outputs are overwritten if provided
- statefulness: stateless relative to the answer input aside from temp fixture creation and candidate execution

[execution_flow]
1. Parse CLI arguments.
2. Read raw answer text from the input file.
3. Extract code from the first fenced Python block or from raw text heuristics.
4. Syntax-check the extracted code if any code was found.
5. Create a temporary directory and build the deterministic filesystem fixture.
6. Write candidate.py into the temp directory when code and syntax are valid.
7. Optionally save extracted candidate code to --save-code.
8. Run candidate.py against the generated fixture path.
9. Determine execution_status from extraction, syntax, runtime return code, or timeout.
10. If runtime succeeds, parse stdout sections for:
   - extension distribution
   - largest files
   - top directories by direct file count
   - summary values and checksum
11. Compare parsed values against exact expected fixture outputs.
12. Build fine-grained boolean checks and detailed task_failures/task_metrics payloads.
13. Convert execution and check results into score, failure_subtype, failure_stage, failure_type, success, quality_class, and usability.
14. Write the report JSON if requested and print it to stdout.

[dependencies]
Python standard library modules:
- argparse
- ast
- json
- os
- re
- subprocess
- sys
- tempfile
- pathlib
- typing

External tools:
- none beyond Python itself

Runtime assumptions:
- candidate code is a CLI Python script that prints the expected report format
- stdout format is intentionally strict
- runtime timeout is fixed at 60 seconds

[callers]
Known direct caller:
- ./benchmark/cli/benchmark_run.py routes task_name coding_fs_strict_v3 into this script

Possible manual usage:
- direct operator evaluation of one strict-filesystem coding answer

Call relationship role:
- canonical evaluator for the strict filesystem coding task

[verification]
Canonical command:
python3 ./benchmark/evaluators/evaluate_coding_fs_strict_v2.py <answer.txt> --save-code <candidate.py> --save-report <report.json>

Expected success signals:
- report JSON is printed
- task_id in report is coding_fs_strict_v3
- evaluator_version in report is coding_fs_strict_eval_v3
- failure and quality fields are present
- expected_fixture contains deterministic fixture expectations

Quick sanity checks:
- confirm file name is _v2 while evaluator_version is v3 and task_id is coding_fs_strict_v3
- verify a perfect candidate yields:
  - execution_status = ok
  - failure_type = null
  - success = true
  - pipeline_usable = true
  - score.score_percent = 100.0
- verify syntax-broken code yields syntax_error / parse_failure
- verify malformed output yields invalid_output_format and constraint-oriented failure typing
- verify partially correct semantic output gets partial_semantic_match when appropriate

[failure_modes]
- no code extracted: execution_status = extraction_failed, failure_stage = format
- syntax error: execution_status = syntax_error, failure_stage = parse
- runtime exception: execution_status = runtime_error, failure_stage = execute
- timeout: execution_status = timeout, failure_stage = execute
- invalid stdout structure: failure_subtype includes invalid_output_format
- exact summary mismatch: summary/checksum failure subtypes emitted
- wrong extension distribution, largest files, or top directories: semantic/constraint failure subtypes emitted
- output ordering mistakes: unsorted subtype flags emitted
- version-name confusion: script filename suggests v2 even though active evaluator version and task target are v3

[notes]
This script is active and should not be deprecated. The key documented truth is that:
- file path name: evaluate_coding_fs_strict_v2.py
- evaluator version: coding_fs_strict_eval_v3
- task id evaluated: coding_fs_strict_v3

That mismatch is real and should be preserved explicitly in docs so future cleanup does not accidentally break the current routing used by benchmark_run.py.

Unlike evaluate_benchmark_python.py, this evaluator is highly task-specific and produces a richer benchmark-native failure taxonomy:
- failure_type
- failure_stage
- failure_subtype
- quality_class
- usable_output
- pipeline_usable
- success

That makes it not just a scorer, but also a direct failure-schema producer for this benchmark task.

This script should remain in the main benchmark tree unless and until a clearly named replacement fully takes over the coding_fs_strict_v3 route.
