---
category: app
title: Pairing and device security
author: system
description: How Home Assistant creates one-time QR claims and how the iPhone connects without receiving HA admin credentials
---

# Pairing and device security

Pairing starts in Home Assistant and finishes on the iPhone.

## Pair a new panel

1. Open **Settings → Devices & Services → OldPhoneKiosk**.
2. In the hub entities, press **Generate pairing QR**.
3. Home Assistant creates a pending device and a one-time claim token.
4. Open the Home Assistant notification created by OldPhoneKiosk.
5. Scan the QR in the iOS app.
6. The app redeems the claim against Home Assistant.
7. Home Assistant returns the device id and device secret.
8. The app stores the secret in Keychain.
9. The app asks HA for a short-lived WebSocket token and connects.

For a custom name/room, call service `oldphonekiosk.pair_new_panel` from Developer Tools → Actions and provide `name`/`room`.

## QR payload

The QR payload contains payload type/version, Home Assistant base URL, one-time claim token, expiry timestamp and optional panel metadata. The compatibility field is currently named `bridge_url` because older iOS model code used that name; in this architecture it points to Home Assistant.

## What the phone never receives

The iPhone does **not** receive Home Assistant administrator credentials, a long-lived HA access token, HACS/GitHub credentials or secrets for other devices.

## Revoke a panel

Call service `oldphonekiosk.revoke_panel` with the panel `device_id`. The device secret becomes invalid and the phone must be paired again.
