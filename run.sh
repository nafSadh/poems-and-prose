#!/usr/bin/env bash
# Build the site, serve _site/ on http://localhost:$PORT, and rebuild on
# any source file change (.md / .yml / .html / .css / .py under src/).
# Usage: ./run.sh [port]   (default 8000)
# Hard-refresh the browser after edits — http.server doesn't push reloads.
set -euo pipefail

PORT="${1:-8765}"
cd "$(dirname "$0")"
exec python3 _build/serve.py "$PORT"
