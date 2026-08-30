from __future__ import annotations

from custom_components.oldphonekiosk.tasks import _task_item_dict


def test_task_item_dict_includes_modal_details_json():
    payload = _task_item_dict(
        {
            "uid": "task-1",
            "summary": "Buy milk",
            "status": "needs_action",
            "due": "2026-08-31",
            "description": "Two bottles",
            "assignee": "Tomasz",
            "priority": "High",
        }
    )

    assert payload == {
        "uid": "task-1",
        "summary": "Buy milk",
        "status": "needs_action",
        "due": "2026-08-31",
        "description": "Two bottles",
        "assignee": "Tomasz",
        "details": {"assignee": "Tomasz", "priority": "High"},
    }
