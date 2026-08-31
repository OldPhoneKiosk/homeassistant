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
        "camera": "front",
        "intercom": "idle",
        "stream": "live",
        "app_version": "0.1.0",
        "last_seen": "2026-08-26T13:41:32.559064Z",
    },
    "media": {"video_url": "http://go2rtc/stream.html?src=panel"},
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
    assert d.camera_mode == "front"
    assert d.intercom == "idle"
    assert d.stream == "live"
    assert d.video_url == "http://go2rtc/stream.html?src=panel"


async def test_start_stop_stream_endpoints():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(
            200,
            json={"device_id": "d", "name": "P", "capabilities": {},
                  "state": {"online": True, "stream": "starting"},
                  "media": {"video_url": "http://v"}},
        )

    client = _client(handler)
    started = await client.async_start_stream("d", camera_mode="back")
    await client.async_stop_stream("d")
    assert seen[0] == ("POST", const.ENDPOINT_STREAM_START.format(device_id="d"), {"camera_mode": "back"})
    assert seen[1][0:2] == ("POST", const.ENDPOINT_STREAM_STOP.format(device_id="d"))
    assert started.stream == "starting"


async def test_from_json_media_defaults_when_absent():
    d = api.PanelDeviceData.from_json({"device_id": "x"})
    assert d.video_url is None
    assert d.camera_mode is None
    assert d.intercom is None


async def test_from_json_accepts_direct_ios_mjpeg_video_url():
    d = api.PanelDeviceData.from_json(
        {
            "device_id": "x",
            "state": {"stream": "live", "camera": "front"},
            "media": {"video_url": "http://192.168.1.20:8765/stream.mjpg"},
        }
    )
    assert d.stream == "live"
    assert d.camera_mode == "front"
    assert d.video_url == "http://192.168.1.20:8765/stream.mjpg"


async def test_set_media_puts_only_provided_fields():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == const.ENDPOINT_MEDIA.format(device_id="dev-1")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "device_id": "dev-1",
                "name": "P",
                "capabilities": {},
                "state": {"online": True, "camera": "back"},
                "media": {"video_url": "http://v"},
            },
        )

    client = _client(handler)
    updated = await client.async_set_media("dev-1", camera_mode="back")
    assert seen["body"] == {"camera_mode": "back"}  # video_url not sent
    assert updated.camera_mode == "back"
    assert updated.video_url == "http://v"


async def test_set_media_can_clear_video_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"device_id": "d", "name": "P", "capabilities": {}, "state": {"online": False}, "media": {"video_url": None}},
        )

    client = _client(handler)
    await client.async_set_media("d", video_url=None)
    assert seen["body"] == {"video_url": None}


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


async def test_delete_device_success():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(204)

    client = _client(handler)
    result = await client.async_delete_device("dev-1")
    assert result is None
    assert seen["method"] == "DELETE"
    assert seen["path"] == const.ENDPOINT_DEVICE.format(device_id="dev-1")


async def test_delete_device_not_found_maps():
    client = _client(lambda req: httpx.Response(404, text="unknown device"))
    with pytest.raises(api.BridgeNotFoundError):
        await client.async_delete_device("ghost")


async def test_delete_device_auth_error_maps():
    client = _client(lambda req: httpx.Response(401, text="nope"))
    with pytest.raises(api.BridgeAuthError):
        await client.async_delete_device("dev-1")


async def test_delete_device_server_error_maps():
    client = _client(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(api.BridgeError):
        await client.async_delete_device("dev-1")


async def test_provision_panel_runs_start_then_approve():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == const.ENDPOINT_PAIRING_START:
            return httpx.Response(200, json={"request_id": "r1", "pairing_code": "482913"})
        if request.url.path == const.ENDPOINT_PAIRING_APPROVE:
            body = json.loads(request.content)
            assert body["pairing_code"] == "482913"
            assert body["name"] == "Kitchen"
            assert body["room"] == "Kitchen"
            return httpx.Response(200, json={"device_id": "dev-9", "device_secret": "sek"})
        return httpx.Response(404)

    client = _client(handler)
    provisioned = await client.async_provision_panel("Kitchen", "Kitchen")
    assert provisioned.device_id == "dev-9"
    assert provisioned.device_secret == "sek"
    assert seen == [const.ENDPOINT_PAIRING_START, const.ENDPOINT_PAIRING_APPROVE]


async def test_create_claim_returns_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == const.ENDPOINT_CLAIM_CREATE
        body = json.loads(request.content)
        assert body["name"] == "Kitchen"
        return httpx.Response(
            200,
            json={"claim_token": "claim-abc", "device_id": "dev-9", "expires_at": "2026-08-26T14:00:00Z"},
        )

    client = _client(handler)
    claim = await client.async_create_claim("Kitchen", "Kitchen")
    assert claim.claim_token == "claim-abc"
    assert claim.device_id == "dev-9"


async def test_provision_panel_auth_error_maps():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == const.ENDPOINT_PAIRING_START:
            return httpx.Response(200, json={"pairing_code": "1"})
        return httpx.Response(401, text="nope")

    client = _client(handler)
    with pytest.raises(api.BridgeAuthError):
        await client.async_provision_panel("X")


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
    assert set(const.SCREENS) == {"photos", "tasks", "dashboard", "sleep"}


def test_from_json_handles_missing_state():
    d = api.PanelDeviceData.from_json({"device_id": "x"})
    assert d.device_id == "x"
    assert d.name == "x"
    assert d.online is False
    assert d.battery is None
    assert d.last_seen is None
