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
| `binary_sensor.<panel>_charging` | whether the iPhone/iPad heartbeat reports charging/full; the raw `battery_state` attribute is `charging`, `full`, `unplugged`, or `unknown` |
| `sensor.<panel>_battery` | battery percentage reported by the app |
| `sensor.<panel>_last_seen` | last heartbeat timestamp |
| `sensor.<panel>_app_version` | iOS app build/version |
| `select.<panel>_screen` | requested panel screen (photos/tasks/actions/dashboard/home/sleep) |
| `text.<panel>_dashboard_url` | dashboard the panel shows on the dashboard screen |
| `text.<panel>_task_source` | task list id/URL feeding the tasks screen |
| `text.<panel>_photo_source` / `select.<panel>_photo_source` | photo feed/camera feeding the photos screen; `camera.*` entities are served through the authenticated panel snapshot endpoint. When HA exposes an `entity_picture` camera proxy property, the panel follows that same tokenized proxy path, matching dashboard rendering. The select refreshes camera options dynamically, so cameras from integrations such as Google Photos Album appear even if they load after OldPhoneKiosk. |
| `text.<panel>_sound` | sound name/id/URL dispatched by the Play sound button |
| `switch.<panel>_photo_time_overlay` | shows/hides the fixed-position clock overlay on the native Photos screen |
| `number.<panel>_dim_after` | seconds before the app dims the panel UI while idle |
| `number.<panel>_sleep_screen_after` | seconds before the app enters its sleep/blank screen while idle |
| `number.<panel>_refresh_tasks_every` | seconds between automatic task refresh requests from the panel; `0` disables auto-refresh |
| `camera.<panel>_camera` | panel camera entity; visible even before stream starts, then shows the live still/MJPEG view once `video_url` arrives |
| `button.<panel>_wake` | send wake command |
| `button.<panel>_sleep` | send sleep command |
| `button.<panel>_start_front_camera` | start the front camera stream |
| `button.<panel>_start_back_camera` | start the back camera stream |
| `button.<panel>_stop_camera` | stop the camera stream |
| `button.<panel>_beep` | play a short attention beep + haptic |
| `button.<panel>_play_sound` | play the configured Sound |
| `button.<panel>_start_intercom` | open an intercom session (ringing/talking) |
| `button.<panel>_stop_intercom` | close the intercom session |

Every control is bound to the phone's Home Assistant **device**, so the whole panel is operated from its device page — Home Assistant is the source of truth and the iOS app only receives and applies commands.

Common state attributes include the durable panel id, camera/media/intercom state, the dashboard/task/photo/sound config, and compatibility fields needed by dashboard cards.

## Services

### `oldphonekiosk.pair_new_panel`

Creates a pending panel and returns a one-time 10-digit pairing code.

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

Start/stop the iOS panel's foreground local MJPEG camera publisher. After start,
the panel reports a LAN `videoUrl` in its heartbeat; Home Assistant exposes that
URL via `camera.<panel>_camera`. The clock/photo screens can keep running, but iOS
must keep the app foreground for camera publishing.

### `oldphonekiosk.set_panel_ui`

Push kiosk navigation/config to a panel. Only provided fields change; they persist and re-apply after a restart.

```yaml
service: oldphonekiosk.set_panel_ui
data:
  device_id: b1e7c2a0-...
  default_screen: dashboard
  dashboard_url: "http://homeassistant.local:8123/lovelace/kitchen"
  task_source: todo.kitchen
  task_refresh_seconds: 60
  photo_source: album.family
```

The same cadence is exposed on each panel device page as `number.<panel>_refresh_tasks_every`. Setting it to `0` disables automatic refresh; otherwise the connected iOS app periodically asks Home Assistant for a fresh snapshot of the configured `todo.*` source.

Each panel also exposes `switch.<panel>_rotate_camera_180deg` (**Rotate camera 180°** / **Obróć kamerę o 180°**). Turn it on when the live camera preview is upside down; Home Assistant persists the setting and replays it to the iOS app as `camera_rotate_180` on reconnect.

Task snapshots include the standard HA todo fields (`uid`, `summary`, `status`, `due`, `description`) and may include `assignee` plus a compact JSON `details` object for extra metadata. The iOS app renders these fields in a read-only task detail modal when the user taps a task row.

### `oldphonekiosk.beep`

Play a short attention beep + haptic on the panel.

```yaml
service: oldphonekiosk.beep
data:
  device_id: b1e7c2a0-...
```

### `oldphonekiosk.play_sound`

Play a sound on the panel: a system sound id, a bundled sound name, or a remote `url`. With none of them, the panel's stored **Sound** value is used.

```yaml
service: oldphonekiosk.play_sound
data:
  device_id: b1e7c2a0-...
  url: "http://homeassistant.local:8123/local/chime.mp3"
```

### `oldphonekiosk.start_intercom` and `oldphonekiosk.stop_intercom`

Open/close an intercom session on the panel. `start_intercom` first starts the panel's front-camera MJPEG publisher, so HA can immediately show the visual call through `camera.<panel>_camera`, then sets the panel intercom state to ringing/talking.

For live two-way audio, add the Lovelace custom card next to the panel camera. The card asks the HA browser for microphone permission, shows the camera preview, creates an audio-only WebRTC peer connection, and uses the integration websocket API as signaling only. Audio media flows directly between the HA browser and the iOS app; Home Assistant does not proxy PCM/Opus audio chunks. Use **Zadzwoń** to start the intercom, iPad front camera, and speaker audio; hold **Mów** only while speaking; use **Rozłącz** to stop the intercom and camera.

Add this dashboard resource after installing/updating the integration and restarting Home Assistant:

```text
/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=0.1.36
```

Then add a manual Lovelace card, using any OldPhoneKiosk entity with `bridge_device_id` plus the camera entity:

```yaml
type: custom:oldphonekiosk-intercom-card
entity: binary_sensor.<panel>_online
camera_entity: camera.<panel>_camera
```

If the selected entity does not expose `bridge_device_id`, pass it explicitly from the card subtitle/device attributes:

```yaml
type: custom:oldphonekiosk-intercom-card
device_id: 85e1c25b-2cc2-44dd-9f88-1e05ed208d98
camera_entity: camera.ipad_camera
name: iPad
```

```yaml
service: oldphonekiosk.start_intercom
data:
  device_id: b1e7c2a0-...
  mode: talk
```
