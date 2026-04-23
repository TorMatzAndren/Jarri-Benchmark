Title: build_coding_folder_scan_v3_fixture.py
ID: script-build-coding-folder-scan-v3-fixture
Date: 2026-04-21
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-21
Revision: 2

@role:script-doc
@subsystem:benchmarking
@scope:llm-benchmarking
@scope:fixture-generation
@scope:synthetic-filesystem-fixtures
@scope:ground-truth-generation
@entity:./benchmark/tasks/build_coding_folder_scan_v3_fixture.py
@script:./benchmark/tasks/build_coding_folder_scan_v3_fixture.py
@semantic:deterministic-filesystem-fixture-builder
@capability:build-a-deterministic-synthetic-directory-tree-and-write-matching-ground-truth-json
@state:documented
@truth:script-behavior
@risk:deletes-and-rebuilds-the-target-root-directory
@risk:file-mtime-values-depend-on-current-wall-clock-time-offset
@risk:fixture-shape-is-hardcoded-and-task-specific
@output:user-specified-fixture-root
@output:user-specified-ground-truth-json

[summary]
build_coding_folder_scan_v3_fixture.py is a deterministic fixture-generation script for a filesystem-scanning benchmark task. It constructs a synthetic directory tree with fixed file sizes, extensions, duplication patterns, directory distributions, large-file cases, and controlled modification-age offsets, then writes the matching ground-truth JSON used to validate task results.

[purpose]
This script exists to generate a reproducible fixture tree and authoritative expected metrics for the coding_folder_scan_v3 benchmark task shape. It ensures that both the filesystem surface and the paired ground-truth JSON can be rebuilt intentionally from code rather than stored as opaque manual artifacts.

[canonical_role]
active
task-helper
fixture-builder
ground-truth-producer

[authority_boundary]
This script is allowed to:
- delete and recreate the requested fixture root directory
- generate deterministic files of exact byte sizes
- apply deterministic age offsets in days relative to current wall-clock time
- compute authoritative expected summary metrics for the generated fixture
- write the resulting ground-truth JSON

This script is not allowed to:
- execute benchmark prompts
- evaluate model outputs directly
- define benchmark runtime policy
- aggregate benchmark results across runs

[inputs]
CLI arguments:
- --root-dir
- --out-json

Argument meanings:
- --root-dir
  - target directory where the synthetic fixture tree is created
- --out-json
  - output path for the computed ground-truth JSON

Environment assumptions:
- the target paths are writable
- Python has filesystem write permission for the chosen root and JSON output locations

Files read:
- none beyond process environment and filesystem state needed to delete/recreate the root

Files written:
- synthetic files beneath the requested fixture root
- ground-truth JSON at the requested output path

Directories mutated:
- the requested fixture root is removed if it already exists, then recreated from scratch

[outputs]
Primary outputs:
- filesystem fixture tree under --root-dir
- ground-truth JSON under --out-json

Ground-truth JSON fields include:
- fixture_version
- root_path
- total_files
- total_directories_including_root
- total_size_bytes
- extension_distribution
- size_distribution
- largest_files
- top_directories_by_file_count
- top_directories_by_total_size
- recent_files
- duplicate_size_groups
- checksum_mod_1m
- generation_notes

stdout behavior:
- prints a compact success JSON summary including:
  - success
  - fixture_root
  - ground_truth_json
  - total_files
  - total_directories_including_root
  - total_size_bytes
  - checksum_mod_1m

[idempotency]
- safe_to_rerun: yes, for deterministic rebuild of the same fixture shape
- overwrite_behavior:
  - deletes any existing fixture root before rebuilding
  - overwrites the specified ground-truth JSON output file
- statefulness:
  - fixture mtimes are computed relative to current wall-clock time, but remain deterministic in day-offset structure

[execution_flow]
1. Parse --root-dir and --out-json.
2. Resolve both paths.
3. Build the hardcoded file specification list.
4. Remove the target fixture root if it already exists.
5. Recreate the root directory.
6. Write every synthetic file with exact byte counts.
7. Apply controlled modification times in day offsets.
8. Compute:
   - total file count
   - total directory count including root
   - total size
   - extension distribution
   - size-bucket distribution
   - largest files
   - top directories by direct file count
   - top directories by direct total size
   - recent files
   - duplicate-size groups
   - checksum_mod_1m
9. Write the ground-truth JSON.
10. Print a compact success summary JSON.

[dependencies]
Python standard library modules:
- argparse
- json
- os
- shutil
- time
- dataclasses
- pathlib
- typing

External tools:
- none

Runtime assumptions:
- output filesystem is writable
- the caller intentionally accepts destructive rebuild of the requested fixture root

[callers]
No caller was re-proven in this audit pass.

Observed role:
- task-specific fixture helper kept inside the active repository

Call relationship role:
- deterministic fixture and ground-truth generator for a filesystem benchmark task

[verification]
Canonical command:
python3 ./benchmark/tasks/build_coding_folder_scan_v3_fixture.py --root-dir /tmp/coding_fixture_v3 --out-json /tmp/coding_fixture_v3_ground_truth.json

Expected success signals:
- /tmp/coding_fixture_v3 exists and contains the generated tree
- /tmp/coding_fixture_v3_ground_truth.json exists
- stdout prints success true and summary counts
- rerunning produces the same structural metrics and checksum_mod_1m

Quick sanity checks:
- verify total_files is non-zero
- inspect the generated extension_distribution
- confirm duplicate_size_groups are present
- confirm largest_files includes the large archive files
- confirm recent_files only includes items with day offsets of 6 or less

[failure_modes]
- unwritable fixture root or JSON path -> filesystem exception
- target fixture root contains important data -> destructive removal causes data loss
- interrupted run after root deletion -> partial fixture state
- wall-clock anomalies -> mtime offsets remain structurally correct in days but absolute timestamps differ by run time

[notes]
This script is deterministic in fixture shape, file sizes, extension layout, directory grouping, duplicate-size grouping, and computed metrics.

The one temporal nuance is that mtimes are set relative to the current wall-clock time, so absolute timestamps differ between runs even though the relative age structure remains fixed.

This file should be documented from current script behavior, not from older branch assumptions alone.
