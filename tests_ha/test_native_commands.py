"""Real NativeOldPhoneKioskClient + Registry command/param plumbing.

These assert the exact WebSocket command messages (and their params) the client
sends for the new media/intercom controls, and that the HA-owned per-panel config
persists — Home Assistant is the source of truth and the panel only receives.
"""

from __future__ import annotations

from custom_components.oldphonekiosk.models import CommandResult
from custom_components.oldphonekiosk.native_client import NativeOldPhoneKioskClient
from custom_components.oldphonekiosk.registry import Registry
from custom_components.oldphonekiosk.store import DeviceStore


class _FakeConn:
    """Records outbound messages and auto-acks commands as success."""

    def __init__(self, registry: Registry, device_id: str) -> None:
        self._registry = registry
        self._device_id = device_id
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        if data.get("type") == "command":
            self._registry.resolve_command(
                self._device_id, CommandResult(id=data["id"], success=True)
            )

    def commands(self) -> list[dict]:
        return [m for m in self.sent if m.get("type") == "command"]


def _online_device() -> tuple[Registry, NativeOldPhoneKioskClient, str, _FakeConn]:
    registry = Registry(DeviceStore(":memory:"))
    claim = registry.create_claim(name="Kitchen")
    device_id = claim.device_id
    conn = _FakeConn(registry, device_id)
    registry.register_connection(device_id, conn)
    return registry, NativeOldPhoneKioskClient(registry), device_id, conn


async def test_beep_sends_beep_command():
    _reg, client, device_id, conn = _online_device()
    await client.async_beep(device_id)
    cmd = conn.commands()[-1]
    assert cmd["command"] == "beep"


async def test_play_sound_falls_back_to_stored_sound():
    registry, client, device_id, conn = _online_device()
    registry.set_media_config(device_id, sound="1007")
    await client.async_play_sound(device_id)
    cmd = conn.commands()[-1]
    assert cmd["command"] == "play_sound"
    assert cmd["params"] == {"sound": "1007"}


async def test_play_sound_url_overrides_stored_sound():
    registry, client, device_id, conn = _online_device()
    registry.set_media_config(device_id, sound="1007")
    await client.async_play_sound(device_id, url="http://ha/local/chime.mp3")
    cmd = conn.commands()[-1]
    assert cmd["command"] == "play_sound"
    assert cmd["params"] == {"url": "http://ha/local/chime.mp3"}


async def test_start_intercom_carries_mode_and_audio_url():
    _reg, client, device_id, conn = _online_device()
    await client.async_start_intercom(
        device_id, mode="ring", audio_url="http://ha/audio"
    )
    cmd = conn.commands()[-1]
    assert cmd["command"] == "start_intercom"
    assert cmd["params"] == {"mode": "ring", "audio_url": "http://ha/audio"}


async def test_stop_intercom_sends_command():
    _reg, client, device_id, conn = _online_device()
    await client.async_stop_intercom(device_id)
    assert conn.commands()[-1]["command"] == "stop_intercom"


async def test_set_panel_ui_pushes_sources_and_persists():
    registry, client, device_id, conn = _online_device()
    await client.async_set_panel_ui(
        device_id, task_source="todo.kitchen", photo_source="album.family"
    )
    cmd = conn.commands()[-1]
    assert cmd["command"] == "configure_ui"
    assert cmd["params"] == {
        "task_source": "todo.kitchen",
        "photo_source": "album.family",
    }
    device = registry.get_device(device_id)
    assert device.media.task_source == "todo.kitchen"
    assert device.media.photo_source == "album.family"


async def test_media_config_persists_across_reload():
    store = DeviceStore(":memory:")
    registry = Registry(store)
    claim = registry.create_claim(name="Kitchen")
    device_id = claim.device_id
    registry.set_media_config(
        device_id,
        dashboard_url="http://ha/lovelace/kitchen",
        task_source="todo.kitchen",
        photo_source="album.family",
        sound="1007",
    )

    # A fresh registry over the same store reloads the persisted config.
    reloaded = Registry(store)
    media = reloaded.get_device(device_id).media
    assert media.dashboard_url == "http://ha/lovelace/kitchen"
    assert media.task_source == "todo.kitchen"
    assert media.photo_source == "album.family"
    assert media.sound == "1007"
