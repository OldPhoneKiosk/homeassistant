from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "custom_components" / "oldphonekiosk" / "frontend.py"


def _load_frontend_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("custom_components.oldphonekiosk.frontend")


class FakeResources:
    loaded = False

    def __init__(self, items=None):
        self._items = items or []
        self.created = []
        self.updated = []
        self.load_calls = 0

    async def async_load(self):
        self.load_calls += 1

    def async_items(self):
        return self._items

    async def async_create_item(self, item):
        self.created.append(item)
        self._items.append(item)
        return item

    async def async_update_item(self, item_id, updates):
        self.updated.append((item_id, updates))
        for item in self._items:
            if item.get("id") == item_id:
                item.update(updates)
                return item
        raise KeyError(item_id)


@pytest.mark.asyncio
async def test_ensure_lovelace_resource_creates_module_resource():
    module = _load_frontend_module()
    resources = FakeResources()
    hass = SimpleNamespace(data={"lovelace": {"resources": resources}})

    await module.async_ensure_lovelace_resource(hass)

    assert resources.load_calls == 1
    assert resources.created == [
        {"res_type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=0.1.42"}
    ]
    assert hass.data["oldphonekiosk"]["lovelace_resource_registered"] is True


@pytest.mark.asyncio
async def test_ensure_lovelace_resource_updates_stale_existing_resource():
    module = _load_frontend_module()
    resources = FakeResources(
        [{"id": "res-1", "type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=0.1.34"}]
    )
    hass = SimpleNamespace(data={"lovelace": {"resources": resources}})

    await module.async_ensure_lovelace_resource(hass)

    assert resources.created == []
    assert resources.updated == [
        (
            "res-1",
            {"res_type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=0.1.42"},
        )
    ]
    assert hass.data["oldphonekiosk"]["lovelace_resource_registered"] is True


@pytest.mark.asyncio
async def test_ensure_lovelace_resource_does_not_duplicate_current_resource():
    module = _load_frontend_module()
    resources = FakeResources(
        [{"id": "res-1", "type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=0.1.42"}]
    )
    hass = SimpleNamespace(data={"lovelace": {"resources": resources}})

    await module.async_ensure_lovelace_resource(hass)

    assert resources.created == []
    assert resources.updated == []
    assert hass.data["oldphonekiosk"]["lovelace_resource_registered"] is True
