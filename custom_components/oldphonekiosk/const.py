"""Constants for the OldPhoneKiosk integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "oldphonekiosk"

# Config entry keys
CONF_BRIDGE_URL = "bridge_url"
CONF_API_KEY = "api_key"

# Bridge HTTP contract
API_KEY_HEADER = "X-Bridge-Api-Key"
ENDPOINT_HEALTH = "/health"
ENDPOINT_DEVICES = "/api/devices"
ENDPOINT_DEVICE = "/api/devices/{device_id}"
ENDPOINT_COMMANDS = "/api/devices/{device_id}/commands"
ENDPOINT_MEDIA = "/api/devices/{device_id}/media"
ENDPOINT_PAIRING_START = "/api/pairing/start"
ENDPOINT_PAIRING_APPROVE = "/api/pairing/approve"

# Camera modes (mirror of Bridge CameraState)
CAMERA_MODES = ["off", "front", "back", "dual"]

# Pairing QR payload
PAIRING_PAYLOAD_VERSION = 1

# Polling
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)

# Panel screens (mirror of Bridge PanelScreen)
SCREEN_PHOTOS = "photos"
SCREEN_TASKS = "tasks"
SCREEN_HOME = "home"
SCREEN_SLEEP = "sleep"
SCREENS = [SCREEN_PHOTOS, SCREEN_TASKS, SCREEN_HOME, SCREEN_SLEEP]

# Commands (mirror of Bridge PanelCommand)
CMD_SHOW_PHOTOS = "show_photos"
CMD_SHOW_TASKS = "show_tasks"
CMD_SHOW_HOME = "show_home"
CMD_SLEEP = "sleep"
CMD_WAKE = "wake"

# Screen (select option) -> command used to reach it
SCREEN_TO_COMMAND = {
    SCREEN_PHOTOS: CMD_SHOW_PHOTOS,
    SCREEN_TASKS: CMD_SHOW_TASKS,
    SCREEN_HOME: CMD_SHOW_HOME,
    SCREEN_SLEEP: CMD_SLEEP,
}

MANUFACTURER = "OldPhoneKiosk"

# Services
SERVICE_REVOKE_PANEL = "revoke_panel"
SERVICE_PAIR_NEW_PANEL = "pair_new_panel"
SERVICE_SET_MEDIA = "set_media"
ATTR_DEVICE_ID = "device_id"  # Bridge device id (not the HA registry device id)
ATTR_NAME = "name"
ATTR_ROOM = "room"
ATTR_VIDEO_URL = "video_url"
ATTR_CAMERA_MODE = "camera_mode"
