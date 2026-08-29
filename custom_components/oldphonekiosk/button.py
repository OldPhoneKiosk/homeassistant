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
    ("wake", "Wake", CMD_WAKE, "mdi:white-balance-sunny"),
    ("sleep", "Sleep", CMD_SLEEP, "mdi:power-sleep"),
)
# Camera controls: front/back start + stop, all bound to the same panel HA device.
STREAM_BUTTONS = (
    ("start_front_camera", "Start front camera", "front", "mdi:camera-front"),
    ("start_back_camera", "Start back camera", "back", "mdi:camera-rear"),
    ("stop_camera", "Stop camera", None, "mdi:camera-off"),
)
# Action buttons dispatched through dedicated client helpers (not plain commands).
ACTION_BUTTONS = (
    ("beep", "Beep", "mdi:bullhorn"),
    ("play_sound", "Play sound", "mdi:music-note"),
    ("start_intercom", "Start intercom", "mdi:phone-in-talk"),
    ("stop_intercom", "Stop intercom", "mdi:phone-hangup"),
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
            PanelCommandButton(coordinator, device_id, key, name, command, icon)
            for device_id in device_ids
            for key, name, command, icon in BUTTONS
        ] + [
            PanelStreamButton(coordinator, device_id, key, name, camera_mode, icon)
            for device_id in device_ids
            for key, name, camera_mode, icon in STREAM_BUTTONS
        ] + [
            PanelActionButton(coordinator, device_id, key, name, icon)
            for device_id in device_ids
            for key, name, icon in ACTION_BUTTONS
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
    def __init__(self, coordinator, device_id, key, name, command, icon=None) -> None:
        super().__init__(coordinator, device_id)
        self._command = command
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_name = name
        if icon:
            self._attr_icon = icon

    async def async_press(self) -> None:
        await self.coordinator.client.async_send_command(self._device_id, self._command)
        await self.coordinator.async_request_refresh()


class PanelStreamButton(OldPhoneKioskEntity, ButtonEntity):
    def __init__(self, coordinator, device_id, key, name, camera_mode, icon) -> None:
        super().__init__(coordinator, device_id)
        self._camera_mode = camera_mode  # None => stop
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self) -> None:
        if self._camera_mode is not None:
            await self.coordinator.client.async_start_stream(
                self._device_id, camera_mode=self._camera_mode
            )
        else:
            await self.coordinator.client.async_stop_stream(self._device_id)
        await self.coordinator.async_request_refresh()


class PanelActionButton(OldPhoneKioskEntity, ButtonEntity):
    """Beep / play sound / intercom controls dispatched via client helpers."""

    def __init__(self, coordinator, device_id, key, name, icon) -> None:
        super().__init__(coordinator, device_id)
        self._key = key
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self) -> None:
        client = self.coordinator.client
        if self._key == "beep":
            await client.async_beep(self._device_id)
        elif self._key == "play_sound":
            await client.async_play_sound(self._device_id)
        elif self._key == "start_intercom":
            await client.async_start_intercom(self._device_id)
        elif self._key == "stop_intercom":
            await client.async_stop_intercom(self._device_id)
        await self.coordinator.async_request_refresh()
