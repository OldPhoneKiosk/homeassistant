"""Tests for the Bridge API client against a mocked httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest

import opk_api as api
import opk_const as const

BASE = "http://bridge.test:8788"
KEY = "secret-key"

DEVICE_JSON = {
    "device_id": "dev-1",
    "name": "Kitchen Panel",
    "room": "Kitchen",
    "model": "iPhone SE",
    "ios_version": "17.0",
    "capabilities": {"photos": True, "tasks": True},
    "state": {
        "online": True,
        "battery": 77,
        "brightness": 0.4,
        "screen": "photos",
        "camera": "off",
        "app_version": "0.1.0",
        "last_seen": "2026-08-26T13:41:32.559064Z",
    },
}


def _client(handler) -> api.BridgeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return api.BridgeClient(BASE, KEY, client=http)


async def test_get_devices_parses_state():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == const.ENDPOINT_DEVICES
        assert request.headers[const.API_KEY_HEADER] == KEY
        return httpx.Response(200, json={"devices": [DEVICE_JSON]})

    client = _client(handler)
    devices = await client.async_get_devices()
    assert len(devices) == 1
    d = devices[0]
    assert isinstance(d, api.PanelDeviceData)
    assert d.device_id == "dev-1"
    assert d.name == "Kitchen Panel"
    assert d.room == "Kitchen"
    assert d.online is True
    assert d.battery == 77
    assert d.screen == "photos"
    assert d.app_version == "0.1.0"
    assert d.last_seen is not None
    assert d.last_seen.year == 2026


async def test_get_devices_empty():
    client = _client(lambda req: httpx.Response(200, json={"devices": []}))
    assert await client.async_get_devices() == []


async def test_auth_error_maps():
    client = _client(lambda req: httpx.Response(401, text="nope"))
    with pytest.raises(api.BridgeAuthError):
        await client.async_get_devices()


async def test_server_error_maps():
    client = _client(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(api.BridgeError):
        await client.async_get_devices()


async def test_connection_error_maps():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = _client(handler)
    with pytest.raises(api.BridgeConnectionError):
        await client.async_get_devices()


async def test_send_command_posts_payload():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == const.ENDPOINT_COMMANDS.format(device_id="dev-1")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "c1", "status": "completed", "success": True})

    client = _client(handler)
    result = await client.async_send_command("dev-1", const.CMD_SHOW_TASKS)
    assert seen["body"] == {"command": "show_tasks"}
    assert result["status"] == "completed"


async def test_async_check_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == const.ENDPOINT_HEALTH:
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"devices": []})

    client = _client(handler)
    assert await client.async_check() is True


async def test_async_check_bad_key():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == const.ENDPOINT_HEALTH:
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(401, text="nope")

    client = _client(handler)
    with pytest.raises(api.BridgeAuthError):
        await client.async_check()


async def test_async_check_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = _client(handler)
    with pytest.raises(api.BridgeConnectionError):
        await client.async_check()


def test_screen_to_command_mapping():
    assert const.SCREEN_TO_COMMAND[const.SCREEN_TASKS] == const.CMD_SHOW_TASKS
    assert const.SCREEN_TO_COMMAND[const.SCREEN_SLEEP] == const.CMD_SLEEP
    assert set(const.SCREENS) == {"photos", "tasks", "home", "sleep"}


def test_from_json_handles_missing_state():
    d = api.PanelDeviceData.from_json({"device_id": "x"})
    assert d.device_id == "x"
    assert d.name == "x"
    assert d.online is False
    assert d.battery is None
    assert d.last_seen is None
