"""Pairing payload helpers (Home-Assistant-independent, unit-testable).

Builds the `PairingPayload` the panel app consumes (see iOS `PairingPayload`).
Pairing is done over Wi‑Fi (zeroconf) discovery or a one-time numeric pairing
code — there is no QR code.
"""

from __future__ import annotations

import json
from typing import Any

from .const import PAIRING_PAYLOAD_VERSION


def build_pairing_payload(
    *,
    bridge_url: str,
    device_id: str,
    device_secret: str,
    name: str | None = None,
    room: str | None = None,
) -> dict[str, Any]:
    """Assemble the pairing payload dict (matches the iOS PairingPayload schema)."""
    payload: dict[str, Any] = {
        "version": PAIRING_PAYLOAD_VERSION,
        "bridge_url": bridge_url.rstrip("/"),
        "device_id": device_id,
        "device_secret": device_secret,
    }
    if name:
        payload["name"] = name
    if room:
        payload["room"] = room
    return payload


def build_claim_payload(
    *,
    bridge_url: str,
    claim_token: str,
    name: str | None = None,
    room: str | None = None,
) -> dict[str, Any]:
    """Assemble a payload carrying a one-time claim token (no device secret).

    Pushed to a discovered phone over the local network; the device redeems the
    token at the Bridge for its credentials.
    """
    payload: dict[str, Any] = {
        "version": PAIRING_PAYLOAD_VERSION,
        "type": "claim",
        "bridge_url": bridge_url.rstrip("/"),
        "claim_token": claim_token,
    }
    if name:
        payload["name"] = name
    if room:
        payload["room"] = room
    return payload


def payload_to_json(payload: dict[str, Any]) -> str:
    """Serialize the payload as compact, stable JSON (pushed to a discovered app)."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
