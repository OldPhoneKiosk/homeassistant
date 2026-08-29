"""Domain models for Bridge device identity, pairing, state and commands."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Timezone-aware UTC now (single source for testability)."""
    return datetime.now(timezone.utc)


class PanelScreen(str, Enum):
    """Screens a panel can display."""

    PHOTOS = "photos"
    TASKS = "tasks"
    ACTIONS = "actions"
    DASHBOARD = "dashboard"
    HOME = "home"
    SLEEP = "sleep"


class CameraState(str, Enum):
    """Camera state of a panel. Camera is deferred in foundation; kept for protocol completeness."""

    OFF = "off"
    FRONT = "front"
    BACK = "back"
    DUAL = "dual"


# Commands accepted by a device. Maps 1:1 to protocol command strings.
class PanelCommand(str, Enum):
    SHOW_PHOTOS = "show_photos"
    SHOW_TASKS = "show_tasks"
    SHOW_HOME = "show_home"
    SHOW_ACTIONS = "show_actions"
    SHOW_DASHBOARD = "show_dashboard"
    CONFIGURE_UI = "configure_ui"
    SLEEP = "sleep"
    WAKE = "wake"
    START_STREAM = "start_stream"
    STOP_STREAM = "stop_stream"


# Screen a command drives the panel to, when applicable.
COMMAND_TARGET_SCREEN: dict[PanelCommand, PanelScreen] = {
    PanelCommand.SHOW_PHOTOS: PanelScreen.PHOTOS,
    PanelCommand.SHOW_TASKS: PanelScreen.TASKS,
    PanelCommand.SHOW_HOME: PanelScreen.HOME,
    PanelCommand.SHOW_ACTIONS: PanelScreen.ACTIONS,
    PanelCommand.SHOW_DASHBOARD: PanelScreen.DASHBOARD,
    PanelCommand.SLEEP: PanelScreen.SLEEP,
    # WAKE has no fixed target screen; device restores previous/home.
}


class IntercomState(str, Enum):
    """Intercom lifecycle of a panel (placeholder for the media MVP)."""

    IDLE = "idle"
    RINGING = "ringing"
    TALKING = "talking"


class StreamState(str, Enum):
    """Publisher (device -> go2rtc) session state. Runtime only; not persisted.

    ``unsupported`` is reported by a device that has no real publisher yet (honest
    placeholder while WebRTC capture is unimplemented)."""

    IDLE = "idle"
    STARTING = "starting"
    LIVE = "live"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class DeviceCapabilities(BaseModel):
    """What a panel device can do. Extensible; foundation keeps it minimal."""

    camera: bool = False
    microphone: bool = False
    photos: bool = True
    tasks: bool = True


class DeviceMedia(BaseModel):
    """Per-device media configuration. ``video_url`` is admin/HA-provided (e.g. a
    go2rtc/WebRTC player page); the Bridge does not hardcode or stream it."""

    video_url: str | None = None


class DeviceState(BaseModel):
    """Latest reported runtime state of a panel."""

    online: bool = False
    battery: int | None = Field(default=None, ge=0, le=100)
    brightness: float | None = Field(default=None, ge=0.0, le=1.0)
    screen: PanelScreen | None = None
    camera: CameraState = CameraState.OFF
    intercom: IntercomState = IntercomState.IDLE
    stream: StreamState = StreamState.IDLE  # runtime only (not persisted)
    app_version: str | None = None
    last_seen: datetime | None = None


class PanelDevice(BaseModel):
    """A paired panel device known to the Bridge.

    Public + last-known-state data only. The device secret is never held here;
    its salted hash lives in the store and is verified separately (see security.py).
    """

    device_id: str
    name: str
    room: str | None = None
    model: str | None = None
    ios_version: str | None = None
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)
    state: DeviceState = Field(default_factory=DeviceState)
    media: DeviceMedia = Field(default_factory=DeviceMedia)
    created_at: datetime = Field(default_factory=utcnow)


class NewDeviceCredentials(BaseModel):
    """Credentials returned to a device exactly once, on pairing approval."""

    device_id: str
    device_secret: str


class PairingRequest(BaseModel):
    """A pending pairing request awaiting admin approval."""

    request_id: str
    pairing_code: str
    display_name: str
    model: str | None = None
    ios_version: str | None = None
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utcnow()) >= self.expires_at


class Claim(BaseModel):
    """A one-time pairing claim, persisted in SQLite (survives restart within TTL).

    Holds no secret: the device is provisioned with an unknown secret at claim
    creation, and the secret is (re)issued only on redeem via rotation — so no
    plaintext secret ever reaches the pairing code, the logs, or the database."""

    claim_token: str
    device_id: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utcnow()) >= self.expires_at


class Command(BaseModel):
    """A command dispatched to a device."""

    id: str
    command: PanelCommand
    params: dict | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CommandResult(BaseModel):
    """A device's response to a command."""

    id: str
    success: bool
    error: str | None = None
