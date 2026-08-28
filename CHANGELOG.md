# Changelog

All notable changes to the OldPhoneKiosk Home Assistant integration are documented here.

## Unreleased

- Dynamically add panel entities after a new pairing claim/device appears, so a scanned QR no longer leaves the phone paired while Home Assistant still shows only the hub button.
- Changed first hub setup so **Add Integration → OldPhoneKiosk** displays a pairing QR and creates the hub only after the phone/tablet connects.
- Added the app icon to the HACS/custom integration package and README.
- Added a hub-level **Generate pairing QR** button entity so users can start pairing from the integration page instead of Developer Tools.
- Added HACS custom repository metadata and one-click My Home Assistant install button.
- Moved pairing/device backend into the Home Assistant integration, removing the external Bridge requirement.
- Added Home Assistant-native pairing, device registry, WebSocket token and WebSocket route docs.
- Added project documentation, issue templates and CI hygiene checks.
