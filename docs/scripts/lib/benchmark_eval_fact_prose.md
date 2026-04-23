Title: benchmark_eval_fact_prose.py
ID: script-benchmark-eval-fact-prose
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
@scope:fact-prose-evaluation
@entity:./benchmark/lib/benchmark_eval_fact_prose.py
@script:./benchmark/lib/benchmark_eval_fact_prose.py
@semantic:legacy-fact-prose-eval-stub
@capability:return-a-minimal-baseline-score-for-nonempty-output
@state:documented
@truth:script-behavior
@risk:far-too-thin-for-current-canonical-benchmark-truth
@risk:ground-truth-is-barely-used
@risk:no-task-specific-semantic-or-constraint-evaluation
@output:return-value-only

[summary]
benchmark_eval_fact_prose.py is a tiny legacy helper that loads ground truth JSON and then assigns 100 if the output text is nonempty, otherwise 0. It does not perform meaningful semantic evaluation, constraint checking, or modern benchmark failure normalization. Current evidence strongly suggests it is a historical baseline stub rather than an active part of the canonical benchmark truth path.

[purpose]
This script appears to have existed as a minimal deterministic baseline before the current fact/prose evaluator was built. Its purpose is only to return a trivial score based on output presence.

[canonical_role]
legacy
deprecation-ready
helper-only
non-authoritative

[authority_boundary]
This script is allowed to:
- load a ground truth JSON file
- assign a trivial score based on whether output text is nonempty
- return a tiny result dictionary

This script is not allowed to:
- define current fact/prose benchmark truth
- perform semantic matching
- perform schema recovery
- emit normalized benchmark failure fields
- replace evaluate_benchmark_task.py

[inputs]
Function inputs:
- output_text
- ground_truth_path

Environment assumptions:
- ground truth path exists and is JSON-readable

Files read:
- ground_truth_path

[outputs]
Return value only:
- schema_adherence_score
- semantic_shadow_score
- score
or
- score / error on invalid ground truth

No files written.

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior: none
- statefulness: stateless

[execution_flow]
1. Try to read and parse the ground truth JSON file.
2. If ground truth is invalid, return score 0.0 with error invalid_ground_truth.
3. If output_text is nonempty after stripping, return 100.0 across the small score fields.
4. Otherwise return 0.0.

[dependencies]
Python standard library modules:
- json

External tools:
- none

[callers]
No confirmed active caller:
- none identified in the current benchmark_run.py + evaluator stack

[verification]
Canonical command pattern:
python3 -c "from benchmark.lib.benchmark_eval_fact_prose import evaluate; print(evaluate('hello', '/path/to/gt.json'))"

Expected success signal:
- returns a very small dictionary

[failure_modes]
- invalid ground truth path or JSON: returns invalid_ground_truth
- empty output text: score 0.0
- nonempty output text regardless of correctness: score 100.0

[notes]
This helper is clearly not aligned with the current benchmark doctrine. It should be treated as a legacy stub and is likely deprecation-ready.
