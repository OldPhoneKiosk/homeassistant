"""Frontend asset registration for OldPhoneKiosk Lovelace cards."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.const import CONF_ID, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from .const import DOMAIN

try:
    from homeassistant.components.lovelace.const import CONF_RESOURCE_TYPE_WS
    from homeassistant.components.lovelace.const import DOMAIN as LOVELACE_DOMAIN
except ImportError:  # pragma: no cover - older/newer HA compatibility fallback
    CONF_RESOURCE_TYPE_WS = "res_type"
    LOVELACE_DOMAIN = "lovelace"

_LOGGER = logging.getLogger(__name__)

DATA_FRONTEND_REGISTERED = "frontend_registered"
DATA_LOVELACE_RESOURCE_REGISTERED = "lovelace_resource_registered"
STATIC_URL = "/oldphonekiosk_static"
INTERCOM_CARD_MODULE = f"{STATIC_URL}/oldphonekiosk-intercom-card.js?v=0.1.42"
INTERCOM_CARD_URL_PREFIX = f"{STATIC_URL}/oldphonekiosk-intercom-card.js"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register OldPhoneKiosk static frontend assets and Lovelace card resource.

    This intentionally does not register a Home Assistant sidebar panel. The
    intercom UI is a custom Lovelace card that can sit next to the camera card.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if getattr(hass, "http", None) is None:
        return
    if not domain_data.get(DATA_FRONTEND_REGISTERED):
        dist_path = Path(__file__).parent / "www"
        await hass.http.async_register_static_paths(
            [frontend.StaticPathConfig(STATIC_URL, str(dist_path), True)]
        )
        domain_data[DATA_FRONTEND_REGISTERED] = True
    await async_ensure_lovelace_resource(hass)


async def async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    """Best-effort auto-add of the Lovelace card resource in storage mode."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_LOVELACE_RESOURCE_REGISTERED):
        return
    lovelace_data: dict[str, Any] | None = hass.data.get(LOVELACE_DOMAIN)
    resources = lovelace_data.get("resources") if lovelace_data else None
    if resources is None:
        _LOGGER.debug("Lovelace resources are not available yet; card asset remains manually addable")
        return
    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True
    existing = list(resources.async_items() or [])
    for item in existing:
        url = item.get(CONF_URL, "")
        if isinstance(url, str) and url.startswith(INTERCOM_CARD_URL_PREFIX):
            if url != INTERCOM_CARD_MODULE:
                update_item = getattr(resources, "async_update_item", None)
                item_id = item.get(CONF_ID)
                if update_item is not None and item_id is not None:
                    await update_item(item_id, {CONF_RESOURCE_TYPE_WS: "module", CONF_URL: INTERCOM_CARD_MODULE})
                else:
                    _LOGGER.info(
                        "OldPhoneKiosk card resource is stale (%s); update it manually to %s",
                        url,
                        INTERCOM_CARD_MODULE,
                    )
            domain_data[DATA_LOVELACE_RESOURCE_REGISTERED] = True
            return
    create_item = getattr(resources, "async_create_item", None)
    if create_item is None:
        _LOGGER.info(
            "Lovelace is likely in YAML mode; add the OldPhoneKiosk card resource manually: %s",
            INTERCOM_CARD_MODULE,
        )
        return
    await create_item({CONF_RESOURCE_TYPE_WS: "module", CONF_URL: INTERCOM_CARD_MODULE})
    domain_data[DATA_LOVELACE_RESOURCE_REGISTERED] = True


async def async_unload_frontend(hass: HomeAssistant) -> None:
    """Mark frontend assets as unloaded.

    Home Assistant does not expose a stable remove-static-path API for custom
    integrations; assets stop being re-registered after the final entry unloads.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.pop(DATA_FRONTEND_REGISTERED, None)
    domain_data.pop(DATA_LOVELACE_RESOURCE_REGISTERED, None)
