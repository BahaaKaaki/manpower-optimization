#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/build_api_sidecar.sh
cd desktop
npm install
npm run build
npm run tauri:build

echo "Pilot desktop artifacts are available under desktop/src-tauri/target/release/bundle"
