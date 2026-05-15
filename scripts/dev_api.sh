#!/usr/bin/env bash
# FastAPI for the desktop app (port 8765). Run in a separate terminal from the UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 -m uvicorn manpower_api.app:app --host 127.0.0.1 --port 8765 --reload
