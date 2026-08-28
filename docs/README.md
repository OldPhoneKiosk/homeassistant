# OldPhoneKiosk documentation

This directory follows the Sembot proxy convention: user-facing and operator documentation is stored as Markdown files named `DOC_*.md` with YAML frontmatter.

## Structure

- `app/` — installation, pairing, entities, services, troubleshooting, issue reporting.
- `development/` — local dev setup, CI gates, release/testing policy.

## File convention

Each document starts with:

```yaml
---
category: app|development
title: Human-readable title
author: system
description: One sentence summary
---
```

CI validates this shape so docs stay usable for future publishing or embedding.
