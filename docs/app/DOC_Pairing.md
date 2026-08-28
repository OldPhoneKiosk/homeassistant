---
category: app
title: Pairing and device security
author: system
description: How Home Assistant creates one-time QR claims and how the iPhone connects without receiving HA admin credentials
---

# Pairing and device security

Pairing starts in Home Assistant and finishes on the iPhone.

## Pair a new panel

1. Open **Settings → Devices & Services → Add Integration → OldPhoneKiosk**.
2. Home Assistant shows a pairing QR before creating the hub.
3. Open the OldPhoneKiosk iOS app and scan the QR.
4. The app redeems the claim against Home Assistant.
5. Home Assistant returns the device id and device secret.
6. The app stores the secret in Keychain and opens its WebSocket connection.
7. Only then does Home Assistant finish the flow and create the OldPhoneKiosk hub/panel.

After the hub exists, add more panels from **Settings → Devices & Services → OldPhoneKiosk → Generate pairing QR**.
When the QR is generated, Home Assistant provisions the pending panel and dynamically adds its online/battery/screen/wake/sleep entities to the existing hub; after the iOS app scans and connects, those entities update from the phone heartbeat.
For a custom name/room, call service `oldphonekiosk.pair_new_panel` from Developer Tools → Actions and provide `name`/`room`.

## QR payload

The QR payload contains payload type/version, Home Assistant base URL, one-time claim token, expiry timestamp and optional panel metadata. The compatibility field is currently named `bridge_url` because older iOS model code used that name; in this architecture it points to Home Assistant.

## What the phone never receives

The iPhone does **not** receive Home Assistant administrator credentials, a long-lived HA access token, HACS/GitHub credentials or secrets for other devices.

## Revoke a panel

Call service `oldphonekiosk.revoke_panel` with the panel `device_id`. The device secret becomes invalid and the phone must be paired again.
