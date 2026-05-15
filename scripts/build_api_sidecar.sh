#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -r requirements-desktop.txt
python3 -m PyInstaller \
  --clean \
  --onefile \
  --name manpower-api \
  --collect-all pulp \
  --collect-all pandas \
  --collect-all openpyxl \
  manpower_api/run.py

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64|Darwin-aarch64)
    TARGET_NAME="manpower-api-aarch64-apple-darwin"
    ;;
  Darwin-x86_64)
    TARGET_NAME="manpower-api-x86_64-apple-darwin"
    ;;
  Linux-x86_64)
    TARGET_NAME="manpower-api-x86_64-unknown-linux-gnu"
    ;;
  Linux-aarch64|Linux-arm64)
    TARGET_NAME="manpower-api-aarch64-unknown-linux-gnu"
    ;;
  MINGW64_NT*-x86_64|MSYS_NT*-x86_64|CYGWIN_NT*-x86_64)
    TARGET_NAME="manpower-api-x86_64-pc-windows-msvc.exe"
    ;;
  *)
    echo "Unsupported platform for automatic Tauri sidecar naming: $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac

mkdir -p desktop/src-tauri/binaries
if [[ "$TARGET_NAME" == *.exe ]]; then
  cp "dist/manpower-api.exe" "desktop/src-tauri/binaries/$TARGET_NAME"
else
  cp "dist/manpower-api" "desktop/src-tauri/binaries/$TARGET_NAME"
  chmod +x "desktop/src-tauri/binaries/$TARGET_NAME"
fi

echo "Sidecar created at desktop/src-tauri/binaries/$TARGET_NAME"
