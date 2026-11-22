#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

DEVICE="${DEVICE:-}"
if [[ -z "$DEVICE" && -n "${1:-}" && "${1:-}" != -* ]]; then
  DEVICE="$1"
  shift
fi

if [[ -z "$DEVICE" ]]; then
  for candidate in /dev/rfcomm0 /dev/ttyUSB0 /dev/ttyACM0; do
    if [[ -e "$candidate" ]]; then
      DEVICE="$candidate"
      break
    fi
  done
fi

if [[ -z "$DEVICE" ]]; then
  echo "No OBD serial device found. Set DEVICE=/dev/rfcomm0 or run find_bluetooth_device.sh first." >&2
  exit 1
fi

exec python3 "$SCRIPT_DIR/read_soc.py" --device "$DEVICE" "$@"
