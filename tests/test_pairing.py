"""Pairing payload helpers (pure, HA-free)."""

from __future__ import annotations

import json

import opk_pairing as pairing


def test_build_payload_matches_ios_schema():
    payload = pairing.build_pairing_payload(
        bridge_url="http://127.0.0.1:8788/",
        device_id="dev-1",
        device_secret="s3cr3t",
        name="Kitchen",
        room="Kitchen",
    )
    assert payload == {
        "version": 1,
        "bridge_url": "http://127.0.0.1:8788",  # trailing slash trimmed
        "device_id": "dev-1",
        "device_secret": "s3cr3t",
        "name": "Kitchen",
        "room": "Kitchen",
    }


def test_build_claim_payload_has_no_secret():
    payload = pairing.build_claim_payload(
        bridge_url="http://127.0.0.1:8788/",
        claim_token="claim-xyz",
        name="Kitchen",
    )
    assert payload == {
        "version": 1,
        "type": "claim",
        "bridge_url": "http://127.0.0.1:8788",
        "claim_token": "claim-xyz",
        "name": "Kitchen",
    }
    assert "device_secret" not in payload


def test_build_payload_omits_optional_fields():
    payload = pairing.build_pairing_payload(
        bridge_url="http://h:8788", device_id="d", device_secret="s"
    )
    assert "name" not in payload and "room" not in payload


def test_payload_to_json_is_stable_and_parseable():
    payload = pairing.build_pairing_payload(
        bridge_url="http://h", device_id="d", device_secret="s"
    )
    text = pairing.payload_to_json(payload)
    # Stable key order, no spaces.
    assert text.startswith("{") and " " not in text
    assert json.loads(text)["device_id"] == "d"


def test_no_qr_helper_exists():
    # QR pairing has been removed; only payload builders remain.
    assert not hasattr(pairing, "payload_to_qr_svg_data_uri")
