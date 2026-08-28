"""Camera entity for OldPhoneKiosk panel MJPEG streams."""

from __future__ import annotations

import httpx
from homeassistant.components.camera import Camera
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
    """Set up dynamic camera entities for every paired panel."""
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices = set(coordinator.data or {})

    def _entities(device_ids: set[str]):
        return [PanelCamera(coordinator, device_id) for device_id in device_ids]

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PanelCamera(OldPhoneKioskEntity, Camera):
    """Proxy still-image camera backed by the panel's local MJPEG endpoint."""

    _attr_translation_key = "camera"
    _attr_name = "Camera"
    _attr_icon = "mdi:camera-wireless"

    def __init__(self, coordinator: OldPhoneKioskCoordinator, device_id: str) -> None:
        Camera.__init__(self)
        OldPhoneKioskEntity.__init__(self, coordinator, device_id)
        self._attr_unique_id = f"{device_id}_camera"

    @property
    def available(self) -> bool:
        device = self.device
        return super().available and device is not None and bool(device.video_url)

    async def stream_source(self) -> str | None:
        """Return the MJPEG URL HA/frontend can use when available."""
        device = self.device
        return device.video_url if device else None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Best-effort latest image by reading the first JPEG frame from MJPEG."""
        source = await self.stream_source()
        if not source:
            return None
        return await self.hass.async_add_executor_job(_fetch_first_jpeg, source)


def _fetch_first_jpeg(url: str) -> bytes | None:
    """Read one JPEG frame from a multipart MJPEG response."""
    try:
        with httpx.stream("GET", url, timeout=5.0) as response:
            response.raise_for_status()
            buffer = b""
            for chunk in response.iter_bytes():
                buffer += chunk
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9", start + 2)
                if start >= 0 and end > start:
                    return buffer[start : end + 2]
                if len(buffer) > 2_000_000:
                    buffer = buffer[-200_000:]
    except Exception:  # noqa: BLE001 - unavailable camera should not spam entity setup
        return None
    return None
