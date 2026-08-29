---
category: app
title: Pairing and device security
author: system
description: How Home Assistant creates one-time pairing codes and how the iPhone connects without receiving HA admin credentials
---

# Pairing and device security

Pairing starts in Home Assistant and finishes on the iPhone/iPad.

## Pair over Wi‑Fi

1. Install/update the OldPhoneKiosk Home Assistant plugin.
2. Open the OldPhoneKiosk iOS app.
3. Press **Pair over Wi‑Fi**. The app advertises itself on the local network for 15 minutes using Bonjour.
4. In Home Assistant, confirm the discovered OldPhoneKiosk device.
5. Home Assistant pushes a one-time claim to the phone/tablet.
6. The app redeems the claim against Home Assistant.
7. Home Assistant returns the device id and device secret.
8. The app stores the secret in Keychain and opens its WebSocket connection.

## 10-digit code fallback

If Wi‑Fi discovery is unavailable, call service `oldphonekiosk.pair_new_panel` or press the hub button **Generate pairing code**. Home Assistant shows a one-time 10-digit code. Type that code in the iOS app to redeem the claim and connect.

## What the phone never receives

The iPhone does **not** receive Home Assistant administrator credentials, a long-lived HA access token, HACS/GitHub credentials or secrets for other devices.

## Revoke a panel

Call service `oldphonekiosk.revoke_panel` with the panel `device_id`. The device secret becomes invalid and the phone must be paired again.
