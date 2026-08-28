#!/usr/bin/env bash
# Validate JSON files and duplicate keys. Adapted from the Sembot proxy CI gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

FILES=()
while IFS= read -r file; do
  FILES+=("$file")
done < <(
  find .github -type f -name '*.json' 2>/dev/null
  find . -maxdepth 1 -type f \( -name '*.json' -o -name 'hacs.json' \) 2>/dev/null
  find custom_components/oldphonekiosk -type f -name '*.json' 2>/dev/null
)

if [ ${#FILES[@]} -eq 0 ]; then
  echo "validate-json: no JSON files found"
  exit 0
fi

python3 - "${FILES[@]}" <<'PY'
import json
import sys
failures = []
for path in sys.argv[1:]:
    try:
        text = open(path, encoding='utf-8').read()
        dupes = []
        def hook(pairs):
            seen = set()
            for key, _ in pairs:
                if key in seen:
                    dupes.append(key)
                seen.add(key)
            return dict(pairs)
        json.loads(text, object_pairs_hook=hook)
        if dupes:
            failures.append((path, 'duplicate keys: ' + ', '.join(sorted(set(dupes)))))
    except json.JSONDecodeError as exc:
        failures.append((path, f'line {exc.lineno} col {exc.colno}: {exc.msg}'))
    except OSError as exc:
        failures.append((path, f'read error: {exc}'))
if failures:
    print(f'validate-json: {len(failures)} invalid file(s):', file=sys.stderr)
    for path, msg in failures:
        print(f'  {path}: {msg}', file=sys.stderr)
    raise SystemExit(1)
print(f'validate-json: OK ({len(sys.argv) - 1} files)')
PY
