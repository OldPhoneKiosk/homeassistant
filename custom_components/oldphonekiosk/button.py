"""Wake/Sleep buttons for OldPhoneKiosk panels."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SLEEP, CMD_WAKE, DOMAIN
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity

BUTTONS = (
    ("wake", "Wake", CMD_WAKE),
    ("sleep", "Sleep", CMD_SLEEP),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PanelCommandButton(coordinator, device_id, key, name, command)
        for device_id in coordinator.data
        for key, name, command in BUTTONS
    )


class PanelCommandButton(OldPhoneKioskEntity, ButtonEntity):
    def __init__(self, coordinator, device_id, key, name, command) -> None:
        super().__init__(coordinator, device_id)
        self._command = command
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_name = name

    async def async_press(self) -> None:
        await self.coordinator.client.async_send_command(self._device_id, self._command)
        await self.coordinator.async_request_refresh()
