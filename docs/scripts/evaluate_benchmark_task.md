Title: evaluate_benchmark_task.py
ID: script-evaluate-benchmark-task
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:fact-evaluation
@scope:prose-evaluation
@scope:failure-normalization
@scope:deterministic-scoring
@entity:./scripts/benchmark/evaluate_benchmark_task.py
@script:./scripts/benchmark/evaluate_benchmark_task.py
@semantic:deterministic-fact-prose-evaluator
@capability:evaluate-fact-and-prose-benchmark-answers-against-ground-truth-and-emit-normalized-failure-schema
@state:documented
@truth:script-behavior
@risk:task-specific-heuristics-are-hardcoded
@risk:ground-truth-schema-must-match-task-expectations
@risk:json-recovery-can-upgrade-bad-output-into-partial-usable-output
@output:single-evaluation-report-json

[summary]
evaluate_benchmark_task.py is the main deterministic evaluator for Jarri fact and prose benchmark tasks. It reads a model answer file plus a task-specific ground truth JSON, evaluates the answer with hardcoded task evaluators, and emits a normalized report containing score, hallucination flags, schema behavior, derived metrics, and a canonical failure schema. This is an active evaluator in the canonical benchmark path.

[purpose]
This script exists to score structured fact and prose tasks without LLM judgment, probabilistic grading, or vague natural-language interpretation. It provides deterministic scoring, recovery-aware JSON parsing, and standardized failure normalization so downstream benchmark analysis can compare models on a stable basis.

[canonical_role]
authoritative
active
evaluation-critical
fact-prose-core

[authority_boundary]
This script is allowed to:
- read answer text from a file
- read ground truth JSON from a file
- evaluate one supported task at a time
- recover JSON from malformed responses in limited deterministic ways
- compute task-specific scores and derived metrics
- append normalized success and failure fields
- write one JSON report

This script is not allowed to:
- execute model code
- browse for facts
- modify benchmark manifests
- aggregate multiple reports
- normalize full benchmark ledgers
- infer unsupported tasks

[supported_tasks]
Supported task IDs:
- fact_task_1
- fact_task_2
- fact_task_3
- prose_task_1
- prose_task_2
- prose_task_3

Task dispatch map:
- EVALUATORS dictionary maps task IDs to evaluator functions

Unsupported task handling:
- exits with SystemExit if task ID is not present in EVALUATORS

[inputs]
CLI arguments:
- answer_file
- --task-id
- --ground-truth
- --save-report

Reads:
- answer text file
- ground truth JSON file

Writes:
- JSON report to --save-report

stdout:
- prints the full JSON report

[input_contract]
The answer file is plain text and may contain:
- direct JSON
- fenced JSON
- multiple fenced blocks
- malformed but recoverable JSON-like output

The ground truth file must be valid JSON and must match the structure expected by the selected task evaluator.

Ground truth expectations by task:
- fact_task_1: object with items, entities, categories, and fields
- fact_task_2: object with required_atomic_claims and support mappings
- fact_task_3: object with items containing classification and accepted note patterns
- prose_task_1: object with max_words, source_word_count, and key_units
- prose_task_2: object with required_sections, required_step_properties, and required_content_units
- prose_task_3: object with max_words, banned_terms, and analogy_patterns

[outputs]
The report always includes:
- evaluator_version
- task_id
- answer_file
- ground_truth_file
- success
- failure_stage
- failure_type
- failure_subtype
- score object

Typical report fields:
- format_valid
- usable_output
- pipeline_usable
- schema_coerced
- hard_failure
- hard_failure_reason
- confidence_classification
- hallucination_flags
- score
- derived_metrics

Score subfields may include:
- score_percent
- score_per_process
- factual_accuracy_score
- hallucination_penalty
- reasoning_consistency_score
- compression_efficiency_score
- constraint_adherence_score
- schema_adherence_score
- semantic_shadow_score

[execution_flow]
1. Parse CLI arguments.
2. Verify task ID is supported.
3. Read answer text.
4. Load ground truth JSON.
5. Dispatch to the evaluator function for the given task.
6. Attach task_id, answer_file, and ground_truth_file to the report.
7. Append normalized success/failure schema through append_normalized_failure_schema().
8. Write the report JSON.
9. Print the report JSON and exit.

[core_helpers]
Key helper families:

Text normalization:
- normalize()
- count_words()
- clamp()
- classify_confidence()

JSON coercion and recovery:
- try_json_loads()
- iter_fenced_blocks()
- extract_balanced_json_candidates()
- parse_json_with_recovery()
- parse_fact_task_1_multi_block_items()

Loose coercion helpers:
- _coerce_jsonish_text()
- _coerce_string_list()
- _coerce_int()

Common report builders:
- base_report()
- hard_failure_result()

Matching and comparison helpers:
- alias_match()
- near_alias_match()
- score_numeric_field()
- semantic_unit_present()
- count_ambiguity_patterns()
- count_redundant_units()
- database_index_relevant()

Failure normalization:
- derive_fact_prose_success()
- derive_fact_prose_failure_stage()
- derive_fact_prose_failure_type()
- derive_fact_prose_failure_subtype()
- append_normalized_failure_schema()

[json-recovery-model]
This script contains an explicit recovery ladder for JSON-like answers.

Recovery order:
1. Direct json.loads on the whole answer
2. json.loads on fenced JSON/code blocks
3. json.loads on balanced JSON substrings extracted from the answer
4. special fact_task_1 multi-block merge logic

Important consequences:
- parse recovery can salvage otherwise invalid responses
- recovered outputs can still be scored
- schema_adherence_score is reduced when recovery/coercion occurs
- schema_coerced is set when recovery or schema coercion occurs

[task-behavior-fact-task-1]
Expected answer shape:
- dict with items list
or
- list coercible into {"items": ...}

Main scoring logic:
- compares predicted entities against ground-truth entities
- scores category matches
- scores field values using alias or numeric matching
- penalizes extra fields and extra entities
- computes a weighted semantic score:
  - 65% field score
  - 20% entity coverage
  - 15% category score

Schema strictness penalties:
- parse_recovered: -20
- schema_coerced: -20
- multi_block_merged: -20

Usability logic:
- pipeline_usable if strict schema score >= 80
- usable_output if semantic score >= 40

Failure signal sources:
- extra_field
- extra_entity
- low_entity_coverage
- field_value_mismatch
- category_mismatch

[task-behavior-fact-task-2]
Expected answer shape:
- dict with:
  - steps as list
  - final_answer as dict

Main scoring logic:
- match required atomic claims
- verify supported_by_fact_ids for each matched claim
- inspect final answer wording for correct conclusion
- penalize incorrect support mapping and contradictions

Score components:
- reasoning coverage score
- support mapping score
- final answer score
- reasoning consistency score
- strict schema score

Failure signal sources:
- incorrect_support_mapping
- contradiction
- incomplete_reasoning_chain
- final_answer_mismatch
- contradiction_detected

[task-behavior-fact-task-3]
Expected answer shape:
- dict with items list

Main scoring logic:
- compare item classifications
- inspect correction_or_note text against accepted note patterns
- detect accepted false premise cases
- penalize invented or weak notes

Usability logic:
- usable_output becomes false if a false or ambiguous statement is incorrectly accepted as true

Failure signal sources:
- accepted_false_premise
- weak_or_invented_note
- classification_mismatch

[task-behavior-prose-task-1]
Expected answer shape:
- dict with:
  - summary
  - word_count

Main scoring logic:
- semantic hit count over required key units
- compression compliance against max_words
- redundancy penalty for repeated normalized sentences

Derived metrics include:
- actual_word_count
- declared_word_count
- compression_ratio
- retention_density
- semantic_hit_count
- repeated_unit_count

Failure signal sources:
- declared_word_count_mismatch
- word_count_violation
- low_semantic_retention
- redundancy_detected

[task-behavior-prose-task-2]
Expected answer shape:
- dict
- ideally exact key order equals required_sections

Main scoring logic:
- structure score from exact section order and minimum steps
- completeness score from required content units
- ambiguity penalty based on vague patterns such as "it", "that", "something", "etc"

Derived metrics include:
- exact_structure
- step_count
- content_hit_count
- ambiguity_pattern_count
- inputs_item_count
- steps_item_count

Failure signal sources:
- structure_invalid
- insufficient_steps
- missing_required_content_unit
- ambiguity_detected

[task-behavior-prose-task-3]
Expected answer shape:
- dict with exactly:
  - intro
  - bullets
  - word_count

Main scoring logic:
- max word constraint
- exactly three bullets
- banned term detection
- required analogy presence
- coherence bonus for nonempty intro, nonduplicate bullets, and database-index relevance

Derived metrics include:
- actual_word_count
- declared_word_count
- bullet_count
- banned_term_hits
- analogy_present

Failure signal sources:
- declared_word_count_mismatch
- word_count_violation
- bullet_count_mismatch
- banned_term_present
- missing_required_analogy

[success-and-failure-normalization]
Success is defined strictly:
- format_valid is true
- hard_failure is false
- pipeline_usable is true
- score_percent == 100.0

Failure stage derivation:
- format when hard failure or invalid format
- constraint for prose tasks with nonzero constraint/compression signal
- semantic otherwise
- None only for perfect success

Failure type derivation:
- format_violation for hard/format failures
- semantic_error when hallucination flags exist
- constraint_violation for prose failures without hallucination flags
- None only for perfect success

Failure subtype derivation aggregates:
- hard failure reasons
- schema recovery/coercion markers
- hallucination flag types
- task-specific mismatch markers

Important note:
The failure subtype field is a list, but only after append_normalized_failure_schema().
Before normalization, evaluator internals mainly use hallucination_flags and derived_metrics.

[determinism]
The script is deterministic under fixed inputs because:
- all evaluation logic is rule-based
- all thresholds are hardcoded
- there is no randomness
- there are no external network dependencies
- JSON recovery order is stable
- subtype sorting uses sorted(set(...))

[dependencies]
Python standard library only:
- argparse
- json
- re
- unicodedata
- pathlib
- typing

External dependencies:
- none

Upstream caller:
- ./benchmark/cli/benchmark_run.py

[callers]
Known direct caller:
- benchmark_run.py through evaluate_fact_prose()

Likely role in system:
- canonical evaluator for fact/prose benchmark experiments
- source of normalized failure schema used downstream by export and failure aggregation

[verification]
Canonical command pattern:
python3 ./scripts/benchmark/evaluate_benchmark_task.py \
  <answer-file> \
  --task-id fact_task_1 \
  --ground-truth <ground-truth.json> \
  --save-report <report.json>

Expected success signals:
- report file is written
- stdout prints valid JSON
- task_id, answer_file, and ground_truth_file are present
- failure_stage, failure_type, and failure_subtype are present after normalization

Good verification targets:
- one perfect structured fact answer
- one malformed JSON answer that should recover
- one unrecoverable invalid JSON answer
- one prose answer violating word count
- one prose answer matching content but with ambiguity markers

[failure_modes]
- unsupported task_id: immediate exit
- invalid ground truth JSON: uncaught json load failure
- wrong ground truth schema for the chosen task: likely KeyError or malformed score behavior
- invalid output JSON with no recoverable fenced/balanced candidate: hard failure invalid_json
- recoverable but schema-wrong output: hard failure schema_invalid
- task answer partially matching content but breaking structure: partial score, not hard failure
- prose tasks can be treated as constraint failures even when semantically close

[important_current_truths]
- This script is not generic across arbitrary tasks; it is six-task-specific.
- JSON recovery is an intentional part of the evaluator, not an accident.
- Fact tasks and prose tasks share one normalized failure schema, but their scoring logic is highly different.
- Prose failures are often routed into constraint stage rather than semantic stage.
- Perfect success requires exact 100.0 score and pipeline usability, not merely useful output.
- append_normalized_failure_schema() is critical because downstream scripts expect normalized failure fields.

[cleanup-notes]
Do not describe this as junk or legacy. This file is part of the active canonical benchmark path through benchmark_run.py.

Potential future hardening areas:
- explicit ground truth schema validation per task
- clearer separation between raw evaluator output and normalized failure projection
- unit tests per task and per recovery path
- central registry-driven task metadata instead of hardcoded EVALUATORS and subtype derivation rules

[operator-notes]
This is one of the main evaluator spine files in the benchmark system. It should stay in the active tree and be treated as canonical documentation priority.
