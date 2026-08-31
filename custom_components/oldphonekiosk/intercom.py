"""In-process WebRTC intercom signaling broker.

Home Assistant is only the signaling broker. Audio/media flows directly over
WebRTC between the HA browser and the iOS panel peer connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid
from typing import Awaitable, Callable, Protocol

IntercomSignalHandler = Callable[[dict], Awaitable[None]]


class IntercomRegistry(Protocol):
    """Minimal device registry interface needed by the signaling broker."""

    def get_device(self, device_id: str): ...
    def is_online(self, device_id: str) -> bool: ...
    async def send_raw(self, device_id: str, message: dict) -> None: ...


async def _noop_handler(frame: dict) -> None:
    """Default handler used until a browser subscribes to session events."""


class IntercomSessionError(Exception):
    """Raised when an intercom session cannot be found or used."""


@dataclass
class IntercomSession:
    """Runtime-only mapping between a browser call and an iOS device."""

    session_id: str
    device_id: str
    handler: IntercomSignalHandler
    state: str = "starting"
    pending_device_signals: list[dict] = field(default_factory=list)


class IntercomBroker:
    """Route WebRTC SDP/ICE messages between HA browser and panel device."""

    def __init__(self, registry: IntercomRegistry) -> None:
        self._registry = registry
        self._sessions: dict[str, IntercomSession] = {}

    def list_sessions(self) -> list[IntercomSession]:
        return list(self._sessions.values())

    async def start_session(
        self, device_id: str, handler: IntercomSignalHandler | None = None
    ) -> IntercomSession:
        """Create a browser-owned intercom session and wake the panel UI."""
        self._registry.get_device(device_id)
        if not self._registry.is_online(device_id):
            raise IntercomSessionError("device offline")
        session = IntercomSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            handler=handler or _noop_handler,
        )
        self._sessions[session.session_id] = session
        await self.send_to_device(
            session.session_id,
            {"type": "intercom_signal", "action": "start"},
        )
        return session

    def get_session(self, session_id: str) -> IntercomSession:
        """Return an active session or raise a protocol error."""
        session = self._sessions.get(session_id)
        if session is None:
            raise IntercomSessionError("unknown intercom session")
        return session

    def set_handler(
        self, session_id: str, handler: IntercomSignalHandler
    ) -> IntercomSession:
        """Attach or replace the browser event handler for a session."""
        session = self.get_session(session_id)
        session.handler = handler
        return session

    async def send_to_device(self, session_id: str, payload: dict) -> None:
        """Forward a signaling frame from HA browser to the iOS device WS."""
        session = self.get_session(session_id)
        frame = dict(payload)
        frame["type"] = "intercom_signal"
        frame["session_id"] = session.session_id
        await self._registry.send_raw(session.device_id, frame)

    async def handle_device_signal(self, device_id: str, payload: dict) -> None:
        """Forward a signaling frame from iOS device to the owning HA browser."""
        session_id = payload.get("session_id")
        if not isinstance(session_id, str):
            return
        session = self._sessions.get(session_id)
        if session is None or session.device_id != device_id:
            return
        frame = dict(payload)
        frame["type"] = "intercom_signal"
        frame["device_id"] = device_id
        await session.handler(frame)
        if frame.get("action") in {"hangup", "error"}:
            self.end_session(session_id)

    def end_session(self, session_id: str) -> IntercomSession | None:
        """Remove a session without sending network frames."""
        return self._sessions.pop(session_id, None)

    async def hangup(self, session_id: str) -> None:
        """Tell the panel to hang up, then remove the runtime session."""
        session = self.get_session(session_id)
        try:
            await self.send_to_device(
                session_id,
                {"type": "intercom_signal", "action": "hangup"},
            )
        finally:
            self.end_session(session_id)

    def cleanup_for_device(self, device_id: str) -> None:
        """Drop sessions for an offline/removed device."""
        for session_id, session in list(self._sessions.items()):
            if session.device_id == device_id:
                self._sessions.pop(session_id, None)

    def cleanup_for_handler(self, handler: IntercomSignalHandler) -> None:
        """Drop sessions owned by a disconnected HA browser connection."""
        for session_id, session in list(self._sessions.items()):
            if session.handler is handler:
                self._sessions.pop(session_id, None)


def validate_device_signal(payload: dict) -> dict:
    """Return a normalized intercom_signal payload."""
    action = payload.get("action")
    session_id = payload.get("session_id")
    if not isinstance(action, str) or not isinstance(session_id, str):
        raise IntercomSessionError("intercom signal requires action and session_id")
    allowed = {"start", "offer", "answer", "ice_candidate", "hangup", "error"}
    if action not in allowed:
        raise IntercomSessionError(f"unsupported intercom action: {action}")
    return dict(payload)
