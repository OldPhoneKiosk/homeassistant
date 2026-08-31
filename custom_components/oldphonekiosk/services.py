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
    ATTR_AUDIO_URL,
    ATTR_CAMERA_MODE,
    ATTR_DASHBOARD_URL,
    ATTR_DEFAULT_SCREEN,
    ATTR_DEVICE_ID,
    ATTR_ENABLED_SCREENS,
    ATTR_INTERCOM_MODE,
    ATTR_NAME,
    ATTR_PHOTO_SOURCE,
    ATTR_ROOM,
    ATTR_SHOW_BOTTOM_MENU,
    ATTR_SOUND,
    ATTR_SOUND_URL,
    ATTR_STREAM_URL,
    ATTR_TASK_SOURCE,
    ATTR_VIDEO_URL,
    CAMERA_MODES,
    DOMAIN,
    SCREENS,
    SERVICE_BEEP,
    SERVICE_PAIR_NEW_PANEL,
    SERVICE_PLAY_SOUND,
    SERVICE_REVOKE_PANEL,
    SERVICE_SET_MEDIA,
    SERVICE_SET_PANEL_UI,
    SERVICE_START_INTERCOM,
    SERVICE_START_STREAM,
    SERVICE_STOP_INTERCOM,
    SERVICE_STOP_STREAM,
)
from .coordinator import OldPhoneKioskCoordinator
from .media_sources import async_resolve_media_source_url, is_media_source

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

SET_PANEL_UI_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_DEFAULT_SCREEN): vol.In([s for s in SCREENS if s != "sleep"]),
        vol.Optional(ATTR_ENABLED_SCREENS): vol.All(
            cv.ensure_list, [vol.In([s for s in SCREENS if s != "sleep"])]
        ),
        vol.Optional(ATTR_SHOW_BOTTOM_MENU): cv.boolean,
        vol.Optional(ATTR_DASHBOARD_URL): vol.Any(None, cv.string),
        vol.Optional(ATTR_TASK_SOURCE): vol.Any(None, cv.string),
        vol.Optional(ATTR_PHOTO_SOURCE): vol.Any(None, cv.string),
    }
)

STOP_STREAM_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

BEEP_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

PLAY_SOUND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_SOUND): cv.string,
        vol.Optional(ATTR_SOUND_URL): cv.string,
    }
)

START_INTERCOM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_INTERCOM_MODE): vol.In(["ring", "talk"]),
        vol.Optional(ATTR_AUDIO_URL): cv.string,
        vol.Optional(ATTR_STREAM_URL): cv.string,
    }
)

STOP_INTERCOM_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _find_coordinator(
    hass: HomeAssistant, device_id: str
) -> OldPhoneKioskCoordinator | None:
    """Return the coordinator whose Bridge currently knows ``device_id``."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if isinstance(coordinator, OldPhoneKioskCoordinator) and device_id in (
            coordinator.data or {}
        ):
            return coordinator
    return None


def _any_coordinator(hass: HomeAssistant) -> OldPhoneKioskCoordinator | None:
    """Return the first configured coordinator (single-Bridge assumption)."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if isinstance(coordinator, OldPhoneKioskCoordinator):
            return coordinator
    return None


async def async_create_pairing_response(
    hass: HomeAssistant,
    coordinator: OldPhoneKioskCoordinator,
    *,
    name: str,
    room: str | None = None,
) -> ServiceResponse:
    """Provision a new panel and surface the one-time pairing code in HA."""
    try:
        claim = await coordinator.client.async_create_claim(name, room)
    except BridgeError as err:
        raise HomeAssistantError(f"Panel provisioning failed: {err}") from err

    pairing_code = claim.claim_token

    await coordinator.async_request_refresh()

    # Surface the one-time pairing code to the user via a persistent notification.
    message = (
        f"To pair **{name}**, open the OldPhoneKiosk app on the phone/tablet, go to "
        f"**Pairing**, and enter this one-time code:\n\n"
        f"## `{pairing_code}`\n\n"
        "The code expires shortly and can be used once. The app only needs your "
        "Home Assistant address — never your admin token."
    )
    persistent_notification.async_create(
        hass,
        message,
        title="OldPhoneKiosk — pair a panel",
        notification_id=f"{DOMAIN}_pair_{claim.device_id}",
    )

    return {
        "device_id": claim.device_id,
        "pairing_code": pairing_code,
    }


async def _async_pair_new_panel(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Provision a new panel and return a one-time 10-digit pairing code."""
    coordinator = _any_coordinator(hass)
    if coordinator is None:
        raise ServiceValidationError("No OldPhoneKiosk backend is configured.")

    return await async_create_pairing_response(
        hass,
        coordinator,
        name=call.data[ATTR_NAME],
        room=call.data.get(ATTR_ROOM),
    )


async def _async_revoke_panel(hass: HomeAssistant, call: ServiceCall) -> None:
    """Revoke a panel on its Bridge and clean up the HA device."""
    device_id: str = call.data[ATTR_DEVICE_ID]

    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'. "
            "Use the panel device id (see the panel's 'bridge_device_id' attribute)."
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
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
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


async def _async_set_panel_ui(hass: HomeAssistant, call: ServiceCall) -> None:
    """Push kiosk navigation/default-screen/dashboard config to an online panel."""
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
        )

    params: dict[str, str] = {}
    if ATTR_DEFAULT_SCREEN in call.data:
        params[ATTR_DEFAULT_SCREEN] = call.data[ATTR_DEFAULT_SCREEN]
    if ATTR_ENABLED_SCREENS in call.data:
        params[ATTR_ENABLED_SCREENS] = ",".join(call.data[ATTR_ENABLED_SCREENS])
    if ATTR_SHOW_BOTTOM_MENU in call.data:
        params[ATTR_SHOW_BOTTOM_MENU] = (
            "true" if call.data[ATTR_SHOW_BOTTOM_MENU] else "false"
        )
    if ATTR_DASHBOARD_URL in call.data:
        params[ATTR_DASHBOARD_URL] = call.data[ATTR_DASHBOARD_URL] or ""
    if ATTR_TASK_SOURCE in call.data:
        params[ATTR_TASK_SOURCE] = call.data[ATTR_TASK_SOURCE] or ""
    if ATTR_PHOTO_SOURCE in call.data:
        params[ATTR_PHOTO_SOURCE] = call.data[ATTR_PHOTO_SOURCE] or ""

    if not params:
        raise ServiceValidationError("Set at least one panel UI option.")

    try:
        await coordinator.client.async_set_panel_ui(
            device_id,
            default_screen=call.data.get(ATTR_DEFAULT_SCREEN),
            enabled_screens=call.data.get(ATTR_ENABLED_SCREENS),
            show_bottom_menu=call.data.get(ATTR_SHOW_BOTTOM_MENU),
            dashboard_url=call.data.get(ATTR_DASHBOARD_URL)
            if ATTR_DASHBOARD_URL in call.data
            else None,
            task_source=call.data.get(ATTR_TASK_SOURCE)
            if ATTR_TASK_SOURCE in call.data
            else None,
            photo_source=call.data.get(ATTR_PHOTO_SOURCE)
            if ATTR_PHOTO_SOURCE in call.data
            else None,
        )
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge set_panel_ui failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_beep(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
        )
    try:
        await coordinator.client.async_beep(device_id)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge beep failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_play_sound(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
        )
    sound = call.data.get(ATTR_SOUND)
    url = call.data.get(ATTR_SOUND_URL)
    if not url and is_media_source(sound):
        resolved_url = await async_resolve_media_source_url(hass, sound)
        if resolved_url:
            url = resolved_url
            sound = None
    try:
        await coordinator.client.async_play_sound(
            device_id,
            sound=sound,
            url=url,
        )
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge play_sound failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_start_intercom(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
        )
    try:
        # Intercom should establish a useful HA-side connection, not only toggle
        # a state banner on the panel. Start the foreground front-camera MJPEG
        # publisher first so `camera.<panel>_camera` receives a live URL from the
        # next device heartbeat, then mark the panel as ringing/talking.
        await coordinator.client.async_start_stream(device_id, camera_mode="front")
        await coordinator.client.async_start_intercom(
            device_id,
            mode=call.data.get(ATTR_INTERCOM_MODE),
            audio_url=call.data.get(ATTR_AUDIO_URL),
            stream_url=call.data.get(ATTR_STREAM_URL),
        )
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge start_intercom failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_stop_intercom(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
        )
    try:
        await coordinator.client.async_stop_intercom(device_id)
    except BridgeError as err:
        raise HomeAssistantError(f"Bridge stop_intercom failed: {err}") from err
    await coordinator.async_request_refresh()


async def _async_start_stream(hass: HomeAssistant, call: ServiceCall) -> None:
    device_id: str = call.data[ATTR_DEVICE_ID]
    coordinator = _find_coordinator(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
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
            f"No configured OldPhoneKiosk backend knows device '{device_id}'."
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

    async def _handle_set_panel_ui(call: ServiceCall) -> None:
        await _async_set_panel_ui(hass, call)

    async def _handle_start_stream(call: ServiceCall) -> None:
        await _async_start_stream(hass, call)

    async def _handle_stop_stream(call: ServiceCall) -> None:
        await _async_stop_stream(hass, call)

    async def _handle_beep(call: ServiceCall) -> None:
        await _async_beep(hass, call)

    async def _handle_play_sound(call: ServiceCall) -> None:
        await _async_play_sound(hass, call)

    async def _handle_start_intercom(call: ServiceCall) -> None:
        await _async_start_intercom(hass, call)

    async def _handle_stop_intercom(call: ServiceCall) -> None:
        await _async_stop_intercom(hass, call)

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
        DOMAIN,
        SERVICE_SET_PANEL_UI,
        _handle_set_panel_ui,
        schema=SET_PANEL_UI_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_STREAM, _handle_start_stream, schema=START_STREAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_STREAM, _handle_stop_stream, schema=STOP_STREAM_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_BEEP, _handle_beep, schema=BEEP_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_PLAY_SOUND, _handle_play_sound, schema=PLAY_SOUND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_INTERCOM,
        _handle_start_intercom,
        schema=START_INTERCOM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_INTERCOM,
        _handle_stop_intercom,
        schema=STOP_INTERCOM_SCHEMA,
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
        hass.services.async_remove(DOMAIN, SERVICE_SET_PANEL_UI)
        hass.services.async_remove(DOMAIN, SERVICE_START_STREAM)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_STREAM)
        hass.services.async_remove(DOMAIN, SERVICE_BEEP)
        hass.services.async_remove(DOMAIN, SERVICE_PLAY_SOUND)
        hass.services.async_remove(DOMAIN, SERVICE_START_INTERCOM)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_INTERCOM)
