---
category: app
title: Home Assistant entities and services
author: system
description: Entities, attributes and services exposed by the OldPhoneKiosk Home Assistant integration
---

# Home Assistant entities and services

After a panel is paired, OldPhoneKiosk exposes entities and services that can be used in dashboards and automations.

## Entities

| Entity | Meaning |
| --- | --- |
| `binary_sensor.<panel>_online` | whether the iPhone is currently connected/recently seen |
| `sensor.<panel>_battery` | battery percentage reported by the app |
| `sensor.<panel>_last_seen` | last heartbeat timestamp |
| `sensor.<panel>_app_version` | iOS app build/version |
| `select.<panel>_screen` | requested panel screen |
| `button.<panel>_wake` | send wake command |
| `button.<panel>_sleep` | send sleep command |

Common state attributes include the durable panel id, camera/media/intercom state, and compatibility fields needed by dashboard cards.

## Services

### `oldphonekiosk.pair_new_panel`

Creates a pending panel and returns a QR payload.

```yaml
service: oldphonekiosk.pair_new_panel
data:
  name: Kitchen Panel
  room: Kitchen
```

### `oldphonekiosk.revoke_panel`

Revokes a panel.

```yaml
service: oldphonekiosk.revoke_panel
data:
  device_id: b1e7c2a0-1234-4f56-8abc-0123456789ab
```

### `oldphonekiosk.set_media`

Sets media/camera intent for a panel.

```yaml
service: oldphonekiosk.set_media
data:
  device_id: b1e7c2a0-...
  video_url: "http://homeassistant.local:1984/stream.html?src=front_door"
  camera_mode: front
```

### `oldphonekiosk.start_stream` and `oldphonekiosk.stop_stream`

Send stream-start/stream-stop intent to the panel. Full media publishing depends on iOS app support and local media/WebRTC setup.
