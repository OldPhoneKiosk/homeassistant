"""Helpers for pushing HA calendar snapshots to OldPhoneKiosk panels."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
from typing import Any

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import CMD_CONFIGURE_CALENDAR
from .models import PanelCommand
from .native_client import NativeOldPhoneKioskClient
from .registry import DeviceOfflineError, Registry

_LOGGER = logging.getLogger(__name__)

CALENDAR_VIEWS = ["month", "week", "day", "list"]
MAX_EVENTS = 80


def calendar_entity_ids(hass: HomeAssistant) -> list[str]:
    """Return currently known ``calendar.*`` entity ids."""
    return sorted(hass.states.async_entity_ids(CALENDAR_DOMAIN))


def normalize_calendar_sources(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize a CSV/list of calendar entity ids preserving order and uniqueness."""
    if value is None:
        raw: list[str] = []
    elif isinstance(value, str):
        raw = value.split(",")
    else:
        raw = list(value)
    result: list[str] = []
    for item in raw:
        entity_id = str(item).strip()
        if entity_id.startswith(f"{CALENDAR_DOMAIN}.") and entity_id not in result:
            result.append(entity_id)
    return result


def _range_for_view(view: str, now: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    """Return the snapshot time range for a calendar view."""
    now = now or dt.datetime.now(dt.UTC)
    local = now.astimezone()
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if view == "day":
        return day_start, day_start + dt.timedelta(days=1)
    if view == "week":
        start = day_start - dt.timedelta(days=day_start.weekday())
        return start, start + dt.timedelta(days=7)
    if view == "month":
        start = day_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    # list: near future agenda
    return day_start, day_start + dt.timedelta(days=31)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _event_dict(calendar_id: str, item: Any, index: int) -> dict[str, Any] | None:
    raw = dataclasses.asdict(item) if dataclasses.is_dataclass(item) else dict(item)
    start = raw.get("start") or raw.get("start_datetime") or raw.get("start_date")
    if not start:
        return None
    end = raw.get("end") or raw.get("end_datetime") or raw.get("end_date")
    title = _stringify(raw.get("summary") or raw.get("title") or raw.get("name") or "Event") or "Event"
    event_id = _stringify(raw.get("uid") or raw.get("id")) or f"{calendar_id}:{index}:{_stringify(start)}:{title}"
    payload: dict[str, Any] = {
        "id": event_id,
        "calendar": calendar_id,
        "title": title,
        "start": _stringify(start),
        "all_day": isinstance(start, dt.date) and not isinstance(start, dt.datetime),
    }
    if end:
        payload["end"] = _stringify(end)
    for key in ("location", "description"):
        value = _stringify(raw.get(key))
        if value:
            payload[key] = value
    return payload


async def async_calendar_events_json(
    hass: HomeAssistant, sources: list[str], view: str = "month"
) -> str:
    """Return a compact JSON snapshot for selected HA calendar entities."""
    if view not in CALENDAR_VIEWS:
        view = "month"
    start, end = _range_for_view(view)
    events: list[dict[str, Any]] = []
    for entity_id in sources:
        try:
            service_response = await hass.services.async_call(
                CALENDAR_DOMAIN,
                "get_events",
                {CONF_ENTITY_ID: entity_id, "start_date_time": start.isoformat(), "end_date_time": end.isoformat()},
                blocking=True,
                return_response=True,
            )
        except Exception:
            _LOGGER.debug("Could not fetch calendar events for %s", entity_id, exc_info=True)
            continue
        raw_events = []
        if isinstance(service_response, dict):
            raw = service_response.get(entity_id) or service_response.get("events") or {}
            raw_events = raw.get("events", raw) if isinstance(raw, dict) else raw
        if not isinstance(raw_events, list):
            continue
        for index, item in enumerate(raw_events):
            event = _event_dict(entity_id, item, index)
            if event:
                events.append(event)
    events.sort(key=lambda e: str(e.get("start") or ""))
    return json.dumps(events[:MAX_EVENTS], ensure_ascii=False, separators=(",", ":"))


async def async_push_calendar_snapshot(
    hass: HomeAssistant,
    client: NativeOldPhoneKioskClient,
    device_id: str,
    calendar_sources: str | list[str],
    *,
    view: str = "month",
    show: bool = False,
) -> None:
    sources = normalize_calendar_sources(calendar_sources)
    if not sources:
        return
    items_json = await async_calendar_events_json(hass, sources, view)
    joined = ",".join(sources)
    params = {"sources": joined, CONF_ENTITY_ID: joined, "view": view, "items": items_json}
    if show:
        params["show"] = "true"
    try:
        await client.async_send_command(device_id, CMD_CONFIGURE_CALENDAR, params=params)
    except DeviceOfflineError:
        return


async def async_push_calendar_snapshot_via_registry(
    hass: HomeAssistant,
    registry: Registry,
    device_id: str,
    calendar_sources: str | list[str],
    *,
    view: str = "month",
    show: bool = False,
) -> None:
    sources = normalize_calendar_sources(calendar_sources)
    if not sources:
        return
    items_json = await async_calendar_events_json(hass, sources, view)
    params = {"sources": ",".join(sources), CONF_ENTITY_ID: ",".join(sources), "view": view, "items": items_json}
    if show:
        params["show"] = "true"
    try:
        await registry.send_command_nowait(device_id, PanelCommand.CONFIGURE_CALENDAR, params=params)
    except DeviceOfflineError:
        return


async def async_handle_calendar_action(
    hass: HomeAssistant,
    registry: Registry,
    device_id: str,
    payload: dict[str, Any],
) -> None:
    """Handle a device-initiated calendar refresh request."""
    if payload.get("action") != "refresh":
        return
    sources = payload.get("sources") or payload.get(CONF_ENTITY_ID) or ""
    view = payload.get("view") or "month"
    if view not in CALENDAR_VIEWS:
        view = "month"
    await async_push_calendar_snapshot_via_registry(
        hass,
        registry,
        device_id,
        sources,
        view=view,
        show=False,
    )
