"""Home Assistant browser websocket API for OldPhoneKiosk intercom."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

DATA_REGISTRY = "registry"
from .intercom import IntercomBroker, IntercomSessionError
from .registry import DeviceOfflineError, UnknownDeviceError

_LOGGER = logging.getLogger(__name__)

DATA_INTERCOM_BROKER = "intercom_broker"
DATA_INTERCOM_WS_REGISTERED = "intercom_ws_registered"


def get_intercom_broker(hass: HomeAssistant) -> IntercomBroker:
    """Return the process-local intercom broker."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    broker = domain_data.get(DATA_INTERCOM_BROKER)
    if broker is None:
        broker = IntercomBroker(domain_data[DATA_REGISTRY])
        domain_data[DATA_INTERCOM_BROKER] = broker
    return broker


def _error_code(exc: Exception) -> str:
    if isinstance(exc, UnknownDeviceError):
        return "unknown_device"
    if isinstance(exc, DeviceOfflineError):
        return "device_offline"
    if isinstance(exc, IntercomSessionError):
        return "invalid_session"
    return "intercom_failed"


async def _send_signal_to_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    *,
    action: str,
) -> None:
    broker = get_intercom_broker(hass)
    session_id = msg["session_id"]
    payload: dict[str, Any] = {"type": "intercom_signal", "action": action}
    for key in ("sdp", "candidate", "sdpMid", "sdpMLineIndex"):
        if key in msg:
            payload[key] = msg[key]
    try:
        await broker.send_to_device(session_id, payload)
    except Exception as exc:  # Home Assistant WS APIs report protocol errors via send_error.
        _LOGGER.debug("Could not forward intercom signal to device", exc_info=True)
        connection.send_error(msg["id"], _error_code(exc), str(exc))
        return
    connection.send_result(msg["id"], {"session_id": session_id, "action": action})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oldphonekiosk/intercom/start",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_intercom_start(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start a call and return its session id."""
    broker = get_intercom_broker(hass)

    try:
        session = await broker.start_session(msg["device_id"])
    except Exception as exc:
        _LOGGER.debug("Could not start intercom session", exc_info=True)
        connection.send_error(msg["id"], _error_code(exc), str(exc))
        return

    connection.send_result(
        msg["id"],
        {
            "session_id": session.session_id,
            "device_id": session.device_id,
            "state": session.state,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oldphonekiosk/intercom/subscribe",
        vol.Required("session_id"): str,
    }
)
@websocket_api.async_response
async def ws_intercom_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe a HA browser connection to device signaling events."""
    broker = get_intercom_broker(hass)
    subscription_id = msg["id"]

    async def handler(frame: dict) -> None:
        connection.send_event(subscription_id, frame)

    try:
        session = broker.set_handler(msg["session_id"], handler)
    except Exception as exc:
        connection.send_error(subscription_id, _error_code(exc), str(exc))
        return

    @callback
    def unsubscribe() -> None:
        broker.end_session(session.session_id)

    connection.subscriptions[subscription_id] = unsubscribe
    connection.send_result(subscription_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oldphonekiosk/intercom/offer",
        vol.Required("session_id"): str,
        vol.Required("sdp"): str,
    }
)
@websocket_api.async_response
async def ws_intercom_offer(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Forward a browser SDP offer to the iOS panel."""
    await _send_signal_to_device(hass, connection, msg, action="offer")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oldphonekiosk/intercom/ice_candidate",
        vol.Required("session_id"): str,
        vol.Required("candidate"): dict,
    }
)
@websocket_api.async_response
async def ws_intercom_ice_candidate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Forward a browser ICE candidate to the iOS panel."""
    await _send_signal_to_device(hass, connection, msg, action="ice_candidate")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oldphonekiosk/intercom/hangup",
        vol.Required("session_id"): str,
    }
)
@websocket_api.async_response
async def ws_intercom_hangup(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Hang up an active call."""
    broker = get_intercom_broker(hass)
    try:
        await broker.hangup(msg["session_id"])
    except Exception as exc:
        _LOGGER.debug("Could not hang up intercom session", exc_info=True)
        connection.send_error(msg["id"], _error_code(exc), str(exc))
        return
    connection.send_result(msg["id"], {"session_id": msg["session_id"], "action": "hangup"})


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register browser-facing websocket commands once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_INTERCOM_WS_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_intercom_start)
    websocket_api.async_register_command(hass, ws_intercom_subscribe)
    websocket_api.async_register_command(hass, ws_intercom_offer)
    websocket_api.async_register_command(hass, ws_intercom_ice_candidate)
    websocket_api.async_register_command(hass, ws_intercom_hangup)
    domain_data[DATA_INTERCOM_WS_REGISTERED] = True
