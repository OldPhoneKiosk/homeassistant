"""HA harness tests for the config flow."""

from __future__ import annotations

import inspect

from types import SimpleNamespace

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.oldphonekiosk.const import DOMAIN
from custom_components.oldphonekiosk.http import DATA_REGISTRY


class _FakeConnection:
    async def send_json(self, data: dict) -> None:
        pass


def _pairing_code_from_form(result) -> str:
    return result["description_placeholders"]["pairing_code"]


async def _start_pairing_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"]["pairing_code"]
    return result


async def test_flow_shows_pairing_code_before_creating_entry(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)

    code = _pairing_code_from_form(result)
    # The manual backup is a one-time 10-digit numeric code (no QR, no payload JSON).
    assert code.isdigit()
    assert len(code) == 10
    assert "qr_svg_data_uri" not in result["description_placeholders"]
    assert "payload" not in result["description_placeholders"]

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_flow_waits_until_phone_connects(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)

    waiting = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert waiting["type"] == data_entry_flow.FlowResultType.FORM
    assert waiting["step_id"] == "pair"
    assert waiting["errors"] == {"base": "waiting_for_phone"}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_flow_creates_native_entry_after_phone_connection(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)
    code = _pairing_code_from_form(result)
    registry = hass.data[DOMAIN][DATA_REGISTRY]

    creds = registry.redeem_claim(code)
    registry.register_connection(creds.device_id, _FakeConnection())

    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert created["title"] == "OldPhoneKiosk"
    assert created["data"] == {}


async def test_flow_is_single_instance_after_created_entry(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)
    code = _pairing_code_from_form(result)
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    creds = registry.redeem_claim(code)
    registry.register_connection(creds.device_id, _FakeConnection())

    first = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert first["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert second["type"] == data_entry_flow.FlowResultType.ABORT


class _FakeResponse:
    status = 204

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self):
        self.posts = []

    def post(self, url, *, json, timeout):
        self.posts.append((url, json, timeout))
        return _FakeResponse()


def _discovered_panel():
    return SimpleNamespace(
        host="192.168.18.50",
        port=8766,
        name="Wall Panel 1234._oldphonekiosk._tcp.local.",
        properties={
            "id": b"panel-instance-1",
            "name": b"Kitchen iPad",
            "model": b"iPad",
            "ios": b"18.0",
            "version": b"0.1.0 (13)",
            "path": b"/pair-claim",
        },
    )


async def test_zeroconf_flow_confirms_and_pushes_claim(monkeypatch, hass: HomeAssistant):
    hass.config.internal_url = "http://192.168.18.10:8123"
    session = _FakeSession()
    monkeypatch.setattr(
        "custom_components.oldphonekiosk.config_flow.async_get_clientsession",
        lambda hass: session,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_discovered_panel(),
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm_discovered"
    assert result["description_placeholders"]["name"] == "Kitchen iPad"

    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={},
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert created["title"] == "OldPhoneKiosk"
    assert session.posts[0][0] == "http://192.168.18.50:8766/pair-claim"
    payload = session.posts[0][1]
    assert payload["type"] == "claim"
    assert payload["bridge_url"] == "http://192.168.18.10:8123"
    assert payload["name"] == "Kitchen iPad"
    assert payload["claim_token"]


def _existing_entry_kwargs() -> dict:
    kwargs = {
        "version": 2,
        "minor_version": 1,
        "domain": DOMAIN,
        "title": "OldPhoneKiosk",
        "data": {},
        "source": config_entries.SOURCE_USER,
        "options": {},
        "unique_id": DOMAIN,
        "entry_id": "opk-entry",
    }
    if "discovery_keys" in inspect.signature(config_entries.ConfigEntry).parameters:
        kwargs["discovery_keys"] = {}
    return kwargs


async def test_zeroconf_flow_uses_bonjour_instance_name_when_txt_name_missing(monkeypatch, hass: HomeAssistant):
    session = _FakeSession()
    monkeypatch.setattr(
        "custom_components.oldphonekiosk.config_flow.async_get_clientsession",
        lambda hass: session,
    )
    discovered = _discovered_panel()
    discovered.name = "Tomasz iPad._oldphonekiosk._tcp.local."
    discovered.properties = {
        key: value for key, value in discovered.properties.items() if key != "name"
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovered,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["description_placeholders"]["name"] == "Tomasz iPad"
    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={},
    )
    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert session.posts[0][1]["name"] == "Tomasz iPad"


async def test_zeroconf_flow_adds_panel_to_existing_hub(monkeypatch, hass: HomeAssistant):
    session = _FakeSession()
    monkeypatch.setattr(
        "custom_components.oldphonekiosk.config_flow.async_get_clientsession",
        lambda hass: session,
    )
    await hass.config_entries.async_add(
        config_entries.ConfigEntry(**_existing_entry_kwargs())
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_discovered_panel(),
    )
    done = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert done["type"] == data_entry_flow.FlowResultType.ABORT
    assert done["reason"] == "pairing_sent"
    assert session.posts
