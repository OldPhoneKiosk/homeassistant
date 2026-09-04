"""The OldPhoneKiosk Home Assistant-native integration."""

from __future__ import annotations

import inspect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .backend import DATA_HTTP_REGISTERED, ensure_backend
from .const import DOMAIN
from .coordinator import OldPhoneKioskCoordinator
from .frontend import async_setup_frontend, async_unload_frontend
from .native_client import NativeOldPhoneKioskClient as BridgeClient
from .services import async_setup_services, async_unload_services
from .websocket_api import async_register_websocket_api

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.TEXT,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old external-Bridge entries to the HA-native single entry."""
    if entry.version < 2:
        kwargs = {"data": {}, "title": "OldPhoneKiosk"}
        if (
            "version"
            in inspect.signature(hass.config_entries.async_update_entry).parameters
        ):
            kwargs["version"] = 2
            hass.config_entries.async_update_entry(entry, **kwargs)
        else:
            hass.config_entries.async_update_entry(entry, **kwargs)
            # HA 2024.1 lacks the version kwarg but allows migration handlers to
            # set the field directly; newer HA requires the kwarg branch above.
            entry.version = 2
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OldPhoneKiosk from a config entry."""
    registry = ensure_backend(hass)
    client = BridgeClient(registry)
    coordinator = OldPhoneKioskCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    await async_setup_frontend(hass)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.data.setdefault(DOMAIN, {}).pop(DATA_HTTP_REGISTERED, None)
    ensure_backend(hass)

    async_setup_services(hass)
    async_register_websocket_api(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()
        if not hass.data[DOMAIN]:
            await async_unload_frontend(hass)
        async_unload_services(hass)
    return unload_ok
