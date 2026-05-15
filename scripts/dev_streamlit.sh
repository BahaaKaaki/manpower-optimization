#!/usr/bin/env bash
# Run from repo root: optional `source .venv/bin/activate` first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -r requirements.txt
exec streamlit run "Manpower Tool.py"
