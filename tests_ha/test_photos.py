from __future__ import annotations

from custom_components.oldphonekiosk.photos import (
    async_camera_source_options,
    async_photo_proxy_path,
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


class FakeCameraEntity:
    entity_picture = "/api/camera_proxy/camera.google_photos_media?token=abc"


class FakeCameraComponent:
    def get_entity(self, entity_id):
        if entity_id == "camera.google_photos_media":
            return FakeCameraEntity()
        return None


def test_photo_proxy_path_uses_camera_entity_picture_token(hass):
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})
    hass.data["camera"] = FakeCameraComponent()

    assert (
        async_photo_proxy_path(hass, "camera.google_photos_media")
        == "/api/camera_proxy/camera.google_photos_media?token=abc"
    )


def test_photo_proxy_path_without_loaded_camera_entity_falls_back_to_server_snapshot(
    hass,
):
    hass.states.async_set("camera.google_photos_media", "idle", {"media_count": 3})

    assert async_photo_proxy_path(hass, "camera.google_photos_media") is None
