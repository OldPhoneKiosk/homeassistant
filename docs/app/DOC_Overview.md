---
category: app
title: What is OldPhoneKiosk
author: system
description: OldPhoneKiosk turns an old iPhone into a local Home Assistant wall panel without a separate bridge service
---

# What is OldPhoneKiosk

OldPhoneKiosk is a Home Assistant wall-panel system for reusing an old iPhone as a dedicated dashboard device.

The project has two parts:

1. **Home Assistant integration** — this public repository. It installs into Home Assistant through HACS and owns pairing, device state, commands, and WebSocket communication.
2. **iOS panel app** — the companion mobile application. It runs on the iPhone, shows the panel UI, stores device credentials in Keychain, and connects directly to Home Assistant.

## Why it exists

A phone already has a good screen, battery, Wi‑Fi, camera, speakers, and secure storage. OldPhoneKiosk lets that phone become a local smart-home panel instead of e-waste.

Typical uses:

- kitchen or hallway Home Assistant panel,
- always-on photo/tasks/dashboard screen,
- quick wake/sleep automation target,
- local device status telemetry: online, battery, app version and last seen,
- future camera/intercom/media scenarios without giving the phone HA admin credentials.

## Current architecture

Earlier builds used an external Bridge service between the phone and Home Assistant. The current architecture removes that extra process. Home Assistant itself serves pairing, WebSocket token and device WebSocket endpoints.

## Security model in one sentence

Home Assistant administrators create a one-time pairing claim; the iPhone redeems it once and receives only a device-specific secret, never a Home Assistant admin token.
