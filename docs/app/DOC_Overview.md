---
category: app
title: What is OldPhoneKiosk
author: system
description: OldPhoneKiosk turns an old iPhone into a local Home Assistant wall panel without a separate bridge service
---

# What is OldPhoneKiosk

OldPhoneKiosk is a Home Assistant wall-panel system for reusing old iPhones, iPads, and Kindle/web displays as dedicated room surfaces.

The project has two parts:

1. **Home Assistant integration** — this public repository. It installs into Home Assistant through HACS and owns pairing, web-display URLs, device state, commands, and WebSocket communication.
2. **iOS panel app** — the companion mobile application. It runs on the iPhone/iPad, shows the panel UI, stores device credentials in Keychain, and connects directly to Home Assistant.
3. **Kindle/web display** — a lightweight server-rendered page opened from one local URL. It can show calendar/tasks/state plus optional signed quick actions, without pairing or storing an HA admin token on the Kindle.

## Why it exists

A phone already has a good screen, battery, Wi‑Fi, camera, speakers, and secure storage. OldPhoneKiosk lets that phone become a local smart-home panel instead of e-waste.

Typical uses:

- kitchen or hallway Home Assistant panel,
- always-on photo/tasks/dashboard screen,
- quick wake/sleep automation target,
- local device status telemetry: online, battery, app version and last seen,
- camera/intercom/media scenarios without giving the phone HA admin credentials,
- calm Kindle e-ink displays with safe links to toggle selected lights/switches and mark existing todo items Done.

## Current architecture

Earlier builds used an external Bridge service between the phone and Home Assistant. The current architecture removes that extra process. Home Assistant itself serves pairing, WebSocket token and device WebSocket endpoints.

## Security model in one sentence

Home Assistant administrators create a one-time pairing claim for iOS panels; the iPhone/iPad redeems it once and receives only a device-specific secret, never a Home Assistant admin token. Kindle/web displays are created in Home Assistant and opened from a signed local URL; optional action links are limited to selected safe entities and existing todo completion.
