"""Pairing QR payload helpers (Home-Assistant-independent, unit-testable).

Builds the `PairingPayload` the panel app scans (see iOS `PairingPayload`) and,
if the optional `qrcode` library is available, renders it as an SVG data URI (SVG
avoids a Pillow dependency).
"""

from __future__ import annotations

import base64
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


def payload_to_json(payload: dict[str, Any]) -> str:
    """Serialize the payload as compact, stable JSON (the QR contents)."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def payload_to_qr_svg_data_uri(payload_json: str) -> str | None:
    """Render the payload JSON as a QR code SVG data URI, or None if `qrcode`
    is not installed. SVG keeps this Pillow-free."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return None

    import io

    image = qrcode.make(
        payload_json, image_factory=qrcode.image.svg.SvgPathImage
    )
    buffer = io.BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
