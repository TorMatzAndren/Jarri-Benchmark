Title: evaluate_constrained_rewrite_v2.py
ID: script-evaluate-constrained-rewrite-v2
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:language-evaluation
@scope:constrained-rewrite
@scope:deterministic-evaluation
@scope:failure-taxonomy
@entity:./benchmark/evaluators/evaluate_constrained_rewrite_v2.py
@script:./benchmark/evaluators/evaluate_constrained_rewrite_v2.py
@semantic:constrained-rewrite-evaluator
@capability:evaluate-constrained-rewrite-v2-answers-against-a-fixed-bullet-format-and-content-contract
@state:documented
@truth:script-behavior
@risk:file-name-version-mismatch-can-confuse-maintainers
@risk:task-is-hardcoded-to-one-fixed-token-and-phrase contract
@risk:strict-bullet-format-and punctuation rules create format hard failures
@output:optional-report-json-path

[summary]
evaluate_constrained_rewrite_v2.py is the active deterministic evaluator used by benchmark_run.py for the language task family. It checks whether the answer is formatted as exactly three bullet points, each with exactly twelve words, containing required tokens and phrases while avoiding forbidden punctuation, and it emits a structured report with normalized benchmark failure fields. This script is active, authoritative, and part of the current benchmark truth path.

[purpose]
This script exists to evaluate a constrained rewriting task where the model must compress and restate information under a strict output contract. It provides deterministic scoring and failure taxonomy production for the current constrained rewrite benchmark task.

[canonical_role]
authoritative
active
runtime-critical
evaluator-boundary

[authority_boundary]
This script is allowed to:
- read one model answer file
- parse bullet-line structure from plain text
- validate bullet count, word count, terminal punctuation, required tokens, required phrases, and forbidden punctuation
- assign execution_status, failure_type, failure_stage, failure_subtype, success, usability, and quality class
- emit a structured report JSON

This script is not allowed to:
- orchestrate benchmark runs
- aggregate results across runs
- evaluate unrelated language tasks
- define benchmark manifests

[inputs]
CLI positional arguments:
- input_file

CLI optional options:
- --save-report

Environment assumptions:
- input file exists and is readable
- answer is expected as plain text with bullet lines beginning `- `

Hardcoded task constants:
- evaluator_version: constrained_rewrite_eval_v3
- task_id: constrained_rewrite_v2
- task_family: language

Hardcoded content requirements:
- required tokens:
  - March
  - 3rd
  - 2021
  - Arcturus
  - Systems
  - 4.2
  - 5.6
  - 12
  - Lina
  - Verne
  - three
  - new
  - European
  - markets
- required phrases:
  - Arcturus Systems
  - Lina Verne
  - three new European markets
- forbidden punctuation regex:
  - [;:!?()"]

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
- required_tokens
- required_phrases
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
3. Split text into lines and extract nonempty bullet lines that begin with `- `.
4. Count words in each bullet line excluding the bullet prefix.
5. Join bullet lines and test for required tokens and required phrases.
6. Detect forbidden punctuation and bullets missing terminal periods.
7. Build boolean checks for:
   - exactly three bullets
   - exactly twelve words in each bullet
   - all bullets ending with period
   - all required tokens present
   - all required phrases present
   - no forbidden punctuation
8. Build failure_subtype and task_failures for bullet count mismatch, word count violations, missing tokens, missing phrases, forbidden punctuation, terminal punctuation violations, and partial semantic match.
9. If bullet count is wrong, mark execution_status as format_violation and hard_failure = true.
10. Otherwise keep execution_status = ok and compute score from checks.
11. Derive failure_stage, failure_type, success, artifact usability, and task metrics.
12. Write the report JSON if requested and print it to stdout.

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
- answer is a plain text bullet list, not JSON
- token and phrase inclusion are case-sensitive substring checks in the raw bullet text
- exact word count is part of the task contract

[callers]
Known direct caller:
- ./benchmark/cli/benchmark_run.py uses this for task_family == language

Possible manual usage:
- direct operator evaluation of one constrained-rewrite answer file

Call relationship role:
- canonical evaluator for the current language benchmark task

[verification]
Canonical command:
python3 ./benchmark/evaluators/evaluate_constrained_rewrite_v2.py <answer.txt> --save-report <report.json>

Expected success signals:
- report JSON is printed
- task_id in report is constrained_rewrite_v2
- evaluator_version in report is constrained_rewrite_eval_v3
- success is true only when the output is fully correct and score_percent is 100.0

Quick sanity checks:
- confirm wrong bullet count yields execution_status = format_violation and hard_failure = true
- confirm missing required tokens yields missing_required_token and constraint_violation
- confirm missing required phrases yields missing_required_phrase and semantic_error
- confirm forbidden punctuation yields forbidden_punctuation_present
- confirm bullets not ending with period yield terminal_punctuation_violation
- confirm partial phrase coverage yields partial_semantic_match
- confirm exact correct answer yields failure_type = null, failure_stage = null, and success = true

[failure_modes]
- fewer or more than three bullet lines: format hard failure
- wrong per-bullet word count: constraint violation
- missing required tokens: constraint violation
- missing required phrases: semantic error
- forbidden punctuation present: constraint violation
- bullets missing terminal periods: constraint violation
- partial phrase match: semantic error
- hardcoded task-specific contract means this script is not generic beyond this one rewrite benchmark

[notes]
This script is active and should not be deprecated. benchmark_run.py directly calls it for the language task family.

There is another naming/version mismatch to preserve explicitly:
- file path name: evaluate_constrained_rewrite_v2.py
- evaluator version: constrained_rewrite_eval_v3
- task id evaluated: constrained_rewrite_v2

That mismatch is real and should remain documented so later cleanup does not accidentally break the active routing.

This evaluator is intentionally strict and contract-based. It does not try to infer “good enough” paraphrase quality outside the hardcoded bullet, word-count, token, phrase, and punctuation requirements. It is both a scorer and a direct producer of benchmark failure taxonomy for this task.
