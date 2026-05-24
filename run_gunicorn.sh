#!/usr/bin/env bash
set -euo pipefail
# Simple helper to run gunicorn from the project root
cd "$(dirname "$0")"

# Activate venv if present
if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  . "venv/bin/activate"
fi

exec gunicorn -w 4 -b 127.0.0.1:8000 "app:app"
