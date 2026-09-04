"""Helpers for HA-owned panel UI configuration payloads.

The iOS app treats Home Assistant as the source of truth for screen/source/UI
settings. Keep conversion into device `configure_ui` params centralized so
services, reconnect replay, and the native in-process client cannot drift.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

UI_STRING_FIELDS = (
    "default_screen",
    "dashboard_url",
    "task_source",
    "photo_source",
    "calendar_sources",
    "calendar_view",
    "kindle_actions",
)
UI_BOOL_FIELDS = (
    "show_bottom_menu",
    "keep_screen_awake",
    "show_connection_banner",
    "show_photo_time_overlay",
    "camera_rotate_180",
)
UI_SECONDS_FIELDS = (
    "dim_after_seconds",
    "sleep_after_seconds",
    "task_refresh_seconds",
)
UI_CONFIG_FIELDS = (
    "dashboard_url",
    "task_source",
    "photo_source",
    "calendar_sources",
    "calendar_view",
    "kindle_actions",
    "enabled_screens",
    *UI_BOOL_FIELDS,
    *UI_SECONDS_FIELDS,
)
_UNSET = object()


def _csv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        return ",".join(str(item) for item in value)
    return str(value)


def _bool_string(value: Any) -> str:
    return "true" if bool(value) else "false"


def _seconds_string(value: Any) -> str:
    return str(int(max(0, float(value))))


def build_configure_ui_params(
    *,
    default_screen: Any = _UNSET,
    enabled_screens: Any = _UNSET,
    show_bottom_menu: Any = _UNSET,
    keep_screen_awake: Any = _UNSET,
    show_connection_banner: Any = _UNSET,
    show_photo_time_overlay: Any = _UNSET,
    dim_after_seconds: Any = _UNSET,
    sleep_after_seconds: Any = _UNSET,
    task_refresh_seconds: Any = _UNSET,
    camera_rotate_180: Any = _UNSET,
    dashboard_url: Any = _UNSET,
    task_source: Any = _UNSET,
    photo_source: Any = _UNSET,
    calendar_sources: Any = _UNSET,
    calendar_view: Any = _UNSET,
    kindle_actions: Any = _UNSET,
    include_empty: bool = True,
) -> dict[str, str]:
    """Build device-facing `configure_ui` params from explicit values.

    `_UNSET` means the caller did not touch the field. `None`/empty string means
    the caller intentionally cleared it and is encoded as an empty string for
    string/CSV fields when `include_empty=True`.
    """
    values = {
        "default_screen": default_screen,
        "dashboard_url": dashboard_url,
        "task_source": task_source,
        "photo_source": photo_source,
        "calendar_sources": calendar_sources,
        "calendar_view": calendar_view,
        "kindle_actions": kindle_actions,
        "enabled_screens": enabled_screens,
        "show_bottom_menu": show_bottom_menu,
        "keep_screen_awake": keep_screen_awake,
        "show_connection_banner": show_connection_banner,
        "show_photo_time_overlay": show_photo_time_overlay,
        "camera_rotate_180": camera_rotate_180,
        "dim_after_seconds": dim_after_seconds,
        "sleep_after_seconds": sleep_after_seconds,
        "task_refresh_seconds": task_refresh_seconds,
    }
    params: dict[str, str] = {}
    for field in (*UI_STRING_FIELDS, "enabled_screens"):
        value = values[field]
        if value is _UNSET or (not include_empty and not value):
            continue
        params[field] = _csv(value)
    for field in UI_BOOL_FIELDS:
        value = values[field]
        if value is not _UNSET:
            params[field] = _bool_string(value)
    for field in UI_SECONDS_FIELDS:
        value = values[field]
        if value is not _UNSET and value is not None:
            params[field] = _seconds_string(value)
    return params


def build_configure_ui_params_from_media(media: Any) -> dict[str, str]:
    """Build reconnect/replay params from a persisted DeviceMedia-like object."""
    kwargs = {
        field: getattr(media, field)
        for field in UI_CONFIG_FIELDS
        if getattr(media, field, None) is not None
    }
    return build_configure_ui_params(**kwargs, include_empty=False)


def build_media_config_kwargs(values: Mapping[str, Any]) -> dict[str, Any]:
    """Build Registry.set_media_config kwargs from explicit UI values."""
    config: dict[str, Any] = {}
    for field in UI_CONFIG_FIELDS:
        if field not in values:
            continue
        value = values[field]
        if field == "enabled_screens":
            config[field] = _csv(value)
        else:
            config[field] = value
    return config
