"""Per-panel numeric controls for OldPhoneKiosk."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SET_BRIGHTNESS, CMD_SET_VOLUME, DOMAIN
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
        return [
            entity
            for device_id in device_ids
            for entity in (
                PanelControlNumber(
                    coordinator,
                    device_id,
                    key="screen_brightness",
                    name="Screen brightness",
                    command=CMD_SET_BRIGHTNESS,
                    icon="mdi:brightness-6",
                    initial=100,
                ),
                PanelControlNumber(
                    coordinator,
                    device_id,
                    key="device_volume",
                    name="Device volume",
                    command=CMD_SET_VOLUME,
                    icon="mdi:volume-high",
                    initial=50,
                ),
            )
        ]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PanelControlNumber(OldPhoneKioskEntity, NumberEntity):
    """Send a 0..100 percent device control command to the panel."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: OldPhoneKioskCoordinator,
        device_id: str,
        *,
        key: str,
        name: str,
        command: str,
        icon: str,
        initial: float,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._command = command
        self._value = initial

    @property
    def native_value(self) -> float | None:
        if self._command == CMD_SET_BRIGHTNESS:
            device = self.device
            if device and device.brightness is not None:
                return round(float(device.brightness) * 100)
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        value = max(0, min(100, float(value)))
        self._value = value
        await self.coordinator.client.async_send_command(
            self._device_id,
            self._command,
            params={"level": f"{value / 100:.3f}", "percent": str(round(value))},
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
