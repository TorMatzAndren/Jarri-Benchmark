#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <percent|wattsw>" >&2
  echo "Examples:" >&2
  echo "  $0 80" >&2
  echo "  $0 112" >&2
  echo "  $0 144w" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "Error: nvidia-smi not found in PATH" >&2
  exit 1
fi

GPU_INDEX="${GPU_INDEX:-0}"
RAW_INPUT="$1"

trim() {
  awk '{$1=$1; print}' <<<"$1"
}

extract_first_number() {
  grep -Eo '[0-9]+([.][0-9]+)?' | head -n 1
}

get_power_block() {
  nvidia-smi -q -i "$GPU_INDEX" -d POWER
}

POWER_BLOCK="$(get_power_block)"

if [[ -z "${POWER_BLOCK:-}" ]]; then
  echo "Error: could not read power information from nvidia-smi" >&2
  exit 2
fi

MIN_WATTS="$(
  printf '%s\n' "$POWER_BLOCK" \
    | grep -i 'Min Power Limit' \
    | extract_first_number \
    || true
)"

MAX_WATTS="$(
  printf '%s\n' "$POWER_BLOCK" \
    | grep -i 'Max Power Limit' \
    | extract_first_number \
    || true
)"

DEFAULT_WATTS="$(
  {
    printf '%s\n' "$POWER_BLOCK" | grep -i 'Default Power Limit' || true
    printf '%s\n' "$POWER_BLOCK" | grep -i 'Power Limit' | grep -vi 'Min Power Limit\|Max Power Limit\|Requested Power Limit\|Enforced Power Limit' || true
  } \
    | extract_first_number \
    || true
)"

REQUESTED_WATTS="$(
  printf '%s\n' "$POWER_BLOCK" \
    | grep -i 'Requested Power Limit' \
    | extract_first_number \
    || true
)"

ENFORCED_WATTS="$(
  printf '%s\n' "$POWER_BLOCK" \
    | grep -i 'Enforced Power Limit' \
    | extract_first_number \
    || true
)"

if [[ -z "${MIN_WATTS:-}" || -z "${MAX_WATTS:-}" ]]; then
  echo "Error: could not parse Min/Max Power Limit from nvidia-smi output" >&2
  exit 2
fi

REFERENCE_WATTS="${DEFAULT_WATTS:-$MAX_WATTS}"
REFERENCE_SOURCE="default"

if [[ -z "${DEFAULT_WATTS:-}" ]]; then
  REFERENCE_SOURCE="max"
fi

MODE=""
REQUEST_WATTS=""

if [[ "$RAW_INPUT" =~ ^[0-9]+([.][0-9]+)?[Ww]$ ]]; then
  MODE="watts"
  REQUEST_WATTS="${RAW_INPUT%[Ww]}"
elif [[ "$RAW_INPUT" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  MODE="percent"
  REQUEST_WATTS="$(
    python3 - "$RAW_INPUT" "$REFERENCE_WATTS" <<'PY'
import sys
percent = float(sys.argv[1])
reference = float(sys.argv[2])
watts = round(reference * (percent / 100.0))
print(int(watts))
PY
  )"
else
  echo "Error: input must be an integer/float percent like 80 or 112, or watts like 144w" >&2
  exit 1
fi

CLAMPED_WATTS="$(
  python3 - "$REQUEST_WATTS" "$MIN_WATTS" "$MAX_WATTS" <<'PY'
import sys
requested = float(sys.argv[1])
min_watts = float(sys.argv[2])
max_watts = float(sys.argv[3])
clamped = max(min_watts, min(max_watts, requested))
print(int(round(clamped)))
PY
)"

echo "GPU index: ${GPU_INDEX}"
echo "Power limits from driver:"
echo "  min:       ${MIN_WATTS} W"
echo "  max:       ${MAX_WATTS} W"
if [[ -n "${DEFAULT_WATTS:-}" ]]; then
  echo "  default:   ${DEFAULT_WATTS} W"
else
  echo "  default:   unavailable"
fi
if [[ -n "${REQUESTED_WATTS:-}" ]]; then
  echo "  requested: ${REQUESTED_WATTS} W"
fi
if [[ -n "${ENFORCED_WATTS:-}" ]]; then
  echo "  enforced:  ${ENFORCED_WATTS} W"
fi

if [[ "$MODE" == "percent" ]]; then
  echo "Input mode: percent"
  echo "Requested percent: ${RAW_INPUT}% of ${REFERENCE_SOURCE} power limit (${REFERENCE_WATTS} W)"
else
  echo "Input mode: watts"
  echo "Requested explicit watts: ${REQUEST_WATTS} W"
fi

if [[ "$CLAMPED_WATTS" != "$(printf '%.0f' "$REQUEST_WATTS")" ]]; then
  echo "Clamped target watts: ${CLAMPED_WATTS} W"
else
  echo "Target watts: ${CLAMPED_WATTS} W"
fi

echo "Applying GPU power limit..."
sudo nvidia-smi -i "$GPU_INDEX" -pl "$CLAMPED_WATTS" >/dev/null

READBACK_LIMIT="$(
  nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits -i "$GPU_INDEX" \
    | head -n 1 \
    | awk '{print int($1)}'
)"

if [[ -z "${READBACK_LIMIT:-}" ]]; then
  echo "Error: could not read back GPU power limit" >&2
  exit 2
fi

if [[ "$READBACK_LIMIT" != "$CLAMPED_WATTS" ]]; then
  echo "Error: requested/applied ${CLAMPED_WATTS} W but read back ${READBACK_LIMIT} W" >&2
  exit 2
fi

echo "Confirmed applied GPU power limit: ${READBACK_LIMIT} W"
exit 0
