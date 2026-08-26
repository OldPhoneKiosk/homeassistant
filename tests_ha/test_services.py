"""HA harness test for the oldphonekiosk.revoke_panel service (full entry setup)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oldphonekiosk.api import PanelDeviceData
from custom_components.oldphonekiosk.const import (
    ATTR_DEVICE_ID,
    ATTR_NAME,
    ATTR_ROOM,
    CONF_API_KEY,
    CONF_BRIDGE_URL,
    DOMAIN,
    SERVICE_PAIR_NEW_PANEL,
    SERVICE_REVOKE_PANEL,
)


class _FakeClient:
    """Fake BridgeClient recording deletes and dropping the device from listings."""

    def __init__(self, *args, **kwargs) -> None:
        self.deleted: list[str] = []
        self._devices = [
            PanelDeviceData(
                device_id="dev-1",
                name="Kitchen",
                room="Kitchen",
                model="iPhone",
                online=True,
                battery=80,
                brightness=0.35,
                screen="home",
                app_version="0.1.0",
                last_seen=datetime.now(timezone.utc),
            )
        ]

    async def async_get_devices(self) -> list[PanelDeviceData]:
        return list(self._devices)

    async def async_delete_device(self, device_id: str) -> None:
        self.deleted.append(device_id)
        self._devices = [d for d in self._devices if d.device_id != device_id]

    async def async_provision_panel(self, name: str, room: str | None = None):
        from custom_components.oldphonekiosk.api import ProvisionedPanel

        self.provisioned = (name, room)
        return ProvisionedPanel(device_id="dev-new", device_secret="new-secret")

    async def close(self) -> None:
        pass


async def test_revoke_panel_service(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.oldphonekiosk.BridgeClient", return_value=fake
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Service registered and the HA device exists for the Bridge device id.
    assert hass.services.has_service(DOMAIN, SERVICE_REVOKE_PANEL)
    registry = dr.async_get(hass)
    assert registry.async_get_device(identifiers={(DOMAIN, "dev-1")}) is not None

    # Revoke: calls Bridge delete and removes the HA device.
    await hass.services.async_call(
        DOMAIN, SERVICE_REVOKE_PANEL, {ATTR_DEVICE_ID: "dev-1"}, blocking=True
    )
    await hass.async_block_till_done()

    assert fake.deleted == ["dev-1"]
    assert registry.async_get_device(identifiers={(DOMAIN, "dev-1")}) is None


async def test_revoke_panel_unknown_device_raises(hass: HomeAssistant):
    from homeassistant.exceptions import ServiceValidationError

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    import pytest

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_REVOKE_PANEL, {ATTR_DEVICE_ID: "nope"}, blocking=True
        )


async def test_pair_new_panel_service_returns_payload(hass: HomeAssistant):
    import json

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BRIDGE_URL: "http://bridge.local:8788", CONF_API_KEY: "k"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_PAIR_NEW_PANEL)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_PAIR_NEW_PANEL,
        {ATTR_NAME: "Kitchen", ATTR_ROOM: "Kitchen"},
        blocking=True,
        return_response=True,
    )

    assert fake.provisioned == ("Kitchen", "Kitchen")
    assert response["device_id"] == "dev-new"
    payload = json.loads(response["payload"])
    assert payload["version"] == 1
    assert payload["bridge_url"] == "http://bridge.local:8788"
    assert payload["device_id"] == "dev-new"
    assert payload["device_secret"] == "new-secret"
    assert payload["name"] == "Kitchen"
    # QR image is included when the qrcode lib is available (SVG data URI).
    if response.get("qr_svg_data_uri") is not None:
        assert response["qr_svg_data_uri"].startswith("data:image/svg+xml;base64,")
