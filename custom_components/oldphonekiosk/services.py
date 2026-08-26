"""Services for the OldPhoneKiosk integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import BridgeError, BridgeNotFoundError
from .const import ATTR_DEVICE_ID, DOMAIN, SERVICE_REVOKE_PANEL
from .coordinator import OldPhoneKioskCoordinator

_LOGGER = logging.getLogger(__name__)

REVOKE_PANEL_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


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


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_REVOKE_PANEL):
        return

    async def _handle_revoke_panel(call: ServiceCall) -> None:
        await _async_revoke_panel(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REVOKE_PANEL,
        _handle_revoke_panel,
        schema=REVOKE_PANEL_SCHEMA,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services once the last config entry is gone."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_REVOKE_PANEL)
