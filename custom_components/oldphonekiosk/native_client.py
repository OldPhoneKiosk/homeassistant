"""In-process OldPhoneKiosk backend used by the Home Assistant integration.

This replaces the old external FastAPI Bridge: Home Assistant owns the device
registry, pairing claims, state, commands, and media settings directly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .api import BridgeNotFoundError
from .models import CameraState, CommandResult, DeviceState, PanelCommand, PanelDevice, PanelScreen, IntercomState, StreamState
from .registry import DeviceOfflineError, Registry, UnknownDeviceError

_UNSET = object()


@dataclass(slots=True)
class PanelClaim:
    """A one-time claim token for pairing (no secret)."""

    claim_token: str
    device_id: str
    expires_at: str


@dataclass(slots=True)
class PanelDeviceData:
    """Normalized view of one panel device for HA entities."""

    device_id: str
    name: str
    room: str | None
    model: str | None
    online: bool
    battery: int | None
    brightness: float | None
    screen: str | None
    camera_mode: str | None
    intercom: str | None
    stream: str | None
    video_url: str | None
    dashboard_url: str | None
    app_version: str | None
    last_seen: datetime | None

    @classmethod
    def from_device(cls, device: PanelDevice) -> "PanelDeviceData":
        state = device.state
        return cls(
            device_id=device.device_id,
            name=device.name or device.device_id,
            room=device.room,
            model=device.model,
            online=state.online,
            battery=state.battery,
            brightness=state.brightness,
            screen=state.screen.value if state.screen else None,
            camera_mode=state.camera.value if state.camera else None,
            intercom=state.intercom.value if state.intercom else None,
            stream=state.stream.value if state.stream else None,
            video_url=device.media.video_url,
            dashboard_url=device.media.dashboard_url,
            app_version=state.app_version,
            last_seen=state.last_seen,
        )


class NativeOldPhoneKioskClient:
    """Async facade over the in-process Registry matching the old BridgeClient API."""

    def __init__(self, registry: Registry, *, go2rtc_url: str | None = None) -> None:
        self.registry = registry
        self.go2rtc_url = go2rtc_url

    async def close(self) -> None:
        return None

    async def async_get_devices(self) -> list[PanelDeviceData]:
        return [PanelDeviceData.from_device(d) for d in self.registry.list_devices()]

    async def async_create_claim(self, name: str, room: str | None = None) -> PanelClaim:
        claim = self.registry.create_claim(name=name, room=room)
        return PanelClaim(
            claim_token=claim.claim_token,
            device_id=claim.device_id,
            expires_at=claim.expires_at.isoformat(),
        )

    async def async_delete_device(self, device_id: str) -> None:
        try:
            self.registry.remove_device(device_id)
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc

    async def async_send_command(self, device_id: str, command: str) -> dict[str, Any]:
        try:
            cmd, result = await self.registry.send_command(device_id, PanelCommand(command))
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc
        except DeviceOfflineError:
            return {"id": "", "status": "offline", "success": False, "error": "device offline"}
        if result is None:
            return {"id": cmd.id, "status": "timeout"}
        if result.success:
            self.registry.apply_command_optimistic_state(device_id, PanelCommand(command))
        return {
            "id": cmd.id,
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "error": result.error,
        }

    async def async_set_panel_ui(
        self,
        device_id: str,
        *,
        default_screen: str | None = None,
        enabled_screens: list[str] | None = None,
        show_bottom_menu: bool | None = None,
        dashboard_url: str | None = None,
    ) -> PanelDeviceData:
        params: dict[str, str] = {}
        if default_screen is not None:
            params["default_screen"] = default_screen
        if enabled_screens is not None:
            params["enabled_screens"] = ",".join(enabled_screens)
        if show_bottom_menu is not None:
            params["show_bottom_menu"] = "true" if show_bottom_menu else "false"
        if dashboard_url is not None:
            params["dashboard_url"] = dashboard_url
        try:
            device = self.registry.set_dashboard_url(device_id, dashboard_url)
            if self.registry.is_online(device_id):
                try:
                    await self.registry.send_command(device_id, PanelCommand.CONFIGURE_UI, params=params)
                except (DeviceOfflineError, asyncio.TimeoutError):
                    pass
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc
        return PanelDeviceData.from_device(device)

    async def async_set_media(
        self,
        device_id: str,
        *,
        video_url: Any = _UNSET,
        camera_mode: str | None = None,
    ) -> PanelDeviceData:
        try:
            device = self.registry.set_media(
                device_id,
                set_video_url=video_url is not _UNSET,
                video_url=None if video_url is _UNSET else video_url,
                camera_mode=CameraState(camera_mode) if camera_mode is not None else None,
            )
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc
        return PanelDeviceData.from_device(device)

    def _stream_name(self, device_id: str) -> str:
        return f"panel_{device_id}"

    def _go2rtc_urls(self, device_id: str) -> tuple[str | None, str | None]:
        if not self.go2rtc_url:
            return None, None
        base = self.go2rtc_url.rstrip("/")
        name = self._stream_name(device_id)
        return f"{base}/stream.html?src={name}", f"{base}/api/webrtc?src={name}"

    async def async_start_stream(self, device_id: str, camera_mode: str | None = None) -> PanelDeviceData:
        viewer, publish = self._go2rtc_urls(device_id)
        camera = CameraState(camera_mode) if camera_mode is not None else CameraState.FRONT
        try:
            if viewer is None:
                device = self.registry.set_stream(
                    device_id,
                    stream_state=StreamState.STARTING,
                    camera_mode=camera,
                )
            else:
                device = self.registry.set_stream(
                    device_id,
                    stream_state=StreamState.STARTING,
                    set_video_url=True,
                    video_url=viewer,
                    camera_mode=camera,
                )
            if self.registry.is_online(device_id):
                params = {"camera_mode": camera.value}
                if viewer:
                    params.update(
                        {
                            "stream_name": self._stream_name(device_id),
                            "viewer_url": viewer,
                        }
                    )
                if publish:
                    params["publish_url"] = publish
                try:
                    await self.registry.send_command(
                        device_id,
                        PanelCommand.START_STREAM,
                        params=params,
                    )
                except (DeviceOfflineError, asyncio.TimeoutError):
                    pass
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc
        return PanelDeviceData.from_device(device)

    async def async_stop_stream(self, device_id: str) -> PanelDeviceData:
        try:
            device = self.registry.set_stream(
                device_id,
                stream_state=StreamState.IDLE,
                set_video_url=True,
                video_url=None,
                camera_mode=CameraState.OFF,
            )
            if self.registry.is_online(device_id):
                try:
                    await self.registry.send_command(device_id, PanelCommand.STOP_STREAM, params={})
                except (DeviceOfflineError, asyncio.TimeoutError):
                    pass
        except UnknownDeviceError as exc:
            raise BridgeNotFoundError("unknown device") from exc
        return PanelDeviceData.from_device(device)


def handle_device_message(registry: Registry, device_id: str, raw: dict[str, Any]) -> None:
    """Route an inbound device WebSocket message."""
    msg_type = raw.get("type")
    if msg_type == "state":
        def enum_or_none(enum_cls, value):
            if value is None:
                return None
            try:
                return enum_cls(value)
            except ValueError:
                return None

        registry.update_state(
            device_id,
            battery=raw.get("battery"),
            brightness=raw.get("brightness"),
            screen=enum_or_none(PanelScreen, raw.get("screen")),
            camera=enum_or_none(CameraState, raw.get("camera")),
            intercom=enum_or_none(IntercomState, raw.get("intercom")),
            stream=enum_or_none(StreamState, raw.get("stream")),
            app_version=raw.get("appVersion"),
            set_video_url="videoUrl" in raw,
            video_url=raw.get("videoUrl"),
        )
    elif msg_type == "command_result":
        command_id = raw.get("id")
        if command_id:
            registry.resolve_command(
                device_id,
                CommandResult(id=command_id, success=bool(raw.get("success")), error=raw.get("error")),
            )
