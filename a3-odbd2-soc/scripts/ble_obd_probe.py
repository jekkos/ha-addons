#!/usr/bin/env python3
import argparse
import asyncio
import sys
from typing import List, Optional

try:
    from bleak import BleakClient
except ModuleNotFoundError as exc:
    raise SystemExit(f"Missing dependency: {exc.name}. Install it with: python3 -m pip install bleak") from exc

WRITE_CANDIDATES = ["0000fff1-0000-1000-8000-00805f9b34fb"]
READ_CANDIDATES = ["0000fff2-0000-1000-8000-00805f9b34fb"]


def iter_characteristics(client):
    for service in client.services:
        for char in getattr(service, "characteristics", []):
            yield char


def find_characteristic(client, preferred_uuids: List[str], property_name: str):
    fallback = None
    preferred = {uuid.lower() for uuid in preferred_uuids}
    for char in iter_characteristics(client):
        if property_name in char.properties:
            if char.uuid.lower() in preferred:
                return char
            fallback = char
    return fallback


def make_handler(buffer: List[bytes]):
    def handler(_, data: bytes) -> None:
        buffer.append(bytes(data))
        sys.stdout.write(f"rx: {bytes(data).decode(errors='replace')!r}\n")
        sys.stdout.flush()

    return handler


async def send_command(client, write_char, read_char, buffer: List[bytes], payload: str, wait: float, use_response: bool, add_cr: bool, do_read: bool) -> None:
    buffer.clear()
    encoded = payload.encode("ascii") + (b"\r" if add_cr else b"")
    await client.write_gatt_char(write_char, encoded, response=use_response)
    await asyncio.sleep(wait)
    if do_read and read_char is not None:
        try:
            data = await client.read_gatt_char(read_char)
            buffer.append(bytes(data))
            sys.stdout.write(f"read: {bytes(data).decode(errors='replace')!r}\n")
            sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(f"read failed: {exc}\n")
            sys.stdout.flush()
    if buffer:
        print("response:")
        print(b"".join(buffer).decode(errors="replace"))
    else:
        print("response: <empty>")


async def subscribe(client, char, handler):
    last_exc = None
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


async def setup_connection(mac: str, write_uuid: str, read_uuid: str, do_read: bool):
    buffer: List[bytes] = []
    handler = make_handler(buffer)
    client = BleakClient(mac)
    last_exc: Optional[Exception] = None

    for attempt in range(4):
        try:
            await client.connect()
            write_char = find_characteristic(client, [write_uuid], "write")
            if write_char is None:
                raise RuntimeError("No writable characteristic found")

            read_char = find_characteristic(client, [read_uuid], "read") if do_read else None

            if "notify" in write_char.properties or "indicate" in write_char.properties:
                await subscribe(client, write_char, handler)
            if read_char is not None and ("notify" in read_char.properties or "indicate" in read_char.properties):
                await subscribe(client, read_char, handler)

            return client, write_char, read_char, buffer, handler
        except Exception as exc:
            last_exc = exc
            sys.stdout.write(f"setup attempt {attempt + 1} failed: {exc}\n")
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2.0 + attempt)

    raise SystemExit(f"Could not set up BLE OBD probe on {mac}: {last_exc}")


async def run(mac: str, payloads: List[str], wait: float, use_response: bool, add_cr: bool, do_read: bool, write_uuid: str, read_uuid: str) -> int:
    client, write_char, read_char, buffer, _ = await setup_connection(mac, write_uuid, read_uuid, do_read)

    try:
        for payload in payloads:
            sys.stdout.write(f"tx: {payload!r}\n")
            sys.stdout.flush()
            await send_command(client, write_char, read_char, buffer, payload, wait, use_response, add_cr, do_read)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe an BLE OBD/ELM327-style device with one or more text payloads.")
    parser.add_argument("--mac", default="00:10:CC:4F:36:03", help="Bluetooth MAC address")
    parser.add_argument("--payload", default=None, help="Text payload to write")
    parser.add_argument("--payloads", default=None, help="Comma-separated payloads, for example ATZ,ATL0,ATSP8")
    parser.add_argument("--wait", type=float, default=1.5, help="Seconds to wait after each payload")
    parser.add_argument("--write-uuid", default=WRITE_CANDIDATES[0], help="Write characteristic UUID")
    parser.add_argument("--read-uuid", default=READ_CANDIDATES[0], help="Read characteristic UUID")
    parser.add_argument("--no-response", action="store_true", help="Use write-without-response")
    parser.add_argument("--no-cr", action="store_true", help="Do not append carriage return")
    parser.add_argument("--read", action="store_true", help="Also read the read characteristic after each command")
    args = parser.parse_args()

    if args.payloads:
        payloads = [item.strip() for item in args.payloads.split(",") if item.strip()]
    elif args.payload:
        payloads = [args.payload]
    else:
        payloads = ["ATZ"]

    return await run(
        args.mac,
        payloads,
        args.wait,
        use_response=not args.no_response,
        add_cr=not args.no_cr,
        do_read=args.read,
        write_uuid=args.write_uuid,
        read_uuid=args.read_uuid,
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
