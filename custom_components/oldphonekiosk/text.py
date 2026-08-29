"""Editable per-panel text fields for OldPhoneKiosk.

Home Assistant is the source of truth for every panel UI source: the dashboard
URL, the tasks list/source, the photos feed/source, and the play_sound target.
Each field persists on the panel's HA device and (except the sound target) pushes
a ``configure_ui`` update to the online panel so it applies immediately.
"""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCREEN_DASHBOARD
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity
from .tasks import async_push_task_snapshot


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices = set(coordinator.data or {})

    def _entities(device_ids: set[str]):
        entities: list[TextEntity] = []
        for device_id in device_ids:
            entities.append(DashboardUrlText(coordinator, device_id))
            entities.append(TaskSourceText(coordinator, device_id))
            entities.append(PhotoSourceText(coordinator, device_id))
            entities.append(SoundText(coordinator, device_id))
        return entities

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class _PanelText(OldPhoneKioskEntity, TextEntity):
    """Base for a per-panel text field backed by the device media config."""

    _attr_native_min = 0
    _attr_native_max = 2048
    _key = ""

    def __init__(self, coordinator: OldPhoneKioskCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{self._key}"
        self._attr_native_value = None

    def _device_value(self) -> str | None:  # pragma: no cover - overridden
        return None

    @property
    def native_value(self) -> str | None:
        return self._attr_native_value or self._device_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self._device_value()
        self.async_write_ha_state()


class DashboardUrlText(_PanelText):
    """Advanced/manual dashboard URL — fallback to the Dashboard select."""

    _key = "dashboard_url"
    _attr_translation_key = "custom_dashboard_url"
    _attr_name = "Custom dashboard URL"
    _attr_icon = "mdi:view-dashboard"
    _attr_entity_category = EntityCategory.CONFIG

    def _device_value(self) -> str | None:
        device = self.device
        return device.dashboard_url if device else None

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


class TaskSourceText(_PanelText):
    """Task list id / source URL feeding the panel's tasks screen."""

    _key = "task_source"
    _attr_translation_key = "custom_task_source"
    _attr_name = "Custom task source"
    _attr_icon = "mdi:format-list-checks"
    _attr_entity_category = EntityCategory.CONFIG

    def _device_value(self) -> str | None:
        device = self.device
        return device.task_source if device else None

    async def async_set_value(self, value: str) -> None:
        task_source = value.strip()
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, task_source=task_source
        )
        await async_push_task_snapshot(
            self.hass, self.coordinator.client, self._device_id, task_source, show=True
        )
        self._attr_native_value = task_source or None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class PhotoSourceText(_PanelText):
    """Photo feed id / source URL feeding the panel's photos screen."""

    _key = "photo_source"
    _attr_translation_key = "custom_photo_source"
    _attr_name = "Custom photo source"
    _attr_icon = "mdi:image-multiple"
    _attr_entity_category = EntityCategory.CONFIG

    def _device_value(self) -> str | None:
        device = self.device
        return device.photo_source if device else None

    async def async_set_value(self, value: str) -> None:
        photo_source = value.strip()
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, photo_source=photo_source
        )
        self._attr_native_value = photo_source or None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class SoundText(_PanelText):
    """Sound name/id/URL the panel's Play sound button dispatches.

    Setting it only persists the target (source of truth); the Play sound button
    (or the play_sound service) is what actually tells the panel to play it.
    """

    _key = "sound"
    _attr_translation_key = "custom_sound"
    _attr_name = "Custom sound"
    _attr_icon = "mdi:music-note"
    _attr_entity_category = EntityCategory.CONFIG

    def _device_value(self) -> str | None:
        device = self.device
        return device.sound if device else None

    async def async_set_value(self, value: str) -> None:
        sound = value.strip()
        await self.coordinator.client.async_set_sound(self._device_id, sound or None)
        self._attr_native_value = sound or None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
