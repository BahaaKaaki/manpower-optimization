#!/usr/bin/env bash
# Build a ready-to-run deployment zip — same approach as Edwin (npm install --omit=dev).
# Pre-installs Linux-compatible Python packages so NO server-side build is needed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${OUTPUT_ZIP:-/tmp/manpower-app.zip}"
STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "Building Vite app..."
( cd "$ROOT/desktop" && npm run build )

echo "Staging source..."
cp -r "$ROOT/manpower_app" "$ROOT/manpower_api" "$STAGE/"
cp -r "$ROOT/desktop/dist" "$STAGE/static"
cp "$ROOT/packaging/azure/manpower_start.sh" "$STAGE/manpower_start.sh"
chmod +x "$STAGE/manpower_start.sh"

echo "Installing Linux-compatible Python packages..."
python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --target "$STAGE/packages" \
  pandas pulp openpyxl fastapi uvicorn python-multipart \
  --quiet --no-cache-dir

rm -f "$OUT"
echo "Writing $OUT ..."
( cd "$STAGE" && zip -rq "$OUT" . -x "**/__pycache__/*" -x "**/*.pyc" -x "**/.DS_Store" )
echo "Done: $OUT ($(du -h "$OUT" | cut -f1))"
