# OldPhoneKiosk — Home Assistant integration

Custom integration that talks **only to the Bridge** and exposes each panel as a
Home Assistant device with entities and screen-control services.

Protocol: see [`_p/docs/protocol-foundation.md`](../_p/docs/protocol-foundation.md).

## Entities per panel (foundation)

| Entity | Type | Purpose |
| ------ | ---- | ------- |
| `binary_sensor.<panel>_online`   | connectivity | Panel online |
| `sensor.<panel>_battery`         | battery %    | Battery level |
| `sensor.<panel>_last_seen`       | timestamp    | Last heartbeat |
| `sensor.<panel>_app_version`     | text         | iOS app version |
| `select.<panel>_screen`          | select       | photos / tasks / home / sleep |
| `button.<panel>_wake`            | button       | Wake command |
| `button.<panel>_sleep`           | button       | Sleep command |

## Install (dev)

Copy the component into your HA config:

```bash
cp -r custom_components/oldphonekiosk <HA_CONFIG>/custom_components/oldphonekiosk
```

Restart Home Assistant, then add the integration:
**Settings → Devices & Services → Add Integration → OldPhoneKiosk**, and enter the
Bridge URL (e.g. `http://127.0.0.1:8788`) and API key.

## Services

### `oldphonekiosk.pair_new_panel`

Provisions a **new** panel on the Bridge (start + approve, using the configured
API key) and returns a **pairing QR payload** to scan in the OldPhoneKiosk app. It
also raises a persistent notification with the QR image (or the raw payload).

```yaml
service: oldphonekiosk.pair_new_panel
data:
  name: Kitchen Panel
  room: Kitchen
```

Response (service supports response data):

```yaml
device_id: "b1e7c2a0-..."
payload: '{"bridge_url":"http://bridge.local:8788","device_id":"...","device_secret":"...","version":1,...}'
qr_svg_data_uri: "data:image/svg+xml;base64,..."   # present when qrcode is installed
```

The panel app scans the QR (or you can paste the `payload`) to finish pairing; it
then fetches a short-lived WS token and connects. The QR image needs the `qrcode`
library (declared in the manifest); without it the payload is still returned.

> The QR carries `device_secret`. Show it briefly and let one panel scan it.
> `bridge_url` must be reachable from the device (not `127.0.0.1` for a real phone).

### `oldphonekiosk.start_stream` / `oldphonekiosk.stop_stream`

Start/stop a media publisher session on the Bridge (go2rtc). `start_stream` takes
`device_id` (+ optional `camera_mode`); the Bridge sets the viewer URL and tells
the panel to publish. Real publishing needs a device build with a WebRTC
publisher — otherwise the panel reports the stream as `unsupported` (visible in the
`stream` attribute). `stop_stream` takes `device_id`.

```yaml
service: oldphonekiosk.start_stream
data: { device_id: b1e7c2a0-..., camera_mode: front }
```

### `oldphonekiosk.set_media`

Sets a panel's **media config** on the Bridge: the `video_url` (a WebRTC/go2rtc
player page the Lovelace card renders) and/or the `camera_mode`.

```yaml
service: oldphonekiosk.set_media
data:
  device_id: b1e7c2a0-...            # Bridge device id
  video_url: "http://homeassistant.local:1984/stream.html?src=front_door"
  camera_mode: front                 # off | front | back | dual
```

Every panel entity also exposes `video_url`, `camera_mode`, and `intercom` as
state attributes, so the Lovelace card can read them (e.g. from
`binary_sensor.<panel>_online`). Nothing is hardcoded — the URL comes from you.

### `oldphonekiosk.revoke_panel`

Revokes and removes a panel on its Bridge (`DELETE /api/devices/{id}`), then
removes the matching Home Assistant device. The panel must re-pair to reconnect.

It takes the **Bridge** `device_id` — not the HA registry device id. Every panel
entity exposes it as the `bridge_device_id` state attribute, so you can read it
from Developer Tools → States (e.g. on `binary_sensor.<panel>_online`).

```yaml
service: oldphonekiosk.revoke_panel
data:
  device_id: b1e7c2a0-1234-4f56-8abc-0123456789ab   # Bridge device id
```

Errors: an unknown/unconfigured id raises a validation error; if the Bridge
already forgot the device, HA still cleans up its side.

## Tests

Fast unit tests cover the Bridge API client and data parsing against a mocked
transport — no Home Assistant runtime required (see ADR 0001).

```bash
cd homeassistant
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

### Full HA runtime harness (`tests_ha/`)

`tests_ha/` runs against a real Home Assistant using
`pytest-homeassistant-custom-component` (PHACC): config flow (happy path +
`cannot_connect`/`invalid_auth`), coordinator data building, and the
`revoke_panel` service (full entry setup → call → device removed).

PHACC pulls a large, version-pinned HA, so install it in a **separate** venv from
the fast `dev` tests. On Python 3.11 use the pinned `ha-test` extra
(HA 2024.1.4 — the last release supporting 3.11):

```bash
cd homeassistant
python3.11 -m venv .venv-ha
. .venv-ha/bin/activate
pip install -e '.[ha-test]'
pytest tests_ha -q
```

> The component keeps a small compat shim for `ConfigFlowResult` (added in
> HA 2024.4) so it loads on both 2024.1 and current HA.
>
> The fast `tests/` run (`pytest`) only collects `tests/` (`testpaths`), so it is
> unaffected and needs neither HA nor PHACC.

### CI

`.github/workflows/tests.yml` (push/PR to `main` + manual dispatch):

| Job | Python | What it runs |
| --- | ------ | ------------ |
| `fast-tests` | 3.11 **and** 3.12 | `pip install -e '.[dev]'` → `pytest` (HA-free unit tests) |
| `ha-harness` | 3.12 | newest `pytest-homeassistant-custom-component<0.14` that resolves on 3.12 → `pytest tests_ha` |

The harness job installs the newest PHACC that resolves on Python 3.12 (pip
backtracks past HA lines that require 3.13), so CI exercises a **newer** Home
Assistant than the local 3.11 pin. Locally, PHACC is pinned to `0.13.90`
(HA 2024.1.4) because that is the last line supporting Python 3.11 — the only
interpreter available on the dev box. The `ConfigFlowResult` shim keeps the
component loading across both.

## Layout

```
custom_components/oldphonekiosk/
  api.py            # pure httpx Bridge client (HA-independent, unit-tested)
  const.py          # domain constants and mappings
  coordinator.py    # DataUpdateCoordinator polling the Bridge
  config_flow.py    # Bridge URL + API key setup
  __init__.py       # entry setup/unload, platform forwarding, service registration
  entity.py         # shared base entity / device_info (+ bridge_device_id attribute)
  services.py       # revoke_panel + pair_new_panel handlers
  services.yaml     # service schemas shown in the HA UI
  pairing.py        # pairing QR payload build + SVG QR (HA-independent)
  binary_sensor.py sensor.py select.py button.py
  strings.json translations/en.json
```
