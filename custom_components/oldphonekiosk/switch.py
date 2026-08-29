"""Per-panel switch controls for OldPhoneKiosk."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
        return [BottomMenuSwitch(coordinator, device_id) for device_id in device_ids]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class BottomMenuSwitch(OldPhoneKioskEntity, SwitchEntity):
    """Show/hide the phone bottom navigation menu from HA."""

    _attr_icon = "mdi:dock-bottom"

    def __init__(self, coordinator: OldPhoneKioskCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_bottom_menu"
        self._attr_name = "Bottom menu"
        self._optimistic: bool | None = None

    @property
    def is_on(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        device = self.device
        if device and device.show_bottom_menu is not None:
            return device.show_bottom_menu
        return True

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, show: bool) -> None:
        self._optimistic = show
        await self.coordinator.client.async_set_panel_ui(
            self._device_id,
            show_bottom_menu=show,
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic = None
        super()._handle_coordinator_update()
