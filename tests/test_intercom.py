from __future__ import annotations

import pytest

from opk_intercom import IntercomBroker, IntercomSessionError, validate_device_signal


class UnknownDeviceError(Exception):
    pass


class DeviceOfflineError(Exception):
    pass


class FakeRegistry:
    def __init__(self) -> None:
        self.devices = {"dev-1": object()}
        self.online = {"dev-1"}
        self.sent: list[tuple[str, dict]] = []

    def get_device(self, device_id: str):
        if device_id not in self.devices:
            raise UnknownDeviceError(device_id)
        return self.devices[device_id]

    def is_online(self, device_id: str) -> bool:
        return device_id in self.online

    async def send_raw(self, device_id: str, message: dict) -> None:
        self.get_device(device_id)
        if not self.is_online(device_id):
            raise DeviceOfflineError(device_id)
        self.sent.append((device_id, message))

    async def send_command_nowait(self, device_id: str, command, params: dict | None = None):
        self.get_device(device_id)
        if not self.is_online(device_id):
            raise DeviceOfflineError(device_id)
        assert isinstance(command, str)
        assert hasattr(command, "value")
        self.sent.append((device_id, {"type": "command", "command": getattr(command, "value"), "params": params}))


@pytest.mark.asyncio
async def test_start_session_sends_start_signal_to_device() -> None:
    registry = FakeRegistry()
    received: list[dict] = []
    broker = IntercomBroker(registry)  # type: ignore[arg-type]

    async def handler(frame: dict) -> None:
        received.append(frame)

    session = await broker.start_session("dev-1", handler)

    assert session.device_id == "dev-1"
    assert registry.sent == [
        (
            "dev-1",
            {"type": "command", "command": "start_stream", "params": {"camera_mode": "front"}},
        ),
        (
            "dev-1",
            {"type": "command", "command": "start_intercom", "params": {"mode": "talk"}},
        ),
        (
            "dev-1",
            {
                "type": "intercom_signal",
                "action": "start",
                "session_id": session.session_id,
            },
        )
    ]
    assert received == []


@pytest.mark.asyncio
async def test_signal_round_trip_between_browser_and_device() -> None:
    registry = FakeRegistry()
    received: list[dict] = []
    broker = IntercomBroker(registry)  # type: ignore[arg-type]

    async def handler(frame: dict) -> None:
        received.append(frame)

    session = await broker.start_session("dev-1", handler)
    await broker.send_to_device(
        session.session_id,
        {"type": "intercom_signal", "action": "offer", "sdp": "v=0"},
    )
    await broker.handle_device_signal(
        "dev-1",
        {"type": "intercom_signal", "action": "answer", "session_id": session.session_id, "sdp": "v=0"},
    )

    assert registry.sent[-1] == (
        "dev-1",
        {
            "type": "intercom_signal",
            "action": "offer",
            "sdp": "v=0",
            "session_id": session.session_id,
        },
    )
    assert received == [
        {
            "type": "intercom_signal",
            "action": "answer",
            "session_id": session.session_id,
            "sdp": "v=0",
            "device_id": "dev-1",
        }
    ]


@pytest.mark.asyncio
async def test_hangup_removes_session_and_notifies_device() -> None:
    registry = FakeRegistry()
    broker = IntercomBroker(registry)  # type: ignore[arg-type]

    async def handler(frame: dict) -> None:
        pass

    session = await broker.start_session("dev-1", handler)
    await broker.hangup(session.session_id)

    assert registry.sent[-3:] == [
        (
            "dev-1",
            {
                "type": "intercom_signal",
                "action": "hangup",
                "session_id": session.session_id,
            },
        ),
        (
            "dev-1",
            {"type": "command", "command": "stop_intercom", "params": None},
        ),
        (
            "dev-1",
            {"type": "command", "command": "stop_stream", "params": None},
        ),
    ]
    with pytest.raises(IntercomSessionError):
        broker.get_session(session.session_id)


def test_validate_device_signal_rejects_invalid_payload() -> None:
    with pytest.raises(IntercomSessionError):
        validate_device_signal({"type": "intercom_signal", "session_id": "s"})
    with pytest.raises(IntercomSessionError):
        validate_device_signal({"type": "intercom_signal", "session_id": "s", "action": "bogus"})


def test_validate_device_signal_accepts_hangup_ice_candidate_and_audio_diagnostics() -> None:
    hangup = validate_device_signal({"type": "intercom_signal", "session_id": "s", "action": "hangup"})
    ice = validate_device_signal({
        "type": "intercom_signal",
        "session_id": "s",
        "action": "ice_candidate",
        "candidate": {"candidate": "candidate:1", "sdpMid": "0", "sdpMLineIndex": 0},
    })
    diagnostics = validate_device_signal({
        "type": "intercom_signal",
        "session_id": "s",
        "action": "audio_diagnostics",
        "diagnostics": {"currentInputs": "Built-In Microphone", "inputChannels": "1"},
    })

    assert hangup["action"] == "hangup"
    assert ice["candidate"]["candidate"] == "candidate:1"
    assert diagnostics["diagnostics"]["inputChannels"] == "1"
