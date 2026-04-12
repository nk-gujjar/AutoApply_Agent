#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
QUERY="${1:-hello}"
SESSION_ID="${2:-cli-session}"

PAYLOAD="$($ROOT_DIR/.venv/bin/python -c 'import json,sys; print(json.dumps({"query": sys.argv[1], "session_id": sys.argv[2]}))' "$QUERY" "$SESSION_ID")"

curl -sS -X POST "$BACKEND_URL/chat" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD"

echo
