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
        return [
            entity
            for device_id in device_ids
            for entity in (
                PanelUISwitch(
                    coordinator,
                    device_id,
                    key="bottom_menu",
                    name="Bottom menu",
                    icon="mdi:dock-bottom",
                    field="show_bottom_menu",
                    default=True,
                ),
                PanelUISwitch(
                    coordinator,
                    device_id,
                    key="keep_screen_awake",
                    name="Keep screen awake in app",
                    icon="mdi:cellphone-lock",
                    field="keep_screen_awake",
                    default=True,
                ),
                PanelUISwitch(
                    coordinator,
                    device_id,
                    key="connection_banner",
                    name="Connection banner",
                    icon="mdi:connection",
                    field="show_connection_banner",
                    default=True,
                ),
                PanelUISwitch(
                    coordinator,
                    device_id,
                    key="camera_rotate_180",
                    name="Rotate camera 180°",
                    icon="mdi:rotate-3d-variant",
                    field="camera_rotate_180",
                    default=False,
                ),
                PanelUISwitch(
                    coordinator,
                    device_id,
                    key="photo_time_overlay",
                    name="Photo time overlay",
                    icon="mdi:clock-outline",
                    field="show_photo_time_overlay",
                    default=False,
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


class PanelUISwitch(OldPhoneKioskEntity, SwitchEntity):
    """Persist and push a boolean configure_ui setting."""

    def __init__(
        self,
        coordinator: OldPhoneKioskCoordinator,
        device_id: str,
        *,
        key: str,
        name: str,
        icon: str,
        field: str,
        default: bool,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._field = field
        self._default = default
        self._optimistic: bool | None = None

    @property
    def is_on(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        device = self.device
        stored = getattr(device, self._field, None) if device else None
        return stored if stored is not None else self._default

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        self._optimistic = value
        await self.coordinator.client.async_set_panel_ui(
            self._device_id,
            **{self._field: value},
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic = None
        super()._handle_coordinator_update()
