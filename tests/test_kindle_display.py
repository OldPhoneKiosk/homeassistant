from __future__ import annotations

from opk_kindle_display import KindleSnapshot, render_kindle_html
from opk_models import DeviceCapabilities, PanelScreen
from opk_registry import Registry
from opk_store import DeviceStore


def test_render_kindle_html_is_read_only_eink_page():
    html = render_kindle_html(
        KindleSnapshot(
            name="Kitchen Kindle",
            screen=PanelScreen.TASKS,
            dashboard_url="/lovelace/kitchen",
            tasks=[{"summary": "Buy milk", "due": "today"}],
            calendar=[{"title": "School pickup", "start": "2026-09-02T15:30:00+02:00"}],
            refresh_seconds=90,
        )
    )

    assert "<title>Kitchen Kindle — OldPhoneKiosk</title>" in html
    assert '<meta http-equiv="refresh" content="90">' in html
    assert "Buy milk" in html
    assert "School pickup" in html
    assert "Camera" not in html
    assert "microphone" not in html.lower()
    assert "background:#fff" in html


def test_registry_create_web_display_provisions_kindle_without_pairing_claim():
    store = DeviceStore(":memory:")
    registry = Registry(store)

    created = registry.create_web_display(name="Kitchen Kindle", room="Kitchen")

    device = registry.get_device(created.device_id)
    assert device.name == "Kitchen Kindle"
    assert device.room == "Kitchen"
    assert device.model == "Kindle Web Display"
    assert device.capabilities == DeviceCapabilities(camera=False, microphone=False, photos=False, tasks=True, calendar=True)
    assert device.state.screen == PanelScreen.DASHBOARD
    assert registry.verify_secret(created.device_id, created.device_secret).device_id == created.device_id
    assert store.load_devices()[0].device_id == created.device_id
    assert store.expired_claims(device.created_at) == []
