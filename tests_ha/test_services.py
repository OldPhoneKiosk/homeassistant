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
                camera_mode="off",
                intercom="idle",
                stream="idle",
                video_url=None,
                app_version="0.1.0",
                last_seen=datetime.now(timezone.utc),
            )
        ]
        self.media_calls: list[dict] = []
        self.stream_calls: list[tuple] = []

    async def async_get_devices(self) -> list[PanelDeviceData]:
        return list(self._devices)

    async def async_set_media(self, device_id, *, video_url=..., camera_mode=None):
        self.media_calls.append(
            {"device_id": device_id, "video_url": video_url, "camera_mode": camera_mode}
        )
        return self._devices[0]

    async def async_delete_device(self, device_id: str) -> None:
        self.deleted.append(device_id)
        self._devices = [d for d in self._devices if d.device_id != device_id]

    async def async_create_claim(self, name: str, room: str | None = None):
        from custom_components.oldphonekiosk.api import PanelClaim

        self.provisioned = (name, room)
        return PanelClaim(
            claim_token="claim-abc",
            device_id="dev-new",
            expires_at="2026-08-26T14:00:00Z",
        )

    async def async_start_stream(self, device_id, camera_mode=None):
        self.stream_calls.append(("start", device_id, camera_mode))
        return self._devices[0]

    async def async_stop_stream(self, device_id):
        self.stream_calls.append(("stop", device_id, None))
        return self._devices[0]

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
    assert payload["type"] == "claim"
    assert payload["bridge_url"] == "http://bridge.local:8788"
    assert payload["claim_token"] == "claim-abc"
    assert payload["name"] == "Kitchen"
    # The QR must NOT carry the device secret.
    assert "device_secret" not in payload
    # QR image is included when the qrcode lib is available (SVG data URI).
    if response.get("qr_svg_data_uri") is not None:
        assert response["qr_svg_data_uri"].startswith("data:image/svg+xml;base64,")


async def test_set_media_service(hass: HomeAssistant):
    from custom_components.oldphonekiosk.const import (
        ATTR_CAMERA_MODE,
        ATTR_VIDEO_URL,
        SERVICE_SET_MEDIA,
    )

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_SET_MEDIA)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEDIA,
        {
            ATTR_DEVICE_ID: "dev-1",
            ATTR_VIDEO_URL: "http://go2rtc/stream.html?src=panel",
            ATTR_CAMERA_MODE: "front",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(fake.media_calls) == 1
    assert fake.media_calls[0]["device_id"] == "dev-1"
    assert fake.media_calls[0]["video_url"] == "http://go2rtc/stream.html?src=panel"
    assert fake.media_calls[0]["camera_mode"] == "front"


async def test_start_and_stop_stream_services(hass: HomeAssistant):
    from custom_components.oldphonekiosk.const import (
        ATTR_CAMERA_MODE,
        SERVICE_START_STREAM,
        SERVICE_STOP_STREAM,
    )

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START_STREAM)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_STREAM)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_STREAM,
        {ATTR_DEVICE_ID: "dev-1", ATTR_CAMERA_MODE: "front"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_STREAM, {ATTR_DEVICE_ID: "dev-1"}, blocking=True
    )
    await hass.async_block_till_done()

    assert fake.stream_calls == [
        ("start", "dev-1", "front"),
        ("stop", "dev-1", None),
    ]
