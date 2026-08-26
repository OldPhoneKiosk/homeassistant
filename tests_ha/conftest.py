"""Fixtures for the Home Assistant harness tests (pytest-homeassistant-custom-component).

These tests require a real HA runtime and PHACC (installed separately, see README);
they live outside `tests/` so the fast, HA-free unit tests are unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repo's `custom_components` package importable by HA's loader.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load the OldPhoneKiosk custom integration in every test."""
    yield
