"""Async HTTP client for the OldPhoneKiosk Bridge.

Intentionally free of any Home Assistant imports so it can be unit-tested
standalone against a mocked httpx transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from .const import (
    API_KEY_HEADER,
    ENDPOINT_CLAIM_CREATE,
    ENDPOINT_COMMANDS,
    ENDPOINT_DEVICE,
    ENDPOINT_DEVICES,
    ENDPOINT_HEALTH,
    ENDPOINT_MEDIA,
    ENDPOINT_PAIRING_APPROVE,
    ENDPOINT_PAIRING_START,
    ENDPOINT_STREAM_START,
    ENDPOINT_STREAM_STOP,
)

_UNSET = object()


class BridgeError(Exception):
    """Base error talking to the Bridge."""


class BridgeAuthError(BridgeError):
    """Invalid or missing API key."""


class BridgeConnectionError(BridgeError):
    """Could not reach the Bridge."""


class BridgeNotFoundError(BridgeError):
    """The Bridge returned 404 (unknown device)."""


@dataclass(slots=True)
class ProvisionedPanel:
    """Per-device credentials produced by provisioning a new panel."""

    device_id: str
    device_secret: str


@dataclass(slots=True)
class PanelClaim:
    """A one-time claim token for pairing (no secret)."""

    claim_token: str
    device_id: str
    expires_at: str


@dataclass(slots=True)
class PanelDeviceData:
    """Normalized view of one panel device from the Bridge."""

    device_id: str
    name: str
    room: str | None
    model: str | None
    online: bool
    battery: int | None
    battery_state: str | None
    brightness: float | None
    screen: str | None
    camera_mode: str | None
    intercom: str | None
    stream: str | None
    video_url: str | None
    dashboard_url: str | None
    app_version: str | None
    last_seen: datetime | None
    task_source: str | None = None
    photo_source: str | None = None
    sound: str | None = None
    enabled_screens: str | None = None
    show_bottom_menu: bool | None = None
    keep_screen_awake: bool | None = None
    show_connection_banner: bool | None = None
    show_photo_time_overlay: bool | None = None
    show_photo_location_overlay: bool | None = None
    dim_after_seconds: float | None = None
    sleep_after_seconds: float | None = None
    task_refresh_seconds: float | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PanelDeviceData:
        state = data.get("state") or {}
        media = data.get("media") or {}
        return cls(
            device_id=data["device_id"],
            name=data.get("name") or data["device_id"],
            room=data.get("room"),
            model=data.get("model"),
            online=bool(state.get("online", False)),
            battery=state.get("battery"),
            battery_state=state.get("battery_state") or state.get("batteryState"),
            brightness=state.get("brightness"),
            screen=state.get("screen"),
            camera_mode=state.get("camera"),
            intercom=state.get("intercom"),
            stream=state.get("stream"),
            video_url=media.get("video_url"),
            dashboard_url=media.get("dashboard_url"),
            app_version=state.get("app_version"),
            last_seen=_parse_dt(state.get("last_seen")),
            task_source=media.get("task_source"),
            photo_source=media.get("photo_source"),
            sound=media.get("sound"),
            enabled_screens=media.get("enabled_screens"),
            show_bottom_menu=media.get("show_bottom_menu"),
            keep_screen_awake=media.get("keep_screen_awake"),
            show_connection_banner=media.get("show_connection_banner"),
            show_photo_time_overlay=media.get("show_photo_time_overlay"),
            show_photo_location_overlay=media.get("show_photo_location_overlay"),
            dim_after_seconds=media.get("dim_after_seconds"),
            sleep_after_seconds=media.get("sleep_after_seconds"),
            task_refresh_seconds=media.get("task_refresh_seconds"),
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class BridgeClient:
    """Thin async client over the Bridge admin API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def _headers(self) -> dict[str, str]:
        return {API_KEY_HEADER: self._api_key}

    async def close(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._client.request(
                method, url, headers=self._headers, timeout=self._timeout, **kwargs
            )
        except httpx.HTTPError as exc:  # connect/timeout/etc.
            raise BridgeConnectionError(str(exc)) from exc
        if resp.status_code == 401:
            raise BridgeAuthError("invalid API key")
        if resp.status_code == 404:
            raise BridgeNotFoundError("unknown device")
        if resp.status_code >= 400:
            raise BridgeError(f"HTTP {resp.status_code}: {resp.text}")
        return resp

    async def async_check(self) -> bool:
        """Validate connectivity + credentials for the config flow.

        Health confirms reachability; devices list confirms the API key.
        """
        try:
            await self._client.get(
                f"{self._base_url}{ENDPOINT_HEALTH}", timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise BridgeConnectionError(str(exc)) from exc
        # This raises BridgeAuthError on a bad key.
        await self._request("GET", ENDPOINT_DEVICES)
        return True

    async def async_get_devices(self) -> list[PanelDeviceData]:
        resp = await self._request("GET", ENDPOINT_DEVICES)
        payload = resp.json()
        return [PanelDeviceData.from_json(d) for d in payload.get("devices", [])]

    async def async_send_command(
        self, device_id: str, command: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"command": command}
        if params is not None:
            body["params"] = params
        resp = await self._request(
            "POST",
            ENDPOINT_COMMANDS.format(device_id=device_id),
            json=body,
        )
        return resp.json()

    async def async_set_panel_ui(
        self,
        device_id: str,
        *,
        default_screen: str | None = None,
        enabled_screens: list[str] | None = None,
        show_bottom_menu: bool | None = None,
        keep_screen_awake: bool | None = None,
        show_connection_banner: bool | None = None,
        show_photo_time_overlay: bool | None = None,
        show_photo_location_overlay: bool | None = None,
        dim_after_seconds: float | None = None,
        sleep_after_seconds: float | None = None,
        dashboard_url: str | None = None,
    ) -> PanelDeviceData:
        """Push panel UI config via the legacy HTTP Bridge command endpoint."""
        params: dict[str, Any] = {}
        if default_screen is not None:
            params["default_screen"] = default_screen
        if enabled_screens is not None:
            params["enabled_screens"] = ",".join(enabled_screens)
        if show_bottom_menu is not None:
            params["show_bottom_menu"] = "true" if show_bottom_menu else "false"
        if keep_screen_awake is not None:
            params["keep_screen_awake"] = "true" if keep_screen_awake else "false"
        if show_connection_banner is not None:
            params["show_connection_banner"] = (
                "true" if show_connection_banner else "false"
            )
        if show_photo_time_overlay is not None:
            params["show_photo_time_overlay"] = (
                "true" if show_photo_time_overlay else "false"
            )
        if show_photo_location_overlay is not None:
            params["show_photo_location_overlay"] = (
                "true" if show_photo_location_overlay else "false"
            )
        if dim_after_seconds is not None:
            params["dim_after_seconds"] = str(int(max(0, dim_after_seconds)))
        if sleep_after_seconds is not None:
            params["sleep_after_seconds"] = str(int(max(0, sleep_after_seconds)))
        if dashboard_url is not None:
            params["dashboard_url"] = dashboard_url
        await self._request(
            "POST",
            ENDPOINT_COMMANDS.format(device_id=device_id),
            json={"command": "configure_ui", "params": params},
        )
        # Legacy bridge may not store dashboard_url; preserve the existing device view.
        devices = await self.async_get_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        raise BridgeNotFoundError("unknown device")

    async def async_delete_device(self, device_id: str) -> None:
        """Revoke/remove a device on the Bridge (DELETE, expects 204).

        Raises BridgeNotFoundError if the Bridge does not know the device.
        """
        await self._request("DELETE", ENDPOINT_DEVICE.format(device_id=device_id))

    async def async_set_media(
        self,
        device_id: str,
        *,
        video_url: Any = _UNSET,
        camera_mode: str | None = None,
    ) -> PanelDeviceData:
        """Set the panel's media config on the Bridge (video_url and/or camera mode).

        Only provided fields are sent (``video_url`` may be None to clear it).
        """
        body: dict[str, Any] = {}
        if video_url is not _UNSET:
            body["video_url"] = video_url
        if camera_mode is not None:
            body["camera_mode"] = camera_mode
        resp = await self._request(
            "PUT", ENDPOINT_MEDIA.format(device_id=device_id), json=body
        )
        return PanelDeviceData.from_json(resp.json())

    async def async_start_stream(
        self, device_id: str, camera_mode: str | None = None
    ) -> PanelDeviceData:
        body: dict[str, Any] = {}
        if camera_mode is not None:
            body["camera_mode"] = camera_mode
        resp = await self._request(
            "POST", ENDPOINT_STREAM_START.format(device_id=device_id), json=body
        )
        return PanelDeviceData.from_json(resp.json())

    async def async_stop_stream(self, device_id: str) -> PanelDeviceData:
        resp = await self._request(
            "POST", ENDPOINT_STREAM_STOP.format(device_id=device_id)
        )
        return PanelDeviceData.from_json(resp.json())

    async def async_create_claim(
        self, name: str, room: str | None = None
    ) -> PanelClaim:
        """Provision a device and get a one-time claim token (the pairing code)."""
        resp = await self._request(
            "POST", ENDPOINT_CLAIM_CREATE, json={"name": name, "room": room}
        )
        data = resp.json()
        return PanelClaim(
            claim_token=data["claim_token"],
            device_id=data["device_id"],
            expires_at=data["expires_at"],
        )

    async def async_provision_panel(
        self, name: str, room: str | None = None
    ) -> ProvisionedPanel:
        """Provision a new panel: start pairing, then approve, returning credentials.

        Home Assistant performs both steps (it holds the API key) so it can hand
        the resulting per-device credentials to the panel during pairing.
        """
        start = await self._request(
            "POST",
            ENDPOINT_PAIRING_START,
            json={"display_name": name},
        )
        pairing_code = start.json()["pairing_code"]
        approve = await self._request(
            "POST",
            ENDPOINT_PAIRING_APPROVE,
            json={"pairing_code": pairing_code, "name": name, "room": room},
        )
        data = approve.json()
        return ProvisionedPanel(
            device_id=data["device_id"], device_secret=data["device_secret"]
        )
