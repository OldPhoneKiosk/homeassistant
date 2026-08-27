"""Device secret hashing.

Device secrets are high-entropy (``secrets.token_urlsafe(32)`` = 256 bits), so a
single salted SHA-256 is sufficient — a slow KDF (bcrypt/argon2) is meant for
low-entropy human passwords and would add a dependency for no security gain here.
The plaintext secret is returned to the device exactly once (at pairing approval)
and never stored; only the salted hash is persisted (see ADR 0002).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGO = "sha256"


def hash_secret(secret: str) -> str:
    """Return ``sha256$<salt_hex>$<digest_hex>`` for a device secret."""
    salt = secrets.token_bytes(16)
    digest = hashlib.sha256(salt + secret.encode("utf-8")).hexdigest()
    return f"{_ALGO}${salt.hex()}${digest}"


def verify_secret(secret: str, stored: str) -> bool:
    """Constant-time verify a secret against a stored ``hash_secret`` value."""
    try:
        algo, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    expected = hashlib.sha256(salt + secret.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, digest_hex)
