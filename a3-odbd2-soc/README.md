# A3 PHEV HV SOC - Home Assistant App

Reads HV SOC and available energy from Audi A3 PHEV via BLE ELM327 and exposes it to Home Assistant via MQTT.

> [!IMPORTANT]
> **HA 2026.11+**: This app uses the new `config.yaml` format (formerly known as "add-ons", now called "apps").
> It must be installed via the **App store** (Settings → Apps → Install app), not the Marketplace (HACS).
> The Marketplace only handles integrations, themes, and dashboards — not apps.

## Features

- Reads HV battery SOC from Audi A3 PHEV (8Y) via BLE ELM327 adapter
- Publishes SOC percentage to `car/a3/hv_soc`
- Publishes estimated available energy (kWh) to `car/a3/hv_kwh`
- Automatic MQTT broker discovery (built-in or external)
- Self-healing: restarts on failure with clear error messages

## Requirements

- Home Assistant Operating System (HAOS) — apps are only available on HAOS
- MQTT broker (built-in or external)
- BLE ELM327 adapter (tested with "S1 Max" BLE)
- Audi A3 PHEV (8Y) with OBD port accessible

## Installation

### Recommended: App store (HAOS)

1. Go to **Settings → Apps → Install app**
2. Click **⋮ → Repositories → Add**
3. Paste: `https://github.com/jekkos/a3-odb2-soc`
4. Click **Add**
5. Find **A3 PHEV HV SOC** and click **Install**

> [!NOTE]
> The first install triggers a GitHub Actions build (~2-3 min) to produce the Docker image.
> If the app doesn't appear after adding the repository, wait for the build to complete, then refresh your browser.

### Not supported: Marketplace (HACS)

The Marketplace (built-in HACS) only handles **integrations**, **themes**, and **dashboards**.
Apps (formerly add-ons) are a separate category managed by the HAOS Supervisor.
Do not add this repository to the Marketplace — it will report "no content to install".

## Configuration

After installation, go to the app settings:

| Option | Description | Default |
|--------|-------------|---------|
| `ble_mac` | BLE adapter MAC address | `00:10:CC:4F:36:03` |
| `obd_pid` | OBD PID to read (hex) | `5B` |
| `read_wait` | Connection wait time (seconds) | `3.0` |
| `read_retries` | Number of retries | `3` |
| `mqtt_host` | MQTT broker hostname (leave empty for built-in) | `core-mosquitto` |
| `mqtt_port` | MQTT broker port | `1883` |
| `mqtt_username` | MQTT username (leave empty for anonymous) | |
| `mqtt_password` | MQTT password (leave empty for anonymous) | |
| `net_usable_kwh` | Net usable HV battery capacity in kWh | `12.4` |

**Note:** The app automatically detects the built-in Mosquitto broker. Only configure `mqtt_host`, `mqtt_username`, and `mqtt_password` if you want to use an external broker.

## MQTT Topics

| Topic | Description |
|-------|-------------|
| `car/a3/hv_soc` | HV battery SOC percentage |
| `car/a3/hv_soc/availability` | Online/offline status |
| `car/a3/hv_kwh` | Estimated available energy (kWh) |

Sensors are automatically discovered by Home Assistant via MQTT Discovery. No manual configuration required.

## Updating

1. Go to **Settings → Apps**
2. Click on **A3 PHEV HV SOC**
3. Click **Update** in the top-right corner

The app auto-updates when a new version is published. To enable auto-update, turn on the **Auto update** toggle on the app's Info tab.

## Troubleshooting

### "Cannot connect to MQTT broker"
- Enable built-in Mosquitto: **Settings → System → Services → Mosquitto**
- Or configure external MQTT in the app settings

### BLE connection failures
- Verify BLE adapter MAC is correct
- Ensure car is awake (not in sleep mode)
- Check BLE adapter pairing in HAOS

### "No values returned"
- Verify OBD port is accessible
- Check that PID `0x5B` works with your adapter
- Look at app logs for detailed errors

### Repository not showing up in App store
- Refresh your browser after adding the repository
- Ensure the repository contains apps (not integrations or themes)
- Check the **Supervisor** log: **Settings → System → Logs → Supervisor**
- Wait for the GitHub Actions build to complete (first install)

### GitHub Actions build failed
Common causes and fixes:
- **Platform name**: Use `linux/arm/v7` (not `linux/armv7`)
- **Base image**: Use `python:3.12-slim` or newer (not `python:3.11-slim`)
- **Image tag**: Ensure the `image:` field in `config.yaml` matches your ghcr.io path
- **GitHub token**: The workflow uses `secrets.GITHUB_TOKEN` — no extra setup needed

## App Format (HA 2026.11+)

Home Assistant 2026.11+ renamed "add-ons" to "apps" and migrated to a new configuration format:

| Old format (config.json) | New format (config.yaml) |
|--------------------------|--------------------------|
| `"network_mode": "host"` | `host_network: true` |
| `boot: auto` | `homeassistant: 2024.1.0` |
| No `image:` field | `image: ghcr.io/...` (required) |
| JSON syntax | YAML syntax |

This app uses the new `config.yaml` format. See the [official HA docs](https://www.home-assistant.io/common-tasks/os/apps/) for more details.

## Development

### Build locally
```bash
docker build -t a3-odb2-soc .
```

### Run locally
```bash
docker run -d --name a3-odb2-soc \
  --network host \
  -e MQTT_HOST=your-broker \
  -e MQTT_USERNAME=your-username \
  -e MQTT_PASSWORD=your-password \
  -e BLE_MAC=your-ble-mac \
  -e NET_USABLE_KWH=12.4 \
  a3-odb2-soc
```

## License

MIT
