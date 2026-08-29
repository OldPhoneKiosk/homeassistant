"""HA harness tests for the config flow."""

from __future__ import annotations

import json

from types import SimpleNamespace

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.oldphonekiosk.const import DOMAIN
from custom_components.oldphonekiosk.http import DATA_REGISTRY


class _FakeConnection:
    async def send_json(self, data: dict) -> None:
        pass


def _payload_from_form(result) -> dict:
    payload = result["description_placeholders"]["payload"]
    return json.loads(payload)


async def _start_pairing_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"]["payload"]
    return result


async def test_flow_shows_pairing_qr_before_creating_entry(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)

    payload = _payload_from_form(result)
    assert payload["version"] == 1
    assert payload["type"] == "claim"
    assert payload["bridge_url"] == "http://homeassistant.local:8123"
    assert payload["claim_token"]
    assert payload["name"] == "OldPhoneKiosk Panel"
    assert result["description_placeholders"]["qr_svg_data_uri"].startswith(
        "data:image/svg+xml;base64,"
    )

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
    payload = _payload_from_form(result)
    registry = hass.data[DOMAIN][DATA_REGISTRY]

    creds = registry.redeem_claim(payload["claim_token"])
    registry.register_connection(creds.device_id, _FakeConnection())

    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert created["title"] == "OldPhoneKiosk"
    assert created["data"] == {}


async def test_flow_is_single_instance_after_created_entry(hass: HomeAssistant):
    result = await _start_pairing_flow(hass)
    payload = _payload_from_form(result)
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    creds = registry.redeem_claim(payload["claim_token"])
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
    assert payload["name"] == "Kitchen iPad"
    assert payload["claim_token"]


async def test_zeroconf_flow_adds_panel_to_existing_hub(monkeypatch, hass: HomeAssistant):
    session = _FakeSession()
    monkeypatch.setattr(
        "custom_components.oldphonekiosk.config_flow.async_get_clientsession",
        lambda hass: session,
    )
    await hass.config_entries.async_add(
        config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="OldPhoneKiosk",
            data={},
            source=config_entries.SOURCE_USER,
            options={},
            unique_id=DOMAIN,
            entry_id="opk-entry",
        )
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
