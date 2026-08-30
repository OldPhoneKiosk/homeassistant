"""Short-lived WebSocket connection tokens.

A device authenticates once with its long-lived ``device_secret`` (via
``POST /api/devices/{id}/ws-token``) and receives a short-lived, HMAC-signed token
to put in the WebSocket URL. This keeps the long-lived secret out of the WS query
string. Tokens are **stateless** (no storage): they carry an expiry and a signature
over ``(device_id, expiry)`` using a server-side signing secret.

Token format: ``"<exp_epoch_seconds>.<hmac_sha256_hex>"``.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WsTokenService:
    """Issues and verifies short-lived, HMAC-signed WebSocket tokens."""

    def __init__(
        self,
        secret: str,
        ttl_seconds: int = 120,
        *,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl = ttl_seconds
        self._now = now

    def _signature(self, device_id: str, exp: int) -> str:
        message = f"ws:{device_id}:{exp}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def issue(self, device_id: str) -> tuple[str, datetime]:
        """Return ``(token, expires_at)`` for a device."""
        expires_at = self._now() + timedelta(seconds=self._ttl)
        exp = int(expires_at.timestamp())
        token = f"{exp}.{self._signature(device_id, exp)}"
        # Normalize expires_at to the whole-second epoch we actually signed.
        return token, datetime.fromtimestamp(exp, tz=UTC)

    def verify(self, device_id: str, token: str) -> bool:
        """Constant-time verify signature and expiry for ``device_id``."""
        parts = token.split(".")
        if len(parts) != 2:
            return False
        exp_str, sig = parts
        try:
            exp = int(exp_str)
        except ValueError:
            return False
        expected = self._signature(device_id, exp)
        if not hmac.compare_digest(expected, sig):
            return False
        return self._now().timestamp() < exp
