#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MAC="${MAC:-00:10:CC:4F:36:03}"
PYTHON="${PYTHON:-$SCRIPT_DIR/../.venv/bin/python}"

exec "$PYTHON" "$SCRIPT_DIR/ble_soc.py" --mac "$MAC" "$@"
