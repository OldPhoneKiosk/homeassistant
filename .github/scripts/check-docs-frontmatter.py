#!/usr/bin/env python3
"""Validate docs/**/DOC_*.md frontmatter, following the Sembot docs convention."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
required = {"category", "title", "author", "description"}
failures: list[str] = []
files = sorted((ROOT / "docs").glob("**/DOC_*.md"))
if not files:
    failures.append("docs: no docs/**/DOC_*.md files found")

for path in files:
    rel = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        failures.append(f"{rel}: missing YAML frontmatter")
        continue
    end = text.find("\n---\n", 4)
    if end == -1:
        failures.append(f"{rel}: unclosed YAML frontmatter")
        continue
    fm = text[4:end]
    keys = set()
    for line in fm.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line)
        if match:
            keys.add(match.group(1))
    missing = sorted(required - keys)
    if missing:
        failures.append(f"{rel}: missing frontmatter keys: {', '.join(missing)}")
    body = text[end + 5 :].strip()
    if not body.startswith("# "):
        failures.append(f"{rel}: first content block must be an H1")

if failures:
    print("docs-frontmatter: failed", file=sys.stderr)
    for failure in failures:
        print(f"  {failure}", file=sys.stderr)
    sys.exit(1)
print(f"docs-frontmatter: OK ({len(files)} docs)")
