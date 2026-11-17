#!/usr/bin/env bash
# Build and serve sadh.ink locally, watching for changes.
#
#   ./run.sh          build _site/ + serve on http://localhost:8765/ (auto-rebuilds)
#   ./run.sh 9000     same, on port 9000
#   ./run.sh build    build _site/ once and exit
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  build) exec python3 _build/build.py ;;
  *)     exec python3 _build/serve.py "${1:-8765}" ;;
esac
