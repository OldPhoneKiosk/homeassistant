"""SQLite persistence for paired devices and their last-known state.

Only durable data lives here: device identity/metadata, the salted secret hash,
and the last reported state. Live WebSocket connections and ``online`` are kept
in memory by the Registry — after a restart every device loads back as offline
until it reconnects (see ADR 0002).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .models import (
    CameraState,
    Claim,
    DeviceCapabilities,
    DeviceMedia,
    DeviceState,
    IntercomState,
    PanelDevice,
    PanelScreen,
)

# Current schema version. Bump when adding a migration below.
SCHEMA_VERSION = 9

# Migration to version 1: the devices table. IF NOT EXISTS makes it idempotent so
# pre-migration databases (created before user_version tracking) upgrade cleanly.
_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS devices (
    device_id     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    room          TEXT,
    model         TEXT,
    ios_version   TEXT,
    capabilities  TEXT NOT NULL,
    secret_hash   TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    battery       INTEGER,
    brightness    REAL,
    screen        TEXT,
    camera        TEXT,
    app_version   TEXT,
    last_seen     TEXT
);
"""

# Migration to version 2: media config (video_url) + intercom state.
_MIGRATION_2 = """
ALTER TABLE devices ADD COLUMN video_url TEXT;
ALTER TABLE devices ADD COLUMN intercom TEXT;
"""

# Migration to version 3: one-time pairing claims (persisted, no secret column).
_MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS claims (
    claim_token TEXT PRIMARY KEY,
    device_id   TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
"""

# Migration to version 4: per-panel dashboard URL controlled from HA device page.
_MIGRATION_4 = """
ALTER TABLE devices ADD COLUMN dashboard_url TEXT;
"""

# Migration to version 5: HA-owned per-panel UI sources controlled from the device
# page: the tasks list/source, the photos feed/source, and the play_sound target.
_MIGRATION_5 = """
ALTER TABLE devices ADD COLUMN task_source TEXT;
ALTER TABLE devices ADD COLUMN photo_source TEXT;
ALTER TABLE devices ADD COLUMN sound TEXT;
"""
# Migration to version 6: HA-owned navigation controls.
_MIGRATION_6 = """
ALTER TABLE devices ADD COLUMN enabled_screens TEXT;
ALTER TABLE devices ADD COLUMN show_bottom_menu INTEGER;
"""
# Migration to version 7: HA-owned screen behavior controls.
_MIGRATION_7 = """
ALTER TABLE devices ADD COLUMN keep_screen_awake INTEGER;
ALTER TABLE devices ADD COLUMN show_connection_banner INTEGER;
ALTER TABLE devices ADD COLUMN dim_after_seconds REAL;
ALTER TABLE devices ADD COLUMN sleep_after_seconds REAL;
"""
# Migration to version 8: HA-owned task refresh cadence.
_MIGRATION_8 = """
ALTER TABLE devices ADD COLUMN task_refresh_seconds REAL;
"""
# Migration to version 9: HA-owned camera orientation override.
_MIGRATION_9 = """
ALTER TABLE devices ADD COLUMN camera_rotate_180 INTEGER;
"""


def _configure_connection(conn: sqlite3.Connection, db_path: str) -> None:
    """Apply production-oriented PRAGMAs.

    WAL only makes sense for on-disk databases; ``:memory:`` keeps its default
    journal. busy_timeout avoids spurious "database is locked" under concurrency.
    """
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring the schema up to ``SCHEMA_VERSION`` using PRAGMA user_version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema version {version} is newer than supported "
            f"{SCHEMA_VERSION}; upgrade the integration"
        )
    if version < 1:
        conn.executescript(_MIGRATION_1)
    if version < 2:
        conn.executescript(_MIGRATION_2)
    if version < 3:
        conn.executescript(_MIGRATION_3)
    if version < 4:
        conn.executescript(_MIGRATION_4)
    if version < 5:
        conn.executescript(_MIGRATION_5)
    if version < 6:
        conn.executescript(_MIGRATION_6)
    if version < 7:
        conn.executescript(_MIGRATION_7)
    if version < 8:
        conn.executescript(_MIGRATION_8)
    if version < 9:
        conn.executescript(_MIGRATION_9)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class DeviceStore:
    """Thin synchronous SQLite store. Local, fast; guarded by a lock."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        if db_path != ":memory:":
            Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            _configure_connection(self._conn, db_path)
            _migrate(self._conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- introspection (used by tests / diagnostics) -----------------

    def schema_version(self) -> int:
        with self._lock:
            return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def journal_mode(self) -> str:
        with self._lock:
            return str(self._conn.execute("PRAGMA journal_mode").fetchone()[0])

    def foreign_keys_enabled(self) -> bool:
        with self._lock:
            return bool(self._conn.execute("PRAGMA foreign_keys").fetchone()[0])

    # ------------------------------------------------------------------

    def upsert_device(self, device: PanelDevice, secret_hash: str) -> None:
        """Insert or replace a device row (identity + hash + last state)."""
        st = device.state
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, room, model, ios_version, capabilities,
                    secret_hash, created_at, battery, brightness, screen, camera,
                    app_version, last_seen, video_url, dashboard_url, intercom,
                    task_source, photo_source, sound, enabled_screens, show_bottom_menu,
                    keep_screen_awake, show_connection_banner, dim_after_seconds, sleep_after_seconds,
                    task_refresh_seconds, camera_rotate_180
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name=excluded.name, room=excluded.room, model=excluded.model,
                    ios_version=excluded.ios_version, capabilities=excluded.capabilities,
                    secret_hash=excluded.secret_hash
                """,
                (
                    device.device_id,
                    device.name,
                    device.room,
                    device.model,
                    device.ios_version,
                    json.dumps(
                        device.capabilities.model_dump()
                        if hasattr(device.capabilities, "model_dump")
                        else device.capabilities.dict()
                    ),
                    secret_hash,
                    device.created_at.isoformat(),
                    st.battery,
                    st.brightness,
                    st.screen.value if st.screen else None,
                    st.camera.value if st.camera else None,
                    st.app_version,
                    st.last_seen.isoformat() if st.last_seen else None,
                    device.media.video_url,
                    device.media.dashboard_url,
                    st.intercom.value if st.intercom else None,
                    device.media.task_source,
                    device.media.photo_source,
                    device.media.sound,
                    device.media.enabled_screens,
                    None
                    if device.media.show_bottom_menu is None
                    else int(device.media.show_bottom_menu),
                    None
                    if device.media.keep_screen_awake is None
                    else int(device.media.keep_screen_awake),
                    None
                    if device.media.show_connection_banner is None
                    else int(device.media.show_connection_banner),
                    device.media.dim_after_seconds,
                    device.media.sleep_after_seconds,
                    device.media.task_refresh_seconds,
                    None
                    if device.media.camera_rotate_180 is None
                    else int(device.media.camera_rotate_180),
                ),
            )
            self._conn.commit()

    def update_state(self, device_id: str, state: DeviceState) -> None:
        """Persist the last-known state columns for a device."""
        with self._lock:
            self._conn.execute(
                """
                UPDATE devices SET
                    battery=?, brightness=?, screen=?, camera=?,
                    intercom=?, app_version=?, last_seen=?
                WHERE device_id=?
                """,
                (
                    state.battery,
                    state.brightness,
                    state.screen.value if state.screen else None,
                    state.camera.value if state.camera else None,
                    state.intercom.value if state.intercom else None,
                    state.app_version,
                    state.last_seen.isoformat() if state.last_seen else None,
                    device_id,
                ),
            )
            self._conn.commit()

    def update_media(self, device_id: str, media: DeviceMedia) -> None:
        """Persist the full per-device media/UI config (HA is the source of truth)."""
        with self._lock:
            self._conn.execute(
                """
                UPDATE devices SET
                    video_url=?, dashboard_url=?, task_source=?, photo_source=?, sound=?,
                    enabled_screens=?, show_bottom_menu=?, keep_screen_awake=?,
                    show_connection_banner=?, dim_after_seconds=?, sleep_after_seconds=?,
                    task_refresh_seconds=?, camera_rotate_180=?
                WHERE device_id=?
                """,
                (
                    media.video_url,
                    media.dashboard_url,
                    media.task_source,
                    media.photo_source,
                    media.sound,
                    media.enabled_screens,
                    None
                    if media.show_bottom_menu is None
                    else int(media.show_bottom_menu),
                    None
                    if media.keep_screen_awake is None
                    else int(media.keep_screen_awake),
                    None
                    if media.show_connection_banner is None
                    else int(media.show_connection_banner),
                    media.dim_after_seconds,
                    media.sleep_after_seconds,
                    media.task_refresh_seconds,
                    None
                    if media.camera_rotate_180 is None
                    else int(media.camera_rotate_180),
                    device_id,
                ),
            )
            self._conn.commit()

    def delete_device(self, device_id: str) -> bool:
        """Delete a device row. Returns True if a row was removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM devices WHERE device_id=?", (device_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_secret_hash(self, device_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT secret_hash FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()
        return row["secret_hash"] if row else None

    def update_secret_hash(self, device_id: str, secret_hash: str) -> None:
        """Rotate a device's stored secret hash (used on claim redeem)."""
        with self._lock:
            self._conn.execute(
                "UPDATE devices SET secret_hash=? WHERE device_id=?",
                (secret_hash, device_id),
            )
            self._conn.commit()

    # ---- claims (one-time pairing tokens; no secret stored) ----------

    def insert_claim(self, claim: Claim) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO claims (claim_token, device_id, expires_at, created_at) "
                "VALUES (?,?,?,?)",
                (
                    claim.claim_token,
                    claim.device_id,
                    claim.expires_at.isoformat(),
                    claim.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def get_claim(self, claim_token: str) -> Claim | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM claims WHERE claim_token=?", (claim_token,)
            ).fetchone()
        return self._row_to_claim(row) if row else None

    def delete_claim(self, claim_token: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM claims WHERE claim_token=?", (claim_token,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def expired_claims(self, now: datetime) -> list[Claim]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM claims WHERE expires_at <= ?", (now.isoformat(),)
            ).fetchall()
        return [self._row_to_claim(row) for row in rows]

    @staticmethod
    def _row_to_claim(row: sqlite3.Row) -> Claim:
        return Claim(
            claim_token=row["claim_token"],
            device_id=row["device_id"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def load_devices(self) -> list[PanelDevice]:
        """Load all devices as offline PanelDevice objects (no secret)."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM devices").fetchall()
        return [self._row_to_device(row) for row in rows]

    @staticmethod
    def _row_to_device(row: sqlite3.Row) -> PanelDevice:
        keys = row.keys()
        intercom_raw = row["intercom"] if "intercom" in keys else None
        video_url = row["video_url"] if "video_url" in keys else None
        dashboard_url = row["dashboard_url"] if "dashboard_url" in keys else None
        task_source = row["task_source"] if "task_source" in keys else None
        photo_source = row["photo_source"] if "photo_source" in keys else None
        sound = row["sound"] if "sound" in keys else None
        enabled_screens = row["enabled_screens"] if "enabled_screens" in keys else None
        show_bottom_menu = (
            row["show_bottom_menu"] if "show_bottom_menu" in keys else None
        )
        keep_screen_awake = (
            row["keep_screen_awake"] if "keep_screen_awake" in keys else None
        )
        show_connection_banner = (
            row["show_connection_banner"] if "show_connection_banner" in keys else None
        )
        dim_after_seconds = (
            row["dim_after_seconds"] if "dim_after_seconds" in keys else None
        )
        sleep_after_seconds = (
            row["sleep_after_seconds"] if "sleep_after_seconds" in keys else None
        )
        task_refresh_seconds = (
            row["task_refresh_seconds"] if "task_refresh_seconds" in keys else None
        )
        camera_rotate_180 = (
            row["camera_rotate_180"] if "camera_rotate_180" in keys else None
        )
        state = DeviceState(
            online=False,  # never persisted true; requires a live connection
            battery=row["battery"],
            brightness=row["brightness"],
            screen=PanelScreen(row["screen"]) if row["screen"] else None,
            camera=CameraState(row["camera"]) if row["camera"] else CameraState.OFF,
            intercom=IntercomState(intercom_raw)
            if intercom_raw
            else IntercomState.IDLE,
            app_version=row["app_version"],
            last_seen=_dt(row["last_seen"]),
        )
        return PanelDevice(
            device_id=row["device_id"],
            name=row["name"],
            room=row["room"],
            model=row["model"],
            ios_version=row["ios_version"],
            capabilities=DeviceCapabilities(**json.loads(row["capabilities"])),
            state=state,
            media=DeviceMedia(
                video_url=video_url,
                dashboard_url=dashboard_url,
                task_source=task_source,
                photo_source=photo_source,
                sound=sound,
                enabled_screens=enabled_screens,
                show_bottom_menu=None
                if show_bottom_menu is None
                else bool(show_bottom_menu),
                keep_screen_awake=None
                if keep_screen_awake is None
                else bool(keep_screen_awake),
                show_connection_banner=None
                if show_connection_banner is None
                else bool(show_connection_banner),
                dim_after_seconds=dim_after_seconds,
                sleep_after_seconds=sleep_after_seconds,
                task_refresh_seconds=task_refresh_seconds,
                camera_rotate_180=None
                if camera_rotate_180 is None
                else bool(camera_rotate_180),
            ),
            created_at=_dt(row["created_at"]) or datetime.now().astimezone(),
        )
