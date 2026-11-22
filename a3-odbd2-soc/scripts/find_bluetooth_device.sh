#!/usr/bin/env bash
set -euo pipefail

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "bluetoothctl not found. Install bluez or run this on the machine with the paired S1 Max." >&2
  exit 1
fi

echo "Adapter:"
bluetoothctl show || true

echo "All devices:"
bluetoothctl devices || true

echo "Paired devices:"
bluetoothctl devices Paired || true

echo "Connected devices:"
bluetoothctl devices Connected || true

echo "Scanning for 10 seconds..."
bluetoothctl power on || true
bluetoothctl scan on || true
sleep 10
bluetoothctl scan off || true

echo "Likely OBD/ELM/S1 Max candidates:"
bluetoothctl devices | grep -Ei 'S1 MAX|S1|ELM|OBD|VGATE|OBDLINK|BLUETOOTH' || echo "No likely candidates found."

echo "Existing serial devices:"
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/rfcomm* 2>/dev/null || echo "No ttyUSB/ttyACM/rfcomm devices visible."
