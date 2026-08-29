"""Buttons for OldPhoneKiosk hub actions and paired panels."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SLEEP, CMD_WAKE, DOMAIN
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity
from .services import async_create_pairing_response

BUTTONS = (
    ("wake", "Wake", CMD_WAKE),
    ("sleep", "Sleep", CMD_SLEEP),
)
STREAM_BUTTONS = (
    ("start_camera", "Start camera"),
    ("stop_camera", "Stop camera"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices = set(coordinator.data or {})

    def _panel_entities(device_ids: set[str]):
        return [
            PanelCommandButton(coordinator, device_id, key, name, command)
            for device_id in device_ids
            for key, name, command in BUTTONS
        ] + [
            PanelStreamButton(coordinator, device_id, key, name)
            for device_id in device_ids
            for key, name in STREAM_BUTTONS
        ]

    entities: list[ButtonEntity] = [HubPairingButton(coordinator, entry)]
    entities.extend(_panel_entities(known_devices))
    async_add_entities(entities)

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_panel_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class HubPairingButton(ButtonEntity):
    """Hub-level button that generates the next one-time pairing code notification."""

    _attr_has_entity_name = True
    _attr_name = "Generate pairing code"
    _attr_translation_key = "generate_pairing_code"

    def __init__(self, coordinator: OldPhoneKioskCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_generate_pairing_code"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "OldPhoneKiosk",
            manufacturer="OldPhoneKiosk",
            model="Home Assistant hub",
        )

    async def async_press(self) -> None:
        """Create a default pairing claim and show the code in notifications."""
        await async_create_pairing_response(
            self.coordinator.hass,
            self.coordinator,
            name="OldPhoneKiosk Panel",
            room=None,
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


class PanelStreamButton(OldPhoneKioskEntity, ButtonEntity):
    def __init__(self, coordinator, device_id, key, name) -> None:
        super().__init__(coordinator, device_id)
        self._key = key
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_name = name
        self._attr_icon = "mdi:camera" if key == "start_camera" else "mdi:camera-off"

    async def async_press(self) -> None:
        if self._key == "start_camera":
            await self.coordinator.client.async_start_stream(self._device_id, camera_mode="front")
        else:
            await self.coordinator.client.async_stop_stream(self._device_id)
        await self.coordinator.async_request_refresh()
