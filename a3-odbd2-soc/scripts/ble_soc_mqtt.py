#!/usr/bin/env python3
"""Read the A3 PHEV HV SOC over BLE and publish it as retained MQTT."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError as exc:
    raise SystemExit(f"Missing dependency: {exc.name}. Install it with: python3 -m pip install paho-mqtt") from exc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ble_soc import read_soc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value
    return default


def env_float(name: str, default: float) -> float:
    raw = env(name)
    if raw:
        return float(raw)
    return default


def mqtt_settings() -> dict:
    topic = env("MQTT_TOPIC", "car/a3/hv_soc")
    return {
        "host": env("MQTT_HOST", "localhost"),
        "port": int(env("MQTT_PORT", "1883")),
        "username": env("MQTT_USERNAME"),
        "password": env("MQTT_PASSWORD"),
        "topic": topic,
        "availability_topic": env("MQTT_AVAILABILITY_TOPIC", topic + "/availability"),
        "kwh_topic": env("MQTT_KWH_TOPIC", "car/a3/hv_kwh"),
    }


def publish_mqtt(payload: str, online: bool, kwh_payload: Optional[str] = None) -> None:
    settings = mqtt_settings()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"a3-ble-soc-{os.getpid()}",
        protocol=mqtt.MQTTv311,
    )
    if settings["username"]:
        client.username_pw_set(settings["username"], settings["password"])
    client.will_set(settings["availability_topic"], payload="offline", qos=1, retain=True)

    client.connect(settings["host"], settings["port"], keepalive=60)
    client.loop_start()

    try:
        client.publish(settings["availability_topic"], payload="online" if online else "offline", qos=1, retain=True)
        publish_discovery(client, settings)
        if online:
            info = client.publish(settings["topic"], payload=payload, qos=1, retain=True)
            info.wait_for_publish(timeout=10)
            if kwh_payload is not None:
                kwh_info = client.publish(settings["kwh_topic"], payload=kwh_payload, qos=1, retain=True)
                kwh_info.wait_for_publish(timeout=10)
    finally:
        client.loop_stop()
        client.disconnect()


def publish_discovery(client, settings: dict) -> None:
    device = {
        "identifiers": ["a3-odbd2-soc"],
        "name": "A3 PHEV HV SOC",
        "model": "40 TFSIe",
        "manufacturer": "Audi",
    }

    soc_config = {
        "name": "A3 PHEV HV SOC",
        "unique_id": "a3_odbd2_soc_hv_soc",
        "state_topic": settings["topic"],
        "availability_topic": settings["availability_topic"],
        "payload_available": "online",
        "payload_not_available": "offline",
        "value_template": "{{ value | float }}",
        "device_class": "battery",
        "state_class": "measurement",
        "unit_of_measurement": "%",
        "device": device,
    }

    kwh_config = {
        "name": "A3 PHEV HV Available Energy",
        "unique_id": "a3_odbd2_soc_hv_kwh",
        "state_topic": settings["kwh_topic"],
        "availability_topic": settings["availability_topic"],
        "payload_available": "online",
        "payload_not_available": "offline",
        "value_template": "{{ value | float }}",
        "state_class": "measurement",
        "unit_of_measurement": "kWh",
        "device": device,
    }

    client.publish(
        f"homeassistant/sensor/{settings['topic'].replace('/', '_')}/config",
        json.dumps(soc_config),
        qos=1,
        retain=True,
    )
    client.publish(
        f"homeassistant/sensor/{settings['kwh_topic'].replace('/', '_')}/config",
        json.dumps(kwh_config),
        qos=1,
        retain=True,
    )


def net_usable_kwh(value: Optional[str] = None) -> float:
    raw = value or env("NET_USABLE_KWH", "12.4")
    number = float(raw)
    if number <= 0:
        raise ValueError("NET_USABLE_KWH must be greater than 0")
    return number


def kwh_from_soc(soc_pct: float, usable_kwh: float) -> str:
    return f"{soc_pct * usable_kwh / 100.0:.3f}"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Publish the A3 PHEV HV SOC to MQTT.")
    parser.add_argument("--mac", default=None, help="BLE adapter MAC address")
    parser.add_argument("--pid", default=None, help="OBD PID to read (hex)")
    parser.add_argument("--wait", type=float, default=None, help="Connection wait time")
    parser.add_argument("--retries", type=int, default=None, help="Number of retries")
    parser.add_argument("--net-kwh", default=None, help="Net usable HV battery capacity in kWh")
    parser.add_argument("--print", action="store_true", help="Also print the result")
    args = parser.parse_args()

    mac = args.mac or env("BLE_MAC", "00:10:CC:4F:36:03")
    pid = args.pid or env("OBD_PID", "5B")
    wait_time = args.wait if args.wait is not None else env_float("READ_WAIT", 3.0)
    retries = args.retries if args.retries is not None else int(env("READ_RETRIES", "3"))
    net_kwh = args.net_kwh or env("NET_USABLE_KWH")

    load_env_file(ENV_FILE)

    try:
        result = await read_soc(mac, pid, wait_time, retries)
    except Exception as exc:
        payload = "offline"
        try:
            publish_mqtt(payload, online=False)
        except Exception as mqtt_exc:
            raise SystemExit(f"SOC read failed: {exc}; MQTT offline publish failed: {mqtt_exc}") from mqtt_exc
        if args.print:
            print(f"soc=unavailable error={exc}")
        return 1

    payload = str(result["soc_pct"])
    usable_kwh = net_usable_kwh(net_kwh)
    kwh_payload = kwh_from_soc(float(payload), usable_kwh)
    publish_mqtt(payload, online=True, kwh_payload=kwh_payload)

    if args.print:
        print(json.dumps({**result, "net_usable_kwh": usable_kwh, "estimated_available_kwh": kwh_payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
