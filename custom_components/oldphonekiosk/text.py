"""Editable per-panel text fields for OldPhoneKiosk."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCREEN_DASHBOARD
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices = set(coordinator.data or {})

    def _entities(device_ids: set[str]):
        return [DashboardUrlText(coordinator, device_id) for device_id in device_ids]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class DashboardUrlText(OldPhoneKioskEntity, TextEntity):
    """Dashboard URL pushed to one phone/tablet panel."""

    _attr_translation_key = "dashboard_url"
    _attr_name = "Dashboard URL"
    _attr_icon = "mdi:view-dashboard"
    _attr_native_min = 0
    _attr_native_max = 2048

    def __init__(self, coordinator: OldPhoneKioskCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_dashboard_url"
        self._attr_native_value = None

    @property
    def native_value(self) -> str | None:
        device = self.device
        return self._attr_native_value or (device.dashboard_url if device else None)

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.device
        self._attr_native_value = device.dashboard_url if device else None
        self.async_write_ha_state()

    async def async_set_value(self, value: str) -> None:
        dashboard_url = value.strip()
        await self.coordinator.client.async_set_panel_ui(
            self._device_id,
            default_screen=SCREEN_DASHBOARD if dashboard_url else None,
            dashboard_url=dashboard_url,
        )
        self._attr_native_value = dashboard_url or None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
