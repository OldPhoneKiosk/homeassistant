---
category: app
title: Troubleshooting
author: system
description: Common OldPhoneKiosk installation, pairing and connectivity problems and how to diagnose them safely
---

# Troubleshooting

## HACS cannot add the repository

Check that the repository URL is exactly `https://github.com/OldPhoneKiosk/homeassistant` and category is **Integration**. The repository must remain public for the one-click HACS flow to work without a private token.

## Integration is installed but not visible

1. Restart Home Assistant after installing through HACS.
2. Check that `custom_components/oldphonekiosk/manifest.json` exists under your HA config directory.
3. Open **Settings → Devices & Services → Add Integration** and search for `OldPhoneKiosk`.

## Pairing code or Wi‑Fi pairing fails

Most failures are URL reachability issues. The phone must reach your Home Assistant URL. If `homeassistant.local` cannot be resolved from the phone, configure a working internal or external HA URL in Home Assistant network settings. Generate a fresh code because pairing codes expire and are single-use.

## Phone pairs but goes offline

Check iPhone Wi‑Fi, iOS app build, Home Assistant logs for `oldphonekiosk`, and whether the panel was revoked and needs re-pairing.

## Intercom card shows a command validation error after pressing Zadzwoń

Upgrade the OldPhoneKiosk Home Assistant integration to `0.1.37` or newer and restart Home Assistant. Older intercom card/backend combinations could start the WebRTC session but fail when the broker sent the panel `start_stream`/`start_intercom` commands, producing a Pydantic `Command command` validation error in the Lovelace card.

## Safe logs to share

Share Home Assistant version, integration version or commit, iOS app build, relevant HA log lines and reproduction steps. Do **not** share active pairing codes or claim tokens, device secrets or full Home Assistant tokens.
