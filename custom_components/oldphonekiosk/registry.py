"""Registry: pairing, devices, live WebSocket connections, commands.

Durable data (devices, secret hash, last-known state) is persisted to SQLite via
``DeviceStore``; live WebSocket connections and ``online`` are kept in memory, so a
restart reloads devices as offline without re-pairing (see ADR 0002). A device
connection is represented abstractly so the registry can be unit-tested without a
real WebSocket: any object with async ``send_json`` works.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import timedelta
from typing import Protocol

from .models import (
    COMMAND_TARGET_SCREEN,
    Claim,
    Command,
    CommandResult,
    DeviceCapabilities,
    DeviceState,
    NewDeviceCredentials,
    PairingRequest,
    PanelCommand,
    PanelDevice,
    utcnow,
)
from .security import hash_secret, verify_secret
from .store import DeviceStore

_UNSET = object()


class DeviceConnection(Protocol):
    """Minimal interface a device transport must satisfy."""

    async def send_json(self, data: dict) -> None: ...


class PairingError(Exception):
    """Raised when a pairing code is invalid or expired."""


class UnknownDeviceError(Exception):
    """Raised when a device_id is not registered."""


class DeviceOfflineError(Exception):
    """Raised when a command targets a device without a live connection."""


class AuthError(Exception):
    """Raised when a device secret does not match."""


class ClaimError(Exception):
    """Raised when a pairing claim token is unknown, expired, or already used."""


def _numeric_code(length: int) -> str:
    """Generate a zero-padded numeric pairing code."""
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


class Registry:
    """Command dispatcher + device cache backed by a durable DeviceStore."""

    def __init__(
        self,
        store: DeviceStore,
        *,
        pairing_ttl_seconds: int = 600,
        pairing_code_length: int = 6,
        command_timeout_seconds: float = 10.0,
        claim_ttl_seconds: int = 600,
        claim_code_length: int = 10,
    ) -> None:
        self._store = store
        self._pairing_ttl = pairing_ttl_seconds
        self._pairing_code_length = pairing_code_length
        self._command_timeout = command_timeout_seconds
        self._claim_ttl = claim_ttl_seconds
        self._claim_code_length = claim_code_length

        self._pending: dict[str, PairingRequest] = {}  # pairing_code -> request
        # Cache of persisted devices, loaded offline at startup.
        self._devices: dict[str, PanelDevice] = {
            d.device_id: d for d in store.load_devices()
        }
        self._connections: dict[str, DeviceConnection] = {}  # device_id -> transport
        # device_id -> {command_id -> Future[CommandResult]}
        self._pending_commands: dict[str, dict[str, asyncio.Future]] = {}

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------

    def start_pairing(
        self,
        *,
        display_name: str,
        model: str | None = None,
        ios_version: str | None = None,
        capabilities: DeviceCapabilities | None = None,
    ) -> PairingRequest:
        """Create a pending pairing request with a fresh code."""
        # Ensure code uniqueness among pending requests.
        code = _numeric_code(self._pairing_code_length)
        while code in self._pending:
            code = _numeric_code(self._pairing_code_length)

        request = PairingRequest(
            request_id=str(uuid.uuid4()),
            pairing_code=code,
            display_name=display_name,
            model=model,
            ios_version=ios_version,
            capabilities=capabilities or DeviceCapabilities(),
            expires_at=utcnow() + timedelta(seconds=self._pairing_ttl),
        )
        self._pending[code] = request
        return request

    def approve_pairing(
        self, *, pairing_code: str, name: str, room: str | None = None
    ) -> NewDeviceCredentials:
        """Approve a pending request, persist the device, and return its secret.

        The plaintext secret is returned once; only its salted hash is stored.
        """
        request = self._pending.get(pairing_code)
        if request is None:
            raise PairingError("unknown pairing code")
        if request.is_expired():
            del self._pending[pairing_code]
            raise PairingError("pairing code expired")

        device, secret = self._create_device(
            name=name,
            room=room,
            model=request.model,
            ios_version=request.ios_version,
            capabilities=request.capabilities,
        )
        del self._pending[pairing_code]  # one-time use
        return NewDeviceCredentials(
            device_id=device.device_id, device_secret=secret
        )

    def _create_device(
        self,
        *,
        name: str,
        room: str | None = None,
        model: str | None = None,
        ios_version: str | None = None,
        capabilities: DeviceCapabilities | None = None,
    ) -> tuple[PanelDevice, str]:
        """Create + persist a device, returning it and its plaintext secret."""
        device = PanelDevice(
            device_id=str(uuid.uuid4()),
            name=name,
            room=room,
            model=model,
            ios_version=ios_version,
            capabilities=capabilities or DeviceCapabilities(),
            state=DeviceState(),
        )
        secret = secrets.token_urlsafe(32)
        self._store.upsert_device(device, hash_secret(secret))
        self._devices[device.device_id] = device
        return device, secret

    # ------------------------------------------------------------------
    # One-time claim tokens (10-digit code / Wi‑Fi pairing without the secret on screen)
    # ------------------------------------------------------------------

    def create_claim(
        self,
        *,
        name: str,
        room: str | None = None,
        model: str | None = None,
        ios_version: str | None = None,
        capabilities: DeviceCapabilities | None = None,
    ) -> Claim:
        """Provision a device and issue a one-time, persisted claim token.

        The token is a short numeric pairing code (``claim_code_length`` digits) so
        the user can read it from Home Assistant and type it into the app, or it can
        be pushed to a discovered phone over the local network. No secret is stored
        in the claim: the device's initial secret is unknown to everyone (its
        plaintext is discarded), and the real secret is issued only on redeem via
        rotation. The claim survives a restart within its TTL (see ADR 0004).
        """
        device, _discarded_secret = self._create_device(
            name=name,
            room=room,
            model=model,
            ios_version=ios_version,
            capabilities=capabilities,
        )
        token = _numeric_code(self._claim_code_length)
        while self._store.get_claim(token) is not None:
            token = _numeric_code(self._claim_code_length)
        claim = Claim(
            claim_token=token,
            device_id=device.device_id,
            expires_at=utcnow() + timedelta(seconds=self._claim_ttl),
        )
        self._store.insert_claim(claim)
        return claim

    def redeem_claim(self, claim_token: str) -> NewDeviceCredentials:
        """Redeem a claim token once, rotating and returning a fresh secret."""
        claim = self._store.get_claim(claim_token)
        if claim is None:
            raise ClaimError("unknown claim token")
        if claim.is_expired():
            self._delete_claim_and_orphan(claim)
            raise ClaimError("claim token expired")
        self._store.delete_claim(claim_token)  # one-time use
        secret = self._rotate_secret(claim.device_id)
        return NewDeviceCredentials(device_id=claim.device_id, device_secret=secret)

    def _rotate_secret(self, device_id: str) -> str:
        """Issue a fresh device secret, persisting only its salted hash."""
        secret = secrets.token_urlsafe(32)
        self._store.update_secret_hash(device_id, hash_secret(secret))
        return secret

    def _delete_claim_and_orphan(self, claim: Claim) -> None:
        """Drop an unredeemed claim and the device provisioned for it."""
        if claim.device_id in self._devices:
            # remove_device deletes the device row (claim cascades) + cache.
            self.remove_device(claim.device_id)
        else:
            self._store.delete_claim(claim.claim_token)

    def purge_expired_claims(self) -> int:
        """Delete expired claims and their orphan (never-redeemed) devices."""
        expired = self._store.expired_claims(utcnow())
        for claim in expired:
            self._delete_claim_and_orphan(claim)
        return len(expired)

    def purge_expired_pairings(self) -> int:
        """Remove expired pending requests. Returns count removed."""
        now = utcnow()
        expired = [c for c, r in self._pending.items() if r.is_expired(now)]
        for code in expired:
            del self._pending[code]
        return len(expired)

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def get_device(self, device_id: str) -> PanelDevice:
        device = self._devices.get(device_id)
        if device is None:
            raise UnknownDeviceError(device_id)
        return device

    def list_devices(self) -> list[PanelDevice]:
        return list(self._devices.values())

    def verify_secret(self, device_id: str, secret: str) -> PanelDevice:
        """Verify a device secret against its stored salted hash (constant time)."""
        device = self.get_device(device_id)
        stored = self._store.get_secret_hash(device_id)
        if stored is None or not verify_secret(secret, stored):
            raise AuthError("invalid device secret")
        return device

    def remove_device(self, device_id: str) -> None:
        """Revoke/remove a device: drop its connection and delete it durably."""
        if device_id not in self._devices:
            raise UnknownDeviceError(device_id)
        self.unregister_connection(device_id)
        self._devices.pop(device_id, None)
        self._store.delete_device(device_id)

    # ------------------------------------------------------------------
    # Connections & state
    # ------------------------------------------------------------------

    def register_connection(self, device_id: str, conn: DeviceConnection) -> None:
        """Mark a device online with a live transport."""
        device = self.get_device(device_id)
        self._connections[device_id] = conn
        device.state.online = True
        device.state.last_seen = utcnow()

    def unregister_connection(self, device_id: str) -> None:
        """Mark a device offline; fail any commands still awaiting result."""
        self._connections.pop(device_id, None)
        device = self._devices.get(device_id)
        if device is not None:
            device.state.online = False
        for fut in self._pending_commands.pop(device_id, {}).values():
            if not fut.done():
                fut.set_exception(DeviceOfflineError(device_id))

    def is_claim_pending(self, claim_token: str) -> bool:
        """Return true when a claim token still exists and has not expired."""
        claim = self._store.get_claim(claim_token)
        if claim is None:
            return False
        if claim.is_expired():
            self._delete_claim_and_orphan(claim)
            return False
        return True

    def is_online(self, device_id: str) -> bool:
        return device_id in self._connections

    def update_state(
        self,
        device_id: str,
        *,
        battery: int | None = None,
        brightness: float | None = None,
        screen=None,
        camera=None,
        intercom=None,
        stream=None,
        app_version: str | None = None,
        set_video_url: bool = False,
        video_url: str | None = None,
    ) -> PanelDevice:
        """Apply a heartbeat/state update from a device."""
        device = self.get_device(device_id)
        st = device.state
        if battery is not None:
            st.battery = battery
        if brightness is not None:
            st.brightness = brightness
        if screen is not None:
            st.screen = screen
        if camera is not None:
            st.camera = camera
        if intercom is not None:
            st.intercom = intercom
        if stream is not None:
            st.stream = stream
        if app_version is not None:
            st.app_version = app_version
        if set_video_url:
            device.media.video_url = video_url
            self._store.update_media(device_id, device.media)
        st.last_seen = utcnow()
        st.online = True
        self._store.update_state(device_id, st)
        return device

    def set_media(
        self,
        device_id: str,
        *,
        set_video_url: bool = False,
        video_url: str | None = None,
        camera_mode=None,
    ) -> PanelDevice:
        """Set per-device media config (video_url) and/or camera mode.

        ``set_video_url`` distinguishes "clear to null" from "leave unchanged".
        Persists the media/state change so it survives restarts.
        """
        device = self.get_device(device_id)
        if set_video_url:
            device.media.video_url = video_url
        if camera_mode is not None:
            device.state.camera = camera_mode
        self._store.update_media(device_id, device.media)
        self._store.update_state(device_id, device.state)
        return device

    def set_dashboard_url(self, device_id: str, dashboard_url: str | None) -> PanelDevice:
        """Persist and expose the dashboard URL selected from the HA device page."""
        return self.set_media_config(device_id, dashboard_url=dashboard_url)

    def set_media_config(
        self,
        device_id: str,
        *,
        dashboard_url: str | None | object = _UNSET,
        task_source: str | None | object = _UNSET,
        photo_source: str | None | object = _UNSET,
        sound: str | None | object = _UNSET,
        enabled_screens: str | None | object = _UNSET,
        show_bottom_menu: bool | None | object = _UNSET,
    ) -> PanelDevice:
        """Persist the HA-owned per-panel UI sources (dashboard/tasks/photos/sound).

        Only fields explicitly passed are changed; empty strings clear to ``None``.
        HA is the source of truth, so these persist and survive a restart.
        """
        device = self.get_device(device_id)
        if dashboard_url is not _UNSET:
            device.media.dashboard_url = dashboard_url or None
        if task_source is not _UNSET:
            device.media.task_source = task_source or None
        if photo_source is not _UNSET:
            device.media.photo_source = photo_source or None
        if sound is not _UNSET:
            device.media.sound = sound or None
        if enabled_screens is not _UNSET:
            device.media.enabled_screens = str(enabled_screens) if enabled_screens else None
        if show_bottom_menu is not _UNSET:
            device.media.show_bottom_menu = bool(show_bottom_menu) if show_bottom_menu is not None else None
        self._store.update_media(device_id, device.media)
        return device

    def set_stream(
        self,
        device_id: str,
        *,
        stream_state,
        set_video_url: bool = False,
        video_url: str | None = None,
        camera_mode=None,
    ) -> PanelDevice:
        """Set the publisher session state (+ viewer video_url / camera mode).

        ``stream`` is runtime only; ``video_url`` is persisted so the Lovelace
        viewer survives a restart until explicitly stopped/cleared.
        """
        device = self.get_device(device_id)
        device.state.stream = stream_state
        if camera_mode is not None:
            device.state.camera = camera_mode
        if set_video_url:
            device.media.video_url = video_url
            self._store.update_media(device_id, device.media)
        self._store.update_state(device_id, device.state)
        return device

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def send_command(
        self, device_id: str, command: PanelCommand, params: dict | None = None
    ) -> tuple[Command, CommandResult | None]:
        """Send a command to a connected device and await its result.

        Returns (command, result). ``result`` is None on timeout.
        Raises UnknownDeviceError / DeviceOfflineError as appropriate.
        """
        self.get_device(device_id)  # validates existence
        conn = self._connections.get(device_id)
        if conn is None:
            raise DeviceOfflineError(device_id)

        cmd = Command(id=str(uuid.uuid4()), command=command, params=params)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_commands.setdefault(device_id, {})[cmd.id] = fut

        message: dict = {"type": "command", "id": cmd.id, "command": command.value}
        if params is not None:
            message["params"] = params
        await conn.send_json(message)

        try:
            result = await asyncio.wait_for(fut, timeout=self._command_timeout)
            return cmd, result
        except asyncio.TimeoutError:
            return cmd, None
        finally:
            self._pending_commands.get(device_id, {}).pop(cmd.id, None)

    async def send_command_nowait(
        self, device_id: str, command: PanelCommand, params: dict | None = None
    ) -> Command:
        """Send a command without waiting for command_result.

        Used while handling an inbound frame from the same device, where waiting
        would block the receive loop from reading the result.
        """
        self.get_device(device_id)
        conn = self._connections.get(device_id)
        if conn is None:
            raise DeviceOfflineError(device_id)
        cmd = Command(id=str(uuid.uuid4()), command=command, params=params)
        message: dict = {"type": "command", "id": cmd.id, "command": command.value}
        if params is not None:
            message["params"] = params
        await conn.send_json(message)
        return cmd

    def resolve_command(self, device_id: str, result: CommandResult) -> bool:
        """Deliver a command_result to a waiting sender. Returns True if matched."""
        fut = self._pending_commands.get(device_id, {}).get(result.id)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        # On success, optimistically reflect the target screen in state.
        return True

    def apply_command_optimistic_state(
        self, device_id: str, command: PanelCommand
    ) -> None:
        """Update the cached screen to a command's target (best-effort)."""
        target = COMMAND_TARGET_SCREEN.get(command)
        if target is not None:
            device = self._devices.get(device_id)
            if device is not None:
                device.state.screen = target
                self._store.update_state(device_id, device.state)
