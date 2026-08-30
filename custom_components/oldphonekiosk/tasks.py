"""Helpers for pushing HA todo list snapshots to OldPhoneKiosk panels."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
from typing import Any

from homeassistant.components.todo import (
    DOMAIN as TODO_DOMAIN,
)
from homeassistant.components.todo import (
    TodoItem,
    TodoListEntity,
)
from homeassistant.components.todo.const import TodoItemStatus
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from .const import CMD_SHOW_TASKS
from .models import PanelCommand
from .native_client import NativeOldPhoneKioskClient
from .registry import DeviceOfflineError, Registry

MAX_TASKS = 40
_LOGGER = logging.getLogger(__name__)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def _task_item_dict(item: Any) -> dict[str, Any]:
    raw = dataclasses.asdict(item) if dataclasses.is_dataclass(item) else dict(item)
    uid = _stringify(raw.get("uid") or raw.get("id") or raw.get("summary") or "") or ""
    result: dict[str, Any] = {"uid": uid}
    for key in ("summary", "status", "due", "description", "assignee"):
        value = _stringify(raw.get(key))
        if value:
            result[key] = value
    details = {
        key: value
        for key, value in (
            (_stringify(value), _stringify(raw_value))
            for value, raw_value in raw.items()
        )
        if key
        and value
        and key not in {"uid", "id", "summary", "status", "due", "description"}
    }
    if details:
        result["details"] = details
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
    try:
        await entity.async_update()
    except Exception:
        _LOGGER.debug(
            "Could not refresh todo entity %s before snapshot", entity_id, exc_info=True
        )
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
        await client.async_send_command(
            device_id, PanelCommand.CONFIGURE_TASKS.value, params=params
        )
        if show:
            await client.async_send_command(device_id, CMD_SHOW_TASKS)
    except DeviceOfflineError:
        return


async def async_push_task_snapshot_via_registry(
    hass: HomeAssistant,
    registry: Registry,
    device_id: str,
    task_source: str,
    *,
    show: bool = False,
) -> None:
    """Push a selected HA todo snapshot using the in-process device registry."""
    if not task_source.startswith(f"{TODO_DOMAIN}."):
        return
    items_json = await async_todo_items_json(hass, task_source)
    params = {CONF_ENTITY_ID: task_source, "source": task_source, "items": items_json}
    if show:
        params["show"] = "true"
    try:
        await registry.send_command_nowait(
            device_id, PanelCommand.CONFIGURE_TASKS, params=params
        )
        if show:
            await registry.send_command_nowait(device_id, PanelCommand.SHOW_TASKS)
    except DeviceOfflineError:
        return


async def async_handle_task_action(
    hass: HomeAssistant,
    registry: Registry,
    device_id: str,
    raw: dict[str, Any],
) -> None:
    """Apply a task action from a paired panel to the configured HA todo entity."""
    source = str(raw.get("source") or "")
    action = str(raw.get("action") or "")
    entity = _todo_entity(hass, source)
    if entity is None:
        return

    if action == "add":
        summary = str(raw.get("summary") or "").strip()
        if summary:
            await entity.async_create_todo_item(TodoItem(summary=summary))
            await entity.async_update_ha_state(force_refresh=True)
    elif action == "complete":
        uid = str(raw.get("uid") or "").strip()
        summary = str(raw.get("summary") or "").strip()
        if uid or summary:
            await entity.async_update_todo_item(
                TodoItem(
                    uid=uid or None,
                    summary=summary or None,
                    status=TodoItemStatus.COMPLETED,
                )
            )
            await entity.async_update_ha_state(force_refresh=True)

    await async_push_task_snapshot_via_registry(hass, registry, device_id, source)
