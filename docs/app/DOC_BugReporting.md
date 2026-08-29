---
category: app
title: Reporting bugs and requesting features
author: system
description: How to report OldPhoneKiosk bugs and request features with enough context for maintainers to reproduce and prioritize them
---

# Reporting bugs and requesting features

Use GitHub Issues so reports are searchable and linked to fixes.

## Report a bug

Open: [Bug report](https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=bug_report.yml)

Include what you were trying to do, what happened, what you expected, reproduction steps, Home Assistant version, OldPhoneKiosk integration version/commit, installation method, iOS app build/version, and relevant HA logs.

Do not include active pairing codes, device secrets, full access tokens or screenshots with private home data unless redacted.

## Request a feature

Open: [Feature request](https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=feature_request.yml)

A useful feature request explains the problem, who needs it, how it should work in Home Assistant, how it should work on the iPhone, what would count as success, and any privacy/security constraints.

## Security-sensitive issues

If the issue involves credential leakage, authentication bypass or unintended access to Home Assistant/device secrets, do not publish exploit details in a public issue. Use the security contact/process from `SECURITY.md`.
