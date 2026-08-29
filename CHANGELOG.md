# Changelog

All notable changes to the OldPhoneKiosk Home Assistant integration are documented here.

## Unreleased

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
