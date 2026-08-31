"""Frontend panel registration for OldPhoneKiosk."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DOMAIN

DATA_FRONTEND_REGISTERED = "frontend_registered"
PANEL_URL_PATH = "oldphonekiosk"
STATIC_URL = "/oldphonekiosk_static"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register the browser intercom panel once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_FRONTEND_REGISTERED) or getattr(hass, "http", None) is None:
        return
    dist_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [
            frontend.StaticPathConfig(
                STATIC_URL,
                str(dist_path),
                True,
            )
        ]
    )
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title="OldPhoneKiosk",
        sidebar_icon="mdi:phone-in-talk",
        webcomponent_name="oldphonekiosk-panel",
        module_url=f"{STATIC_URL}/oldphonekiosk-panel.js?v=0.1.30",
        embed_iframe=True,
        require_admin=False,
        config_panel_domain=DOMAIN,
    )
    domain_data[DATA_FRONTEND_REGISTERED] = True


async def async_unload_frontend(hass: HomeAssistant) -> None:
    """Remove the browser panel."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.pop(DATA_FRONTEND_REGISTERED, False):
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
