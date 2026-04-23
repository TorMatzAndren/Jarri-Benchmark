Title: sync_benchmark_ui_data.sh
ID: script_sync_benchmark_ui_data
Date: 2026-04-21
Author: Matz
Type: scripts
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 1

---

@role:scripts
@subsystem:benchmarking
@scope:benchmarking
@scope:benchmark-ui
@scope:data-sync
@scope:analysis-artifacts
@scope:registries
@script:./scripts/export/sync_benchmark_ui_data.sh
@status:active

[summary]
sync_benchmark_ui_data.sh copies canonical benchmark registry, verification, joined, failure, and per-family analysis JSON artifacts from the main project benchmark tree into the benchmark UI data tree under `./benchmark_ui/data`. It also creates a deterministic `data_index.json` manifest describing the synced UI-visible artifact surface.

[purpose]
This script exists to materialize the benchmark UI data directory from canonical benchmark outputs already produced elsewhere in the project. It is a bridge from benchmark analysis storage into the UI-facing data tree, not a generator of new benchmark truth.

[inputs]
This script has no command-line arguments.

It reads from:
- `./benchmarks/_analysis_inventory`
- `./benchmarks/_analysis_joined`
- `./benchmarks/_analysis_failures`
- `./benchmarks/_analysis/coding_measurement_v3`
- `./benchmarks/_analysis/fact_prose_v2`
- `./benchmarks/_analysis/knowledge_measurement_v2`
- `./benchmarks/_analysis/language_measurement_v2`
- `./benchmarks/_analysis/math_measurement_v1`

[outputs]
The script creates or updates files under:
- `./benchmark_ui/data/registries`
- `./benchmark_ui/data/verification`
- `./benchmark_ui/data/joined`
- `./benchmark_ui/data/failures`
- `./benchmark_ui/data/analysis/coding_measurement_v3`
- `./benchmark_ui/data/analysis/fact_prose_v2`
- `./benchmark_ui/data/analysis/knowledge_measurement_v2`
- `./benchmark_ui/data/analysis/language_measurement_v2`
- `./benchmark_ui/data/analysis/math_measurement_v1`

It also writes:
- `./benchmark_ui/data/data_index.json`

[behaviour]
1. Resolve:
   - `SRC_ROOT=.`
   - `UI_ROOT=./benchmark_ui`
   - `DATA_ROOT=./benchmark_ui/data`
2. Create the full destination directory structure if it does not already exist.
3. Define `copy_if_exists`, which:
   - copies a source file to a destination when the source exists
   - prints `copied:` when successful
   - prints `missing:` when the source file is absent
4. Copy registry files into `data/registries`.
5. Copy registry verification output into `data/verification`.
6. Copy joined analysis outputs into `data/joined`.
7. Copy failure aggregate outputs into `data/failures`.
8. Copy per-family benchmark export artifacts into `data/analysis/<family>`.
9. Write a static `data_index.json` file describing the expected UI data sections and file layout.
10. Print the written data index path.
11. Print a completion message.

[copied_registry_files]
- `benchmarks/_analysis_inventory/benchmark_inventory_manifest.json`
- `benchmarks/_analysis_inventory/benchmark_canonical_registry.json`
- `benchmarks/_analysis_inventory/benchmark_producer_registry.json`

[copied_verification_files]
- `benchmarks/_analysis_inventory/benchmark_canonical_registry_verification.json`

[copied_joined_files]
- `benchmarks/_analysis_joined/joined_failure_energy_by_model.json`
- `benchmarks/_analysis_joined/joined_failure_energy_by_task.json`
- `benchmarks/_analysis_joined/joined_failure_energy_by_tdp.json`
- `benchmarks/_analysis_joined/joined_failure_energy_rows.json`
- `benchmarks/_analysis_joined/joined_failure_energy_by_model_task_tdp.json`

[copied_failure_files]
- `benchmarks/_analysis_failures/failure_by_model.json`
- `benchmarks/_analysis_failures/failure_by_task.json`
- `benchmarks/_analysis_failures/failure_by_task_family.json`
- `benchmarks/_analysis_failures/failure_by_tdp.json`
- `benchmarks/_analysis_failures/failure_records.json`

[copied_analysis_files]
For each of:
- `coding_measurement_v3`
- `fact_prose_v2`
- `knowledge_measurement_v2`
- `language_measurement_v2`
- `math_measurement_v1`

the script copies:
- `benchmark_export.json`
- `normalized_runs.json`
- `aggregate_by_model_gpu_tdp_task.json`

[data_index_role]
`data_index.json` is written directly by this script and acts as a UI-facing inventory of the synced artifact surface. It is not discovered dynamically from the destination tree.

[used_by]
- `./run_me.sh`

[dependencies]
- Bash
- `cp`
- writable benchmark UI directory
- canonical benchmark output files already generated upstream

[failure_modes]
- source files may be missing, in which case the script reports them but continues
- destination write failures will stop execution because the script runs with `set -euo pipefail`
- stale or partial upstream analysis outputs will propagate into the UI tree if copied

[notes]
This script is a sync/export bridge for the benchmark UI. It does not validate artifact correctness beyond simple file presence at copy time, and it does not rebuild any upstream benchmark outputs itself.

