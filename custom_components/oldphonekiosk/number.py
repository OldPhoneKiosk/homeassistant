"""Per-panel numeric controls for OldPhoneKiosk."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
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
                PanelCommandNumber(
                    coordinator,
                    device_id,
                    key="screen_brightness",
                    name="Screen brightness",
                    command=CMD_SET_BRIGHTNESS,
                    icon="mdi:brightness-6",
                    initial=100,
                ),
                PanelCommandNumber(
                    coordinator,
                    device_id,
                    key="device_volume",
                    name="Device volume",
                    command=CMD_SET_VOLUME,
                    icon="mdi:volume-high",
                    initial=50,
                ),
                PanelUINumber(
                    coordinator,
                    device_id,
                    key="dim_after_seconds",
                    name="Dim after",
                    icon="mdi:brightness-4",
                    field="dim_after_seconds",
                    initial=60,
                    minimum=10,
                    maximum=3600,
                    step=5,
                ),
                PanelUINumber(
                    coordinator,
                    device_id,
                    key="sleep_after_seconds",
                    name="Sleep screen after",
                    icon="mdi:sleep",
                    field="sleep_after_seconds",
                    initial=180,
                    minimum=10,
                    maximum=7200,
                    step=5,
                ),
                PanelUINumber(
                    coordinator,
                    device_id,
                    key="task_refresh_seconds",
                    name="Refresh tasks every",
                    icon="mdi:refresh",
                    field="task_refresh_seconds",
                    initial=0,
                    minimum=0,
                    maximum=86400,
                    step=5,
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


class PanelCommandNumber(OldPhoneKioskEntity, NumberEntity):
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


class PanelUINumber(OldPhoneKioskEntity, NumberEntity):
    """Persist and push a numeric configure_ui setting."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: OldPhoneKioskCoordinator,
        device_id: str,
        *,
        key: str,
        name: str,
        icon: str,
        field: str,
        initial: float,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._field = field
        self._value = initial

    @property
    def native_value(self) -> float | None:
        device = self.device
        stored = getattr(device, self._field, None) if device else None
        return stored if stored is not None else self._value

    async def async_set_native_value(self, value: float) -> None:
        value = max(
            self._attr_native_min_value, min(self._attr_native_max_value, float(value))
        )
        self._value = value
        await self.coordinator.client.async_set_panel_ui(
            self._device_id,
            **{self._field: value},
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
