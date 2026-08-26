"""DataUpdateCoordinator polling the Bridge for panel devices."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BridgeClient, BridgeError, PanelDeviceData
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OldPhoneKioskCoordinator(DataUpdateCoordinator[dict[str, PanelDeviceData]]):
    """Fetch all panels from the Bridge and index them by device_id."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: BridgeClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, PanelDeviceData]:
        try:
            devices = await self.client.async_get_devices()
        except BridgeError as err:
            raise UpdateFailed(f"Bridge error: {err}") from err
        return {d.device_id: d for d in devices}
