#!/usr/bin/env bash
set -euo pipefail

MAC="${1:-}"
if [[ -z "$MAC" ]]; then
  echo "Usage: bind_rfcomm.sh MAC [CHANNEL]" >&2
  exit 1
fi

NAME="${NAME:-a3-obd}"
CHANNEL="${2:-}"

if command -v sdptool >/dev/null 2>&1; then
  found=$(sdptool search "0x1101" 2>/dev/null | awk -v mac="$MAC" '
    tolower($0) ~ tolower(mac) {
      for (i = 1; i < NF; i++) {
        if (tolower($i) == "channel") {
          print $(i + 1)
          exit
        }
      }
    }')
  if [[ -n "$found" ]]; then
    CHANNEL="$found"
  fi
fi

if [[ -z "$CHANNEL" ]]; then
  CHANNEL=1
fi

rfcomm bind "${NAME}-${CHANNEL}" "$MAC" "$CHANNEL" 2>/dev/null || true

for i in 0 1 2 3; do
  if [[ -e "/dev/rfcomm${i}" ]]; then
    echo "/dev/rfcomm${i}"
    exit 0
  fi
done

for ch in 1 2 3; do
  rfcomm bind "${NAME}-${ch}" "$MAC" "$ch" 2>/dev/null || true
  for i in 0 1 2 3; do
    if [[ -e "/dev/rfcomm${i}" ]]; then
      echo "/dev/rfcomm${i}"
      exit 0
    fi
  done
done

echo "No rfcomm device created. Check MAC, pairing, permissions, and SPP channel." >&2
exit 1
