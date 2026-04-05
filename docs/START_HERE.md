# Start Here

This repository is a multi-agent job automation system with FastAPI backend, Streamlit frontend, and LLM-based routing.

## 1) Run the stack

```bash
./scripts/run_full_stack.sh
```

## 2) Verify health

```bash
curl -s http://127.0.0.1:8000/health
```

## 3) Run first chat flow

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"find the jd from https://apply.careers.microsoft.com/careers/job/1970393556640618","session_id":"demo"}'
```

## 4) Telegram flow

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"give me the 5 jobs of the telegram group @jobs_and_internships_updates","session_id":"demo"}'
```

## 5) Core behavior

- Routing uses `LLMRouter` and catalog hints/default payloads.
- Resume intent runs `jd_extractor` then `resume_rewrite`.
- Telegram intent runs `telegram_scraper` with retry handling.
- `fetch_jobs` is cache-first with live fallback.
- Chat memory persists by `session_id` in `data/chat_memory`.
- `/chat` returns clean user-facing response and optional resume metadata.
- `/chat/debug` returns technical response payload.
