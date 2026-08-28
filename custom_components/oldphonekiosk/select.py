"""Screen select for OldPhoneKiosk panels."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCREEN_TO_COMMAND, SCREENS
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
        return [ScreenSelect(coordinator, device_id) for device_id in device_ids]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class ScreenSelect(OldPhoneKioskEntity, SelectEntity):
    _attr_translation_key = "screen"
    _attr_options = SCREENS

    def __init__(self, coordinator, device_id) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_screen"
        self._attr_name = "Screen"

    @property
    def current_option(self) -> str | None:
        device = self.device
        if device is None or device.screen not in SCREENS:
            return None
        return device.screen

    async def async_select_option(self, option: str) -> None:
        command = SCREEN_TO_COMMAND[option]
        await self.coordinator.client.async_send_command(self._device_id, command)
        await self.coordinator.async_request_refresh()
