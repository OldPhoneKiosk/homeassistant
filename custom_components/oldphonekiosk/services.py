"""Services for the OldPhoneKiosk integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import BridgeError, BridgeNotFoundError
from .const import (
    ATTR_CAMERA_MODE,
    ATTR_DEVICE_ID,
    ATTR_NAME,
    ATTR_ROOM,
    ATTR_VIDEO_URL,
    CAMERA_MODES,
    CONF_BRIDGE_URL,
    DOMAIN,
    SERVICE_PAIR_NEW_PANEL,
    SERVICE_REVOKE_PANEL,
    SERVICE_SET_MEDIA,
    SERVICE_START_STREAM,
    SERVICE_STOP_STREAM,
)
from .coordinator import OldPhoneKioskCoordinator
from .pairing import (
    build_pairing_payload,
    payload_to_json,
    payload_to_qr_svg_data_uri,
)

_LOGGER = logging.getLogger(__name__)

REVOKE_PANEL_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

PAIR_NEW_PANEL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_ROOM): cv.string,
    }
)

SET_MEDIA_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Optional(ATTR_VIDEO_URL): vol.Any(None, cv.string),
            vol.Optional(ATTR_CAMERA_MODE): vol.In(CAMERA_MODES),
        }
    ),
    # Require at least one media field to change.
    cv.has_at_least_one_key(ATTR_VIDEO_URL, ATTR_CAMERA_MODE),
)

START_STREAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_CAMERA_MODE): vol.In(CAMERA_MODES),
    }
)

STOP_STREAM_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _find_coordinator(
    hass: HomeAssistant, device_id: str
) -> OldPhoneKioskCoordinator | None:
    """Return the coordinator whose Bridge currently knows ``device_id``."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if (
            isinstance(coordinator, OldPhoneKioskCoordinator)
            and device_id in (coordinator.data or {})
        ):
            return coordinator
    return None


def _any_coordinator(hass: HomeAssistant) -> OldPhoneKioskCoordinator | None:
    """Return the first configured coordinator (single-Bridge assumption)."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if isinstance(coordinator, OldPhoneKioskCoordinator):
            return coordinator
    return None


async def _async_pair_new_panel(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Provision a new panel on the Bridge and return a scannable QR payload."""
    name: str = call.data[ATTR_NAME]
    room: str | None = call.data.get(ATTR_ROOM)

    coordinator = _any_coordinator(hass)
    if coordinator is None:
        raise ServiceValidationError("No OldPhoneKiosk Bridge is configured.")

    try:
        provisioned = await coordinator.client.async_provision_panel(name, room)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge provisioning failed: {err}") from err

    bridge_url = coordinator.entry.data[CONF_BRIDGE_URL]
    payload = build_pairing_payload(
        bridge_url=bridge_url,
        device_id=provisioned.device_id,
        device_secret=provisioned.device_secret,
        name=name,
        room=room,
    )
    payload_json = payload_to_json(payload)
    qr_data_uri = payload_to_qr_svg_data_uri(payload_json)

    await coordinator.async_request_refresh()

    # Surface the QR (or the payload) to the user via a persistent notification.
    if qr_data_uri:
        message = f"Scan this QR in the OldPhoneKiosk app to pair **{name}**:\n\n![pairing qr]({qr_data_uri})"
    else:
        message = (
            f"Pair **{name}** in the OldPhoneKiosk app with this payload "
            f"(install `qrcode` for an image):\n\n```\n{payload_json}\n```"
        )
    persistent_notification.async_create(
        hass,
        message,
        title="OldPhoneKiosk — pair a panel",
        notification_id=f"{DOMAIN}_pair_{provisioned.device_id}",
    )

    return {
        "device_id": provisioned.device_id,
        "payload": payload_json,
        "qr_svg_data_uri": qr_data_uri,
    }


async def _async_revoke_panel(hass: HomeAssistant, call: ServiceCall) -> None:
    """Revoke a panel on its Bridge and clean up the HA device."""
    device_id: str = call.data[ATTR_DEVICE_ID]

    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk Bridge knows device '{device_id}'. "
            "Use the Bridge device id (see the panel's 'bridge_device_id' attribute)."
        )

    try:
        await coordinator.client.async_delete_device(device_id)
    except BridgeNotFoundError:
        # Already gone on the Bridge — continue to clean up the HA side.
        _LOGGER.info("Device %s already absent on Bridge; cleaning up HA", device_id)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge revoke failed: {err}") from err

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, device_id)})
    if device is not None:
        registry.async_remove_device(device.id)

    await coordinator.async_request_refresh()


async def _async_set_media(hass: HomeAssistant, call: ServiceCall) -> None:
    """Set a panel's media config (video_url / camera_mode) on its Bridge."""
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk Bridge knows device '{device_id}'."
        )

    kwargs: dict = {}
    if ATTR_VIDEO_URL in call.data:
        kwargs["video_url"] = call.data[ATTR_VIDEO_URL]
    if ATTR_CAMERA_MODE in call.data:
        kwargs["camera_mode"] = call.data[ATTR_CAMERA_MODE]

    try:
        await coordinator.client.async_set_media(device_id, **kwargs)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge set_media failed: {err}") from err

    await coordinator.async_request_refresh()


async def _async_start_stream(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk Bridge knows device '{device_id}'."
        )
    try:
        await coordinator.client.async_start_stream(
            device_id, camera_mode=call.data.get(ATTR_CAMERA_MODE)
        )
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge start_stream failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_stop_stream(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk Bridge knows device '{device_id}'."
        )
    try:
        await coordinator.client.async_stop_stream(device_id)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge stop_stream failed: {err}") from err
    await coordinator.async_request_refresh()


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_REVOKE_PANEL):
        return

    async def _handle_revoke_panel(call: ServiceCall) -> None:
        await _async_revoke_panel(hass, call)

    async def _handle_pair_new_panel(call: ServiceCall) -> ServiceResponse:
        return await _async_pair_new_panel(hass, call)

    async def _handle_set_media(call: ServiceCall) -> None:
        await _async_set_media(hass, call)

    async def _handle_start_stream(call: ServiceCall) -> None:
        await _async_start_stream(hass, call)

    async def _handle_stop_stream(call: ServiceCall) -> None:
        await _async_stop_stream(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REVOKE_PANEL,
        _handle_revoke_panel,
        schema=REVOKE_PANEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEDIA,
        _handle_set_media,
        schema=SET_MEDIA_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_STREAM, _handle_start_stream, schema=START_STREAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_STREAM, _handle_stop_stream, schema=STOP_STREAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAIR_NEW_PANEL,
        _handle_pair_new_panel,
        schema=PAIR_NEW_PANEL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services once the last config entry is gone."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_REVOKE_PANEL)
        hass.services.async_remove(DOMAIN, SERVICE_PAIR_NEW_PANEL)
        hass.services.async_remove(DOMAIN, SERVICE_SET_MEDIA)
        hass.services.async_remove(DOMAIN, SERVICE_START_STREAM)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_STREAM)
