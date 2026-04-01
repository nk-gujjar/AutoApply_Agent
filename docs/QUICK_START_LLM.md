# Quick Start (LLM Routing)

## Prerequisites

- Virtual environment with dependencies.
- Ollama model available (or Groq key if using Groq).
- `.env` configured (`LLM_PROVIDER`, model, optional Naukri creds).

## Start

```bash
./scripts/run_full_stack.sh
```

## First query

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch 3 jobs with descriptions","session_id":"demo"}'
```
