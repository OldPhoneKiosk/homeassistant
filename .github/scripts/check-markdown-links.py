#!/usr/bin/env python3
"""Check local Markdown links point to existing files."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
files = [ROOT / name for name in ["README.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"]]
files += sorted((ROOT / "docs").glob("**/*.md"))
pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
failures: list[str] = []
for path in files:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        raw = match.group(1).strip()
        if raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = raw.split("#", 1)[0]
        if not target:
            continue
        parsed = urlparse(target)
        if parsed.scheme:
            continue
        candidate = (path.parent / unquote(parsed.path)).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            failures.append(f"{path.relative_to(ROOT)}: link escapes repo: {raw}")
            continue
        if not candidate.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing link target: {raw}")
if failures:
    print("markdown-links: failed", file=sys.stderr)
    for failure in failures:
        print(f"  {failure}", file=sys.stderr)
    sys.exit(1)
print(f"markdown-links: OK ({len(files)} files)")
