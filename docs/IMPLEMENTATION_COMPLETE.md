# Implementation Complete Checklist

## Backend API

- [x] `GET /health`
- [x] `POST /chat`
- [x] `POST /chat/debug`
- [x] `GET /artifacts/resume/{file_name}`
- [x] `GET /.well-known/agent-card.json`
- [x] `GET /agent-cards`
- [x] `POST /message:send`
- [x] `GET /tasks`
- [x] `GET /tasks/{task_id}`

## Routing and orchestration

- [x] LLM intent parsing.
- [x] Catalog-driven routing manifest.
- [x] Multi-agent A2A sequence support.
- [x] Telegram scraping agent in routing catalog.
- [x] Telegram agent retry support (up to 5 attempts).

## Memory and state

- [x] Session-scoped chat memory.
- [x] Persistent chat memory on disk under `data/chat_memory`.
- [x] JD context persistence (last JD link/details).
