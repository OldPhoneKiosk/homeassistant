"""Pure frontend resource constants/helpers for OldPhoneKiosk.

This module intentionally has no Home Assistant imports so fast unit tests can
exercise cache-busting/resource matching without loading HA.
"""

from __future__ import annotations

STATIC_URL = "/oldphonekiosk_static"
INTERCOM_CARD_FILENAME = "oldphonekiosk-intercom-card.js"
INTERCOM_CARD_VERSION = "1.1.0"
INTERCOM_CARD_MODULE = f"{STATIC_URL}/{INTERCOM_CARD_FILENAME}?v={INTERCOM_CARD_VERSION}"
INTERCOM_CARD_URL_PREFIX = f"{STATIC_URL}/{INTERCOM_CARD_FILENAME}"


def is_intercom_card_resource_url(url: object) -> bool:
    """Return true for any cache-busted OldPhoneKiosk intercom card resource URL."""
    return isinstance(url, str) and url.startswith(INTERCOM_CARD_URL_PREFIX)


def is_intercom_card_resource(item: dict[str, object], url_key: str = "url") -> bool:
    """Return true for any cache-busted OldPhoneKiosk intercom card resource item."""
    return is_intercom_card_resource_url(item.get(url_key, ""))
