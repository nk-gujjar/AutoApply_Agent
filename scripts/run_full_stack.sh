#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/start_ollama_safe.sh"

# Free backend port if stale process exists.
if lsof -ti tcp:8000 >/dev/null 2>&1; then
	echo "Port 8000 is busy. Stopping existing process(es)..."
	lsof -ti tcp:8000 | xargs kill -9
	sleep 1
fi

# Start backend in background
"$ROOT_DIR/.venv/bin/python" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload >/tmp/autoapply-backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend running at http://127.0.0.1:8000 (pid=$BACKEND_PID)"
echo "Logs: /tmp/autoapply-backend.log"

# Start frontend in foreground
"$ROOT_DIR/.venv/bin/python" -m streamlit run "$ROOT_DIR/frontend/chat_frontend.py"
