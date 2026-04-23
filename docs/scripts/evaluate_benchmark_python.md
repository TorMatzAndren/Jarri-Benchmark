Title: evaluate_benchmark_python.py
ID: script-evaluate-benchmark-python
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
@scope:deterministic-execution
@scope:fixture-based-scoring
@entity:./scripts/benchmark/evaluate_benchmark_python.py
@script:./scripts/benchmark/evaluate_benchmark_python.py
@semantic:generic-python-benchmark-evaluator
@capability:extract-python-run-against-small-fixtures-and-score-output-deterministically
@state:documented
@truth:script-behavior
@risk:generic-and-weaker-than-specialized-coding-evaluators
@risk:stdout-shape-is-contract-sensitive
@risk:only-supports-three-generic-task-types
@output:single-evaluation-report-json

[summary]
evaluate_benchmark_python.py is a deterministic generic coding evaluator used for simple Python benchmark tasks. It extracts Python code from model output, syntax-checks it, runs it against a small temporary fixture, inspects stdout using task-specific regex and content checks, and emits a JSON evaluation report. It is an active evaluator in the canonical benchmark path for the generic coding task branch, but it is weaker and more generic than the specialized coding evaluators.

[purpose]
This script exists to evaluate basic Python scripting tasks without human review. It provides a small deterministic execution harness for three task classes:
- folder_scan
- csv_summary
- log_parser

It is suitable for generic code-output benchmarks where the contract is primarily:
- extract code
- execute code with one path argument
- inspect stdout for expected structure and values

[canonical_role]
active
generic
coding-evaluator
used-by-benchmark-run

[authority_boundary]
This script is allowed to:
- read one model answer file
- extract candidate Python code from raw text or fenced blocks
- syntax-check the code
- build a small temporary fixture
- execute the candidate with a single path argument
- inspect stdout deterministically
- write one evaluation report

This script is not allowed to:
- evaluate arbitrary languages
- evaluate complex coding tasks with bespoke fixtures beyond the three built-ins
- normalize downstream failure schema
- aggregate results across runs
- perform semantic reasoning about prose or factual tasks

[supported_tasks]
Supported task names:
- folder_scan
- csv_summary
- log_parser

Unsupported tasks:
- raise ValueError in build_fixture() or evaluate_stdout()

[inputs]
CLI arguments:
- input_file
- --task
- --save-code
- --save-report

Reads:
- the model answer file

Writes:
- optional extracted Python file via --save-code
- optional report JSON via --save-report

stdout:
- prints the full JSON report

[input_contract]
The input file is expected to contain either:
- a fenced Python code block
- raw Python text that begins like code
- or no extractable code

The candidate program is expected to accept one positional path argument:
- directory path for folder_scan
- CSV file path for csv_summary
- log file path for log_parser

The candidate is expected to print enough structured text to stdout for deterministic parsing.

[outputs]
The report contains:
- success
- input_file
- task
- extraction_mode
- syntax_valid
- syntax_error
- features
- runtime
- execution_status
- artifact_usability
- stdout_checks
- score
- expected_fixture

Runtime subfields:
- command
- returncode
- stdout
- stderr
- timed_out

Score subfields:
- checks
- passed_checks
- total_checks
- score_percent
- hard_failure

[execution_flow]
1. Parse CLI arguments.
2. Read the answer text.
3. Extract Python code from a fenced block or raw-text heuristic.
4. Run ast.parse syntax validation.
5. Detect simple static feature flags from the code text.
6. Build a temporary fixture for the selected task.
7. Write candidate.py into the temp directory.
8. Run candidate.py with the fixture path as its only argument.
9. If runtime succeeds, evaluate stdout with task-specific checks.
10. Determine execution_status.
11. Build a score object.
12. Derive artifact_usability from execution status and score.
13. Emit the JSON report.
14. Optionally save extracted code and report.

[code-extraction]
Extraction modes:
- markdown_fence
- raw_text
- none

Extraction logic:
- first fenced Python block wins
- otherwise treat the whole stripped answer as code if it starts like Python or contains def
- otherwise extraction fails

This means the script assumes a single primary candidate, not multiple alternatives.

[syntax-validation]
Syntax validation uses:
- ast.parse()

Outputs:
- syntax_valid boolean
- syntax_error text on failure

If no code is extracted:
- syntax_valid becomes false
- syntax_error becomes "No code extracted"

[feature-detection]
detect_features() records lightweight static hints:
- uses_argparse
- uses_os_walk
- uses_csv
- uses_counter
- uses_pathlib
- has_try_except
- mentions_stat
- contains_markdown_fence
- reads_stdin
- uses_input_prompt
- has_infinite_loop_pattern

These are descriptive only, except:
- reads_stdin can trigger contract_violation
- uses_input_prompt can trigger contract_violation

[fixtures]
The script builds one of three temporary fixtures.

[fixture-folder-scan]
build_folder_fixture() creates:
- a root directory with nested/deep, images, docs
- five files with fixed sizes

Expected facts include:
- expected_files = 5
- expected_folders_excluding_root = 4
- expected_folders_including_root = 5
- expected_recent_files = 5
- extensions_present = [.txt, .md, .jpg, .csv, .bin]
- expected_sizes_desc = [5000, 1400, 600, 180, 60]

[fixture-csv-summary]
build_csv_fixture() creates:
- sample.csv with 5 rows
- columns: name, age, city, score

Expected facts include:
- expected_rows = 5
- expected_columns = [name, age, city, score]
- expected_numeric_columns = [age, score]
- expected_text_columns = [name, city]

[fixture-log-parser]
build_log_fixture() creates:
- app.log with 7 fixed lines

Expected facts include:
- expected_total_lines = 7
- expected_info = 3
- expected_warning = 1
- expected_error = 3
- expected_earliest = 2026-04-14 10:00:00
- expected_latest = 2026-04-14 10:06:00
- expected_top_error = Database unavailable

[runtime-model]
The candidate is run as:
- python candidate.py <fixture-path>

Runtime controls:
- timeout = 20 seconds
- stdin = DEVNULL
- stdout/stderr captured

Timeout behavior:
- returncode becomes None
- stderr is set to "Timed out after 20 seconds"
- timed_out becomes true

[stdout-evaluation-folder-scan]
evaluate_folder_scan() checks for:
- total files line presence
- total folders line presence
- exact total file count
- total folder count matching either excluding-root or including-root expectation
- largest files listed in descending size order
- at least 5 parsed size lines
- extension count lines covering expected extensions
- recent files signal via words like "modified" or "last 7 days"

Important detail:
This evaluator is permissive about folder count because it accepts either:
- excluding root
- including root

[stdout-evaluation-csv-summary]
evaluate_csv_summary() checks for:
- exact row count line
- all expected column names mentioned
- numeric columns mentioned
- text columns mentioned
- min/max/avg terminology present
- common value analysis wording present

The check for common values is phrase-based and accepts several variants.

[stdout-evaluation-log-parser]
evaluate_log_parser() checks for:
- exact total line count
- exact INFO/WARNING/ERROR counts
- earliest timestamp present
- latest timestamp present
- common error text present

[execution-status]
determine_execution_status() returns:
- extraction_failed
- syntax_error
- runtime_not_attempted
- timeout
- runtime_error
- contract_violation
- ok

Contract violation occurs when static feature detection finds:
- sys.stdin usage
- input() usage

This means a candidate can execute successfully but still be marked as a contract violation.

[scoring]
If execution_status != ok:
- score_percent = 0
- hard_failure = true

If execution_status == ok:
- all boolean entries in stdout_checks are counted
- passed_checks / total_checks * 100

Non-boolean parsed values inside stdout_checks are preserved but do not count toward score.

Artifact usability:
- unusable if execution_status != ok
- usable if score_percent >= 80
- partial otherwise

[report-shape]
The report does not append the richer failure taxonomy used by specialized evaluators. It is a simpler generic evaluation report.

Important fields:
- execution_status
- artifact_usability
- stdout_checks
- score
- expected_fixture

Notably absent compared with specialized evaluators:
- failure_stage
- failure_type
- failure_subtype
- quality_class
- pipeline_usable
- normalized task_failures structure

This is important because benchmark_run.py treats this evaluator as a generic coding path and later derives common metrics from a thinner report shape.

[determinism]
The script is deterministic under stable Python/runtime conditions because:
- fixtures are generated from hardcoded content
- parsing uses deterministic regex and fixed phrase checks
- timeout is fixed
- no randomness is used
- no network access occurs

[dependencies]
Python standard library only:
- argparse
- ast
- json
- os
- re
- shutil
- subprocess
- sys
- tempfile
- textwrap
- pathlib
- typing

Note:
- shutil is imported but not used in the current file

[callers]
Known active caller:
- ./benchmark/cli/benchmark_run.py

Caller behavior:
- benchmark_run.py uses this script for generic coding tasks:
  - folder_scan
  - csv_summary
  - log_parser

Specialized coding tasks do not use this script:
- coding_fs_strict_v3 is routed to evaluate_coding_fs_strict_v2.py instead

[position-in-system]
This script is active, but not the strongest coding evaluation layer. It is best understood as the generic fallback evaluator for simple Python stdout-contract tasks inside the current benchmark stack.

It is below specialized evaluators in strictness and reporting richness.

[verification]
Canonical command pattern:
python3 ./scripts/benchmark/evaluate_benchmark_python.py \
  <answer.txt> \
  --task folder_scan \
  --save-code <candidate.py> \
  --save-report <report.json>

Good verification targets:
- one valid folder scan script
- one valid CSV summary script
- one valid log parser script
- one answer with no code
- one syntax-invalid code sample
- one script that calls input()
- one script that times out

Expected success signals:
- execution_status = ok
- stdout_checks populated
- score passed/total values make sense
- artifact_usability becomes usable or partial

[failure_modes]
- no code found: extraction_failed
- invalid Python syntax: syntax_error
- candidate crashes: runtime_error
- candidate blocks or loops: timeout
- candidate reads stdin or prompts for input: contract_violation
- candidate runs but prints wrong structure/content: ok with low score and partial usability
- unsupported task value: argparse rejects it or build_fixture/evaluate_stdout raises ValueError

[important_current_truths]
- This is an active evaluator in the benchmark_run path.
- It is generic and contract-oriented, not a rich semantic code evaluator.
- It uses temporary fixtures and actual subprocess execution.
- It scores only boolean stdout checks.
- It does not emit the full normalized failure schema by itself.
- It is more permissive and thinner than the specialized coding evaluators.

[cleanup-notes]
Do not mark this as deprecated. It is still used by benchmark_run.py for the generic coding task branch.

Potential future hardening:
- remove unused shutil import
- add normalized failure taxonomy fields directly in this evaluator
- separate parsed-details fields from pass/fail checks more explicitly
- add stricter output contracts per task
- add a safe sandbox layer if runtime isolation becomes more important

[operator-notes]
This is worth keeping documented as active infrastructure, but the more benchmark-critical coding truth path is now in the specialized evaluators and benchmark_run orchestration around them.
