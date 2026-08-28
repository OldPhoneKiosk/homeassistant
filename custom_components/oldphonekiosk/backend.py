"""Shared in-process backend bootstrap for OldPhoneKiosk."""

from __future__ import annotations

import secrets

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .http import DATA_REGISTRY, DATA_WS_TOKENS, async_register_http_views
from .registry import Registry
from .store import DeviceStore
from .wstoken import WsTokenService

DATA_HTTP_REGISTERED = "http_registered"


def ensure_backend(hass: HomeAssistant) -> Registry:
    """Create the in-process backend once per Home Assistant process.

    The backend may be needed before the config entry exists: the config flow can
    generate a QR claim, the phone redeems it via HTTP, and only then does the
    flow create the integration entry.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    registry = domain_data.get(DATA_REGISTRY)
    if registry is None:
        db_path = hass.config.path("oldphonekiosk/oldphonekiosk.db")
        store = DeviceStore(db_path)
        registry = Registry(store)
        registry.purge_expired_claims()
        domain_data[DATA_REGISTRY] = registry
        domain_data[DATA_WS_TOKENS] = WsTokenService(secrets.token_urlsafe(32))

    if getattr(hass, "http", None) is not None and not domain_data.get(DATA_HTTP_REGISTERED):
        async_register_http_views(hass)
        domain_data[DATA_HTTP_REGISTERED] = True

    return registry
