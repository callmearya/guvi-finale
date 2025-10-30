#!/usr/bin/env bash
set -euo pipefail

APP_MODULE=${1:-webapp:create_app}
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-5000}

if [ ! -d ".venv" ]; then
  echo "Virtual environment .venv not found. Create one with python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
export FLASK_APP=$APP_MODULE
flask --app "$APP_MODULE" run --host "$HOST" --port "$PORT"
