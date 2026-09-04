from __future__ import annotations

from opk_kindle_actions import (
    build_complete_task_url,
    build_entity_action,
    build_toggle_url,
)


def test_build_toggle_url_allows_only_safe_toggle_domains():
    assert build_toggle_url("dev-1", "secret", "light.hallway") == (
        "/api/oldphonekiosk/web-display/dev-1/action"
        "?token=secret&action=toggle&entity_id=light.hallway"
    )
    assert build_toggle_url("dev-1", "secret", "switch.kindle_charger") is not None
    assert build_toggle_url("dev-1", "secret", "input_boolean.guest_mode") is not None
    assert build_toggle_url("dev-1", "secret", "sensor.temperature") is None
    assert build_toggle_url("dev-1", "secret", "light.bad/name") is None


def test_build_complete_task_url_quotes_source_and_uid():
    assert build_complete_task_url("dev-1", "secret", "todo.kitchen", "milk & bread") == (
        "/api/oldphonekiosk/web-display/dev-1/action"
        "?token=secret&action=complete_task&source=todo.kitchen&uid=milk+%26+bread"
    )


def test_build_entity_action_uses_friendly_name_and_current_state():
    state = type(
        "State",
        (),
        {"state": "off", "attributes": {"friendly_name": "Hallway light"}},
    )()

    assert build_entity_action("dev-1", "secret", "light.hallway", state) == {
        "entity_id": "light.hallway",
        "label": "Hallway light",
        "state": "off",
        "url": "/api/oldphonekiosk/web-display/dev-1/action?token=secret&action=toggle&entity_id=light.hallway",
    }
