#!/usr/bin/env python3
"""Read Audi A3 PHEV HV battery SOC over BLE OBD-II PID 0x5B."""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

try:
    from bleak import BleakClient
except ModuleNotFoundError as exc:
    raise SystemExit(f"Missing dependency: {exc.name}. Install it with: python3 -m pip install bleak") from exc

DEFAULT_MAC = "00:10:CC:4F:36:03"
WRITE_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
READ_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"


def parse_soc(response: str, pid: str) -> Optional[dict]:
    """Extract the single-byte PID response from an ELM/OBD notification stream."""
    pid_hex = pid.strip().upper()
    if len(pid_hex) == 1:
        pid_hex = "0" + pid_hex
    pattern = re.compile(r"41\s+" + pid_hex + r"\s+([0-9A-Fa-f]{2})", re.IGNORECASE)
    match = pattern.search(response)
    if not match:
        return None
    raw = int(match.group(1), 16)
    return {
        "pid": "0x" + pid_hex,
        "raw": raw,
        "soc_pct": round(raw * 100 / 255, 1),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def make_handler(buffer: List[bytes]):
    def handler(_, data: bytes) -> None:
        buffer.append(bytes(data))

    return handler


def iter_characteristics(client):
    for service in client.services:
        for char in getattr(service, "characteristics", []):
            yield char


def find_writable(client, uuid: str):
    for char in iter_characteristics(client):
        if char.uuid.lower() == uuid.lower() and "write" in char.properties:
            return char
    for char in iter_characteristics(client):
        if "write" in char.properties:
            return char
    return None


def find_readable(client, uuid: str):
    for char in iter_characteristics(client):
        if char.uuid.lower() == uuid.lower() and "read" in char.properties:
            return char
    return None


async def subscribe(client, char, handler):
    last_exc: Optional[Exception] = None
    for use_start in (False, True):
        try:
            await client.start_notify(char, handler, bluez={"use_start_notify": use_start})
            return
        except Exception as exc:
            last_exc = exc
            try:
                await client.stop_notify(char)
            except Exception:
                pass
    raise last_exc


async def connect_and_wait(mac: str, write_uuid: str, read_uuid: str, retries: int) -> Tuple[Any, Any, Optional[Any], List[bytes]]:
    buffer: List[bytes] = []
    handler = make_handler(buffer)
    client = BleakClient(mac)
    last_exc: Optional[Exception] = None

    for attempt in range(retries):
        try:
            await client.connect()
            write_char = find_writable(client, write_uuid)
            if write_char is None:
                raise RuntimeError("No writable characteristic found")
            read_char = find_readable(client, read_uuid)
            if "notify" in write_char.properties or "indicate" in write_char.properties:
                await subscribe(client, write_char, handler)
            if read_char is not None and ("notify" in read_char.properties or "indicate" in read_char.properties):
                await subscribe(client, read_char, handler)
            return client, write_char, read_char, buffer
        except Exception as exc:
            last_exc = exc
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2.0 + attempt)

    raise RuntimeError(f"Could not connect to BLE OBD device {mac}: {last_exc}")


async def write_once(client, write_char, read_char, buffer: List[bytes], payload: str, wait: float) -> str:
    buffer.clear()
    await client.write_gatt_char(write_char, payload.encode("ascii") + b"\r", response=True)
    await asyncio.sleep(wait)
    if read_char is not None:
        try:
            buffer.append(bytes(await client.read_gatt_char(read_char)))
        except Exception:
            pass
    return b"".join(buffer).decode(errors="replace")


async def read_soc(mac: str, pid: str, wait: float, retries: int) -> dict:
    client, write_char, read_char, buffer = await connect_and_wait(mac, WRITE_UUID, READ_UUID, retries)
    last_error = "no_response"
    try:
        # The adapter settings from previous runs usually persist. Try the
        # direct PID first, then fall back to re-initialising the OBD port.
        for setup in (
            ["01 " + pid.upper()],
            ["ATL0", "ATSP1", "ATSH7E0", "01 " + pid.upper()],
            ["ATZ", "ATL0", "ATSP1", "ATSH7E0", "01 " + pid.upper()],
        ):
            for payload in setup:
                response = await write_once(client, write_char, read_char, buffer, payload, wait)
                parsed = parse_soc(response, pid)
                if parsed:
                    return parsed
                if "NO DATA" in response:
                    last_error = "no_data"
                elif "SEARCHING" in response:
                    last_error = "searching"
                else:
                    last_error = "no_recognised_response"
        raise RuntimeError(last_error)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main() -> int:
    parser = argparse.ArgumentParser(description="Read the A3 PHEV HV SOC over BLE OBD.")
    parser.add_argument("--mac", default=DEFAULT_MAC)
    parser.add_argument("--pid", default="5B", help="OBD-II PID to read (default: 5B)")
    parser.add_argument("--wait", type=float, default=3.0, help="Seconds to wait after each OBD write")
    parser.add_argument("--retries", type=int, default=3, help="Connection setup retries")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--raw", action="store_true", help="Print raw value only")
    parser.add_argument("--soc", action="store_true", help="Print SOC percentage only")
    args = parser.parse_args()

    result = await read_soc(args.mac, args.pid, args.wait, args.retries)
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.raw:
        print(result["raw"])
    elif args.soc:
        print(result["soc_pct"])
    else:
        print(f"soc_pct={result['soc_pct']} raw={result['raw']} pid={result['pid']} ts={result['ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
