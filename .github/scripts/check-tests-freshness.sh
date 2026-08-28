#!/usr/bin/env bash
# Pre-merge check: Python integration changes should update tests unless explicitly reviewed.
# Override with [tests-checked] in the PR body.
set -euo pipefail
BASE="${1:-${BASE_REF:-origin/main}}"

if [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -f "$GITHUB_EVENT_PATH" ]; then
  BODY="$(jq -r '.pull_request.body // ""' "$GITHUB_EVENT_PATH" 2>/dev/null || true)"
  if printf '%s' "$BODY" | grep -q '\[tests-checked\]'; then
    echo "OK: [tests-checked] override present."
    exit 0
  fi
fi

changed="$(git diff --name-only "$BASE"...HEAD || true)"
code_changed="$(grep -E '^custom_components/oldphonekiosk/.*\.py$' <<<"$changed" || true)"
tests_changed="$(grep -E '^(tests|tests_ha)/' <<<"$changed" || true)"

if [ -n "$code_changed" ] && [ -z "$tests_changed" ]; then
  {
    echo "### Tests may need updates"
    echo
    echo "Python integration code changed but no tests changed."
    echo
    printf -- '- `%s`\n' $code_changed | head -20
    echo
    echo "Update tests/tests_ha or add \`[tests-checked]\` to the PR body with justification."
  } | tee -a "${GITHUB_STEP_SUMMARY:-/dev/stderr}"
  exit 1
fi

echo "tests-freshness: OK"
