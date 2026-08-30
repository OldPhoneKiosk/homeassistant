# Changelog

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

