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

## Layout

```
custom_components/oldphonekiosk/
  api.py            # pure httpx Bridge client (HA-independent, unit-tested)
  const.py          # domain constants and mappings
  coordinator.py    # DataUpdateCoordinator polling the Bridge
  config_flow.py    # Bridge URL + API key setup
  __init__.py       # entry setup/unload, platform forwarding, service registration
  entity.py         # shared base entity / device_info (+ bridge_device_id attribute)
  services.py       # oldphonekiosk.revoke_panel handler
  services.yaml     # service schema shown in the HA UI
  binary_sensor.py sensor.py select.py button.py
  strings.json translations/en.json
```
