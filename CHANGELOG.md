# Changelog

## 1.0.0 - 2026-09-01

- Mark OldPhoneKiosk's Home Assistant integration as the first stable HACS release.
- Keep the HACS metadata/branding updates and bump the Lovelace intercom card cache-busting URL to `?v=1.0.0`.

## 0.1.47 - 2026-09-01

- Expand HACS repository metadata so HACS renders the release/tag source, README, minimum Home Assistant version, and hides the default branch from install choices.

## 0.1.46 - 2026-09-01

- Release the production-readiness cleanup that centralizes Home Assistant-owned `configure_ui` payload formatting across services, reconnect replay and the native client.
- Include the latest internal frontend resource helper refactor so Lovelace card cache-busting remains consistent after upgrades.

## 0.1.45 - 2026-09-01

- Keep the iPad WebRTC remote audio stream attached after Lovelace card re-renders so diagnostic/status refreshes do not break playback.

## 0.1.44 - 2026-09-01

- Show all iPad intercom audio diagnostics in the HA card, including local WebRTC media-source and outbound RTP stats from iOS builds.

## 0.1.43 - 2026-09-01

- Add iPad audio-route diagnostics to the intercom card for persistent iPad→HA `level=0` capture debugging.

## 0.1.42 - 2026-09-01

- Add Lovelace intercom diagnostics for iPad→HA answer audio direction and inbound RTP stats.

## 0.1.41 - 2026-09-01

- Fix intercom WebRTC negotiation by acquiring and attaching the HA browser microphone track before creating the offer; **Mów** now only toggles the already-negotiated track.
- Re-send persisted calendar configuration and a fresh calendar snapshot when a panel reconnects, and handle device-initiated calendar refresh requests.

## 0.1.40 - 2026-09-01

- Fix Lovelace intercom audio playback for WebRTC remote audio tracks that arrive without an attached stream.
- Bump the intercom custom-card resource URL so browsers load the fixed card JavaScript after upgrade.

## 0.1.39 - 2026-08-31

- Add a native `calendar` panel screen backed by Home Assistant `calendar.*` entities.
- Add panel device controls for Calendar sources (including multi-calendar combinations) and Calendar view (`month`, `week`, `day`, `list`).
- Extend `oldphonekiosk.set_panel_ui` with `calendar_sources` and `calendar_view`, and push calendar event snapshots to connected iOS panels.

## 0.1.38 - 2026-08-31

- Fix the Lovelace intercom card `Rozłącz` flow so it sends the HA/iPad hangup before unsubscribing from the session.
- Add intercom signaling logs for `browser->device` and `device->browser` actions to diagnose iPad answer/ICE/audio paths.

## 0.1.37 - 2026-08-31

- Fix the Lovelace intercom `Zadzwoń` flow so backend-issued `start_stream` and `start_intercom` commands validate correctly before being sent to the panel.
- Keep the lightweight intercom broker compatible with fast tests while using string-compatible command values accepted by Home Assistant/Pydantic at runtime.

## 0.1.36 - 2026-08-31

- Make `Zadzwoń` start the intercom/camera/speaker without requiring browser microphone access; the browser asks for microphone only when holding `Mów`.
- Make the intercom card prefer the panel-reported `video_url` and avoid HA `/api/camera_proxy` fallback for OldPhoneKiosk camera entities while no stream URL is available.
- Prevent repeated `500 Internal Server Error` camera proxy requests before/while the iPad camera stream is starting.

## 0.1.35 - 2026-08-31

- Update an existing stale Lovelace resource URL for `oldphonekiosk-intercom-card.js` to the current cache-busted version instead of treating any old `?v=` as current.
- Fixes HA continuing to load the old two-button intercom card after upgrading to v0.1.34.

## 0.1.34 - 2026-08-31

- Change the intercom card to call/hold-to-talk/hangup UX: `Zadzwoń` starts intercom + front camera + speaker, `Mów` enables the browser microphone only while pressed, and `Rozłącz` stops intercom + camera.
- Make websocket intercom start/hangup mirror the device-page start/stop behavior by controlling the front camera stream lifecycle.

## 0.1.33 - 2026-08-31

- Show intercom card call/setup errors instead of immediately overwriting them with `Rozłączono`.
- Remove the unsupported visual editor hook warning from the custom card.
- Support explicit `device_id` card config and absolute HA camera proxy URLs.

## 0.1.32 - 2026-08-31

- Automatically add the `oldphonekiosk-intercom-card.js` Lovelace resource when Lovelace storage resources are available.
- Keep the manual resource URL documented as a fallback for YAML-mode Lovelace setups.

## 0.1.31 - 2026-08-31

- Replace the experimental `/oldphonekiosk` sidebar page with a Lovelace custom card.
- Add `custom:oldphonekiosk-intercom-card` for camera preview plus browser microphone/speaker WebRTC intercom in one dashboard card.
- Keep WebRTC signaling backend unchanged and remove sidebar panel registration.

## 0.1.30 - 2026-08-31

- Add the `/oldphonekiosk` Home Assistant frontend panel for browser microphone/speaker WebRTC intercom.
- Add authenticated HA websocket signaling commands for intercom start, subscribe, offer, ICE candidate, and hangup.
- Route `intercom_signal` frames over the existing panel device WebSocket so iOS can exchange SDP/ICE without using Home Assistant as the audio media server.

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

