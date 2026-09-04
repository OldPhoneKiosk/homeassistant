"""Device-facing HTTP/WebSocket endpoints served by Home Assistant."""

from __future__ import annotations

import json
import logging

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .calendar import (
    async_calendar_events_json,
    async_handle_calendar_action,
    async_push_calendar_snapshot_via_registry,
    normalize_calendar_sources,
)
from .const import DOMAIN
from .kindle_actions import build_complete_task_url, build_entity_action, is_safe_toggle_entity
from .kindle_display import KindleSnapshot, render_kindle_html
from .models import PanelCommand, PanelScreen
from .intercom import IntercomSessionError, validate_device_signal
from .native_client import handle_device_message
from .photos import async_get_photo_snapshot, async_photo_proxy_path
from .registry import AuthError, ClaimError, Registry, UnknownDeviceError
from .tasks import async_handle_task_action, async_push_task_snapshot_via_registry, async_todo_items_json
from .ui_config import build_configure_ui_params_from_media
from .websocket_api import get_intercom_broker
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
    params = build_configure_ui_params_from_media(media)
    if params:
        await registry.send_command_nowait(
            device_id, PanelCommand.CONFIGURE_UI, params=params
        )
    if media.task_source:
        await async_push_task_snapshot_via_registry(
            hass, registry, device_id, media.task_source
        )
    if media.calendar_sources:
        await async_push_calendar_snapshot_via_registry(
            hass,
            registry,
            device_id,
            media.calendar_sources,
            view=media.calendar_view or "month",
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


class WebDisplayView(HomeAssistantView):
    """Action-capable Kindle/web display page generated by Home Assistant."""

    url = "/api/oldphonekiosk/web-display/{device_id}"
    name = "api:oldphonekiosk:web-display"
    requires_auth = False

    async def get(self, request: web.Request, device_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        token = request.query.get("token", "")
        try:
            device = _registry(hass).verify_secret(device_id, token)
        except UnknownDeviceError:
            return web.Response(status=404, text="unknown display")
        except AuthError:
            return web.Response(status=401, text="invalid display token")

        media = device.media
        tasks: list[dict] = []
        if media.task_source:
            try:
                tasks = json.loads(await async_todo_items_json(hass, media.task_source))
                for item in tasks:
                    uid = str(item.get("uid") or "").strip()
                    if uid:
                        item["complete_url"] = build_complete_task_url(
                            device_id, token, media.task_source, uid
                        )
            except Exception:
                _LOGGER.debug("Could not render Kindle task snapshot", exc_info=True)
        actions: list[dict] = []
        for entity_id in [
            item.strip()
            for item in str(media.kindle_actions or "").split(",")
            if item.strip()
        ]:
            action = build_entity_action(
                device_id, token, entity_id, hass.states.get(entity_id)
            )
            if action:
                actions.append(action)
        calendar: list[dict] = []
        sources = normalize_calendar_sources(media.calendar_sources)
        if sources:
            try:
                calendar = json.loads(
                    await async_calendar_events_json(
                        hass, sources, media.calendar_view or "list"
                    )
                )
            except Exception:
                _LOGGER.debug("Could not render Kindle calendar snapshot", exc_info=True)
        screen = device.state.screen or PanelScreen.DASHBOARD
        refresh = int(media.task_refresh_seconds or 60)
        html = render_kindle_html(
            KindleSnapshot(
                name=device.name,
                screen=screen.value,
                dashboard_url=media.dashboard_url,
                tasks=tasks,
                calendar=calendar,
                actions=actions,
                refresh_seconds=refresh,
            )
        )
        return web.Response(
            text=html,
            content_type="text/html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    async def get_action(self, request: web.Request, device_id: str) -> web.Response:
        """Execute one safe old-browser action and redirect back to the display."""
        hass: HomeAssistant = request.app["hass"]
        token = request.query.get("token", "")
        try:
            device = _registry(hass).verify_secret(device_id, token)
        except UnknownDeviceError:
            return web.Response(status=404, text="unknown display")
        except AuthError:
            return web.Response(status=401, text="invalid display token")

        action = request.query.get("action", "")
        if action == "toggle":
            entity_id = request.query.get("entity_id", "")
            if not is_safe_toggle_entity(entity_id):
                return web.Response(status=400, text="unsupported action entity")
            domain = entity_id.split(".", 1)[0]
            await hass.services.async_call(
                domain, "toggle", {"entity_id": entity_id}, blocking=True
            )
        elif action == "complete_task":
            source = request.query.get("source") or device.media.task_source or ""
            uid = request.query.get("uid", "")
            if not source.startswith("todo.") or not uid:
                return web.Response(status=400, text="invalid task action")
            await async_handle_task_action(
                hass,
                _registry(hass),
                device_id,
                {"type": "task_action", "action": "complete", "source": source, "uid": uid},
            )
        else:
            return web.Response(status=400, text="unsupported action")

        location = f"/api/oldphonekiosk/web-display/{device_id}?token={token}"
        return web.HTTPFound(location=location)


class WebDisplayActionView(HomeAssistantView):
    """Safe Kindle/web-display action links backed by HA services."""

    url = "/api/oldphonekiosk/web-display/{device_id}/action"
    name = "api:oldphonekiosk:web-display:action"
    requires_auth = False

    async def get(self, request: web.Request, device_id: str) -> web.Response:
        return await WebDisplayView().get_action(request, device_id)


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
                        elif raw.get("type") == "calendar_action":
                            await async_handle_calendar_action(
                                hass, registry, device_id, raw
                            )
                        elif raw.get("type") == "intercom_signal":
                            try:
                                await get_intercom_broker(hass).handle_device_signal(
                                    device_id, validate_device_signal(raw)
                                )
                            except IntercomSessionError:
                                _LOGGER.debug(
                                    "Ignoring invalid device intercom signal",
                                    exc_info=True,
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
    hass.http.register_view(WebDisplayView())
    hass.http.register_view(WebDisplayActionView())
    hass.http.register_view(DeviceWebSocketView())
