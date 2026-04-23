Title: set_gpu_power_limit_linux.sh
ID: script-set-gpu-power-limit-linux
Date: 2026-04-23
Author: Matz
Type: script-doc
Subsystem: benchmarking
Updated: 2026-04-23
Revision: 1

@role:script-doc
@subsystem:benchmarking
@scope:gpu-power-control
@scope:linux-runtime
@scope:nvidia-power-management
@scope:benchmark-runtime-support
@entity:./set_gpu_power_limit_linux.sh
@script:./set_gpu_power_limit_linux.sh
@semantic:linux-native-gpu-power-limit-controller
@capability:resolve-percent-or-watt-inputs-against-driver-reported-power-limits-and-apply-a-confirmed-nvidia-power-limit
@state:documented
@truth:script-behavior
@risk:requires-nvidia-smi-and-supported-driver-state
@risk:requires-sufficient-privileges-for-power-limit-changes
@risk:power-limit-fields-may-vary-slightly-by-driver-or-card
@output:stdout-confirmation-lines

[summary]
set_gpu_power_limit_linux.sh is the canonical GPU power-limit helper for the current Jarri benchmark environment on Linux. It accepts either a bare numeric TDP token interpreted as percent, such as `80` or `112`, or an explicit watt token such as `144w`. It reads the GPU power-limit surface from `nvidia-smi`, resolves the requested token into a target watt value, clamps that value into the supported min/max range, applies the limit through `nvidia-smi -pl`, reads the limit back, and exits success only when the confirmed applied value matches the resolved target.

[purpose]
This script exists to provide one deterministic authority path for GPU power-limit control inside the benchmark runtime. It uses direct Linux-native NVIDIA control while also making the benchmark TDP surface more portable across cards with different wattage ranges.

[canonical_role]
active
canonical-for-current-environment
runtime-helper
linux-native-helper

[authority_boundary]
This script is allowed to:
- validate one CLI input token
- interpret a bare numeric token as a percentage
- interpret a token ending in `w` or `W` as explicit watts
- query driver-reported power information through `nvidia-smi`
- derive a target watt value from a percentage token
- clamp the target watt value into the supported min/max range
- apply the resulting watt value through `nvidia-smi -pl`
- read back the active power limit and confirm the result

This script is not allowed to:
- define benchmark truth beyond confirmed power-limit state
- choose benchmark sweep ladders by itself
- perform benchmark execution
- aggregate telemetry or ledger outputs
- pretend to support non-NVIDIA environments

[current_environment_truth]
This script is canonical for the current Jarri benchmark environment on Linux.

That means:
- it is the live authority path for GPU power-limit requests during benchmark execution
- runtime scripts should call this helper instead of hardcoding a universal percent-to-watt map
- its percent interpretation is intentionally card-aware rather than tied to one fixed host ladder

[input_contract]
CLI positional input:
- <tdp-token>

Accepted token forms:
- bare integer or decimal number, interpreted as percent
  - examples:
    - `80`
    - `100`
    - `112`
- explicit watts with `w` or `W` suffix
  - examples:
    - `144w`
    - `270W`

Percent interpretation:
- a bare numeric token is interpreted as a percentage of the driver-reported reference limit
- the script prefers `Default Power Limit` when available
- if `Default Power Limit` is unavailable, the script falls back to `Max Power Limit`

Environment variable:
- `GPU_INDEX`
  - optional
  - defaults to `0`

Environment assumptions:
- `nvidia-smi` is installed and available in PATH
- the selected GPU supports configurable power limits
- the active user can execute the required privileged command
- `python3` is available for small numeric calculations

[driver_queries]
The script queries NVIDIA power information through:
- `nvidia-smi -q -i <gpu_index> -d POWER`

It attempts to parse:
- `Min Power Limit`
- `Max Power Limit`
- `Default Power Limit` when exposed
- `Requested Power Limit` when exposed
- `Enforced Power Limit` when exposed

Readback confirmation is performed through:
- `nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits -i <gpu_index>`

[outputs]
stdout:
- selected GPU index
- driver-reported min/max/default/requested/enforced values when available
- input mode
- resolved or explicit target watt value
- clamp message when the requested value exceeds supported bounds
- confirmed applied GPU power limit message on success

stderr:
- usage errors
- malformed token errors
- `nvidia-smi` availability or parse failures
- readback mismatch failures

exit codes:
- 0 on confirmed match
- 1 on usage, validation, or missing-tool failure
- 2 on power-surface parsing or readback failure

[idempotency]
- safe_to_rerun: yes
- overwrite_behavior:
  - no files are written by this script
- statefulness:
  - mutates live GPU power-limit state for the selected GPU

[execution_flow]
1. Enable strict bash mode.
2. Require exactly one CLI argument.
3. Require that `nvidia-smi` exists in PATH.
4. Resolve target GPU index from `GPU_INDEX` or default to `0`.
5. Read the POWER section from `nvidia-smi -q`.
6. Parse min and max power limits.
7. Try to parse default, requested, and enforced power limits.
8. Classify the input token:
   - bare numeric token -> percent mode
   - `w`/`W` suffixed token -> explicit watt mode
9. In percent mode:
   9.1 choose the reference limit
   9.2 compute target watts from the requested percent
10. Clamp the target watt value into the supported min/max range.
11. Apply the clamped watt value through:
   - `sudo nvidia-smi -i <gpu_index> -pl <watts>`
12. Read back the active power limit through `nvidia-smi`.
13. Exit success only if the readback matches the applied target.

[dependencies]
Shell:
- bash
- awk
- grep
- head

External tools:
- `nvidia-smi`
- `sudo`
- `python3`

External environment:
- NVIDIA driver stack installed and functioning
- supported NVIDIA GPU
- permission to change GPU power limits

No bridge behavior:
- this script does not write external bridge control files
- this script does not depend on `/mnt/c/Jarri`
- this script does not wait for a separate host-side controller

[callers]
Confirmed active runtime caller:
- ./benchmark/cli/benchmark_run.py

Possible direct operator usage:
- can be run manually to set and confirm a GPU power limit on the local Linux host
- can be used with percent tokens for portable card-relative control
- can be used with watt tokens for exact fixed-limit control

Call relationship role:
- canonical GPU power-limit helper for the benchmark runtime environment

[verification]
Canonical commands:
- `bash ./set_gpu_power_limit_linux.sh 80`
- `bash ./set_gpu_power_limit_linux.sh 112`
- `bash ./set_gpu_power_limit_linux.sh 144w`

Expected success signals:
- driver power-limit surface is printed
- the input mode is identified correctly
- a target watt value is shown
- the requested power limit is applied
- the readback value matches the applied value
- the script prints `Confirmed applied GPU power limit: ... W`
- exit code 0

Expected failure cases:
- malformed token -> exit 1
- `nvidia-smi` missing -> exit 1
- driver power-limit surface missing min/max fields -> exit 2
- privilege failure -> subprocess failure
- unsupported or unconfirmable requested limit -> exit 2

Quick checks:
- `nvidia-smi`
- `nvidia-smi -q -d POWER`
- `nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits`

[failure_modes]
- wrong argument count -> usage printed, exit 1
- malformed token -> validation failure, exit 1
- `nvidia-smi` missing -> exit 1
- min/max power limits cannot be parsed -> exit 2
- privileged apply command fails -> shell failure
- readback is missing or empty -> exit 2
- readback does not match applied target watts -> exit 2

[notes]
Important current truths:
- bare numeric TDP tokens are no longer tied to one fixed universal watt map
- percent interpretation is now card-aware
- over-100 values such as `112` are allowed and are resolved against the driver-reported reference limit
- explicit watt values remain available through the `w` suffix
- the final authoritative control surface is still NVIDIA watts via `nvidia-smi -pl`

This document should be kept literal. If the helper changes again, rewrite it from the active script behavior rather than by patching older environment assumptions.
