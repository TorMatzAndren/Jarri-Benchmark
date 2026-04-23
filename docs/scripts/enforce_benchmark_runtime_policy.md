Title: enforce_benchmark_runtime_policy.py
ID: script-enforce-benchmark-runtime-policy
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:runtime-policy
@scope:ledger-filtering
@scope:canonical-runtime-enforcement
@entity:./scripts/benchmark/enforce_benchmark_runtime_policy.py
@script:./scripts/benchmark/enforce_benchmark_runtime_policy.py
@truth:script-behavior
@state:documented
@output:./benchmarks/_analysis_inventory/benchmark_runtime_policy_enforcement.json

[summary]
enforce_benchmark_runtime_policy.py loads a benchmark runtime policy JSON, reads a hardcoded set of canonical benchmark ledgers, removes rows that violate the configured runtime policy, writes rejected rows into per-ledger quarantine JSONL files, creates one-time backup copies of the original ledgers, rewrites the retained canonical ledgers in place, and emits an enforcement summary JSON. This is a mutating enforcement script, not just a reporting helper.

[purpose]
This script exists to enforce a canonical runtime policy over selected benchmark ledgers by excluding rows associated with disallowed models, disallowed runtime residency statuses, explicitly non-canonical runtime flags, and hybrid processor split evidence.

[role]
active
mutating
policy-enforcement
ledger-sanitizer

[inputs]
Hardcoded project paths:
- PROJECT_ROOT = .
- BENCHMARKS_ROOT = ./benchmarks
- POLICY_PATH = ./benchmark_runtime_policy.json
- OUT_DIR = ./benchmarks/_analysis_inventory
- OUT_PATH = ./benchmarks/_analysis_inventory/benchmark_runtime_policy_enforcement.json

Hardcoded canonical ledgers:
- ./benchmarks/coding_measurement_v3/llm_benchmark_runs.jsonl
- ./benchmarks/fact_prose_v2/llm_benchmark_runs.jsonl
- ./benchmarks/knowledge_measurement_v2/llm_benchmark_runs.jsonl
- ./benchmarks/language_measurement_v2/llm_benchmark_runs.jsonl
- ./benchmarks/math_measurement_v1/llm_benchmark_runs.jsonl

Expected policy structure:
- benchmark_runtime_policy.json
  - canonical_runtime_policy
    - exclude_models
    - exclude_runtime_statuses

Expected row structure in each ledger:
- model
- runtime_validation
  - residency_status or runtime_status
  - canonical_runtime
  - processor_split

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmarks/_analysis_inventory/benchmark_runtime_policy_enforcement.json

Per-ledger mutation outputs:
- retained rows rewritten back into each canonical ledger path
- rejected rows written to:
  - <ledger>.runtime_rejected.jsonl
- one-time backup written to:
  - <ledger>.pre_runtime_policy_backup.jsonl

Summary JSON fields:
- generated_at_utc
- policy_path
- ledgers
- totals
  - rows_seen
  - rows_retained
  - rows_rejected
- status

Per-ledger summary entry fields:
- ledger_path
- backup_path
- quarantine_path
- rows_seen
- rows_retained
- rows_rejected
- rejected_models

[behavior]
The script:
1. Loads runtime policy from ./benchmark_runtime_policy.json.
2. Creates ./benchmarks/_analysis_inventory if needed.
3. Iterates over the hardcoded canonical ledger list.
4. Reads each ledger as JSONL if it exists.
5. Evaluates each row against should_reject().
6. Splits rows into retained and rejected sets.
7. Creates a one-time full backup of the original ledger if:
   - the ledger exists
   - the backup file does not already exist
8. Rewrites the ledger path with retained rows only.
9. Writes rejected rows to the quarantine JSONL if any exist.
10. Deletes the quarantine JSONL if no rejected rows remain and the file exists.
11. Builds summary statistics per ledger and overall.
12. Writes the enforcement summary JSON.
13. Prints the summary output path.

[policy_model]
Loaded policy dataclass:
- exclude_models: set[str]
- exclude_runtime_statuses: set[str]

A row is rejected if any of the following hold:
- row["model"] is in exclude_models
- runtime_validation residency_status or runtime_status is in exclude_runtime_statuses
- runtime_validation canonical_runtime is False
- runtime_validation processor_split is a string containing "CPU/GPU"

Rejection reasons emitted by the script:
- excluded_model
- excluded_runtime_status:<value>
- canonical_runtime_false
- processor_split_hybrid:<value>

[functions]
utc_now_iso()
- returns UTC ISO timestamp

load_json(path)
- loads a JSON file

load_policy()
- reads benchmark_runtime_policy.json
- extracts canonical_runtime_policy
- returns a Policy dataclass

should_reject(row, policy)
- evaluates row rejection conditions
- returns:
  - reject boolean
  - list of textual rejection reasons

read_jsonl(path)
- reads JSONL rows from a ledger
- returns empty list if the file does not exist

write_jsonl(path, rows)
- writes rows to JSONL, replacing file contents

main()
- orchestrates full enforcement
- mutates ledgers
- writes quarantine and summary outputs
- prints OUT_PATH

[idempotency]
- safe_to_rerun: conditionally
- overwrite_behavior:
  - rewrites canonical ledgers with retained rows only
  - rewrites quarantine JSONL files
  - rewrites the summary JSON
  - creates backup files only once and leaves existing backups intact
- side_effects:
  - destructive in-place filtering of canonical ledgers
  - persistent quarantine file creation or deletion
  - persistent backup creation

Important consequence:
This is not a read-only analysis script. Running it changes benchmark ledger state.

[dependencies]
Python standard library only:
- json
- dataclasses
- datetime
- pathlib
- typing

No external commands are executed.

[references]
Observed references shown in investigation:
- ./all_scripts_now.txt
- ./benchmarks/_analysis_inventory/benchmark_producer_discovery.json
- ./doc_queue_core_now.txt
- ./file_inventory_clean.txt
- ./run_me.sh
- ./undocumented_not_in_deprecated_now.txt
- ./undocumented_scripts_abs_now.txt
- ./undocumented_scripts_now.txt

Observed caller from shown references:
- ./run_me.sh

[validation]
Direct validation command:
python3 ./scripts/benchmark/enforce_benchmark_runtime_policy.py

Expected success signals:
- prints ./benchmarks/_analysis_inventory/benchmark_runtime_policy_enforcement.json
- summary JSON is written
- existing canonical ledgers are rewritten
- backup files appear on first run for existing ledgers
- quarantine files appear only when rows are rejected

Validation checks:
- inspect summary totals:
  - rows_seen
  - rows_retained
  - rows_rejected
- inspect each ledger summary entry
- confirm backup files were created only once
- confirm rejected rows include _runtime_policy_rejection_reasons
- confirm hybrid CPU/GPU rows are rejected when processor_split contains CPU/GPU

Safe validation caution:
Because this script mutates canonical ledgers, validation should be done only when that mutation is intended.

[failure_modes]
- missing benchmark_runtime_policy.json: script fails during load
- malformed policy JSON: script fails during JSON parse or field access
- malformed JSONL row: script fails during json.loads
- missing ledger file: treated as empty ledger, not a hard failure
- unexpected row schema: row may silently avoid some rejection rules if expected keys are absent
- existing backup file can become stale relative to later reruns because backups are only created once
- hardcoded ledger list means new canonical ledgers are ignored until the script is updated

[notes]
This script lives directly under ./, so its document belongs under:
- ./docs/scripts/enforce_benchmark_runtime_policy.md

This script is closer to a canonical sanitation pass than a reporting pass. It should be treated carefully because it rewrites the benchmark ledgers in place.
