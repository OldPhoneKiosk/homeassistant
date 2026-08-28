---
category: development
title: CI and release checks
author: system
description: Continuous integration checks for tests, HACS packaging, documentation and repository hygiene
---

# CI and release checks

The CI follows the same philosophy as the Sembot proxy repository: fast feedback, explicit permissions, focused hygiene gates, and documentation freshness checks.

## Workflows

### `tests.yml` — HA integration tests

Runs on push, pull request, and manual dispatch.

Jobs:

- `fast-tests` on Python 3.11 and 3.12: install dev dependencies, compile the custom component, run `pytest -q`.
- `ha-harness` on Python 3.12: install `pytest-homeassistant-custom-component`, print HA/PHACC versions, compile the custom component, run `pytest tests_ha -q`.

### `lint.yml` — repository checks

Runs on push, pull request, and manual dispatch.

Jobs:

- `validate-json` — validates JSON and duplicate keys in `.github`, root metadata and integration translation files.
- `hacs-layout` — checks HACS-required files and verifies the My Home Assistant button points to this repository.
- `docs-frontmatter` — checks every `docs/**/DOC_*.md` has required YAML frontmatter.
- `docs-freshness` — on PRs, code/service changes must update docs or explicitly opt out with `[docs-checked]`.
- `tests-freshness` — on PRs, code changes with nearby tests should update tests or opt out with `[tests-checked]`.
- `changelog-freshness` — on PRs, product changes should update `CHANGELOG.md` or opt out with `[changelog-checked]`.
- `markdown-links` — checks local relative links in Markdown.

## Local pre-push checklist

```bash
python -m compileall -q custom_components/oldphonekiosk
pytest -q tests tests_ha
.github/scripts/validate-json.sh
.github/scripts/check-docs-frontmatter.py
.github/scripts/check-hacs-layout.sh
.github/scripts/check-markdown-links.py
```

## Release policy

Before publishing a HACS release/tag, all checks on `main` must be green, `CHANGELOG.md` should be updated, `manifest.json` version should match the release tag, and a real HA instance should install/update through HACS and pair one real iPhone panel.
