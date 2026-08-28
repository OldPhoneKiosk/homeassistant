# Contributing

Thanks for helping improve OldPhoneKiosk.

## Report issues first when unsure

For bugs and feature ideas, open an issue before large implementation work:

- Bug report: https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=bug_report.yml
- Feature request: https://github.com/OldPhoneKiosk/homeassistant/issues/new?template=feature_request.yml

## Development checklist

1. Create a focused branch.
2. Update or add tests for behavior changes.
3. Update `docs/**/DOC_*.md` for user-visible behavior changes.
4. Update `CHANGELOG.md` for product changes.
5. Run locally:

```bash
python -m compileall -q custom_components/oldphonekiosk
pytest -q tests tests_ha
.github/scripts/validate-json.sh
.github/scripts/check-docs-frontmatter.py
.github/scripts/check-hacs-layout.sh
.github/scripts/check-markdown-links.py
```

If docs/tests/changelog truly do not need a change, explain why in the PR body and include the relevant override marker: `[docs-checked]`, `[tests-checked]`, or `[changelog-checked]`.

## Security

Do not include Home Assistant tokens, device secrets, active claim tokens, or private home details in public issues, PRs, logs, or screenshots.
