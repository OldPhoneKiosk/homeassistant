"""Sensors for OldPhoneKiosk panels: battery, last_seen, app_version."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PanelDeviceData
from .const import DOMAIN
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity


@dataclass(frozen=True, kw_only=True)
class PanelSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PanelDeviceData], int | str | datetime | None]


SENSORS: tuple[PanelSensorDescription, ...] = (
    PanelSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.battery,
    ),
    PanelSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.last_seen,
    ),
    PanelSensorDescription(
        key="app_version",
        translation_key="app_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.app_version,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PanelSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


class PanelSensor(OldPhoneKioskEntity, SensorEntity):
    entity_description: PanelSensorDescription

    def __init__(self, coordinator, device_id, description) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_name = description.key.replace("_", " ").title()

    @property
    def native_value(self):
        device = self.device
        if device is None:
            return None
        return self.entity_description.value_fn(device)
