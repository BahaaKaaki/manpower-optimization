#!/usr/bin/env bash
# Tauri + Vite UI. Start scripts/dev_api.sh in another terminal first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/desktop"
if [[ ! -d node_modules ]]; then
  npm install
fi
exec npm run tauri:dev
