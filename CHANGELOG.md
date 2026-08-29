# Changelog

All notable changes to the OldPhoneKiosk Home Assistant integration are documented here.

## Unreleased

## 0.1.14 - 2026-08-29

- Added HA todo task snapshots for the phone Tasks screen. Selecting a `todo.*` task list now pushes the list items to the paired panel via `configure_tasks` and switches the phone to Tasks.

## 0.1.13 - 2026-08-29

- Fixed additional Lovelace dashboard URLs: dashboards such as `dashboard-oscar` now generate top-level paths like `/dashboard-oscar/2` instead of invalid `/lovelace/dashboard-oscar/2` paths.

## 0.1.12 - 2026-08-29

- When Lovelace view/tab URLs are discoverable, the Dashboard select now exposes the concrete tab URLs only and avoids the default `/lovelace` / `/lovelace/0` Home target that caused panels to refresh back to Home.

## 0.1.11 - 2026-08-29

- Removed the unused Home and Actions screens from Home Assistant screen selectors; normal kiosk navigation now offers Photos, Tasks and Dashboard only.

## 0.1.10 - 2026-08-29

- Pairing now prefers Home Assistant's configured Local/Internal URL when sending the connection URL to the phone, preventing newly paired devices from saving an unreachable fallback URL and staying stuck on “Connecting”.

## 0.1.9 - 2026-08-29

- Fixed the Dashboard select to send phone-loadable absolute Home Assistant URLs when HA has an internal/external URL configured, instead of sending only `/lovelace/...` paths.
- Added Lovelace view/tab URLs to Dashboard select options when HA exposes dashboard views, so the phone can be pointed directly at tabs like `/lovelace/ada`, `/lovelace/tomas` or `/lovelace/dashboard`.

## 0.1.8 - 2026-08-29

- Added HA-first per-panel select controls for Dashboard, Task list, Sound and Photo source on the device page, so users can pick from Home Assistant resources instead of typing raw values.
- Dashboard options are discovered from Lovelace dashboards with safe defaults, Task list options come from `todo.*` entities, and Sound/Photo source options are discovered best-effort from `media_source` (including local media / Google Photos where HA exposes them).
- Kept advanced `Custom dashboard URL`, `Custom task source`, `Custom photo source` and `Custom sound` text entities as fallback configuration controls.
- Resolved selected `media-source://...` sound files to playable URLs when pressing **Play sound**, so the iOS receiver gets a URL it can actually play.
- Discovery now prefers the real phone/tablet name from Bonjour, falling back to the Bonjour instance name before using a generic panel name.

## 0.1.7 - 2026-08-29

- Added per-panel Home Assistant device-page controls: Dashboard URL text entity plus Start camera / Stop camera buttons, so users do not need Developer Tools service calls for common panel setup.
- Made Home Assistant the full source of truth for every panel: added device-page **Task source** and **Photo source** text entities (feeding the tasks/photos screens via `configure_ui`), a **Sound** text entity plus **Play sound** and **Beep** buttons, and **Start intercom** / **Stop intercom** buttons. Split the camera control into **Start front camera** / **Start back camera** / **Stop camera**. All controls are bound to the phone's Home Assistant device.
- Added matching `beep`, `play_sound`, `start_intercom`, `stop_intercom` services and documented the previously missing `set_panel_ui` service (now also taking `task_source` / `photo_source`). The `play_sound` contract accepts a system-sound id, a bundled sound name, or a remote `url`; the intercom contract carries `audio_url` / `stream_url` for a future live-audio build (honest MVP: the panel reflects ringing/talking state, no live capture/streaming yet).
- Persisted the per-panel dashboard/tasks/photos/sound config (schema v5) so it survives a restart, and fixed the dashboard URL not being restored on reload.

## 0.1.6 - 2026-08-29

- Added no-code local discovery pairing: the iOS app advertises itself with Bonjour/mDNS and Home Assistant can confirm/send a one-time claim without manual code entry.

- Added a Home Assistant camera entity backed by the panel-reported local MJPEG URL, and forward `start_stream` to online panels even without go2rtc configured.
- Dynamically add panel entities after a new pairing claim/device appears, so a newly paired phone no longer stays hidden while Home Assistant still shows only the hub button.
- Changed first hub setup so **Add Integration → OldPhoneKiosk** displays a pairing code and creates the hub only after the phone/tablet connects.
- Added the app icon to the HACS/custom integration package and README.
- Added a hub-level **Generate pairing code** button entity so users can start pairing from the integration page instead of Developer Tools.
- Added HACS custom repository metadata and one-click My Home Assistant install button.
- Moved pairing/device backend into the Home Assistant integration, removing the external Bridge requirement.
- Added Home Assistant-native pairing, device registry, WebSocket token and WebSocket route docs.
- Added project documentation, issue templates and CI hygiene checks.
