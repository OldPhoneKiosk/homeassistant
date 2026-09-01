"""Tests for device-facing configure_ui payload helpers."""

from __future__ import annotations

from types import SimpleNamespace

from opk_ui_config import (
    build_configure_ui_params,
    build_configure_ui_params_from_media,
    build_media_config_kwargs,
)


def test_build_configure_ui_params_formats_values_for_device_command():
    assert build_configure_ui_params(
        default_screen="calendar",
        enabled_screens=["tasks", "dashboard"],
        show_bottom_menu=False,
        keep_screen_awake=True,
        show_connection_banner=False,
        show_photo_time_overlay=True,
        camera_rotate_180=True,
        dim_after_seconds=45.9,
        sleep_after_seconds=-12,
        task_refresh_seconds=120,
        dashboard_url=None,
        task_source="todo.kitchen",
        photo_source="",
        calendar_sources=["calendar.family", "calendar.school"],
        calendar_view="week",
    ) == {
        "default_screen": "calendar",
        "enabled_screens": "tasks,dashboard",
        "show_bottom_menu": "false",
        "keep_screen_awake": "true",
        "show_connection_banner": "false",
        "show_photo_time_overlay": "true",
        "camera_rotate_180": "true",
        "dim_after_seconds": "45",
        "sleep_after_seconds": "0",
        "task_refresh_seconds": "120",
        "dashboard_url": "",
        "task_source": "todo.kitchen",
        "photo_source": "",
        "calendar_sources": "calendar.family,calendar.school",
        "calendar_view": "week",
    }


def test_build_configure_ui_params_from_media_skips_empty_values_on_reconnect():
    media = SimpleNamespace(
        dashboard_url="",
        task_source="todo.kitchen",
        photo_source=None,
        calendar_sources="calendar.family",
        calendar_view="month",
        enabled_screens="tasks,dashboard",
        show_bottom_menu=False,
        keep_screen_awake=None,
        show_connection_banner=True,
        show_photo_time_overlay=None,
        camera_rotate_180=True,
        dim_after_seconds=0,
        sleep_after_seconds=None,
        task_refresh_seconds=300,
    )

    assert build_configure_ui_params_from_media(media) == {
        "task_source": "todo.kitchen",
        "calendar_sources": "calendar.family",
        "calendar_view": "month",
        "enabled_screens": "tasks,dashboard",
        "show_bottom_menu": "false",
        "show_connection_banner": "true",
        "camera_rotate_180": "true",
        "dim_after_seconds": "0",
        "task_refresh_seconds": "300",
    }


def test_build_media_config_kwargs_persists_enabled_screens_as_csv():
    assert build_media_config_kwargs(
        {
            "enabled_screens": ["photos", "tasks"],
            "show_bottom_menu": False,
            "dashboard_url": "http://ha.local/lovelace",
            "default_screen": "dashboard",
        }
    ) == {
        "enabled_screens": "photos,tasks",
        "show_bottom_menu": False,
        "dashboard_url": "http://ha.local/lovelace",
    }
