from __future__ import annotations

from custom_components.oldphonekiosk.photos import (
    async_camera_source_options,
    resolve_photo_camera_entity_id,
)


def test_camera_source_options_prefers_camera_with_imported_media(hass):
    hass.states.async_set("camera.empty_media", "idle", {"media_count": 0})
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})

    assert async_camera_source_options(hass)[0] == "camera.google_photos_media"


def test_resolve_photo_camera_entity_accepts_direct_camera(hass):
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})

    assert (
        resolve_photo_camera_entity_id(hass, "camera.google_photos_media")
        == "camera.google_photos_media"
    )


def test_resolve_photo_camera_entity_accepts_media_source_camera_child(hass):
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})

    assert (
        resolve_photo_camera_entity_id(
            hass, "media-source://camera/camera.google_photos_media"
        )
        == "camera.google_photos_media"
    )


def test_resolve_photo_camera_root_chooses_best_camera(hass):
    hass.states.async_set("camera.other", "idle", {})
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})

    assert (
        resolve_photo_camera_entity_id(hass, "media-source://camera")
        == "camera.google_photos_media"
    )
