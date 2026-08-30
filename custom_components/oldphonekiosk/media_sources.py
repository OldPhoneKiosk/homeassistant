"""Best-effort Home Assistant media-source helpers for OldPhoneKiosk."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

MEDIA_SOURCE_PREFIX = "media-source://"
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif")
PHOTO_WORDS = ("photo", "photos", "image", "images", "album", "albums", "google")


def is_media_source(value: str | None) -> bool:
    return bool(value and value.startswith(MEDIA_SOURCE_PREFIX))


def _child_id(child) -> str | None:
    return getattr(child, "media_content_id", None)


def _child_title(child) -> str:
    return (getattr(child, "title", None) or "").lower()


def _child_class(child) -> str:
    value = getattr(child, "media_class", None)
    raw = getattr(value, "value", value)
    return str(raw or "").lower()


def _looks_audio(child) -> bool:
    media_id = (_child_id(child) or "").lower()
    media_class = _child_class(child)
    return media_class in {"music", "track", "audio", "playlist"} or media_id.endswith(
        AUDIO_EXTENSIONS
    )


def _looks_photo_source(child) -> bool:
    media_id = (_child_id(child) or "").lower()
    title = _child_title(child)
    media_class = _child_class(child)
    can_expand = bool(getattr(child, "can_expand", False))
    return (
        media_class in {"album", "app", "directory", "folder", "image", "photo"}
        or media_id.endswith(IMAGE_EXTENSIONS)
        or any(word in media_id or word in title for word in PHOTO_WORDS)
        or can_expand
    )


async def async_media_source_options(
    hass: HomeAssistant,
    *,
    kind: str,
    max_depth: int = 2,
    max_items: int = 80,
) -> list[str]:
    """Return media-source ids suitable for HA select options.

    This is intentionally best-effort and conservative: HA installations vary a lot
    (local media, Google Photos, DLNA, camera providers). We include ids, not labels,
    because SelectEntity options are strings and the selected value is what iOS needs
    to receive later.
    """
    try:
        from homeassistant.components import media_source
    except Exception:  # noqa: BLE001
        return []

    options: list[str] = []
    seen: set[str | None] = set()

    def accepted(child) -> bool:
        return _looks_audio(child) if kind == "audio" else _looks_photo_source(child)

    async def browse(media_id: str | None, depth: int) -> None:
        if len(options) >= max_items or media_id in seen:
            return
        seen.add(media_id)
        try:
            node = await media_source.async_browse_media(hass, media_id)
        except Exception:  # noqa: BLE001
            return
        for child in getattr(node, "children", None) or []:
            child_id = _child_id(child)
            if not child_id or child_id in options:
                continue
            if accepted(child):
                options.append(child_id)
                if len(options) >= max_items:
                    return
            if depth < max_depth and getattr(child, "can_expand", False):
                await browse(child_id, depth + 1)

    await browse(None, 0)
    return options


async def async_resolve_media_source_url(
    hass: HomeAssistant, value: str | None
) -> str | None:
    """Resolve a media-source id to a playable URL for the iOS receiver."""
    if not is_media_source(value):
        return None
    try:
        from homeassistant.components import media_source

        media = await media_source.async_resolve_media(hass, value)
    except Exception:  # noqa: BLE001
        return None
    return getattr(media, "url", None)
