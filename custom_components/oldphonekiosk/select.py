"""Per-panel select entities for OldPhoneKiosk.

Home Assistant is the source of truth for every panel UI source. Instead of
typing raw strings, the user picks from HA's own resources:

* Dashboard  — a Lovelace dashboard URL (discovered from HA, plus defaults).
* Task list  — a ``todo.*`` entity id (discovered from HA states).
* Sound      — a HA media-source audio file or iOS system-sound id.
* Photo source — a HA media-source album/folder/source (best-effort discovery, e.g. Google Photos).

Each select applies immediately (``async_set_panel_ui`` / ``async_set_sound``) and
writes state. The matching ``Custom …`` text entities remain for advanced/manual
values (a full URL, a bundled sound name, an id HA cannot enumerate).
"""

from __future__ import annotations

import logging
from itertools import combinations
from typing import ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .calendar import CALENDAR_VIEWS, async_push_calendar_snapshot, calendar_entity_ids
from .const import DOMAIN, SCREEN_CALENDAR, SCREEN_DASHBOARD, SCREEN_PHOTOS, SCREEN_TO_COMMAND, SCREENS
from .coordinator import OldPhoneKioskCoordinator
from .entity import OldPhoneKioskEntity
from .media_sources import async_media_source_options
from .photos import async_camera_source_options
from .tasks import async_push_task_snapshot

_LOGGER = logging.getLogger(__name__)

# Common iOS system-sound ids offered as ready picks. The value stored/sent is the
# id itself (iOS maps a numeric ``sound`` to a system sound). A bundled name or a
# remote URL can still be set through the "Custom sound" text entity.
SOUND_PRESET_IDS = ["1007", "1013", "1016", "1057", "1104", "1304"]

# Fallback dashboard paths when HA exposes no discoverable Lovelace dashboards.
DEFAULT_DASHBOARD_URLS = ["/lovelace", "/lovelace/default_view"]


def _absolute_dashboard_url(hass: HomeAssistant, dashboard_url: str) -> str:
    """Return a phone-loadable absolute dashboard URL when HA knows its base URL."""
    url = dashboard_url.strip()
    if not url or "://" in url:
        return url

    base_url = hass.config.internal_url or hass.config.external_url
    if base_url:
        base = base_url.rstrip("/")
        path = url if url.startswith("/") else f"/{url}"
        return f"{base}{path}"
    return url


def _todo_entities(hass: HomeAssistant) -> list[str]:
    """Return the ``todo.*`` entity ids currently known to HA."""
    return sorted(hass.states.async_entity_ids("todo"))


def _dashboard_urls(hass: HomeAssistant) -> list[str]:
    """Best-effort discovery of Lovelace dashboard URL paths.

    Reads the Lovelace registry from ``hass.data`` across HA versions (dataclass or
    dict). Returns ``[]`` when nothing is discoverable so the caller can fall back.
    """
    data = hass.data.get("lovelace")
    dashboards = None
    if data is not None:
        dashboards = getattr(data, "dashboards", None)
        if dashboards is None and isinstance(data, dict):
            dashboards = data.get("dashboards")
    urls: list[str] = []
    if isinstance(dashboards, dict):
        for url_path in dashboards:
            path = _dashboard_base_path(url_path)
            if path not in urls:
                urls.append(path)
    return urls


def _dashboard_base_path(url_path: str | None) -> str:
    """Return the frontend path for a Lovelace dashboard.

    Home Assistant's default dashboard lives under ``/lovelace``. Additional
    dashboards use their configured ``url_path`` as a top-level frontend path,
    e.g. a dashboard with ``url_path=dashboard-oscar`` is served at
    ``/dashboard-oscar``, not ``/lovelace/dashboard-oscar``.
    """
    if url_path in (None, "lovelace"):
        return "/lovelace"
    path = str(url_path).strip("/")
    return f"/{path}"


def _looks_like_default_lovelace_home(url: str) -> bool:
    """Return true for Lovelace root/home URLs that commonly resolve to /lovelace/0."""
    normalized = url.strip().rstrip("/")
    return normalized.endswith(("/lovelace", "/lovelace/0"))


async def _dashboard_view_urls(hass: HomeAssistant) -> list[str]:
    """Best-effort dashboard + view/tab URLs from loaded Lovelace configs."""
    data = hass.data.get("lovelace")
    dashboards = None
    if data is not None:
        dashboards = getattr(data, "dashboards", None)
        if dashboards is None and isinstance(data, dict):
            dashboards = data.get("dashboards")
    if not isinstance(dashboards, dict):
        return []

    urls: list[str] = []
    for url_path, dashboard in dashboards.items():
        base_path = _dashboard_base_path(url_path)
        async_load = getattr(dashboard, "async_load", None)
        if async_load is None:
            continue
        try:
            config = await async_load(False)
        except Exception:
            _LOGGER.debug("Could not load Lovelace dashboard config", exc_info=True)
            continue
        views = config.get("views", []) if isinstance(config, dict) else []
        if not isinstance(views, list):
            continue
        for index, view in enumerate(views):
            if not isinstance(view, dict):
                continue
            view_path = str(view.get("path") or index).strip("/")
            if not view_path:
                continue
            url = f"{base_path}/{view_path}"
            if url not in urls:
                urls.append(url)
    return urls


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OldPhoneKioskCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices = set(coordinator.data or {})

    def _entities(device_ids: set[str]):
        entities: list[SelectEntity] = []
        for device_id in device_ids:
            entities.append(ScreenSelect(coordinator, device_id))
            entities.append(DefaultScreenSelect(coordinator, device_id))
            entities.append(VisibleScreensSelect(coordinator, device_id))
            entities.append(DashboardSelect(coordinator, device_id))
            entities.append(TaskListSelect(coordinator, device_id))
            entities.append(SoundSelect(coordinator, device_id))
            entities.append(PhotoSourceSelect(coordinator, device_id))
            entities.append(CalendarSourcesSelect(coordinator, device_id))
            entities.append(CalendarViewSelect(coordinator, device_id))
        return entities

    async_add_entities(_entities(known_devices))

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data or {}) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(_entities(new_devices))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class ScreenSelect(OldPhoneKioskEntity, SelectEntity):
    _attr_translation_key = "screen"
    _attr_options = SCREENS

    def __init__(self, coordinator, device_id) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_screen"
        self._attr_name = "Screen"

    @property
    def current_option(self) -> str | None:
        device = self.device
        if device is None or device.screen not in SCREENS:
            return None
        return device.screen

    async def async_select_option(self, option: str) -> None:
        if option == SCREEN_CALENDAR:
            sources = getattr(self.device, "calendar_sources", None) or ""
            view = getattr(self.device, "calendar_view", None) or "month"
            if sources:
                await async_push_calendar_snapshot(
                    self.hass,
                    self.coordinator.client,
                    self._device_id,
                    sources,
                    view=view,
                    show=True,
                )
            else:
                await self.coordinator.client.async_send_command(
                    self._device_id,
                    SCREEN_TO_COMMAND[option],
                    params={"items": "[]", "view": view, "show": "true"},
                )
        else:
            command = SCREEN_TO_COMMAND[option]
            await self.coordinator.client.async_send_command(self._device_id, command)
        await self.coordinator.async_request_refresh()


class DefaultScreenSelect(OldPhoneKioskEntity, SelectEntity):
    """Pick the screen the iPad returns to after launch/config changes."""

    _attr_translation_key = "default_screen"
    _attr_name = "Default screen"
    _attr_icon = "mdi:tablet-dashboard"
    _attr_options = [s for s in SCREENS if s != "sleep"]

    def __init__(self, coordinator, device_id) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_default_screen"
        self._selected: str | None = None

    @property
    def current_option(self) -> str | None:
        return self._selected or "dashboard"

    async def async_select_option(self, option: str) -> None:
        self._selected = option
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, default_screen=option
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class VisibleScreensSelect(OldPhoneKioskEntity, SelectEntity):
    """Pick the enabled screen set exposed in the app's bottom navigation."""

    _attr_translation_key = "visible_screens"
    _attr_name = "Visible screens"
    _attr_icon = "mdi:view-dashboard-outline"
    _attr_options: ClassVar[list[str]] = [
        "dashboard",
        "tasks,dashboard",
        "photos,tasks,dashboard",
        "photos,tasks,dashboard,calendar",
        "photos,tasks,dashboard,calendar,sleep",
    ]

    def __init__(self, coordinator, device_id) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_visible_screens"
        self._selected: str | None = None

    @property
    def current_option(self) -> str | None:
        if self._selected:
            return self._selected
        device = self.device
        stored = getattr(device, "enabled_screens", None) if device else None
        return stored or "photos,tasks,dashboard"

    async def async_select_option(self, option: str) -> None:
        screens = [screen.strip() for screen in option.split(",") if screen.strip()]
        self._selected = ",".join(screens)
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, enabled_screens=screens
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._selected = None
        super()._handle_coordinator_update()


class _SourceSelect(OldPhoneKioskEntity, SelectEntity):
    """Base for a per-panel source select backed by the device media config.

    Options come from ``_discovered()`` (HA resources) plus any extra options set by
    async discovery, and always include the current stored value so HA never warns
    about a ``current_option`` outside ``options``.

    The chosen value is applied optimistically (``_selected``) so the select shows it
    immediately, exactly like the "Custom …" text entities — the coordinator refresh
    is debounced and may not round-trip before the user looks. A real refresh
    realigns ``_selected`` to the device's persisted value.
    """

    _key = ""

    def __init__(self, coordinator: OldPhoneKioskCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{self._key}_select"
        self._discovered_extra: list[str] = []
        self._selected: str | None = None

    def _discovered(self) -> list[str]:  # pragma: no cover - overridden
        return []

    def _stored(self) -> str | None:  # pragma: no cover - overridden
        return None

    @property
    def options(self) -> list[str]:
        opts: list[str] = []
        for option in [*self._discovered(), *self._discovered_extra]:
            if option and option not in opts:
                opts.append(option)
        for current in (self._stored(), self._selected):
            if current and current not in opts:
                opts.append(current)
        return opts

    @property
    def current_option(self) -> str | None:
        return self._selected or self._stored() or None

    @callback
    def _handle_coordinator_update(self) -> None:
        # Realign the optimistic pick to the device's persisted value on a real
        # refresh (HA is the source of truth). During revoke the HA entity may
        # already be removed from the entity registry; avoid writing a stale
        # select state after its backing device is gone.
        if self.device is None:
            return
        self._selected = self._stored()
        super()._handle_coordinator_update()

    def _apply_selected(self, option: str) -> None:
        self._selected = option or None
        self.async_write_ha_state()


class DashboardSelect(_SourceSelect):
    """Pick the Lovelace dashboard the panel shows on its ``dashboard`` screen."""

    _key = "dashboard"
    _attr_translation_key = "dashboard"
    _attr_name = "Dashboard"
    _attr_icon = "mdi:view-dashboard"

    @property
    def options(self) -> list[str]:
        """Prefer concrete Lovelace view URLs over dashboard roots.

        Home Assistant redirects the default dashboard root ``/lovelace`` to the
        first view (often ``/lovelace/0`` / Home). When concrete view/tab URLs
        are known, expose only those so a HA picker change cannot send the
        phone back to Home by accident.
        """
        opts: list[str] = []
        source = self._discovered_extra or self._discovered()
        for option in source:
            if option and option not in opts:
                opts.append(option)
        for current in (self._stored(), self._selected):
            if (
                current
                and current not in opts
                and not (
                    self._discovered_extra
                    and _looks_like_default_lovelace_home(current)
                )
            ):
                opts.append(current)
        return opts

    def _discovered(self) -> list[str]:
        return _dashboard_urls(self.hass) or DEFAULT_DASHBOARD_URLS

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_refresh_views()

    async def _async_refresh_views(self) -> None:
        self._discovered_extra = await _dashboard_view_urls(self.hass)
        self.async_write_ha_state()

    def _stored(self) -> str | None:
        device = self.device
        return device.dashboard_url if device else None

    async def async_select_option(self, option: str) -> None:
        dashboard_url = _absolute_dashboard_url(self.hass, option)
        await self.coordinator.client.async_set_panel_ui(
            self._device_id,
            default_screen=SCREEN_DASHBOARD,
            dashboard_url=dashboard_url,
        )
        self._apply_selected(dashboard_url)
        await self.coordinator.async_request_refresh()


class TaskListSelect(_SourceSelect):
    """Pick the HA to-do list (``todo.*`` entity) feeding the tasks screen."""

    _key = "task_list"
    _attr_translation_key = "task_list"
    _attr_name = "Task list"
    _attr_icon = "mdi:format-list-checks"

    def _discovered(self) -> list[str]:
        return _todo_entities(self.hass)

    def _stored(self) -> str | None:
        device = self.device
        return device.task_source if device else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, task_source=option
        )
        await async_push_task_snapshot(
            self.hass, self.coordinator.client, self._device_id, option, show=True
        )
        self._apply_selected(option)
        await self.coordinator.async_request_refresh()


class SoundSelect(_SourceSelect):
    """Pick a HA media-source audio file or iOS system-sound id."""

    _key = "sound"
    _attr_translation_key = "sound"
    _attr_name = "Sound"
    _attr_icon = "mdi:music-note"

    def _discovered(self) -> list[str]:
        return list(SOUND_PRESET_IDS)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_refresh_sources()

    async def _async_refresh_sources(self) -> None:
        self._discovered_extra = await async_media_source_options(
            self.hass, kind="audio"
        )
        self.async_write_ha_state()

    def _stored(self) -> str | None:
        device = self.device
        return device.sound if device else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.async_set_sound(self._device_id, option or None)
        self._apply_selected(option)
        await self.coordinator.async_request_refresh()


class PhotoSourceSelect(_SourceSelect):
    """Pick the photo source/album feeding the panel's photos screen.

    Options are discovered from ``media_source`` (e.g. Google Photos albums, local
    media folders/images) when available; otherwise only the current value is offered and the
    "Custom photo source" text entity is used for manual entry.
    """

    _key = "photo_source"
    _attr_translation_key = "photo_source"
    _attr_name = "Photo source"
    _attr_icon = "mdi:image-multiple"

    @property
    def options(self) -> list[str]:
        opts: list[str] = []
        for option in [
            *async_camera_source_options(self.hass),
            *self._discovered(),
            *self._discovered_extra,
        ]:
            if option and option not in opts:
                opts.append(option)
        for current in (self._stored(), self._selected):
            if current and current not in opts:
                opts.append(current)
        return opts

    def _stored(self) -> str | None:
        device = self.device
        return device.photo_source if device else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._handle_state_changed)
        )
        await self._async_refresh_sources()

    @callback
    def _handle_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if isinstance(entity_id, str) and entity_id.startswith("camera."):
            self.async_write_ha_state()

    async def _async_refresh_sources(self) -> None:
        """Populate options from ``media_source`` albums/folders (best-effort)."""
        media_options = await async_media_source_options(self.hass, kind="photos")
        self._discovered_extra = [
            *async_camera_source_options(self.hass),
            *media_options,
        ]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, default_screen=SCREEN_PHOTOS, photo_source=option
        )
        self._apply_selected(option)
        await self.coordinator.client.async_send_command(
            self._device_id, SCREEN_TO_COMMAND[SCREEN_PHOTOS]
        )
        await self.coordinator.async_request_refresh()


class CalendarSourcesSelect(_SourceSelect):
    """Pick one or more HA calendar entities feeding the calendar screen."""

    _key = "calendar_sources"
    _attr_translation_key = "calendar_sources"
    _attr_name = "Calendar sources"
    _attr_icon = "mdi:calendar-multiple"

    def _discovered(self) -> list[str]:
        entities = calendar_entity_ids(self.hass)
        options = list(entities)
        for size in range(2, min(len(entities), 4) + 1):
            options.extend(",".join(combo) for combo in combinations(entities, size))
        return options

    def _stored(self) -> str | None:
        device = self.device
        return getattr(device, "calendar_sources", None) if device else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._handle_state_changed)
        )

    @callback
    def _handle_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if isinstance(entity_id, str) and entity_id.startswith("calendar."):
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        view = getattr(self.device, "calendar_view", None) or "month"
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, default_screen=SCREEN_CALENDAR, calendar_sources=option, calendar_view=view
        )
        await async_push_calendar_snapshot(
            self.hass, self.coordinator.client, self._device_id, option, view=view, show=True
        )
        self._apply_selected(option)
        await self.coordinator.async_request_refresh()


class CalendarViewSelect(_SourceSelect):
    """Pick the default calendar layout shown on the iPad."""

    _key = "calendar_view"
    _attr_translation_key = "calendar_view"
    _attr_name = "Calendar view"
    _attr_icon = "mdi:calendar-month"
    _attr_options = CALENDAR_VIEWS

    def _discovered(self) -> list[str]:
        return list(CALENDAR_VIEWS)

    def _stored(self) -> str | None:
        device = self.device
        return getattr(device, "calendar_view", None) if device else None

    @property
    def current_option(self) -> str | None:
        return self._selected or self._stored() or "month"

    async def async_select_option(self, option: str) -> None:
        sources = getattr(self.device, "calendar_sources", None) or ""
        await self.coordinator.client.async_set_panel_ui(
            self._device_id, default_screen=SCREEN_CALENDAR, calendar_sources=sources, calendar_view=option
        )
        if sources:
            await async_push_calendar_snapshot(
                self.hass, self.coordinator.client, self._device_id, sources, view=option, show=True
            )
        self._apply_selected(option)
        await self.coordinator.async_request_refresh()
