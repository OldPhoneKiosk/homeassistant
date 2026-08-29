"""Wire schemas: HTTP request/response DTOs and WebSocket message envelopes.

Keep this file aligned with `_p/docs/protocol-foundation.md`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .models import (
    CameraState,
    DeviceCapabilities,
    IntercomState,
    PanelCommand,
    PanelScreen,
    StreamState,
)

# --------------------------------------------------------------------------
# Pairing HTTP DTOs
# --------------------------------------------------------------------------


class PairingStartRequest(BaseModel):
    display_name: str
    model: str | None = None
    ios_version: str | None = None
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)


class PairingStartResponse(BaseModel):
    request_id: str
    pairing_code: str
    expires_at: datetime


class PairingApproveRequest(BaseModel):
    pairing_code: str
    name: str
    room: str | None = None


class PairingApproveResponse(BaseModel):
    device_id: str
    device_secret: str


# --------------------------------------------------------------------------
# One-time claim tokens (10-digit code / Wi‑Fi pairing without the secret on screen)
# --------------------------------------------------------------------------


class ClaimCreateRequest(BaseModel):
    name: str
    room: str | None = None
    model: str | None = None
    ios_version: str | None = None


class ClaimCreateResponse(BaseModel):
    claim_token: str
    device_id: str
    expires_at: datetime


class ClaimRedeemRequest(BaseModel):
    claim_token: str


class ClaimRedeemResponse(BaseModel):
    device_id: str
    device_secret: str


# --------------------------------------------------------------------------
# WebSocket token DTOs (device-facing; authenticated by device_secret)
# --------------------------------------------------------------------------


class WsTokenRequest(BaseModel):
    device_secret: str


class WsTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    # Ready-to-use WS path (client prefixes ws(s)://<bridge-host>).
    ws_path: str


# --------------------------------------------------------------------------
# Device HTTP DTOs (safe projections — never expose device_secret)
# --------------------------------------------------------------------------


class DeviceStateView(BaseModel):
    online: bool
    battery: int | None = None
    brightness: float | None = None
    screen: PanelScreen | None = None
    camera: CameraState = CameraState.OFF
    intercom: IntercomState = IntercomState.IDLE
    stream: StreamState = StreamState.IDLE
    app_version: str | None = None
    last_seen: datetime | None = None


class DeviceMediaView(BaseModel):
    video_url: str | None = None      # viewer (go2rtc player page) for Lovelace
    stream_name: str | None = None    # go2rtc stream name (derived)
    publish_url: str | None = None    # WHIP publish endpoint the device would use


class DeviceView(BaseModel):
    device_id: str
    name: str
    room: str | None = None
    model: str | None = None
    ios_version: str | None = None
    capabilities: DeviceCapabilities
    state: DeviceStateView
    media: DeviceMediaView


class DeviceListResponse(BaseModel):
    devices: list[DeviceView]


# --------------------------------------------------------------------------
# Media HTTP DTOs
# --------------------------------------------------------------------------


class MediaUpdateRequest(BaseModel):
    """Admin/HA sets the media config. Only fields explicitly present are applied
    (use ``model_fields_set`` to distinguish absent from null)."""

    video_url: str | None = None
    camera_mode: CameraState | None = None


class StreamStartRequest(BaseModel):
    """Start a publisher session; optional camera mode (default front)."""

    camera_mode: CameraState | None = None


# --------------------------------------------------------------------------
# Command HTTP DTOs
# --------------------------------------------------------------------------


class SendCommandRequest(BaseModel):
    command: PanelCommand


class SendCommandResponse(BaseModel):
    id: str
    status: Literal["sent", "queued", "timeout", "completed", "failed"]
    success: bool | None = None
    error: str | None = None


# --------------------------------------------------------------------------
# WebSocket message envelopes (device <-> bridge)
# --------------------------------------------------------------------------


class StateMessage(BaseModel):
    """Device -> Bridge heartbeat/state."""

    type: Literal["state"] = "state"
    battery: int | None = Field(default=None, ge=0, le=100)
    brightness: float | None = Field(default=None, ge=0.0, le=1.0)
    screen: PanelScreen | None = None
    camera: CameraState = CameraState.OFF
    intercom: IntercomState | None = None
    stream: StreamState | None = None
    appVersion: str | None = None


class CommandMessage(BaseModel):
    """Bridge -> Device command."""

    type: Literal["command"] = "command"
    id: str
    command: PanelCommand
    params: dict | None = None


class CommandResultMessage(BaseModel):
    """Device -> Bridge command result."""

    type: Literal["command_result"] = "command_result"
    id: str
    success: bool
    error: str | None = None
