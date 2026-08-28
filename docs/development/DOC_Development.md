---
category: development
title: Development guide
author: system
description: Local development workflow for the OldPhoneKiosk Home Assistant custom integration
---

# Development guide

## Repository boundary

This repository contains only the Home Assistant custom integration. The iOS app is intentionally separate and may remain private.

The integration must remain Python because Home Assistant loads `custom_components` in its Python runtime. A Go backend would require a separate add-on or sidecar process, which this architecture avoids.

## Local environment

```bash
cd homeassistant
python3.11 -m venv .venv-ha
. .venv-ha/bin/activate
pip install -e '.[ha-test]'
```

## Test commands

```bash
python -m compileall -q custom_components/oldphonekiosk
pytest -q
pytest tests_ha -q
pytest -q tests tests_ha
```

## Code structure

- `http.py` — HA HTTP/WebSocket views for device-facing routes.
- `native_client.py` — in-process facade replacing the previous external bridge client.
- `registry.py` — device registry, command queue, online state.
- `store.py` — SQLite persistence under `<HA_CONFIG>/oldphonekiosk/`.
- `security.py` — device secret hashing.
- `wstoken.py` — short-lived WebSocket token signing/verification.
- `services.py` — Home Assistant service handlers.
- `tests/` — fast tests without HA runtime.
- `tests_ha/` — Home Assistant harness tests.

## Compatibility rules

Keep old payload field names when the iOS app still depends on them, do not give devices HA admin tokens, keep pairing tokens one-time and short-lived, and raise user-readable Home Assistant errors from services.
