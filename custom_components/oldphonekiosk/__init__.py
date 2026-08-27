"""The OldPhoneKiosk Home Assistant-native integration."""

from __future__ import annotations

import inspect
import secrets

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OldPhoneKioskCoordinator
from .http import DATA_REGISTRY, DATA_WS_TOKENS, async_register_http_views
from .native_client import NativeOldPhoneKioskClient as BridgeClient
from .registry import Registry
from .services import async_setup_services, async_unload_services
from .store import DeviceStore
from .wstoken import WsTokenService

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
]


def _ensure_backend(hass: HomeAssistant) -> Registry:
    """Create the in-process backend once per HA process."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    registry = domain_data.get(DATA_REGISTRY)
    if registry is not None:
        return registry
    db_path = hass.config.path("oldphonekiosk/oldphonekiosk.db")
    store = DeviceStore(db_path)
    registry = Registry(store)
    registry.purge_expired_claims()
    domain_data[DATA_REGISTRY] = registry
    domain_data[DATA_WS_TOKENS] = WsTokenService(secrets.token_urlsafe(32))
    if getattr(hass, "http", None) is not None:
        async_register_http_views(hass)
    return registry


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old external-Bridge entries to the HA-native single entry."""
    if entry.version < 2:
        kwargs = {"data": {}, "title": "OldPhoneKiosk"}
        if "version" in inspect.signature(hass.config_entries.async_update_entry).parameters:
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
    registry = _ensure_backend(hass)
    client = BridgeClient(registry)
    coordinator = OldPhoneKioskCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()
        async_unload_services(hass)
    return unload_ok
