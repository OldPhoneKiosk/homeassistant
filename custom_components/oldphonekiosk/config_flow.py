"""Config flow for the Home Assistant-native OldPhoneKiosk backend."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

try:  # HA >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # HA < 2024.4
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from .backend import ensure_backend
from .const import DOMAIN
from .pairing import build_claim_payload, payload_to_json
from .registry import Registry

_LOGGER = logging.getLogger(__name__)

DEFAULT_PANEL_NAME = "OldPhoneKiosk Panel"
DISCOVERY_PAIRING_PATH = "/pair-claim"


class OldPhoneKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OldPhoneKiosk."""

    VERSION = 2

    _registry: Registry
    _claim_token: str | None = None
    _device_id: str | None = None
    _discovered_panel: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start hub setup by showing a pairing code, not an empty hub."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self._ensure_pairing_claim()
        return self._show_pairing_form()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish setup only after the phone has redeemed the code and connected."""
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

    async def async_step_zeroconf(self, discovery_info: Any) -> ConfigFlowResult:
        """Handle no-code phone/tablet discovery from Bonjour/mDNS."""
        props = dict(getattr(discovery_info, "properties", {}) or {})
        host = getattr(discovery_info, "host", None)
        port = getattr(discovery_info, "port", None)
        if not host or not port:
            return self.async_abort(reason="invalid_discovery")

        instance_id = _txt(props, "id") or getattr(discovery_info, "name", None) or f"{host}:{port}"
        await self.async_set_unique_id(f"discovered:{instance_id}")
        self._abort_if_unique_id_configured()

        self._discovered_panel = {
            "id": instance_id,
            "host": host,
            "port": port,
            "name": _txt(props, "name") or DEFAULT_PANEL_NAME,
            "model": _txt(props, "model") or "iOS device",
            "ios": _txt(props, "ios") or "unknown",
            "app_version": _txt(props, "version") or "unknown",
            "path": _txt(props, "path") or DISCOVERY_PAIRING_PATH,
        }
        self.context["title_placeholders"] = {"name": self._discovered_panel["name"]}
        return await self.async_step_confirm_discovered()

    async def async_step_confirm_discovered(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm that this is the phone/tablet to pair."""
        panel = self._discovered_panel
        if panel is None:
            return self.async_abort(reason="invalid_discovery")

        if user_input is None:
            return self.async_show_form(
                step_id="confirm_discovered",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "name": panel["name"],
                    "model": panel["model"],
                    "ios": panel["ios"],
                    "app_version": panel["app_version"],
                    "host": panel["host"],
                },
            )

        created_entry = bool(self._async_current_entries())
        ok = await self._push_claim_to_discovered_panel(panel)
        if not ok:
            return self.async_show_form(
                step_id="confirm_discovered",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
                description_placeholders={
                    "name": panel["name"],
                    "model": panel["model"],
                    "ios": panel["ios"],
                    "app_version": panel["app_version"],
                    "host": panel["host"],
                },
            )

        if not created_entry:
            return self.async_create_entry(title="OldPhoneKiosk", data={})
        return self.async_abort(reason="pairing_sent")

    def _ensure_pairing_claim(self) -> None:
        """Create the backend and one pairing-code claim for this config-flow run."""
        if self._claim_token is not None:
            return

        self._registry = ensure_backend(self.hass)
        claim = self._registry.create_claim(name=DEFAULT_PANEL_NAME)
        self._claim_token = claim.claim_token
        self._device_id = claim.device_id

    async def _push_claim_to_discovered_panel(self, panel: dict[str, Any]) -> bool:
        self._registry = ensure_backend(self.hass)
        claim = self._registry.create_claim(
            name=panel["name"], model=panel["model"], ios_version=panel["ios"]
        )
        payload = build_claim_payload(
            bridge_url=self._ha_base_url(),
            claim_token=claim.claim_token,
            name=panel["name"],
        )
        url = f"http://{panel['host']}:{panel['port']}{panel['path']}"
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status not in (200, 202, 204):
                    _LOGGER.warning("OldPhoneKiosk discovery push failed: %s", response.status)
                    return False
                return True
        except (TimeoutError, ClientError, OSError) as exc:
            _LOGGER.warning("Could not push OldPhoneKiosk claim to discovered app", exc_info=True)
            return False

    def _show_pairing_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        assert self._claim_token is not None
        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({}),
            errors=errors or {},
            description_placeholders={
                "pairing_code": self._claim_token,
            },
        )

    def _ha_base_url(self) -> str:
        try:
            return get_url(self.hass, prefer_external=False).rstrip("/")
        except Exception:  # noqa: BLE001 - fallback for tests/minimal HA config
            base = getattr(self.hass.config.api, "base_url", None) or ""
            return base.rstrip("/") or "http://homeassistant.local:8123"


def _txt(props: dict[Any, Any], key: str) -> str | None:
    value = props.get(key)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None:
        return None
    return str(value)
