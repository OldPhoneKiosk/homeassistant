"""Device-facing HTTP/WebSocket endpoints served by Home Assistant."""

from __future__ import annotations

import json
import logging

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import PanelCommand
from .native_client import handle_device_message
from .photos import async_get_photo_snapshot, async_photo_proxy_path
from .registry import AuthError, ClaimError, Registry, UnknownDeviceError
from .tasks import async_handle_task_action, async_push_task_snapshot_via_registry
from .wstoken import WsTokenService

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = "registry"
DATA_WS_TOKENS = "ws_tokens"


def _registry(hass: HomeAssistant) -> Registry:
    return hass.data[DOMAIN][DATA_REGISTRY]


def _ws_tokens(hass: HomeAssistant) -> WsTokenService:
    return hass.data[DOMAIN][DATA_WS_TOKENS]


async def _send_persisted_config(
    hass: HomeAssistant, registry: Registry, device_id: str
) -> None:
    """Send HA-owned panel config and task snapshot immediately after WS connect."""
    media = registry.get_device(device_id).media
    params: dict[str, str] = {}
    if media.dashboard_url:
        params["dashboard_url"] = media.dashboard_url
    if media.task_source:
        params["task_source"] = media.task_source
    if media.photo_source:
        params["photo_source"] = media.photo_source
    if media.enabled_screens:
        params["enabled_screens"] = media.enabled_screens
    if media.show_bottom_menu is not None:
        params["show_bottom_menu"] = "true" if media.show_bottom_menu else "false"
    if media.keep_screen_awake is not None:
        params["keep_screen_awake"] = "true" if media.keep_screen_awake else "false"
    if media.show_connection_banner is not None:
        params["show_connection_banner"] = (
            "true" if media.show_connection_banner else "false"
        )
    if media.show_photo_time_overlay is not None:
        params["show_photo_time_overlay"] = (
            "true" if media.show_photo_time_overlay else "false"
        )
    if media.camera_rotate_180 is not None:
        params["camera_rotate_180"] = "true" if media.camera_rotate_180 else "false"
    if media.dim_after_seconds is not None:
        params["dim_after_seconds"] = str(int(media.dim_after_seconds))
    if media.sleep_after_seconds is not None:
        params["sleep_after_seconds"] = str(int(media.sleep_after_seconds))
    if media.task_refresh_seconds is not None:
        params["task_refresh_seconds"] = str(int(media.task_refresh_seconds))
    if params:
        await registry.send_command_nowait(
            device_id, PanelCommand.CONFIGURE_UI, params=params
        )
    if media.task_source:
        await async_push_task_snapshot_via_registry(
            hass, registry, device_id, media.task_source
        )


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


class DevicePhotoSnapshotView(HomeAssistantView):
    """Authenticated snapshot endpoint for the iOS Photos screen."""

    url = "/api/oldphonekiosk/devices/{device_id}/photo.jpg"
    name = "api:oldphonekiosk:devices:photo"
    requires_auth = False

    async def get(self, request: web.Request, device_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        registry = _registry(hass)
        secret = request.headers.get("X-OldPhoneKiosk-Device-Secret", "")
        try:
            device = registry.verify_secret(device_id, secret)
        except UnknownDeviceError:
            return web.Response(status=404, text="unknown device")
        except AuthError:
            return web.Response(status=401, text="invalid device secret")
        proxy_path = async_photo_proxy_path(hass, device.media.photo_source)
        if proxy_path:
            raise web.HTTPFound(location=proxy_path)
        try:
            content, content_type = await async_get_photo_snapshot(
                hass, device.media.photo_source
            )
        except ValueError as exc:
            return web.Response(status=404, text=str(exc))
        except Exception as exc:
            _LOGGER.debug("Could not fetch panel photo snapshot", exc_info=True)
            return web.Response(status=502, text=str(exc))
        return web.Response(
            body=content,
            content_type=content_type,
            headers={"Cache-Control": "no-store, max-age=0"},
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
            await _send_persisted_config(hass, registry, device_id)
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        raw = json.loads(msg.data)
                        if raw.get("type") == "task_action":
                            await async_handle_task_action(
                                hass, registry, device_id, raw
                            )
                        else:
                            handle_device_message(registry, device_id, raw)
                    except Exception:
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
    hass.http.register_view(DevicePhotoSnapshotView())
    hass.http.register_view(DeviceWebSocketView())
