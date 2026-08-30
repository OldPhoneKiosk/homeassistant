"""Photo snapshot helpers for OldPhoneKiosk panel photo screens."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

CAMERA_SOURCE_PREFIX = "media-source://camera"


def async_camera_source_options(hass: HomeAssistant) -> list[str]:
    """Return camera entity ids that can feed the panel Photos screen."""
    camera_ids = sorted(hass.states.async_entity_ids("camera"))

    def score(entity_id: str) -> tuple[int, str]:
        state = hass.states.get(entity_id)
        attrs: dict[str, Any] = dict(state.attributes) if state else {}
        media_count = attrs.get("media_count")
        name = f"{entity_id} {attrs.get('friendly_name', '')}".lower()
        # Prefer Google Photos camera entities with imported media.
        if isinstance(media_count, int) and media_count > 0:
            return (0, entity_id)
        if "google" in name and "photo" in name:
            return (1, entity_id)
        if entity_id.endswith("_media"):
            return (2, entity_id)
        return (3, entity_id)

    return sorted(camera_ids, key=score)


def resolve_photo_camera_entity_id(
    hass: HomeAssistant, source: str | None
) -> str | None:
    """Resolve a panel photo_source into a HA camera entity id.

    Supported inputs:
    - camera.<entity>
    - media-source://camera/camera.<entity>
    - media-source://camera/<entity_without_camera_prefix>
    - media-source://camera root: best available camera, preferring imported Google Photos
    """
    value = (source or "").strip()
    if not value:
        return None
    if value.startswith("camera."):
        return value if hass.states.get(value) is not None else None
    if value.startswith(f"{CAMERA_SOURCE_PREFIX}/"):
        tail = value.removeprefix(f"{CAMERA_SOURCE_PREFIX}/").strip("/")
        candidates = [tail]
        if not tail.startswith("camera."):
            candidates.append(f"camera.{tail}")
        for candidate in candidates:
            if hass.states.get(candidate) is not None:
                return candidate
    if value == CAMERA_SOURCE_PREFIX:
        options = async_camera_source_options(hass)
        return options[0] if options else None
    return None


def async_photo_proxy_path(hass: HomeAssistant, source: str | None) -> str | None:
    """Return HA's tokenized camera proxy path for a photo source when available.

    This mirrors what Lovelace uses for dashboard camera cards. Camera
    ``entity_picture`` is an entity property, not a regular state attribute in
    modern HA, so read it from the loaded camera entity object.
    """
    entity_id = resolve_photo_camera_entity_id(hass, source)
    if not entity_id:
        return None
    from homeassistant.components import camera

    component = hass.data.get(camera.DOMAIN)
    camera_entity = component.get_entity(entity_id) if component is not None else None
    entity_picture = getattr(camera_entity, "entity_picture", None)
    if isinstance(entity_picture, str) and entity_picture:
        return entity_picture
    return None


async def async_get_photo_snapshot(
    hass: HomeAssistant, source: str | None
) -> tuple[bytes, str]:
    """Fetch image bytes/content-type for a panel photo source."""
    entity_id = resolve_photo_camera_entity_id(hass, source)
    if not entity_id:
        raise ValueError("photo_source is not a camera entity")

    from homeassistant.components import camera

    image = await camera.async_get_image(hass, entity_id, timeout=10)
    content = getattr(image, "content", None)
    if not content:
        raise ValueError(f"camera {entity_id} returned no image")
    content_type = getattr(image, "content_type", None) or "image/jpeg"
    return content, content_type
