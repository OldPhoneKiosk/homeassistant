# OldPhoneKiosk — Home Assistant integration

<p align="center">
  <img src="icon.png" alt="OldPhoneKiosk icon" width="128" height="128">
</p>

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=OldPhoneKiosk&repository=homeassistant&category=integration)
[![HA integration tests](https://github.com/OldPhoneKiosk/homeassistant/actions/workflows/tests.yml/badge.svg)](https://github.com/OldPhoneKiosk/homeassistant/actions/workflows/tests.yml)
[![Repository checks](https://github.com/OldPhoneKiosk/homeassistant/actions/workflows/lint.yml/badge.svg)](https://github.com/OldPhoneKiosk/homeassistant/actions/workflows/lint.yml)

OldPhoneKiosk turns an old iPhone into a local Home Assistant wall panel: a dashboard/control surface that can be paired, monitored, woken, put to sleep, and directed from Home Assistant.

This repository is the **public Home Assistant integration package**. It installs through HACS and contains the backend that runs inside Home Assistant. The companion iOS app lives in a separate repository and can stay private.

## What it does

- pairs an iPhone panel with Home Assistant using a one-time QR claim token,
- stores panel credentials and state inside the Home Assistant config directory,
- exposes panel status as Home Assistant entities,
- lets automations/services send commands to a panel,
- serves device API and WebSocket routes directly from Home Assistant,
- removes the need for a separate Bridge/server process.

## Architecture

```text
Home Assistant + this custom integration
        │
        │ admin actions: normal Home Assistant auth
        │ device actions: device secret + short-lived WS token
        ▼
iPhone OldPhoneKiosk app
```

Device-facing routes are served by Home Assistant:

| Route | Purpose |
| --- | --- |
| `POST /api/oldphonekiosk/pairing/claim/redeem` | iPhone redeems a one-time QR claim and receives device credentials |
| `POST /api/oldphonekiosk/devices/{device_id}/ws-token` | paired device asks for a short-lived WebSocket token |
| `GET /api/oldphonekiosk/ws/device/{device_id}?token=...` | panel WebSocket for state updates and commands |

The QR carries a one-time claim token, not a long-lived device secret. The app redeems the claim once, stores the device secret in Keychain, then uses short-lived WebSocket tokens for live connections.

## Documentation

- [Overview](docs/app/DOC_Overview.md)
- [Installation with HACS](docs/app/DOC_Installation.md)
- [Pairing and security model](docs/app/DOC_Pairing.md)
- [Home Assistant entities and services](docs/app/DOC_HomeAssistant.md)
- [Troubleshooting](docs/app/DOC_Troubleshooting.md)
- [Reporting bugs and requesting features](docs/app/DOC_BugReporting.md)
- [Developer guide](docs/development/DOC_Development.md)
- [CI and release checks](docs/development/DOC_CI.md)

## Install through HACS

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=OldPhoneKiosk&repository=homeassistant&category=integration)

1. Make sure [HACS](https://hacs.xyz/) is installed in Home Assistant.
2. Click the button above.
3. Pick your Home Assistant instance when My Home Assistant asks.
4. HACS opens the custom repository dialog with repository `OldPhoneKiosk/homeassistant` and category `Integration`.
5. Add/download the integration in HACS.
6. Restart Home Assistant.
7. Add the integration: **Settings → Devices & Services → Add Integration → OldPhoneKiosk**.
8. The Add hub flow shows a QR; scan it from the iOS app.
9. Home Assistant creates the hub only after the phone/tablet connects.

No Bridge URL or API key is requested anymore.

## Entities per panel

| Entity | Type | Purpose |
| ------ | ---- | ------- |
| `binary_sensor.<panel>_online` | connectivity | Panel online/offline |
| `sensor.<panel>_battery` | battery % | Battery level |
| `sensor.<panel>_last_seen` | timestamp | Last heartbeat from the iPhone |
| `sensor.<panel>_app_version` | text | iOS app version |
| `select.<panel>_screen` | select | active screen: photos / tasks / home / sleep |
| `button.<panel>_wake` | button | wake the panel |
| `button.<panel>_sleep` | button | put the panel to sleep |
| `camera.<panel>_camera` | camera | local MJPEG camera stream published by the iOS app while streaming is active |

## Main services

For the first device, use **Settings → Devices & Services → Add Integration → OldPhoneKiosk**. The flow shows a QR code and does not create the hub until the iOS app scans and connects.

After the hub exists, open the OldPhoneKiosk integration page and use the hub entity **Generate pairing QR** to add more panels. Pressing that button creates a Home Assistant notification with a QR code that the iOS app can scan.

For named/room-specific setup you can still call the service manually:

### `oldphonekiosk.pair_new_panel`

```yaml
service: oldphonekiosk.pair_new_panel
data:
  name: Kitchen Panel
  room: Kitchen
```

Returns `device_id`, raw QR `payload`, and `qr_svg_data_uri` when QR rendering is available. The payload keeps the compatibility field `bridge_url`, but it points to Home Assistant.

### `oldphonekiosk.revoke_panel`

```yaml
service: oldphonekiosk.revoke_panel
data:
  device_id: b1e7c2a0-1234-4f56-8abc-0123456789ab
```

Revokes and removes a panel. The phone must re-pair to reconnect.

### `oldphonekiosk.set_media`, `start_stream`, `stop_stream`

These services control the panel camera stream. `start_stream` sends a command to the online iOS app; the app opens a foreground local MJPEG server and reports its `videoUrl` back to Home Assistant, which exposes it as `camera.<panel>_camera`. `stop_stream` stops the publisher and clears the camera URL.

## Reporting bugs and feature requests

Use GitHub Issues:

- [Report a bug](https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=bug_report.yml)
- [Request a feature](https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=feature_request.yml)

Include HA version, integration version/commit, installation method, iOS app build, relevant logs, and reproduction steps. Do not paste secrets, tokens, QR payloads with active claim tokens, or full device secrets.

## Tests

```bash
cd homeassistant
python3.11 -m venv .venv-ha
. .venv-ha/bin/activate
pip install -e '.[ha-test]'
python -m compileall -q custom_components/oldphonekiosk
pytest -q tests tests_ha
```

CI runs the same checks plus repository hygiene checks for JSON, HACS layout, documentation frontmatter, changelog freshness, test freshness, and Markdown links.

## Layout

```text
custom_components/oldphonekiosk/  # Home Assistant integration
docs/app/                         # user/operator docs, DOC_*.md
docs/development/                 # development and CI docs, DOC_*.md
.github/workflows/                # tests and repository checks
.github/scripts/                  # local/CI quality gates
```

The HA custom integration itself must be Python because Home Assistant integrations run in HA's Python runtime. A Go implementation would have to be a separate add-on/sidecar process, which this project intentionally avoids.
