"""Test bootstrap.

The integration package's ``__init__`` imports Home Assistant, which we do not
install for these fast unit tests. We therefore load the HA-independent modules
(``const``, ``api``) under a synthetic package so their relative imports resolve
without executing the real package ``__init__``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_COMPONENT_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "oldphonekiosk"
)

_PKG = "opk_component"


def _load_component_modules() -> None:
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(_COMPONENT_DIR)]
    sys.modules[_PKG] = pkg

    for name in ("const", "api", "pairing"):
        spec = importlib.util.spec_from_file_location(
            f"{_PKG}.{name}", _COMPONENT_DIR / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{_PKG}.{name}"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        # Expose under a short, importable alias for tests.
        sys.modules[f"opk_{name}"] = module


_load_component_modules()
