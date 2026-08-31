# Changelog

## 0.1.29 - 2026-08-31

- Add a per-panel **Rotate camera 180°** switch that persists in Home Assistant and is replayed to the iOS app on reconnect.
- The camera rotation setting is sent through `configure_ui` as `camera_rotate_180`, allowing the iOS MJPEG publisher to correct upside-down camera output.

## 0.1.28 - 2026-08-31

- Keep the panel Camera entity visible on the Home Assistant device page even before the iOS app reports a live MJPEG URL.
- Add camera diagnostics attributes (`video_url`, `camera_mode`, `stream`) so operators can verify whether Start front/back camera produced a stream URL.

## 0.1.27 - 2026-08-31

- Make Start intercom establish a practical HA-side video connection by starting the panel's front-camera MJPEG publisher before setting intercom state.
- The intercom button/service now opens the camera path users need for an incoming/talk session; live two-way audio remains reserved for the later WebRTC audio path.

## 0.1.26 - 2026-08-31

- Document the direct iOS local MJPEG camera path for front/back camera streaming into Home Assistant.
- Refresh service descriptions so camera streaming no longer appears blocked on WebRTC/go2rtc.

## 0.1.25 - 2026-08-31

- Remove the unused photo location overlay switch because Google Photos Picker does not provide location metadata.
- Keep the photo clock overlay as the only HA-driven photo metadata overlay.

## 0.1.24 - 2026-08-30

- Add per-panel photo overlay switches for showing the clock on the native iPad Photos screen.

## 0.1.23 - 2026-08-30

- Track iOS charging state from panel heartbeats and expose it as a `Charging` binary sensor plus `battery_state` attributes.

## 0.1.22 - 2026-08-30

- Build the iOS Photos screen camera proxy redirect from the loaded HA camera entity's `entity_picture` property, ensuring the tokenized proxy URL is used instead of falling back to a server snapshot path that can return 500/502.

## 0.1.21 - 2026-08-30

- Prefer Home Assistant's own camera proxy URL for the iOS Photos screen when a camera entity exposes `entity_picture`, matching the dashboard path that already renders Google Photos correctly.

## 0.1.20 - 2026-08-30

- Refresh camera entities dynamically in the Photo source picker so Google Photos cameras that load after OldPhoneKiosk still appear in the select options.

## 0.1.19 - 2026-08-30

- Add authenticated panel photo snapshot endpoint for the iOS Photos screen.
- Discover `camera.*` entities in the panel Photo source picker and prefer cameras with imported media such as Google Photos Album.
- Selecting a Photo source now switches the panel to the Photos screen.

## 0.1.18 - 2026-08-30

- Include task `assignee` and a JSON `details` object in snapshots sent to iOS so the phone can show task detail modals.

## 0.1.17 - 2026-08-30

- Add per-panel `number.*_refresh_tasks_every` control for automatic task refresh cadence.
- Persist task refresh cadence in the Home Assistant-owned device config database.
- Send task refresh cadence to the iOS app on connect and when changed.
- Include task refresh cadence in legacy bridge/native client models.

