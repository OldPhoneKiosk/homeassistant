from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "custom_components" / "oldphonekiosk" / "frontend.py"


def _load_frontend_module():
    previous_parent = sys.modules.get("custom_components")
    previous_package = sys.modules.get("custom_components.oldphonekiosk")
    previous_frontend = sys.modules.get("custom_components.oldphonekiosk.frontend")
    try:
        parent = types.ModuleType("custom_components")
        parent.__path__ = [str(ROOT / "custom_components")]
        package = types.ModuleType("custom_components.oldphonekiosk")
        package.__path__ = [str(ROOT / "custom_components" / "oldphonekiosk")]
        sys.modules["custom_components"] = parent
        sys.modules["custom_components.oldphonekiosk"] = package
        spec = importlib.util.spec_from_file_location(
            "custom_components.oldphonekiosk.frontend", FRONTEND
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["custom_components.oldphonekiosk.frontend"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in (
            ("custom_components.oldphonekiosk.frontend", previous_frontend),
            ("custom_components.oldphonekiosk", previous_package),
            ("custom_components", previous_parent),
        ):
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


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
        {"res_type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=1.0.0"}
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
            {"res_type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=1.0.0"},
        )
    ]
    assert hass.data["oldphonekiosk"]["lovelace_resource_registered"] is True


@pytest.mark.asyncio
async def test_ensure_lovelace_resource_does_not_duplicate_current_resource():
    module = _load_frontend_module()
    resources = FakeResources(
        [{"id": "res-1", "type": "module", "url": "/oldphonekiosk_static/oldphonekiosk-intercom-card.js?v=1.0.0"}]
    )
    hass = SimpleNamespace(data={"lovelace": {"resources": resources}})

    await module.async_ensure_lovelace_resource(hass)

    assert resources.created == []
    assert resources.updated == []
    assert hass.data["oldphonekiosk"]["lovelace_resource_registered"] is True
