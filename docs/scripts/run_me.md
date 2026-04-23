Title: run_me.sh
ID: script-run-me
Date: 2026-04-22
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-23
Revision: 3

@role:script-doc
@subsystem:benchmarking
@scope:benchmark-entrypoint
@scope:benchmark-sweep-orchestration
@scope:runtime-policy-enforcement
@scope:failure-join-rebuild
@scope:ui-data-sync
@scope:ui-surface-generation
@scope:duckdb-import
@scope:duckdb-export
@entity:./run_me.sh
@script:./run_me.sh
@semantic:top-level-canonical-benchmark-entrypoint
@capability:optionally-run-a-benchmark-sweep-then-rebuild-the-full-canonical-analysis-ui-and-duckdb-chain
@state:documented
@truth:script-behavior
@risk:depends-on-many-downstream-scripts-and-a-working-virtualenv
@risk:partial-chain-failure-stops-the-entire-run-because-shell-strict-mode-is-enabled
@risk:tdp-level-usage-is-request-token-based-and-hardware-interpreted
@output:./benchmark_ui/data/ui_model_profiles.json
@output:./benchmark_ui/data/ui_model_task_taskdetail.json
@output:./benchmark_ui/data/duckdb_model_rankings.json
@output:./benchmark_ui/data/duckdb_task_rankings.json
@output:./benchmark_ui/data/duckdb_model_task_tdp.json
@output:./benchmark_ui/data/duckdb_pareto_frontiers.json
@output:./benchmark_ui/data/duckdb_task_registry.json
@output:./benchmark_ui/data/duckdb_failure_surfaces.json

[summary]
run_me.sh is the top-level canonical entrypoint for the current benchmark system.

It has two modes:
- rebuild-only mode, when no sweep arguments are supplied
- full sweep plus canonical rebuild mode, when --models and --repeats are supplied

In full mode it first delegates benchmark execution into the sweep stack, then runs the full post-run chain: runtime policy enforcement, joined analysis rebuild, benchmark UI data sync, DuckDB import, UI surface generation, and DuckDB export surfaces.

This script is the main operator-facing entrypoint and should be treated as the canonical shell surface for the current benchmark workflow.

[purpose]
This script exists to unify the operational path of the benchmark system.

Instead of making the operator remember one command for sweeping and another for rebuilding exports, it provides a single shell entrypoint that can:
- run a benchmark sweep when requested
- rebuild canonical analysis from existing artifacts when no sweep is requested
- refresh UI and DuckDB outputs in the correct order

It is the orchestration spine above both benchmark execution wrappers and post-run canonicalization.

[canonical_role]
authoritative
active
top-level-orchestration
main-entrypoint
execution-and-rebuild-spine

[authority_boundary]
This script is allowed to:
- parse sweep arguments
- decide whether to run sweep mode or rebuild-only mode
- validate that required local scripts and the virtualenv Python exist
- delegate benchmark execution into jarri_benchmark_sweep.sh
- run the benchmark runtime policy enforcement pass
- rebuild the canonical failure/join analysis chain
- sync benchmark UI data artifacts
- import canonical JSON into DuckDB
- generate UI profile and task-detail JSON
- export DuckDB-backed ranking, frontier, registry, and failure-surface JSON

This script is not allowed to:
- run Ollama directly by itself
- evaluate raw model answers directly
- define scoring truth by itself
- define benchmark manifests
- replace the downstream scripts it invokes
- define hardware-level GPU wattage truth by itself

[inputs]
CLI interface:
- no arguments for rebuild-only mode
- optional sweep arguments:
  - --models <model1,model2,...>
  - --repeats <n>
  - --experiments <exp1,exp2,...>
  - --tdp-levels <token1,token2,...>
  - -h | --help

Mode rules:
- if --models and --repeats are both supplied, a benchmark sweep is run first
- if neither sweep argument is supplied, only the canonical rebuild chain runs
- supplying only one of --models or --repeats is an error

Hardcoded environment assumptions:
- . exists
- ./venv/bin/python exists
- downstream scripts referenced by this wrapper exist
- downstream shell scripts referenced by this wrapper are executable

Required file dependencies:
- ./scripts/benchmark/enforce_benchmark_runtime_policy.py
- ./scripts/export/rebuild_failure_join_chain.sh
- ./scripts/export/sync_benchmark_ui_data.sh
- ./scripts/ui/generate_benchmark_ui_profiles.py
- ./scripts/ui/generate_benchmark_ui_taskdetail.py
- ./scripts/benchmark/import_benchmark_json_to_duckdb.py
- ./scripts/export/export_duckdb_model_rankings.py
- ./scripts/export/export_duckdb_task_rankings.py
- ./scripts/export/export_duckdb_model_task_tdp.py
- ./scripts/export/export_duckdb_pareto_frontiers.py
- ./scripts/export/export_duckdb_task_registry.py
- ./scripts/export/export_duckdb_failure_surfaces.py

Required executable dependencies:
- ./scripts/benchmark/jarri_benchmark_sweep.sh when sweep mode is enabled
- ./scripts/export/rebuild_failure_join_chain.sh
- ./scripts/export/sync_benchmark_ui_data.sh

[outputs]
This script itself prints phase banners and mode information to stdout.

Its downstream chain produces or refreshes artifacts including:
- ./benchmarks/_analysis_inventory/benchmark_runtime_policy_enforcement.json
- joined and failure analysis surfaces rebuilt by rebuild_failure_join_chain.sh
- synced benchmark_ui data produced by sync_benchmark_ui_data.sh
- ./benchmarks/_db/benchmark.duckdb
- ./benchmark_ui/data/ui_model_profiles.json
- ./benchmark_ui/data/ui_model_task_taskdetail.json
- ./benchmark_ui/data/duckdb_model_rankings.json
- ./benchmark_ui/data/duckdb_task_rankings.json
- ./benchmark_ui/data/duckdb_model_task_tdp.json
- ./benchmark_ui/data/duckdb_pareto_frontiers.json
- ./benchmark_ui/data/duckdb_task_registry.json
- ./benchmark_ui/data/duckdb_failure_surfaces.json

[execution_flow]
1. Enable strict shell mode with set -euo pipefail.
2. Define PROJECT_ROOT, VENV_PY, and all downstream script paths.
3. Initialize sweep-related state variables.
4. Parse CLI arguments:
   - --models
   - --repeats
   - --experiments
   - --tdp-levels
   - --help
5. If sweep mode is requested, require both --models and --repeats.
6. Print a top-level mode banner.
7. Validate required files and executables.
8. If sweep mode is enabled:
   8.1 require jarri_benchmark_sweep.sh to be executable
   8.2 build the delegated sweep command
   8.3 pass through --experiments if supplied
   8.4 pass through --tdp-levels if supplied
   8.5 run the delegated sweep as step [0/11]
9. Run enforce_benchmark_runtime_policy.py.
10. Run rebuild_failure_join_chain.sh.
11. Run sync_benchmark_ui_data.sh.
12. Run import_benchmark_json_to_duckdb.py.
13. Run generate_benchmark_ui_profiles.py.
14. Run generate_benchmark_ui_taskdetail.py.
15. Run export_duckdb_model_rankings.py.
16. Run export_duckdb_task_rankings.py.
17. Run export_duckdb_model_task_tdp.py.
18. Run export_duckdb_pareto_frontiers.py.
19. Run export_duckdb_task_registry.py.
20. Run export_duckdb_failure_surfaces.py.
21. Print a completion banner.

[ordering_contract]
The current canonical downstream order is:

1. runtime policy enforcement
2. joined-analysis rebuild
3. benchmark UI data sync
4. DuckDB import
5. UI profile generation
6. UI task-detail generation
7. DuckDB export surfaces

This ordering matters because the UI scripts now belong to the same late rebuild layer as DuckDB-backed outputs, even when some UI scripts still read synced JSON surfaces directly rather than querying DuckDB themselves.

[current_phase_labels]
Current printed numbered phases are:
- [0/11] Running benchmark sweep, only in sweep mode
- [1/11] Enforcing canonical runtime policy
- [2/11] Rebuilding canonical benchmark analysis chain
- [3/11] Syncing benchmark UI data
- [4/11] Importing canonical JSON into DuckDB
- [5/11] Generating benchmark UI model profiles
- [6/11] Generating benchmark UI task detail surface
- [7/11] Exporting DuckDB model rankings
- [8/11] Exporting DuckDB task and model-task-TDP surfaces
- [9/11] Exporting DuckDB Pareto frontiers
- [10/11] Exporting task registry
- [11/11] Exporting failure surfaces

[dependencies]
Shell/runtime:
- bash
- strict shell mode support
- executable downstream shell scripts

Python/runtime:
- ./venv/bin/python

Downstream scripts:
- ./scripts/benchmark/jarri_benchmark_sweep.sh
- ./scripts/benchmark/enforce_benchmark_runtime_policy.py
- ./scripts/export/rebuild_failure_join_chain.sh
- ./scripts/export/sync_benchmark_ui_data.sh
- ./scripts/benchmark/import_benchmark_json_to_duckdb.py
- ./scripts/ui/generate_benchmark_ui_profiles.py
- ./scripts/ui/generate_benchmark_ui_taskdetail.py
- ./scripts/export/export_duckdb_model_rankings.py
- ./scripts/export/export_duckdb_task_rankings.py
- ./scripts/export/export_duckdb_model_task_tdp.py
- ./scripts/export/export_duckdb_pareto_frontiers.py
- ./scripts/export/export_duckdb_task_registry.py
- ./scripts/export/export_duckdb_failure_surfaces.py

[callers]
Observed role:
- operator-invoked top-level entrypoint

Known relationship:
- delegates optional execution into ./scripts/benchmark/jarri_benchmark_sweep.sh
- then serializes the canonical rebuild, UI, and DuckDB chain

[idempotency]
- safe_to_rerun: conditionally
- in rebuild-only mode:
  - expected as part of normal canonical rebuild workflow
  - downstream scripts generally refresh canonical outputs
- in sweep mode:
  - not a no-op
  - creates additional benchmark rows and artifacts before rebuilding downstream surfaces

Important consequence:
Re-running in sweep mode changes the benchmark corpus before the rebuild chain runs.
Re-running in rebuild-only mode refreshes the derived layers from existing artifacts.

[tdp_policy_note]
The --tdp-levels argument is a request-token surface.

Current token contract:
- bare numeric tokens are interpreted downstream as percent
  - examples:
    - 41
    - 80
    - 100
    - 112
- tokens ending in w or W are interpreted downstream as explicit watts
  - examples:
    - 144w
    - 168w
    - 192w

Important current truth:
- run_me.sh does not itself resolve percent-to-watt conversion
- run_me.sh only passes the token list through to the sweep layer
- final percent or watt interpretation happens downstream in the Linux GPU power helper
- percent tokens are hardware-interpreted rather than globally fixed across all cards

This means:
- the same percent token may resolve to different watt values on different cards
- watt tokens remain the explicit fixed-power override form
- this wrapper should not be described as owning the final GPU power contract

[verification]
Canonical rebuild-only command:
bash ./run_me.sh

Canonical sweep-plus-rebuild command:
bash ./run_me.sh --models qwen3:8b --repeats 1

Example with experiments:
bash ./run_me.sh --models qwen3:8b,mistral:7b --repeats 3 --experiments fact_prose_v2,math_measurement_v1

Example with percent-token TDP pass-through:
bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 41,50,60,70

Example with mixed token shapes:
bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 80,100,112
bash ./run_me.sh --models qwen3:8b --repeats 1 --tdp-levels 144w,168w,192w

Expected success signals:
- correct mode banner prints
- sweep runs first when requested
- all numbered phases print cleanly
- no missing-file or missing-executable guard trips
- no downstream script exits nonzero
- final completion banner is printed
- expected UI and DuckDB export JSON files exist and are freshly updated

Quick sanity checks:
- verify ./venv/bin/python exists
- verify rebuild_failure_join_chain.sh and sync_benchmark_ui_data.sh are executable
- verify DuckDB import now occurs before the two UI-generation steps
- verify benchmark_ui/data contains fresh duckdb_*.json files after completion
- verify benchmark_ui/data contains ui_model_profiles.json and ui_model_task_taskdetail.json
- verify benchmark_runtime_policy_enforcement.json was refreshed

[failure_modes]
- missing virtualenv Python path
- missing downstream script path
- downstream shell script not executable
- sweep mode requested without both --models and --repeats
- delegated sweep failure
- runtime policy enforcement failure
- failure-join chain rebuild failure
- UI sync failure
- DuckDB import failure
- UI generation failure
- DuckDB export failure
- any downstream nonzero exit aborts the wrapper immediately because of strict shell mode

[notes]
This script is no longer only a collector/orchestrator over existing benchmark artifacts.

It is now the top-level benchmark entrypoint that can optionally perform both:
- benchmark execution through the sweep stack
- canonical rebuild/export through the post-run chain

Important current truths:
- run_me.sh should be treated as the main operator entrypoint
- sweep arguments are passed down into jarri_benchmark_sweep.sh
- rebuild_failure_join_chain.sh is part of the canonical rebuild path invoked by this script
- DuckDB import currently precedes UI profile/task-detail generation in the canonical order
- --tdp-levels is now a token pass-through surface rather than a fixed universal watt map
