# Quick Start (LLM Routing)

## Prerequisites

- Virtual environment with dependencies.
- Ollama model available (or Groq key if using Groq).
- `.env` configured (`LLM_PROVIDER`, model, optional Naukri creds).
- For Telegram scraping: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `PHONE_NUMBER` configured.

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

## Telegram query

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"give me the 5 jobs of the telegram group @jobs_and_internships_updates","session_id":"demo"}'
```
