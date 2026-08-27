"""Config flow for the Home Assistant-native OldPhoneKiosk backend."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow

try:  # HA >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # HA < 2024.4
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from .const import DOMAIN


class OldPhoneKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OldPhoneKiosk."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="OldPhoneKiosk", data={})
