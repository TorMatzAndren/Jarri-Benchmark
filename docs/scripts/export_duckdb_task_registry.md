Title: export_duckdb_task_registry.py
ID: script-export-duckdb-task-registry
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:task-registry
@scope:benchmark-metadata
@scope:ui-export
@entity:./scripts/export/export_duckdb_task_registry.py
@script:./scripts/export/export_duckdb_task_registry.py
@truth:script-behavior
@state:documented
@output:./benchmark_ui/data/duckdb_task_registry.json

[summary]
export_duckdb_task_registry.py builds a task registry JSON for the benchmark UI by scanning canonical benchmark roots for prompt_*.txt files, inferring task IDs from prompt filenames, attaching hardcoded task metadata from TASK_METADATA, and exporting prompt-level descriptive rows into duckdb_task_registry.json. Despite the duckdb name, this script does not read DuckDB at all. It is a prompt-root and metadata exporter.

[purpose]
This script exists to provide a stable task catalog for the benchmark UI and related reporting surfaces. It converts prompt files plus curated task metadata into a single JSON registry that describes what each task is, where it lives, what kind of benchmark family it belongs to, and what success and failure generally mean.

[role]
active
exporter
task-catalog-builder
ui-data-builder
prompt-root-scanner

[naming_note]
The filename begins with export_duckdb_, but the script does not access DuckDB. Its actual source is:
- benchmark prompt roots
- hardcoded TASK_METADATA
This is important because the name can mislead future maintenance.

[inputs]
Hardcoded paths:
- PROJECT_ROOT = .
- BENCHMARKS_DIR = ./benchmarks
- OUT_PATH = ./benchmark_ui/data/duckdb_task_registry.json

Canonical benchmark roots scanned:
- ./benchmarks/coding_measurement_v3
- ./benchmarks/math_measurement_v1
- ./benchmarks/knowledge_measurement_v2
- ./benchmarks/language_measurement_v2
- ./benchmarks/fact_prose_v2

Files read within each root:
- prompt_*.txt
- manifest.json path is recorded but manifest content is not read

Hardcoded metadata source:
- TASK_METADATA dict inside the script

No CLI arguments are used.

[outputs]
Primary output:
- ./benchmark_ui/data/duckdb_task_registry.json

Payload structure:
- generated_at_utc
- source
- rows

Source field value:
- "benchmark prompt roots"

Each row contains:
- task_id
- task_title
- task_family
- task_description
- success_definition
- common_failure_modes
- primary_axis
- benchmark_root
- prompt_path
- manifest_path
- prompt_first_line
- prompt_preview

stdout behavior:
- prints the output JSON path on success

[task_id_derivation]
Task IDs are inferred from prompt filenames:
- prompt_coding_fs_strict_v3.txt -> coding_fs_strict_v3
- prompt_fact_task_1.txt -> fact_task_1

Rule:
- if the prompt stem starts with prompt_, strip that prefix
- otherwise use the raw stem unchanged

[metadata_behavior]
For known task IDs, the script uses TASK_METADATA for:
- title
- description
- success_definition
- common_failure_modes
- primary_axis
- family

For unknown task IDs:
- task_title falls back to task_id with underscores replaced by spaces and title-cased
- task_family falls back to the benchmark family from BENCHMARK_ROOTS
- other descriptive fields may remain null or empty

This means the export is partly dynamic and partly curated by hand.

[functions]
utc_now_iso()
- returns current UTC timestamp in ISO format

read_text_safe(path)
- reads UTF-8 text and strips it
- returns None on failure

first_nonempty_line(text)
- returns the first non-empty stripped line from prompt text
- returns None if text is missing or empty

summarize_prompt(text, max_chars=260)
- normalizes whitespace
- truncates long prompt text with ...
- returns None if no text is available

detect_task_id_from_prompt_path(path)
- derives task_id from filename stem
- strips prompt_ prefix when present

collect_prompt_files(root)
- returns sorted prompt_*.txt files under a benchmark root

main()
- iterates over BENCHMARK_ROOTS
- skips roots that do not exist
- records manifest path for each root
- scans prompt files
- reads prompt text
- merges prompt-derived info with TASK_METADATA
- writes the final JSON registry
- prints the output path
- returns 0

[family_roots]
BENCHMARK_ROOTS maps benchmark families to roots as follows:
- coding -> ./benchmarks/coding_measurement_v3
- math -> ./benchmarks/math_measurement_v1
- knowledge -> ./benchmarks/knowledge_measurement_v2
- language -> ./benchmarks/language_measurement_v2
- fact_prose -> ./benchmarks/fact_prose_v2

The exported task_family comes from:
1. TASK_METADATA family when present
2. otherwise the family_name from this root map

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - rewrites ./benchmark_ui/data/duckdb_task_registry.json
- side_effects:
  - no benchmark mutation
  - no DuckDB mutation
  - no manifest mutation
  - deterministic overwrite for a fixed prompt tree and fixed TASK_METADATA

[dependencies]
Python standard library only:
- json
- re
- datetime
- pathlib

No third-party packages are used.
No DuckDB access is used.

[references]
Observed references shown in investigation:
- ./all_scripts_now.txt
- ./benchmarks/_analysis_inventory/benchmark_producer_discovery.json
- ./doc_queue_export_ui_now.txt
- ./file_inventory_clean.txt
- ./run_me.sh
- ./undocumented_not_in_deprecated_now.txt
- ./undocumented_scripts_abs_now.txt
- ./undocumented_scripts_now.txt

Observed caller from shown references:
- ./run_me.sh

[validation]
Direct validation command:
python3 ./scripts/export/export_duckdb_task_registry.py

Expected success signals:
- prints ./benchmark_ui/data/duckdb_task_registry.json
- output file exists
- output file is valid JSON
- payload contains a rows list
- rows contain prompt_path and benchmark_root values pointing at canonical benchmark roots

Quick JSON validation:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_task_registry.json').expanduser(); d=json.loads(p.read_text()); print(type(d.get('rows')).__name__, len(d.get('rows', [])))"

Prompt coverage validation:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_task_registry.json').expanduser(); rows=json.loads(p.read_text())['rows']; print(sorted({r['task_family'] for r in rows}))"

Prompt-root sanity check:
python3 -c "import json, pathlib; p=pathlib.Path('./benchmark_ui/data/duckdb_task_registry.json').expanduser(); rows=json.loads(p.read_text())['rows']; print(rows[0]['prompt_path'] if rows else None)"

Manual sanity checks:
- verify every exported row came from a real prompt_*.txt file
- verify task_title and task_description are present for known tasks
- verify unknown tasks still export with fallback title/family
- verify manifest_path is recorded even though manifest content is not read

[failure_modes]
- benchmark root missing: root is silently skipped
- no prompt_*.txt in a root: no rows generated for that root
- prompt file unreadable: prompt_first_line and prompt_preview may become null
- output parent directory missing: write failure unless parent already exists
- TASK_METADATA drift from real evaluator meaning: exported descriptions can become stale
- filename/task_id mismatch: task metadata fallback may become generic rather than canonical
- misleading script name: file suggests DuckDB export even though none is used

[notes]
This script is a registry builder, not a performance exporter.

Important current truths:
- it does not inspect benchmark results
- it does not inspect evaluator reports
- it does not read DuckDB
- it does not parse manifest.json contents
- it uses prompt files as the dynamic source of task presence
- it uses TASK_METADATA as the descriptive truth layer

Because the descriptive layer is hardcoded, this script must be kept in sync with real benchmark task evolution or the UI registry will become narratively stale even if the prompt files are current.

This script lives directly under ./, so its canonical document belongs under:
- ./docs/scripts/export_duckdb_task_registry.md
