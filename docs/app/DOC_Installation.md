---
category: app
title: Installation
author: system
description: Install OldPhoneKiosk in Home Assistant through HACS using the README button or a custom repository entry
---

# Installation

The recommended installation method is HACS as a custom repository.

## Before you start

You need Home Assistant with HACS installed, network access from Home Assistant to GitHub, and an iPhone/iPad that can reach the Home Assistant base URL from the same network or through your configured external HA URL.

The `OldPhoneKiosk/homeassistant` repository is public so HACS can download it without a private GitHub token.

## Install with the README button

1. Open the project README on GitHub.
2. Click **Open your Home Assistant instance and add this repository to HACS**.
3. Choose your Home Assistant instance in My Home Assistant.
4. HACS opens the custom repository dialog.
5. Confirm repository `OldPhoneKiosk/homeassistant` and category `Integration`.
6. Add the repository.
7. Download **OldPhoneKiosk** in HACS.
8. Restart Home Assistant.
9. Go to **Settings → Devices & Services → Add Integration → OldPhoneKiosk**.
10. Open the iOS app and press **Pair over Wi‑Fi**.
11. Confirm the discovered phone/tablet in Home Assistant.
12. Home Assistant creates the OldPhoneKiosk hub only after the phone/tablet connects.

No Bridge URL and no API key are required.

## Pair additional phones/tablets

1. Open **Settings → Devices & Services → OldPhoneKiosk**.
2. Select the OldPhoneKiosk hub/device.
3. Press the **Generate pairing code** button entity.
4. Type the one-time 10-digit code in the iOS app.

If you need a custom panel name or room, use **Developer Tools → Actions → `oldphonekiosk.pair_new_panel`** instead.

## Manual custom repository fallback

If the button does not open your HA instance, open **HACS → Integrations → Custom repositories**, add `https://github.com/OldPhoneKiosk/homeassistant`, choose category **Integration**, then download and restart HA.

OldPhoneKiosk's HACS metadata is configured for normal release/tag source downloads. It does not require a separate ZIP release asset.

## Manual developer install

```bash
cp -r custom_components/oldphonekiosk <HA_CONFIG>/custom_components/oldphonekiosk
```

Restart Home Assistant afterwards.

## Updating

Use the HACS update flow. After updating, restart Home Assistant so new Python modules and service schemas are loaded.
