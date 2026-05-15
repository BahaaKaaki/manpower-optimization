#!/bin/bash
# Azure App Service startup — all deps pre-installed in /packages (no Oryx build needed).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export STATIC_ROOT="$SCRIPT_DIR/static"
export PYTHONPATH="$SCRIPT_DIR/packages:$SCRIPT_DIR:${PYTHONPATH:-}"
export PORT="${PORT:-${WEBSITES_PORT:-8000}}"

PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

echo "Manpower startup: PORT=$PORT PYTHON=$PY PWD=$PWD" >&2
exec "$PY" -m uvicorn manpower_api.app:app --host 0.0.0.0 --port "$PORT"
