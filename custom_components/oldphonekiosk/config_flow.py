"""Config flow for the Home Assistant-native OldPhoneKiosk backend."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.network import get_url

try:  # HA >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # HA < 2024.4
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from .backend import ensure_backend
from .const import DOMAIN
from .pairing import build_claim_payload, payload_to_json, payload_to_qr_svg_data_uri
from .registry import Registry

DEFAULT_PANEL_NAME = "OldPhoneKiosk Panel"


class OldPhoneKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OldPhoneKiosk."""

    VERSION = 2

    _registry: Registry
    _claim_token: str | None = None
    _device_id: str | None = None
    _payload_json: str | None = None
    _qr_data_uri: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start hub setup by showing a QR, not by creating an empty hub."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self._ensure_pairing_claim()
        return self._show_pairing_form()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish setup only after the phone has scanned and connected."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self._ensure_pairing_claim()

        if user_input is None:
            return self._show_pairing_form()

        assert self._device_id is not None
        assert self._claim_token is not None
        if self._registry.is_online(self._device_id):
            return self.async_create_entry(title="OldPhoneKiosk", data={})

        if not self._registry.is_claim_pending(self._claim_token):
            # The app may have redeemed the claim but not opened the WebSocket yet;
            # keep the flow explicit so users do not get an empty-looking hub.
            return self._show_pairing_form(errors={"base": "not_connected"})

        return self._show_pairing_form(errors={"base": "waiting_for_phone"})

    def _ensure_pairing_claim(self) -> None:
        """Create the backend and one QR claim for this config-flow run."""
        if self._claim_token is not None:
            return

        self._registry = ensure_backend(self.hass)
        claim = self._registry.create_claim(name=DEFAULT_PANEL_NAME)
        self._claim_token = claim.claim_token
        self._device_id = claim.device_id

        payload = build_claim_payload(
            bridge_url=self._ha_base_url(),
            claim_token=claim.claim_token,
            name=DEFAULT_PANEL_NAME,
        )
        self._payload_json = payload_to_json(payload)
        self._qr_data_uri = payload_to_qr_svg_data_uri(self._payload_json)

    def _show_pairing_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        assert self._payload_json is not None
        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({}),
            errors=errors or {},
            description_placeholders={
                "qr_svg_data_uri": self._qr_data_uri or "",
                "payload": self._payload_json,
            },
        )

    def _ha_base_url(self) -> str:
        try:
            return get_url(self.hass, prefer_external=False).rstrip("/")
        except Exception:  # noqa: BLE001 - fallback for tests/minimal HA config
            base = getattr(self.hass.config.api, "base_url", None) or ""
            return base.rstrip("/") or "http://homeassistant.local:8123"
