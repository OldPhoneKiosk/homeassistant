"""Frontend asset registration for OldPhoneKiosk Lovelace cards."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant

from .const import DOMAIN

DATA_FRONTEND_REGISTERED = "frontend_registered"
STATIC_URL = "/oldphonekiosk_static"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register OldPhoneKiosk static frontend assets once.

    This intentionally does not register a Home Assistant sidebar panel. The
    intercom UI is a custom Lovelace card loaded from the static asset path.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_FRONTEND_REGISTERED) or getattr(hass, "http", None) is None:
        return
    dist_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [frontend.StaticPathConfig(STATIC_URL, str(dist_path), True)]
    )
    domain_data[DATA_FRONTEND_REGISTERED] = True


async def async_unload_frontend(hass: HomeAssistant) -> None:
    """Mark frontend assets as unloaded.

    Home Assistant does not expose a stable remove-static-path API for custom
    integrations; assets stop being re-registered after the final entry unloads.
    """
    hass.data.setdefault(DOMAIN, {}).pop(DATA_FRONTEND_REGISTERED, None)
