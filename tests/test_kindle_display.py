from __future__ import annotations

from opk_kindle_display import KindleSnapshot, render_kindle_html


def test_render_kindle_html_is_read_only_eink_page():
    html = render_kindle_html(
        KindleSnapshot(
            name="Kitchen Kindle",
            screen="tasks",
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


def test_render_kindle_html_escapes_user_controlled_values():
    html = render_kindle_html(
        KindleSnapshot(
            name='<script>alert("x")</script>',
            tasks=[{"summary": "Milk <b>now</b>"}],
        )
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Milk &lt;b&gt;now&lt;/b&gt;" in html


def test_render_kindle_html_includes_safe_action_links_for_controls_and_todos():
    html = render_kindle_html(
        KindleSnapshot(
            name="Kitchen Kindle",
            tasks=[
                {
                    "uid": "task-1",
                    "summary": "Buy milk",
                    "complete_url": "/api/oldphonekiosk/web-display/dev-1/action?token=s&action=complete_task&uid=task-1",
                }
            ],
            actions=[
                {
                    "label": "Hallway light",
                    "state": "off",
                    "url": "/api/oldphonekiosk/web-display/dev-1/action?token=s&action=toggle&entity_id=light.hallway",
                }
            ],
        )
    )

    assert "Quick actions" in html
    assert "Hallway light" in html
    assert "Toggle" in html
    assert "Done" in html
    assert "complete_task" in html
    assert "light.hallway" in html
