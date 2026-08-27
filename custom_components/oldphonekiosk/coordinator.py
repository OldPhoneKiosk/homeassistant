"""DataUpdateCoordinator reading panel devices from the in-process backend."""

from __future__ import annotations

import inspect
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BridgeError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .native_client import NativeOldPhoneKioskClient, PanelDeviceData

_LOGGER = logging.getLogger(__name__)


class OldPhoneKioskCoordinator(DataUpdateCoordinator[dict[str, PanelDeviceData]]):
    """Fetch all panels from the backend and index them by device_id."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: NativeOldPhoneKioskClient
    ) -> None:
        kwargs = {}
        if "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters:
            kwargs["config_entry"] = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            **kwargs,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, PanelDeviceData]:
        try:
            devices = await self.client.async_get_devices()
        except BridgeError as err:
            raise UpdateFailed(f"Bridge error: {err}") from err
        return {d.device_id: d for d in devices}
