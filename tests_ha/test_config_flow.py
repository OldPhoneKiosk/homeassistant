"""HA harness tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.oldphonekiosk.const import (
    CONF_API_KEY,
    CONF_BRIDGE_URL,
    DOMAIN,
)

USER_INPUT = {CONF_BRIDGE_URL: "http://127.0.0.1:8788", CONF_API_KEY: "secret"}


async def _start_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_flow_happy_path_creates_entry(hass: HomeAssistant):
    with patch(
        "custom_components.oldphonekiosk.config_flow.BridgeClient"
    ) as mock_client, patch(
        "custom_components.oldphonekiosk.async_setup_entry", return_value=True
    ):
        instance = mock_client.return_value
        instance.async_check = AsyncMock(return_value=True)
        instance.close = AsyncMock()

        result = await _start_flow(hass)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_BRIDGE_URL] == "http://127.0.0.1:8788"
    assert result2["data"][CONF_API_KEY] == "secret"


async def test_flow_cannot_connect(hass: HomeAssistant):
    from custom_components.oldphonekiosk.api import BridgeConnectionError

    with patch(
        "custom_components.oldphonekiosk.config_flow.BridgeClient"
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_check = AsyncMock(side_effect=BridgeConnectionError("refused"))
        instance.close = AsyncMock()

        result = await _start_flow(hass)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_flow_invalid_auth(hass: HomeAssistant):
    from custom_components.oldphonekiosk.api import BridgeAuthError

    with patch(
        "custom_components.oldphonekiosk.config_flow.BridgeClient"
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_check = AsyncMock(side_effect=BridgeAuthError("bad key"))
        instance.close = AsyncMock()

        result = await _start_flow(hass)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
