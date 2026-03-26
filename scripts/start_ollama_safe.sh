#!/usr/bin/env bash
set -euo pipefail

if lsof -iTCP:11434 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "Ollama is already running on 127.0.0.1:11434"
  exit 0
fi

echo "Starting Ollama server..."
ollama serve >/tmp/ollama-serve.log 2>&1 &
sleep 2

if lsof -iTCP:11434 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "Ollama started successfully"
else
  echo "Failed to start Ollama. Check /tmp/ollama-serve.log"
  exit 1
fi
