#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/start_ollama_safe.sh"

exec "$ROOT_DIR/.venv/bin/python" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
