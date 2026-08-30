"""HA harness test for the oldphonekiosk.revoke_panel service (full entry setup)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
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
                battery_state="charging",
                brightness=0.35,
                screen="home",
                camera_mode="off",
                intercom="idle",
                stream="idle",
                video_url=None,
                dashboard_url=None,
                app_version="0.1.0",
                last_seen=datetime.now(UTC),
            )
        ]
        self.media_calls: list[dict] = []
        self.stream_calls: list[tuple] = []
        self.ui_calls: list[dict] = []
        self.sound_calls: list[tuple] = []
        self.action_calls: list[tuple] = []
        self.command_calls: list[tuple] = []

    async def async_get_devices(self) -> list[PanelDeviceData]:
        return list(self._devices)

    async def async_set_media(self, device_id, *, video_url=..., camera_mode=None):
        self.media_calls.append(
            {"device_id": device_id, "video_url": video_url, "camera_mode": camera_mode}
        )
        return self._devices[0]

    async def async_send_command(self, device_id, command, params=None):
        self.command_calls.append((device_id, command, params))
        return {"id": "c", "status": "completed", "success": True}

    async def async_delete_device(self, device_id: str) -> None:
        self.deleted.append(device_id)
        self._devices = [d for d in self._devices if d.device_id != device_id]

    async def async_create_claim(self, name: str, room: str | None = None):
        from custom_components.oldphonekiosk.api import PanelClaim

        self.provisioned = (name, room)
        self._devices.append(
            PanelDeviceData(
                device_id="dev-new",
                name=name,
                room=room,
                model=None,
                online=False,
                battery=None,
                battery_state=None,
                brightness=None,
                screen=None,
                camera_mode="off",
                intercom="idle",
                stream="idle",
                video_url=None,
                dashboard_url=None,
                app_version=None,
                last_seen=None,
            )
        )
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

    async def async_set_panel_ui(self, device_id, **kwargs):
        self.ui_calls.append({"device_id": device_id, **kwargs})
        current = self._devices[0]
        changes = {}
        for key in (
            "dashboard_url",
            "task_source",
            "photo_source",
            "enabled_screens",
            "show_bottom_menu",
            "keep_screen_awake",
            "show_connection_banner",
            "dim_after_seconds",
            "sleep_after_seconds",
            "task_refresh_seconds",
        ):
            if kwargs.get(key) is not None:
                value = kwargs.get(key)
                changes[key] = (
                    ",".join(value)
                    if key == "enabled_screens" and isinstance(value, list)
                    else value
                )
        self._devices[0] = replace(current, **changes)
        return self._devices[0]

    async def async_set_sound(self, device_id, sound):
        self.sound_calls.append((device_id, sound))
        self._devices[0] = replace(self._devices[0], sound=sound)
        return self._devices[0]

    async def async_beep(self, device_id):
        self.action_calls.append(("beep", device_id))
        return {"id": "c", "status": "completed", "success": True}

    async def async_play_sound(self, device_id, *, sound=None, url=None):
        self.action_calls.append(("play_sound", device_id, sound, url))
        return {"id": "c", "status": "completed", "success": True}

    async def async_start_intercom(
        self, device_id, *, mode=None, audio_url=None, stream_url=None
    ):
        self.action_calls.append(
            ("start_intercom", device_id, mode, audio_url, stream_url)
        )
        return {"id": "c", "status": "completed", "success": True}

    async def async_stop_intercom(self, device_id):
        self.action_calls.append(("stop_intercom", device_id))
        return {"id": "c", "status": "completed", "success": True}

    async def close(self) -> None:
        pass


async def test_revoke_panel_service(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)

    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
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


async def test_pair_new_panel_service_returns_pairing_code(hass: HomeAssistant):
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
    # The service returns a one-time pairing code (the claim token), no QR/payload.
    assert response["pairing_code"] == "claim-abc"
    assert "payload" not in response
    assert "qr_svg_data_uri" not in response


async def test_pairing_button_creates_code_notification(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("button.oldphonekiosk_generate_pairing_code")
    assert state is not None

    with patch(
        "custom_components.oldphonekiosk.services.persistent_notification.async_create"
    ) as create_notification:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.oldphonekiosk_generate_pairing_code"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert fake.provisioned == ("OldPhoneKiosk Panel", None)
    create_notification.assert_called_once()
    assert (
        create_notification.call_args.kwargs["title"] == "OldPhoneKiosk — pair a panel"
    )
    assert (
        create_notification.call_args.kwargs["notification_id"]
        == f"{DOMAIN}_pair_dev-new"
    )

    assert hass.states.get("binary_sensor.oldphonekiosk_panel_online") is not None
    assert hass.states.get("select.oldphonekiosk_panel_screen") is not None
    assert hass.states.get("button.oldphonekiosk_panel_wake") is not None
    assert hass.states.get("button.oldphonekiosk_panel_sleep") is not None
    assert hass.states.get("button.kitchen_start_front_camera") is not None
    assert hass.states.get("button.kitchen_start_back_camera") is not None
    assert hass.states.get("button.kitchen_stop_camera") is not None
    assert hass.states.get("button.kitchen_beep") is not None
    assert hass.states.get("button.kitchen_play_sound") is not None
    assert hass.states.get("button.kitchen_start_intercom") is not None
    assert hass.states.get("button.kitchen_stop_intercom") is not None
    assert hass.states.get("text.kitchen_custom_dashboard_url") is not None
    assert hass.states.get("text.kitchen_custom_task_source") is not None
    assert hass.states.get("text.kitchen_custom_photo_source") is not None
    assert hass.states.get("text.kitchen_custom_sound") is not None
    # HA-first source pickers: primary UX is the select controls on the device page.
    assert hass.states.get("select.kitchen_dashboard") is not None
    assert hass.states.get("select.kitchen_visible_screens") is not None
    assert hass.states.get("select.kitchen_task_list") is not None
    assert hass.states.get("select.kitchen_sound") is not None
    assert hass.states.get("select.kitchen_photo_source") is not None
    assert hass.states.get("switch.kitchen_bottom_menu") is not None
    assert hass.states.get("switch.kitchen_keep_screen_awake_in_app") is not None
    assert hass.states.get("switch.kitchen_connection_banner") is not None
    assert hass.states.get("switch.kitchen_photo_time_overlay") is not None
    assert hass.states.get("switch.kitchen_photo_location_overlay") is not None
    assert hass.states.get("number.kitchen_screen_brightness") is not None
    assert hass.states.get("number.kitchen_device_volume") is not None
    assert hass.states.get("number.kitchen_dim_after") is not None
    assert hass.states.get("number.kitchen_sleep_screen_after") is not None
    assert hass.states.get("number.kitchen_refresh_tasks_every") is not None
    assert hass.states.get("camera.kitchen_camera") is not None
    assert hass.states.get("sensor.oldphonekiosk_panel_battery") is not None
    charging = hass.states.get("binary_sensor.kitchen_charging")
    assert charging is not None
    assert charging.state == "on"
    assert charging.attributes["battery_state"] == "charging"


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


async def test_device_page_controls_start_camera_and_set_dashboard_url(
    hass: HomeAssistant,
):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.kitchen_start_front_camera"},
        blocking=True,
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": "text.kitchen_custom_dashboard_url",
            "value": "http://homeassistant.local:8123/lovelace/kitchen",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert fake.stream_calls == [("start", "dev-1", "front")]
    assert fake.ui_calls[-1] == {
        "device_id": "dev-1",
        "default_screen": "dashboard",
        "dashboard_url": "http://homeassistant.local:8123/lovelace/kitchen",
    }
    assert (
        hass.states.get("text.kitchen_custom_dashboard_url").state
        == "http://homeassistant.local:8123/lovelace/kitchen"
    )


async def test_start_back_camera_button(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.kitchen_start_back_camera"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert fake.stream_calls == [("start", "dev-1", "back")]


async def test_task_photo_sound_text_and_action_buttons(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Custom (advanced) text sources push configure_ui (tasks/photos) and persist sound.
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.kitchen_custom_task_source", "value": "todo.kitchen"},
        blocking=True,
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.kitchen_custom_photo_source", "value": "album.family"},
        blocking=True,
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.kitchen_custom_sound", "value": "1007"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert fake.ui_calls[-2]["task_source"] == "todo.kitchen"
    assert fake.ui_calls[-1]["photo_source"] == "album.family"
    assert fake.sound_calls == [("dev-1", "1007")]
    assert hass.states.get("text.kitchen_custom_task_source").state == "todo.kitchen"
    assert hass.states.get("text.kitchen_custom_photo_source").state == "album.family"
    assert hass.states.get("text.kitchen_custom_sound").state == "1007"

    # Action buttons dispatch beep / play_sound / start+stop intercom.
    for entity in (
        "button.kitchen_beep",
        "button.kitchen_play_sound",
        "button.kitchen_start_intercom",
        "button.kitchen_stop_intercom",
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity}, blocking=True
        )
    await hass.async_block_till_done()

    kinds = [call[0] for call in fake.action_calls]
    assert kinds == ["beep", "play_sound", "start_intercom", "stop_intercom"]


async def test_source_selects_apply_from_ha_resources(hass: HomeAssistant):
    """HA-first pickers: dashboard/task-list/sound selects apply immediately."""
    hass.config.internal_url = "http://homeassistant.local:8123"
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # A to-do list is offered to the task-list select as a ready pick.
    hass.states.async_set("todo.kitchen", "0")
    await hass.async_block_till_done()

    # Dashboard select pushes the dashboard screen + URL (no manual string typing).
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kitchen_dashboard", "option": "/lovelace"},
        blocking=True,
    )
    # Task-list select stores the todo entity id chosen from HA states.
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kitchen_task_list", "option": "todo.kitchen"},
        blocking=True,
    )
    # Sound select stores a system-sound id preset.
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kitchen_sound", "option": "1013"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert {
        "device_id": "dev-1",
        "default_screen": "dashboard",
        "dashboard_url": "http://homeassistant.local:8123/lovelace",
    } in fake.ui_calls
    assert any(c.get("task_source") == "todo.kitchen" for c in fake.ui_calls)
    assert (
        "dev-1",
        "configure_tasks",
        {
            "entity_id": "todo.kitchen",
            "source": "todo.kitchen",
            "items": "[]",
            "show": "true",
        },
    ) in fake.command_calls
    assert ("dev-1", "show_tasks", None) in fake.command_calls
    assert fake.sound_calls == [("dev-1", "1013")]

    assert (
        hass.states.get("select.kitchen_dashboard").state
        == "http://homeassistant.local:8123/lovelace"
    )
    assert hass.states.get("select.kitchen_task_list").state == "todo.kitchen"
    assert hass.states.get("select.kitchen_sound").state == "1013"
    assert (
        "todo.kitchen"
        in hass.states.get("select.kitchen_task_list").attributes["options"]
    )

    # Photo-source select must include cameras that appear after OldPhoneKiosk setup.
    hass.states.async_set(
        "camera.google_photos_picker_tkowalski_iseno_net_none",
        "idle",
        {"media_count": 3},
    )
    await hass.async_block_till_done()
    assert (
        "camera.google_photos_picker_tkowalski_iseno_net_none"
        in hass.states.get("select.kitchen_photo_source").attributes["options"]
    )


async def test_device_page_navigation_and_device_level_controls(hass: HomeAssistant):
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.kitchen_bottom_menu"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.kitchen_keep_screen_awake_in_app"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.kitchen_connection_banner"},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kitchen_visible_screens", "option": "tasks,dashboard"},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.kitchen_screen_brightness", "value": 42},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.kitchen_device_volume", "value": 35},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.kitchen_dim_after", "value": 45},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.kitchen_sleep_screen_after", "value": 120},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.kitchen_refresh_tasks_every", "value": 30},
        blocking=True,
    )

    assert any(c.get("show_bottom_menu") is False for c in fake.ui_calls)
    assert any(c.get("keep_screen_awake") is False for c in fake.ui_calls)
    assert any(c.get("show_connection_banner") is False for c in fake.ui_calls)
    assert any(
        c.get("enabled_screens") == ["tasks", "dashboard"] for c in fake.ui_calls
    )
    assert any(c.get("dim_after_seconds") == 45 for c in fake.ui_calls)
    assert any(c.get("sleep_after_seconds") == 120 for c in fake.ui_calls)
    assert any(c.get("task_refresh_seconds") == 30 for c in fake.ui_calls)
    assert (
        "dev-1",
        "set_brightness",
        {"level": "0.420", "percent": "42"},
    ) in fake.command_calls
    assert (
        "dev-1",
        "set_volume",
        {"level": "0.350", "percent": "35"},
    ) in fake.command_calls


async def test_dashboard_select_offers_lovelace_view_tabs(hass: HomeAssistant):
    """Dashboard picker includes concrete Lovelace view/tab URLs."""
    hass.config.internal_url = "http://homeassistant.local:8123"

    class _FakeLovelaceDashboard:
        async def async_load(self, force):
            return {
                "views": [
                    {"title": "ADA", "path": "ada"},
                    {"title": "TOMAS", "path": "tomas"},
                    {"title": "OSCAR", "path": "oscar"},
                    {"title": "Kitchen", "path": "dashboard"},
                ]
            }

    class _FakeOscarDashboard:
        async def async_load(self, force):
            return {
                "views": [{"title": "Overview"}, {"title": "Rooms"}, {"title": "Kids"}]
            }

    hass.data["lovelace"] = {
        "dashboards": {
            None: _FakeLovelaceDashboard(),
            "dashboard-oscar": _FakeOscarDashboard(),
        }
    }

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("select.kitchen_dashboard")
    assert state is not None
    assert "/lovelace" not in state.attributes["options"]
    assert "/lovelace/0" not in state.attributes["options"]
    assert "/lovelace/ada" in state.attributes["options"]
    assert "/lovelace/tomas" in state.attributes["options"]
    assert "/lovelace/oscar" in state.attributes["options"]
    assert "/lovelace/dashboard" in state.attributes["options"]
    assert "/dashboard-oscar/0" in state.attributes["options"]
    assert "/dashboard-oscar/2" in state.attributes["options"]
    assert "/lovelace/dashboard-oscar/2" not in state.attributes["options"]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kitchen_dashboard", "option": "/dashboard-oscar/2"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert {
        "device_id": "dev-1",
        "default_screen": "dashboard",
        "dashboard_url": "http://homeassistant.local:8123/dashboard-oscar/2",
    } in fake.ui_calls


async def test_dashboard_select_does_not_keep_stale_lovelace_home_when_views_exist(
    hass: HomeAssistant,
):
    """A stale /lovelace/0 selection should not remain the picker option when views exist."""
    hass.config.internal_url = "http://homeassistant.local:8123"

    class _FakeLovelaceDashboard:
        async def async_load(self, force):
            return {"views": [{"title": "Tomas", "path": "tomas"}]}

    hass.data["lovelace"] = {"dashboards": {None: _FakeLovelaceDashboard()}}
    fake = _FakeClient()
    fake._devices[0] = replace(
        fake._devices[0], dashboard_url="http://homeassistant.local:8123/lovelace/0"
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("select.kitchen_dashboard")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["options"] == ["/lovelace/tomas"]


async def test_play_sound_button_resolves_media_source_sound(
    hass: HomeAssistant, monkeypatch
):
    """A HA media-source sound selection is resolved to a phone-playable URL."""
    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async def _resolve(_hass, value):
        assert value == "media-source://media_source/local/chime.mp3"
        return "http://homeassistant.local:8123/media/local/chime.mp3"

    monkeypatch.setattr(
        "custom_components.oldphonekiosk.button.async_resolve_media_source_url",
        _resolve,
    )

    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": "text.kitchen_custom_sound",
            "value": "media-source://media_source/local/chime.mp3",
        },
        blocking=True,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.kitchen_play_sound"}, blocking=True
    )
    await hass.async_block_till_done()

    assert fake.sound_calls == [
        ("dev-1", "media-source://media_source/local/chime.mp3")
    ]
    assert fake.action_calls[-1] == (
        "play_sound",
        "dev-1",
        None,
        "http://homeassistant.local:8123/media/local/chime.mp3",
    )


async def test_play_sound_and_intercom_services(hass: HomeAssistant):
    from custom_components.oldphonekiosk.const import (
        SERVICE_BEEP,
        SERVICE_PLAY_SOUND,
        SERVICE_START_INTERCOM,
        SERVICE_STOP_INTERCOM,
    )

    fake = _FakeClient()
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BRIDGE_URL: "http://x", CONF_API_KEY: "k"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.oldphonekiosk.BridgeClient", return_value=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_BEEP)
    assert hass.services.has_service(DOMAIN, SERVICE_PLAY_SOUND)
    assert hass.services.has_service(DOMAIN, SERVICE_START_INTERCOM)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_INTERCOM)

    await hass.services.async_call(
        DOMAIN, SERVICE_BEEP, {ATTR_DEVICE_ID: "dev-1"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {ATTR_DEVICE_ID: "dev-1", "url": "http://ha/local/chime.mp3"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_INTERCOM,
        {ATTR_DEVICE_ID: "dev-1", "mode": "talk"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_INTERCOM, {ATTR_DEVICE_ID: "dev-1"}, blocking=True
    )
    await hass.async_block_till_done()

    assert fake.action_calls[0] == ("beep", "dev-1")
    assert fake.action_calls[1] == (
        "play_sound",
        "dev-1",
        None,
        "http://ha/local/chime.mp3",
    )
    assert fake.action_calls[2] == ("start_intercom", "dev-1", "talk", None, None)
    assert fake.action_calls[3] == ("stop_intercom", "dev-1")
