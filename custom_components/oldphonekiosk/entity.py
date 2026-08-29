"""Shared base entity for OldPhoneKiosk panels."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .native_client import PanelDeviceData
from .const import DOMAIN, MANUFACTURER
from .coordinator import OldPhoneKioskCoordinator


class OldPhoneKioskEntity(CoordinatorEntity[OldPhoneKioskCoordinator]):
    """Base entity bound to one panel device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OldPhoneKioskCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device(self) -> PanelDeviceData | None:
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        return super().available and self.device is not None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        # Expose the panel device id (for revoke_panel) plus media/camera/intercom
        # so the Lovelace card can read them from any panel entity.
        device = self.device
        return {
            "bridge_device_id": self._device_id,
            "video_url": device.video_url if device else None,
            "dashboard_url": device.dashboard_url if device else None,
            "task_source": device.task_source if device else None,
            "photo_source": device.photo_source if device else None,
            "sound": device.sound if device else None,
            "camera_mode": device.camera_mode if device else None,
            "intercom": device.intercom if device else None,
            "stream": device.stream if device else None,
        }

    @property
    def device_info(self) -> DeviceInfo:
        device = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            name=device.name if device else self._device_id,
            model=device.model if device else None,
            suggested_area=device.room if device else None,
            sw_version=device.app_version if device else None,
        )
