#!/usr/bin/env bash
# Unzip manpower-deploy.zip (or path arg) into a temp dir and pip install like Oryx; fail if API import breaks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="${1:-$ROOT/manpower-deploy.zip}"
if [[ ! -f "$ZIP" ]]; then
  echo "Missing ZIP: $ZIP — run ./deploy.sh --skip-deploy first." >&2
  exit 1
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP/extract"
cd "$TMP/extract"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python -c "import manpower_api.app as a; print('verify-azure-package OK:', a.app.title)"
