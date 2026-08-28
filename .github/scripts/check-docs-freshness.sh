#!/usr/bin/env bash
# Pre-merge check: user-visible integration changes should update docs/**/DOC_*.md.
# Override with [docs-checked] in the PR body when docs were reviewed and no change is needed.
set -euo pipefail
BASE="${1:-${BASE_REF:-origin/main}}"

if [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -f "$GITHUB_EVENT_PATH" ]; then
  BODY="$(jq -r '.pull_request.body // ""' "$GITHUB_EVENT_PATH" 2>/dev/null || true)"
  if printf '%s' "$BODY" | grep -q '\[docs-checked\]'; then
    echo "OK: [docs-checked] override present."
    exit 0
  fi
fi

changed="$(git diff --name-only "$BASE"...HEAD || true)"
docs_changed=false
grep -q '^docs/' <<<"$changed" && docs_changed=true
grep -q '^README.md$' <<<"$changed" && docs_changed=true

product_changed="$(grep -E '^(custom_components/oldphonekiosk/.*\.(py|yaml|json)|hacs\.json)$' <<<"$changed" || true)"
if [ -n "$product_changed" ] && [ "$docs_changed" = false ]; then
  {
    echo "### Documentation may need updates"
    echo
    echo "This PR changes integration/package behavior but did not update docs or README."
    echo
    echo "Changed product files:"
    printf -- '- `%s`\n' $product_changed | head -20
    echo
    echo "Update docs/**/DOC_*.md or add \`[docs-checked]\` to the PR body with justification."
  } | tee -a "${GITHUB_STEP_SUMMARY:-/dev/stderr}"
  exit 1
fi

echo "docs-freshness: OK"
