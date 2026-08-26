"""HA harness test for the coordinator."""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oldphonekiosk.api import PanelDeviceData
from custom_components.oldphonekiosk.const import (
    CONF_API_KEY,
    CONF_BRIDGE_URL,
    DOMAIN,
)
from custom_components.oldphonekiosk.coordinator import OldPhoneKioskCoordinator


class _FakeClient:
    def __init__(self, devices: list[PanelDeviceData]) -> None:
        self._devices = devices

    async def async_get_devices(self) -> list[PanelDeviceData]:
        return list(self._devices)

    async def close(self) -> None:
        pass


def _device(device_id: str, name: str) -> PanelDeviceData:
    return PanelDeviceData(
        device_id=device_id,
        name=name,
        room="Kitchen",
        model="iPhone SE",
        online=True,
        battery=80,
        brightness=0.35,
        screen="home",
        camera_mode="off",
        intercom="idle",
        stream="idle",
        video_url=None,
        app_version="0.1.0",
        last_seen=datetime.now(timezone.utc),
    )


async def test_coordinator_indexes_devices_by_id(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)

    client = _FakeClient([_device("dev-1", "Kitchen"), _device("dev-2", "Hallway")])
    coordinator = OldPhoneKioskCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    assert set(coordinator.data) == {"dev-1", "dev-2"}
    assert coordinator.data["dev-1"].name == "Kitchen"
    assert coordinator.data["dev-2"].online is True
