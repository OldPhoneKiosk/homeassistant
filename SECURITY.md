# Security policy

OldPhoneKiosk pairs a physical/mobile device with Home Assistant, so credential handling matters.

## Do not publish sensitive details

Do not open a public issue with Home Assistant long-lived access tokens, active QR claim tokens, device secrets, full unredacted Home Assistant logs containing private URLs or device identifiers, or exploit steps for authentication bypasses.

## Supported version

The supported version is the latest `main` branch and latest GitHub release when releases are published.

## Reporting a vulnerability

If you find a vulnerability, open a minimal public issue saying that a security report exists and avoid exploit details. If GitHub private vulnerability reporting is enabled for the repository, use that. Otherwise contact the repository owner/maintainer privately.

## Security expectations

- The iPhone app must never receive Home Assistant administrator credentials.
- Pairing claim tokens must be one-time and expire.
- WebSocket access should use short-lived tokens derived from device credentials.
- Revoking a panel must invalidate its device secret.
