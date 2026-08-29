"""Device-facing HTTP/WebSocket endpoints served by Home Assistant."""

from __future__ import annotations

import json
import logging

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .native_client import handle_device_message
from .tasks import async_handle_task_action
from .registry import AuthError, ClaimError, Registry, UnknownDeviceError
from .wstoken import WsTokenService

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = "registry"
DATA_WS_TOKENS = "ws_tokens"


def _registry(hass: HomeAssistant) -> Registry:
    return hass.data[DOMAIN][DATA_REGISTRY]


def _ws_tokens(hass: HomeAssistant) -> WsTokenService:
    return hass.data[DOMAIN][DATA_WS_TOKENS]


class ClaimRedeemView(HomeAssistantView):
    """Redeem a one-time pairing claim for device credentials."""

    url = "/api/oldphonekiosk/pairing/claim/redeem"
    name = "api:oldphonekiosk:pairing:claim:redeem"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            data = await request.json()
            claim_token = data["claim_token"]
            creds = _registry(hass).redeem_claim(claim_token)
        except (json.JSONDecodeError, KeyError):
            return web.json_response({"detail": "invalid request"}, status=400)
        except ClaimError as exc:
            return web.json_response({"detail": str(exc)}, status=410)
        return web.json_response(
            {"device_id": creds.device_id, "device_secret": creds.device_secret}
        )


class WsTokenView(HomeAssistantView):
    """Exchange a long-lived device secret for a short-lived WebSocket token."""

    url = "/api/oldphonekiosk/devices/{device_id}/ws-token"
    name = "api:oldphonekiosk:devices:ws-token"
    requires_auth = False

    async def post(self, request: web.Request, device_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            data = await request.json()
            device_secret = data["device_secret"]
            _registry(hass).verify_secret(device_id, device_secret)
        except (json.JSONDecodeError, KeyError):
            return web.json_response({"detail": "invalid request"}, status=400)
        except UnknownDeviceError:
            return web.json_response({"detail": "unknown device"}, status=404)
        except AuthError:
            return web.json_response({"detail": "invalid device secret"}, status=401)
        token, expires_at = _ws_tokens(hass).issue(device_id)
        return web.json_response(
            {
                "token": token,
                "expires_at": expires_at.isoformat(),
                "ws_path": f"/api/oldphonekiosk/ws/device/{device_id}?token={token}",
            }
        )


class DeviceWebSocketView(HomeAssistantView):
    """Device WebSocket: state heartbeat + command channel."""

    url = "/api/oldphonekiosk/ws/device/{device_id}"
    name = "api:oldphonekiosk:ws:device"
    requires_auth = False

    async def get(self, request: web.Request, device_id: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        registry = _registry(hass)
        token = request.query.get("token")
        if not token or not _ws_tokens(hass).verify(device_id, token):
            return web.Response(status=401, text="invalid token")
        try:
            registry.get_device(device_id)
        except UnknownDeviceError:
            return web.Response(status=404, text="unknown device")

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        registry.register_connection(device_id, ws)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        raw = json.loads(msg.data)
                        if raw.get("type") == "task_action":
                            await async_handle_task_action(hass, registry, device_id, raw)
                        else:
                            handle_device_message(registry, device_id, raw)
                    except Exception:  # noqa: BLE001 - bad device frames are ignored
                        _LOGGER.debug("Ignoring invalid device frame", exc_info=True)
                elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSED):
                    break
        finally:
            registry.unregister_connection(device_id)
        return ws


def async_register_http_views(hass: HomeAssistant) -> None:
    """Register device-facing HA HTTP endpoints."""
    hass.http.register_view(ClaimRedeemView())
    hass.http.register_view(WsTokenView())
    hass.http.register_view(DeviceWebSocketView())
