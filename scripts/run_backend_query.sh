#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/start_ollama_safe.sh"

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/main.py" --mode query --query "${1:-hello}" --max-jobs "${2:-1}"
