"""Safe action-link helpers for Kindle/old-browser web displays."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

ACTION_PATH_TEMPLATE = "/api/oldphonekiosk/web-display/{device_id}/action"
SAFE_TOGGLE_DOMAINS = {"light", "switch", "input_boolean"}
_ENTITY_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _action_path(device_id: str) -> str:
    return ACTION_PATH_TEMPLATE.format(device_id=device_id)


def is_safe_toggle_entity(entity_id: str) -> bool:
    """Return True if a Kindle may toggle this HA entity directly."""
    if not _ENTITY_RE.match(entity_id):
        return False
    domain = entity_id.split(".", 1)[0]
    return domain in SAFE_TOGGLE_DOMAINS


def build_toggle_url(device_id: str, token: str, entity_id: str) -> str | None:
    """Build a signed Kindle link for toggling one safe HA entity."""
    if not is_safe_toggle_entity(entity_id):
        return None
    query = urlencode({"token": token, "action": "toggle", "entity_id": entity_id})
    return f"{_action_path(device_id)}?{query}"


def build_complete_task_url(device_id: str, token: str, source: str, uid: str) -> str:
    """Build a signed Kindle link for marking a HA todo item complete."""
    query = urlencode(
        {"token": token, "action": "complete_task", "source": source, "uid": uid}
    )
    return f"{_action_path(device_id)}?{query}"


def build_entity_action(
    device_id: str, token: str, entity_id: str, state: Any | None
) -> dict[str, str] | None:
    """Build renderer data for a single quick toggle action."""
    url = build_toggle_url(device_id, token, entity_id)
    if not url:
        return None
    attrs = getattr(state, "attributes", {}) or {}
    label = str(attrs.get("friendly_name") or entity_id)
    value = str(getattr(state, "state", "")) if state is not None else "unknown"
    return {"entity_id": entity_id, "label": label, "state": value, "url": url}
