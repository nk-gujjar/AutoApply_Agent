#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Free backend port if a previous process is still running.
if lsof -ti tcp:8000 >/dev/null 2>&1; then
	echo "Port 8000 is busy. Stopping existing process(es)..."
	lsof -ti tcp:8000 | xargs kill -9
	sleep 1
fi

exec "$ROOT_DIR/.venv/bin/python" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
