# Changelog

## 0.1.18 - 2026-08-30

- Include task `assignee` and a JSON `details` object in snapshots sent to iOS so the phone can show task detail modals.

## 0.1.17 - 2026-08-30

- Add per-panel `number.*_refresh_tasks_every` control for automatic task refresh cadence.
- Persist task refresh cadence in the Home Assistant-owned device config database.
- Send task refresh cadence to the iOS app on connect and when changed.
- Include task refresh cadence in legacy bridge/native client models.

