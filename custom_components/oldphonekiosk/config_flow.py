"""Config flow for OldPhoneKiosk: Bridge URL + API key."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import BridgeAuthError, BridgeClient, BridgeConnectionError
from .const import CONF_API_KEY, CONF_BRIDGE_URL, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BRIDGE_URL, default="http://127.0.0.1:8788"): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class OldPhoneKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OldPhoneKiosk."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_BRIDGE_URL].rstrip("/")
            client = BridgeClient(url, user_input[CONF_API_KEY])
            try:
                await client.async_check()
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except BridgeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surface as generic error
                errors["base"] = "unknown"
            finally:
                await client.close()

            if not errors:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"OldPhoneKiosk ({url})",
                    data={CONF_BRIDGE_URL: url, CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
