Title: rebuild_failure_join_chain.sh
ID: script-rebuild-failure-join-chain
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:analysis-rebuild
@scope:failure-analysis
@scope:joined-analysis
@scope:canonical-analysis-chain
@entity:./scripts/export/rebuild_failure_join_chain.sh
@script:./scripts/export/rebuild_failure_join_chain.sh
@semantic:canonical-post-run-analysis-reconstruction
@capability:rebuild-normalized-exports-failure-aggregation-and-joined-failure-energy-views
@state:documented
@truth:script-behavior
@risk:depends-on-upstream-artifacts-being-present-and-consistent
@risk:hardcoded-experiment-set-may-exclude-new-benchmark-families
@risk:large-report-count-can-stress-shell-argument-expansion
@risk:joins-are-only-as-correct-as-normalization-and-failure-records
@input:benchmark-directory-tree
@output:analysis-failure-and-joined-artifact-directories

[summary]
rebuild_failure_join_chain.sh is the canonical post-run reconstruction script for the Jarri benchmark system. It rebuilds normalized exports, aggregates evaluator failures, and produces the joined failure + energy analysis layer. It defines the exact order in which analysis truth is reconstructed from raw benchmark artifacts.

[purpose]
This script exists to guarantee that all benchmark analysis layers can be deterministically rebuilt from the filesystem. It removes ambiguity in:
- export ordering
- failure aggregation
- join construction
- sanity validation

It is the authoritative operator entrypoint for reconstructing analysis truth after benchmark execution.

[canonical_role]
authoritative
analysis-reconstruction-spine
operator-facing
post-run-truth-builder

[authority_boundary]
This script is allowed to:
- define the canonical rebuild sequence
- select which experiment directories are included
- call normalization, failure aggregation, and join scripts
- verify required intermediate artifacts exist
- expose sanity snapshots via jq

This script is not allowed to:
- normalize ledger rows itself
- evaluate benchmark results
- classify failures itself
- invent or repair missing data
- mutate benchmark execution artifacts
- define scoring or ranking logic

[inputs]
CLI arguments:
- none

Hardcoded paths:
- BENCH_ROOT = ./benchmarks
- ANALYSIS_ROOT = ./benchmarks/_analysis
- FAIL_ROOT = ./benchmarks/_analysis_failures
- JOIN_ROOT = ./benchmarks/_analysis_joined

Hardcoded experiment set:
- coding_measurement_v3
- math_measurement_v1
- knowledge_measurement_v2
- language_measurement_v2
- fact_prose_v2

Environment assumptions:
- bash is available
- python3 is available
- jq is installed
- benchmark directories exist
- report files exist
- upstream scripts are functional

Files read:
- *_report.json files under BENCH_ROOT
- normalized_runs.json files produced by export stage
- joined analysis outputs for sanity inspection

Directories read:
- ./benchmarks/*
- _analysis, _analysis_failures, _analysis_joined

Required upstream artifacts:
- llm_benchmark_runs.jsonl (indirectly)
- evaluator report JSON files
- working:
  - jarri_benchmark_export.py
  - jarri_benchmark_failure_aggregate.py
  - jarri_benchmark_failure_join.py

[outputs]
Created if missing:
- ./benchmarks/_analysis

Indirect outputs (via called scripts):
- ./benchmarks/_analysis/<experiment>/*
- ./benchmarks/_analysis_failures/*
- ./benchmarks/_analysis_joined/*

Key output artifacts:
- normalized_runs.json
- failure_records.json
- joined_failure_energy_summary.json
- joined_failure_energy_by_model.json
- joined_failure_energy_rows.json

Temporary artifacts:
- report list file via mktemp (deleted on exit)

stdout behavior:
- prints step banners
- prints export progress
- prints report count
- prints normalized file verification
- prints jq-based summaries
- prints Done

stderr behavior:
- explicit error if normalized outputs are missing
- subprocess failures propagate via strict mode

[idempotency]
- safe_to_rerun: yes (assuming deterministic upstream scripts)
- overwrite_behavior:
  - downstream scripts overwrite their outputs
- statefulness:
  - reconstructive only
  - no mutation of source benchmark data

Important consequence:
Running this script repeatedly should produce the same analysis outputs given unchanged upstream artifacts.

[execution_flow]
STEP 0 — export rebuild
- create _analysis directory
- for each experiment:
  - run jarri_benchmark_export.py
  - produce normalized_runs.json and aggregate outputs

STEP 1 — report collection
- find all *_report.json files under BENCH_ROOT
- exclude:
  - _analysis
  - _analysis_failures
  - _analysis_joined
- sort and store paths in temporary file
- print report count

STEP 2 — failure aggregation
- call jarri_benchmark_failure_aggregate.py
- pass all report paths
- produce:
  - failure_summary.json
  - failure_records.json
  - grouped failure views

STEP 3 — normalization verification
- verify normalized_runs.json exists for each experiment
- abort if any are missing

STEP 4 — join reconstruction
- call jarri_benchmark_failure_join.py
- join:
  - normalized runs
  - failure_records.json
- produce joined failure + energy views

STEP 5 — sanity inspection
- use jq to print:
  - unmatched row count
  - summary snapshot
  - compact per-model view

[dependencies]
Internal scripts:
- ./benchmark/cli/jarri_benchmark_export.py
- ./benchmark/cli/jarri_benchmark_failure_aggregate.py
- ./benchmark/cli/jarri_benchmark_failure_join.py

Shell tools:
- bash
- find
- sort
- wc
- tr
- mktemp
- jq

Runtime assumptions:
- failure aggregate accepts large argument lists
- joined outputs have stable filenames

[callers]
Primary:
- operator manual execution

Possible:
- higher-level rebuild wrapper (not present here)

Role:
- canonical analysis reconstruction entrypoint

[verification]
Canonical command:
bash ./scripts/export/rebuild_failure_join_chain.sh

Expected success signals:
- all experiments exported successfully
- report count is nonzero
- normalized_runs.json verified for each experiment
- failure_records.json created
- joined outputs created
- unmatched row count printed
- summary snapshot printed
- Done printed

Expected artifact locations:
- ./benchmarks/_analysis/<experiment>/normalized_runs.json
- ./benchmarks/_analysis_failures/failure_records.json
- ./benchmarks/_analysis_joined/joined_failure_energy_summary.json

Quick sanity checks:
- normalized_runs.json exists for all experiments
- failure_records.json exists
- unmatched row count is reasonable (0 in your current run)
- summary metrics look consistent
- no experiment silently missing

[failure_modes]
- missing export script
- missing failure aggregate script
- missing join script
- jq not installed
- missing experiment directory
- no report files found
- argument expansion overflow with many report files
- missing normalized outputs after export
- join schema mismatch
- stale experiment list

[notes]
This script defines the canonical reconstruction chain for benchmark analysis.

Important current truths:
- experiment set is explicitly hardcoded
- normalization must happen before failure aggregation
- failure aggregation must happen before join
- join output is the first unified failure + energy truth surface
- jq output is inspection only, not canonical data

This script should remain orchestration-only. It must not accumulate logic from the Python analysis stages.
