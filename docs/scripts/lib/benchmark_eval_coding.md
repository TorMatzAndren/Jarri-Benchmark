Title: benchmark_eval_coding.py
ID: script-benchmark-eval-coding
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:legacy-evaluation
@scope:coding-evaluation
@entity:./benchmark/lib/benchmark_eval_coding.py
@script:./benchmark/lib/benchmark_eval_coding.py
@semantic:legacy-coding-eval-stub
@capability:execute-a-python-file-and-return-a-minimal-pass-fail-result
@state:documented
@truth:script-behavior
@risk:far-too-thin-for-current-canonical-benchmark-truth
@risk:no-fixture-based-validation
@risk:no-task-specific-scoring-or-failure-taxonomy
@output:return-value-only

[summary]
benchmark_eval_coding.py is a tiny legacy helper that executes a Python file and returns a minimal pass/fail style dictionary based only on whether the script exits successfully. It does not use fixtures, task contracts, stdout validation, or modern benchmark failure schema. Current evidence strongly suggests it is a historical evaluation stub and not part of the active canonical benchmark truth path.

[purpose]
This script appears to have existed as a minimal coding evaluation helper before the current deterministic evaluator stack was developed. Its purpose is only to run code and classify the outcome very coarsely.

[canonical_role]
legacy
deprecation-ready
helper-only
non-authoritative

[authority_boundary]
This script is allowed to:
- run a Python file with a 10 second timeout
- classify the execution result coarsely
- return a minimal dictionary

This script is not allowed to:
- define modern coding benchmark truth
- validate task-specific correctness
- use deterministic fixtures
- emit canonical benchmark reports
- define failure_stage, failure_subtype, quality_class, or modern score structures

[inputs]
Function input:
- code_path

Environment assumptions:
- python3 executable exists
- target code path exists and is runnable

Files read:
- target Python code file indirectly through subprocess

[outputs]
Return value only:
- execution_status
- artifact_usability
- score

No files written.

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: none
- statefulness: stateless except for executing the candidate script

[execution_flow]
1. Run `python3 <code_path>` with timeout 10 seconds.
2. If execution succeeds, return success / usable / 100.0.
3. If execution raises CalledProcessError, return runtime_error / unusable / 0.0.
4. If any other exception occurs, return failure / unusable / 0.0.

[dependencies]
Python standard library modules:
- subprocess

External tools:
- python3

[callers]
No confirmed active caller:
- none identified in the current benchmark_run.py + evaluator stack

[verification]
Canonical command pattern:
python3 -c "from benchmark.lib.benchmark_eval_coding import evaluate; print(evaluate('/path/to/script.py'))"

Expected success signal:
- returns a small dictionary

[failure_modes]
- missing python3: subprocess failure
- missing code path: failure classification
- runtime error in candidate: runtime_error
- timeout or other exception: failure

[notes]
This helper is much too weak to represent current benchmark truth. It should be treated as a legacy stub and is likely deprecation-ready.
