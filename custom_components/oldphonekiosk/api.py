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
    ENDPOINT_COMMANDS,
    ENDPOINT_DEVICES,
    ENDPOINT_HEALTH,
)


class BridgeError(Exception):
    """Base error talking to the Bridge."""


class BridgeAuthError(BridgeError):
    """Invalid or missing API key."""


class BridgeConnectionError(BridgeError):
    """Could not reach the Bridge."""


@dataclass(slots=True)
class PanelDeviceData:
    """Normalized view of one panel device from the Bridge."""

    device_id: str
    name: str
    room: str | None
    model: str | None
    online: bool
    battery: int | None
    brightness: float | None
    screen: str | None
    app_version: str | None
    last_seen: datetime | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PanelDeviceData":
        state = data.get("state") or {}
        return cls(
            device_id=data["device_id"],
            name=data.get("name") or data["device_id"],
            room=data.get("room"),
            model=data.get("model"),
            online=bool(state.get("online", False)),
            battery=state.get("battery"),
            brightness=state.get("brightness"),
            screen=state.get("screen"),
            app_version=state.get("app_version"),
            last_seen=_parse_dt(state.get("last_seen")),
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

    async def async_send_command(self, device_id: str, command: str) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            ENDPOINT_COMMANDS.format(device_id=device_id),
            json={"command": command},
        )
        return resp.json()
