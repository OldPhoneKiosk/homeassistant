# OldPhoneKiosk — Home Assistant integration

Custom integration that contains the OldPhoneKiosk backend **inside Home Assistant**. There is no separate Bridge service/process: pairing, device registry, short-lived WebSocket tokens, commands, and device state are owned by the HA integration.

Protocol: see [`_p/docs/protocol-foundation.md`](../_p/docs/protocol-foundation.md).

## Architecture

```text
iPhone OldPhoneKiosk app  →  Home Assistant custom_components/oldphonekiosk
```

Device-facing routes are served by Home Assistant:

- `POST /api/oldphonekiosk/pairing/claim/redeem`
- `POST /api/oldphonekiosk/devices/{device_id}/ws-token`
- `GET  /api/oldphonekiosk/ws/device/{device_id}?token=...`

The QR carries a one-time claim token, not the long-lived device secret. The app redeems the claim once, stores its device secret in Keychain, then uses short-lived WS tokens for WebSocket connections.

## Entities per panel

| Entity | Type | Purpose |
| ------ | ---- | ------- |
| `binary_sensor.<panel>_online` | connectivity | Panel online |
| `sensor.<panel>_battery` | battery % | Battery level |
| `sensor.<panel>_last_seen` | timestamp | Last heartbeat |
| `sensor.<panel>_app_version` | text | iOS app version |
| `select.<panel>_screen` | select | photos / tasks / home / sleep |
| `button.<panel>_wake` | button | Wake command |
| `button.<panel>_sleep` | button | Sleep command |

## Install/dev

Copy the component into your HA config:

```bash
cp -r custom_components/oldphonekiosk <HA_CONFIG>/custom_components/oldphonekiosk
```

Restart Home Assistant, then add the integration:
**Settings → Devices & Services → Add Integration → OldPhoneKiosk**.

No Bridge URL or API key is requested anymore.

## Services

### `oldphonekiosk.pair_new_panel`

Provisions a **new** panel in Home Assistant and returns a pairing QR payload to scan in the OldPhoneKiosk app. The QR carries a **one-time claim token**; the app redeems it at Home Assistant for its credentials. A persistent notification with the QR image (or raw payload) is also raised.

```yaml
service: oldphonekiosk.pair_new_panel
data:
  name: Kitchen Panel
  room: Kitchen
```

Response (service supports response data):

```yaml
device_id: "b1e7c2a0-..."
payload: '{"type":"claim","bridge_url":"http://homeassistant.local:8123","claim_token":"...","version":1,...}'
qr_svg_data_uri: "data:image/svg+xml;base64,..."   # present when qrcode is installed
```

`bridge_url` is kept in the payload for compatibility with the current iOS app model, but it now points to the Home Assistant base URL. It must be reachable from the phone.

### `oldphonekiosk.start_stream` / `oldphonekiosk.stop_stream`

Start/stop a media publisher session through Home Assistant/go2rtc. `start_stream` takes `device_id` (+ optional `camera_mode`), sets the viewer URL, and tells the panel to publish. Real publishing needs a device build with a WebRTC publisher — otherwise the panel reports the stream as `unsupported`.

```yaml
service: oldphonekiosk.start_stream
data: { device_id: b1e7c2a0-..., camera_mode: front }
```

### `oldphonekiosk.set_media`

Sets a panel's **media config** in Home Assistant: the `video_url` (a WebRTC/go2rtc player page the Lovelace card renders) and/or the `camera_mode`.

```yaml
service: oldphonekiosk.set_media
data:
  device_id: b1e7c2a0-...
  video_url: "http://homeassistant.local:1984/stream.html?src=front_door"
  camera_mode: front                 # off | front | back | dual
```

Every panel entity exposes `bridge_device_id` (compatibility name), `video_url`, `camera_mode`, and `intercom` as state attributes, so the Lovelace card can read them.

### `oldphonekiosk.revoke_panel`

Revokes and removes a panel from OldPhoneKiosk in Home Assistant. The panel must re-pair to reconnect.

```yaml
service: oldphonekiosk.revoke_panel
data:
  device_id: b1e7c2a0-1234-4f56-8abc-0123456789ab
```

Errors: an unknown/unconfigured id raises a validation error.

## Tests

Fast unit tests and Home Assistant harness tests:

```bash
cd homeassistant
python3.11 -m venv .venv-ha
. .venv-ha/bin/activate
pip install -e '.[ha-test]'
pytest -q tests tests_ha
```

The HA custom integration itself must be Python because Home Assistant integrations run in HA's Python runtime. A Go implementation would have to be a separate add-on/sidecar process, which this project intentionally avoids.

## Layout

```text
custom_components/oldphonekiosk/
  __init__.py       # backend setup, storage, platform forwarding, services
  http.py           # HA-served pairing/ws-token/websocket routes
  native_client.py  # in-process backend facade used by HA coordinator/services
  registry.py       # paired device registry, commands, online state
  store.py          # SQLite persistence under <HA_CONFIG>/oldphonekiosk/
  security.py       # device secret hashing
  wstoken.py        # short-lived WebSocket token signing/verification
  models.py         # device, claim, state and command models
  protocol.py       # wire protocol helpers
  pairing.py        # QR payload build + SVG QR
  coordinator.py    # DataUpdateCoordinator over the in-process backend
  entity.py         # shared base entity / device_info
  services.py       # pair/revoke/media/stream service handlers
  services.yaml     # service schemas shown in the HA UI
  binary_sensor.py sensor.py select.py button.py
  strings.json translations/en.json
```
