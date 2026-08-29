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
ENDPOINT_STREAM_START = "/api/devices/{device_id}/stream/start"
ENDPOINT_STREAM_STOP = "/api/devices/{device_id}/stream/stop"
ENDPOINT_PAIRING_START = "/api/pairing/start"
ENDPOINT_PAIRING_APPROVE = "/api/pairing/approve"
ENDPOINT_CLAIM_CREATE = "/api/pairing/claim/create"

# Camera modes (mirror of Bridge CameraState)
CAMERA_MODES = ["off", "front", "back", "dual"]

# Pairing payload version (shared with the iOS PairingPayload schema)
PAIRING_PAYLOAD_VERSION = 1

# One-time pairing code: a numeric claim token the user types into the app as the
# manual backup to Wi‑Fi (zeroconf) discovery. QR pairing has been removed.
PAIRING_CODE_LENGTH = 10

# Polling
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)

# Panel screens (mirror of Bridge PanelScreen)
SCREEN_PHOTOS = "photos"
SCREEN_TASKS = "tasks"
SCREEN_HOME = "home"
SCREEN_ACTIONS = "actions"
SCREEN_DASHBOARD = "dashboard"
SCREEN_SLEEP = "sleep"
SCREENS = [SCREEN_PHOTOS, SCREEN_TASKS, SCREEN_DASHBOARD, SCREEN_SLEEP]

# Commands (mirror of Bridge PanelCommand)
CMD_SHOW_PHOTOS = "show_photos"
CMD_SHOW_TASKS = "show_tasks"
CMD_SHOW_HOME = "show_home"
CMD_SHOW_ACTIONS = "show_actions"
CMD_SHOW_DASHBOARD = "show_dashboard"
CMD_CONFIGURE_UI = "configure_ui"
CMD_CONFIGURE_TASKS = "configure_tasks"
CMD_SLEEP = "sleep"
CMD_WAKE = "wake"
CMD_BEEP = "beep"
CMD_PLAY_SOUND = "play_sound"
CMD_SET_BRIGHTNESS = "set_brightness"
CMD_SET_VOLUME = "set_volume"
CMD_START_INTERCOM = "start_intercom"
CMD_STOP_INTERCOM = "stop_intercom"

# Screen (select option) -> command used to reach it
SCREEN_TO_COMMAND = {
    SCREEN_PHOTOS: CMD_SHOW_PHOTOS,
    SCREEN_TASKS: CMD_SHOW_TASKS,
    SCREEN_HOME: CMD_SHOW_HOME,
    SCREEN_ACTIONS: CMD_SHOW_ACTIONS,
    SCREEN_DASHBOARD: CMD_SHOW_DASHBOARD,
    SCREEN_SLEEP: CMD_SLEEP,
}

MANUFACTURER = "OldPhoneKiosk"

# Services
SERVICE_REVOKE_PANEL = "revoke_panel"
SERVICE_PAIR_NEW_PANEL = "pair_new_panel"
SERVICE_SET_MEDIA = "set_media"
SERVICE_SET_PANEL_UI = "set_panel_ui"
SERVICE_START_STREAM = "start_stream"
SERVICE_STOP_STREAM = "stop_stream"
SERVICE_BEEP = "beep"
SERVICE_PLAY_SOUND = "play_sound"
SERVICE_START_INTERCOM = "start_intercom"
SERVICE_STOP_INTERCOM = "stop_intercom"
ATTR_DEVICE_ID = "device_id"  # Bridge device id (not the HA registry device id)
ATTR_NAME = "name"
ATTR_ROOM = "room"
ATTR_VIDEO_URL = "video_url"
ATTR_CAMERA_MODE = "camera_mode"
ATTR_DEFAULT_SCREEN = "default_screen"
ATTR_ENABLED_SCREENS = "enabled_screens"
ATTR_SHOW_BOTTOM_MENU = "show_bottom_menu"
ATTR_DASHBOARD_URL = "dashboard_url"
ATTR_TASK_SOURCE = "task_source"
ATTR_PHOTO_SOURCE = "photo_source"
ATTR_SOUND = "sound"
ATTR_SOUND_URL = "url"
ATTR_AUDIO_URL = "audio_url"
ATTR_STREAM_URL = "stream_url"
ATTR_INTERCOM_MODE = "mode"
