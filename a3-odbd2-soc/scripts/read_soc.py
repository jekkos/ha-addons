#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is required. Install it with: pip3 install pyserial")

DEFAULT_TARGETS = ["7E0", "7E5"]
DEFAULT_DIDS = ["1150", "1E0E"]
DEFAULT_PAIRS = [("7E0", "1150"), ("7E5", "1E0E")]


def clean_hex(value):
    return value.strip().upper().replace("0X", "")


def split_hex(value):
    value = clean_hex(value)
    if len(value) % 2:
        value = "0" + value
    return " ".join(value[i : i + 2] for i in range(0, len(value), 2))


def read_until_quiet(ser, timeout, quiet=0.25):
    buf = b""
    start = time.time()
    last_data = time.time()
    while time.time() < start + timeout:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting)
            last_data = time.time()
        elif buf and time.time() - last_data > quiet:
            break
        else:
            time.sleep(0.02)
    return buf.decode(errors="replace")


def send_cmd(ser, cmd, timeout=1.0):
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    ser.write((cmd + "\r\n").encode())
    ser.flush()
    return read_until_quiet(ser, timeout)


def command_for(did, raw_iso):
    cmd = "22 " + split_hex(did)
    if raw_iso:
        cmd = "03 " + cmd
    return cmd


def scaled_candidates(raw_int):
    out = {}
    if raw_int is None:
        return out
    out["raw"] = raw_int
    if raw_int <= 1000:
        out["div10"] = raw_int / 10
    if raw_int <= 1023:
        out["percent_1023"] = raw_int * 100 / 1023
    return out


def parse_response(response, did):
    did_parts = split_hex(did).split()
    pattern = (
        r"^\s*\+?62\s+"
        + r"\s+".join(re.escape(part) for part in did_parts)
        + r"\s+((?:[0-9A-Fa-f]{2}\s*)+)"
    )
    match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
    if match:
        data = [int(part, 16) for part in match.group(1).split()]
        raw_int = int.from_bytes(bytes(data), "big") if data else None
        return {
            "ok": True,
            "value_bytes": data,
            "raw_int": raw_int,
            "value": raw_int if raw_int is not None and raw_int <= 100 else None,
            "scaled_candidates": scaled_candidates(raw_int),
        }

    negative = re.search(r"^\s*\+?7f\s+22\s+([0-9A-Fa-f]{2})", response, re.IGNORECASE | re.MULTILINE)
    if negative:
        return {
            "ok": False,
            "error": "negative_response",
            "nrc": int(negative.group(1), 16),
        }

    if re.search(r"^\s*(NO DATA|ERROR|NOT SUPPORTED)", response, re.IGNORECASE | re.MULTILINE):
        return {"ok": False, "error": "adapter_error"}

    return {"ok": False, "error": "no_recognised_response"}


def build_pairs(args):
    if args.all:
        targets = [clean_hex(x) for x in args.targets.split(",") if x.strip()]
        dids = [clean_hex(x) for x in args.dids.split(",") if x.strip()]
        return [(target, did) for target in targets for did in dids]

    if args.pairs:
        pairs = []
        for part in args.pairs.split(","):
            part = part.strip()
            if not part:
                continue
            target, did = part.split(":", 1)
            pairs.append((clean_hex(target), clean_hex(did)))
        return pairs

    return DEFAULT_PAIRS


def read_soc(device, pairs=None, baud=115200, raw_iso=False, extended=True, timeout=1.0):
    pairs = pairs or DEFAULT_PAIRS
    ser = serial.Serial(device, baudrate=baud, timeout=1)
    results = []
    try:
        send_cmd(ser, "ATZ", 1.5)
        send_cmd(ser, "ATL0", 0.5)
        send_cmd(ser, "ATSP08", 0.5)
        send_cmd(ser, "ATCA0" if raw_iso else "ATCA1", 0.5)

        for target, did in pairs:
            send_cmd(ser, f"ATSH{target}", 0.5)
            if extended:
                send_cmd(ser, "10 03", 1.0)
            cmd = command_for(did, raw_iso)
            raw = send_cmd(ser, cmd, timeout)
            result = {
                "target": target,
                "did": did,
                "command": cmd,
                "raw": raw.strip(),
            }
            result.update(parse_response(raw, did))
            results.append(result)
    finally:
        ser.close()
    return results


def display_value(result):
    if result.get("value") is not None:
        return result["value"]
    if result.get("raw_int") is not None:
        return result["raw_int"]
    return None


def main():
    parser = argparse.ArgumentParser(description="Read candidate Audi A3 8Y SOC DIDs over an ELM327/UDS adapter.")
    parser.add_argument("--device", required=True, help="/dev/ttyUSB0, /dev/rfcomm0, etc.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--pairs", help="Comma list like 7E0:1150,7E5:1E0E")
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS), help="Comma list of target addresses")
    parser.add_argument("--dids", default=",".join(DEFAULT_DIDS), help="Comma list of DIDs")
    parser.add_argument("--all", action="store_true", help="Test every target/DID combination")
    parser.add_argument("--raw-iso", action="store_true", help="Prefix requests with ISO-TP single-frame length 03")
    parser.add_argument("--no-extended", action="store_true", help="Skip UDS extended session 10 03")
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--value-only", action="store_true")
    args = parser.parse_args()

    results = read_soc(
        args.device,
        build_pairs(args),
        args.baud,
        args.raw_iso,
        not args.no_extended,
        args.timeout,
    )

    if args.value_only:
        for result in results:
            value = display_value(result)
            if value is not None:
                print(value)
                return
        sys.exit(2)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    for result in results:
        print(
            "target=0x{target} did=0x{did} command={command} ok={ok}".format(
                target=result["target"],
                did=result["did"],
                command=result["command"],
                ok=result["ok"],
            )
        )
        print(f"  raw={result['raw']!r}")
        if result.get("value_bytes") is not None:
            print(f"  value_bytes={result['value_bytes']}")
            print(f"  raw_int={result['raw_int']}")
            print(f"  value={result['value']}")
            print(f"  scaled={result['scaled_candidates']}")
        if result.get("error"):
            print(f"  error={result['error']} nrc={result.get('nrc', '')}")


if __name__ == "__main__":
    main()
