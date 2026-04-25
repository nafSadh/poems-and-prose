#!/usr/bin/env bash
# Build the site and serve _site/ on http://localhost:$PORT.
# Usage: ./run.sh [port]   (default 8000)
# Re-run after editing .md, _poems.yml, templates, or styles — no auto-reload.
set -euo pipefail

PORT="${1:-8000}"
cd "$(dirname "$0")"

echo "→ building…"
python3 _build/build.py

echo "→ serving http://localhost:$PORT/"
exec python3 -m http.server "$PORT" -d _site
