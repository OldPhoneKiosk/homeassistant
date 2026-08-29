"""Helpers for pushing HA todo list snapshots to OldPhoneKiosk panels."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from typing import Any

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN, TodoListEntity
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from .const import CMD_SHOW_TASKS
from .models import PanelCommand
from .native_client import NativeOldPhoneKioskClient
from .registry import DeviceOfflineError

MAX_TASKS = 40


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def _task_item_dict(item: Any) -> dict[str, str]:
    raw = dataclasses.asdict(item) if dataclasses.is_dataclass(item) else dict(item)
    uid = _stringify(raw.get("uid") or raw.get("id") or raw.get("summary") or "") or ""
    result: dict[str, str] = {"uid": uid}
    for key in ("summary", "status", "due", "description"):
        value = _stringify(raw.get(key))
        if value:
            result[key] = value
    return result


def _todo_entity(hass: HomeAssistant, entity_id: str) -> TodoListEntity | None:
    component = hass.data.get(TODO_DOMAIN)
    if not isinstance(component, EntityComponent):
        return None
    entity = component.get_entity(entity_id)
    return entity if isinstance(entity, TodoListEntity) else None


async def async_todo_items_json(hass: HomeAssistant, entity_id: str) -> str:
    """Return a compact JSON snapshot for a HA todo entity."""
    entity = _todo_entity(hass, entity_id)
    if entity is None:
        return "[]"
    items = entity.todo_items or []
    payload = [
        data
        for data in (_task_item_dict(item) for item in items)
        if data.get("status") != "completed"
    ][:MAX_TASKS]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def async_push_task_snapshot(
    hass: HomeAssistant,
    client: NativeOldPhoneKioskClient,
    device_id: str,
    task_source: str,
    *,
    show: bool = False,
) -> None:
    """Push the selected HA todo list snapshot to an online panel.

    Non-HA sources are ignored; the configured source remains stored as-is.
    """
    if not task_source.startswith(f"{TODO_DOMAIN}."):
        return
    items_json = await async_todo_items_json(hass, task_source)
    params = {CONF_ENTITY_ID: task_source, "source": task_source, "items": items_json}
    if show:
        params["show"] = "true"
    try:
        await client.async_send_command(device_id, PanelCommand.CONFIGURE_TASKS.value, params=params)
        if show:
            await client.async_send_command(device_id, CMD_SHOW_TASKS)
    except DeviceOfflineError:
        return
