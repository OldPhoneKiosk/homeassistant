#!/usr/bin/env bash
# Validate HACS custom repository layout and README install button.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

fail=0
need_file() {
  if [ ! -f "$1" ]; then
    echo "::error file=$1::missing required HACS/integration file"
    fail=1
  fi
}

need_file hacs.json
need_file custom_components/oldphonekiosk/manifest.json
need_file custom_components/oldphonekiosk/__init__.py
need_file README.md

python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('custom_components/oldphonekiosk/manifest.json').read_text())
assert manifest['domain'] == 'oldphonekiosk'
assert manifest.get('config_flow') is True
assert manifest.get('version')
hacs = json.loads(Path('hacs.json').read_text())
assert hacs.get('name') == 'OldPhoneKiosk'
PY

if ! grep -q 'my.home-assistant.io/redirect/hacs_repository/?owner=OldPhoneKiosk&repository=homeassistant&category=integration' README.md; then
  echo "::error file=README.md::missing or incorrect My Home Assistant HACS repository button"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "hacs-layout: OK"
