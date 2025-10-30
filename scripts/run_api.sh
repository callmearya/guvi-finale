#!/usr/bin/env bash
set -euo pipefail

APP_MODULE=${1:-app.main:app}
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

if [ ! -d ".venv" ]; then
  echo "Virtual environment .venv not found. Create one with python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
