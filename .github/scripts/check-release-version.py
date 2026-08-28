#!/usr/bin/env python3
"""Check that manifest.json version matches a release tag like v0.1.0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("usage: check-release-version.py <tag>", file=sys.stderr)
    sys.exit(2)

tag = sys.argv[1]
expected = tag[1:] if tag.startswith("v") else tag
manifest = json.loads(Path("custom_components/oldphonekiosk/manifest.json").read_text())
actual = manifest.get("version")
if actual != expected:
    print(
        f"manifest version mismatch: manifest has {actual!r}, release tag expects {expected!r}",
        file=sys.stderr,
    )
    sys.exit(1)
print(f"release-version: OK ({tag} -> {actual})")
