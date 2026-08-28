"""Online binary sensor for OldPhoneKiosk panels."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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
        return [OnlineBinarySensor(coordinator, device_id) for device_id in device_ids]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class OnlineBinarySensor(OldPhoneKioskEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, coordinator, device_id) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool | None:
        device = self.device
        return None if device is None else device.online

    @property
    def available(self) -> bool:
        # Online sensor should remain available even when the panel is offline.
        return self.coordinator.last_update_success and self.device is not None
