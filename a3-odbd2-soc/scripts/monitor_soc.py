#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_soc import build_pairs, display_value, read_soc


def parse_args():
    parser = argparse.ArgumentParser(description="Periodically read candidate Audi A3 8Y SOC DIDs.")
    parser.add_argument("--device", required=True)
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--output")
    parser.add_argument("--format", choices=["kv", "json", "value"], default="kv")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--pairs")
    parser.add_argument("--targets", default="7E0,7E5")
    parser.add_argument("--dids", default="1150,1E0E")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--raw-iso", action="store_true")
    parser.add_argument("--no-extended", action="store_true")
    parser.add_argument("--timeout", type=float, default=1.0)
    return parser.parse_args()


def write_line(line, output):
    print(line)
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def result_line(results, fmt):
    ts = datetime.now(timezone.utc).isoformat()
    if fmt == "json":
        return json.dumps({"ts": ts, "results": results})

    if fmt == "value":
        for result in results:
            value = display_value(result)
            if value is not None:
                return str(value)
        return f"ts={ts} error=no_value"

    parts = [f"ts={ts}"]
    for result in results:
        label = f"{result['target']}_{result['did']}"
        value = display_value(result)
        if value is not None:
            parts.append(f"{label}={value}")
        else:
            parts.append(f"{label}=err:{result.get('error', 'unknown')}")
    return " ".join(parts)


def main():
    args = parse_args()
    pairs = build_pairs(args)
    while True:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            results = read_soc(
                args.device,
                pairs,
                args.baud,
                args.raw_iso,
                not args.no_extended,
                args.timeout,
            )
        except Exception as exc:
            write_line(f"ts={ts} error={type(exc).__name__}:{exc}", args.output)
        else:
            write_line(result_line(results, args.format), args.output)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
