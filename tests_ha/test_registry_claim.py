"""Registry claim tests: the one-time pairing code is a 10-digit numeric token."""

from __future__ import annotations

import pytest

from custom_components.oldphonekiosk.const import PAIRING_CODE_LENGTH
from custom_components.oldphonekiosk.registry import ClaimError, Registry
from custom_components.oldphonekiosk.store import DeviceStore


def _registry() -> Registry:
    return Registry(DeviceStore(":memory:"))


def test_create_claim_uses_ten_digit_numeric_code():
    reg = _registry()
    claim = reg.create_claim(name="Kitchen")
    assert claim.claim_token.isdigit()
    assert len(claim.claim_token) == PAIRING_CODE_LENGTH == 10


def test_redeem_claim_returns_credentials_and_is_one_time():
    reg = _registry()
    claim = reg.create_claim(name="Kitchen")

    creds = reg.redeem_claim(claim.claim_token)
    assert creds.device_id == claim.device_id
    assert creds.device_secret  # a fresh secret is issued on redeem

    # A claim is single-use.
    with pytest.raises(ClaimError):
        reg.redeem_claim(claim.claim_token)


def test_redeem_unknown_code_raises():
    reg = _registry()
    with pytest.raises(ClaimError):
        reg.redeem_claim("0000000000")


def test_pairing_codes_are_unique():
    reg = _registry()
    tokens = {reg.create_claim(name=f"Panel {i}").claim_token for i in range(25)}
    assert len(tokens) == 25
