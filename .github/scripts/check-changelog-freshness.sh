#!/usr/bin/env bash
# Pre-merge check: product/package changes should update CHANGELOG.md unless explicitly reviewed.
# Override with [changelog-checked] in the PR body.
set -euo pipefail
BASE="${1:-${BASE_REF:-origin/main}}"

if [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -f "$GITHUB_EVENT_PATH" ]; then
  BODY="$(jq -r '.pull_request.body // ""' "$GITHUB_EVENT_PATH" 2>/dev/null || true)"
  if printf '%s' "$BODY" | grep -q '\[changelog-checked\]'; then
    echo "OK: [changelog-checked] override present."
    exit 0
  fi
fi

changed="$(git diff --name-only "$BASE"...HEAD || true)"
product_changed="$(grep -E '^(custom_components/oldphonekiosk/|hacs\.json|pyproject\.toml)' <<<"$changed" || true)"
if [ -n "$product_changed" ] && ! grep -q '^CHANGELOG.md$' <<<"$changed"; then
  {
    echo "### Changelog may need updates"
    echo
    echo "Product/package files changed but CHANGELOG.md did not."
    echo
    printf -- '- `%s`\n' $product_changed | head -20
    echo
    echo "Update CHANGELOG.md or add \`[changelog-checked]\` to the PR body with justification."
  } | tee -a "${GITHUB_STEP_SUMMARY:-/dev/stderr}"
  exit 1
fi

echo "changelog-freshness: OK"
