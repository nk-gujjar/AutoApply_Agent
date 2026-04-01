# AutoApply Multi-Agent System

AutoApply is a FastAPI + Streamlit project for job discovery, JD extraction, resume tailoring, and application automation.

## Current Status (as of 2026-04-01)

- LLM-driven intent routing is enabled via `LLMRouter`.
- Agent loading and routing metadata are catalog-driven from `modules/multi_agent/config/agent_catalog.yaml`.
- Resume tailoring flow is a two-agent sequence: `jd_extractor -> resume_rewrite`.
- Chat memory supports session-based follow-up commands for last query, last conversation, last JD link, and last JD details.
- Resume download metadata is returned by `/chat` when a resume PDF is generated.
- A2A endpoints are available from the backend (`/.well-known/agent-card.json`, `/message:send`, `/tasks`).

## Run

```bash
./scripts/run_full_stack.sh
```

## API Summary

- `GET /health`
- `POST /chat`
- `POST /chat/debug`
- `GET /artifacts/resume/{file_name}`
- `GET /.well-known/agent-card.json`
- `GET /agent-cards`
- `POST /message:send`
- `GET /tasks`
- `GET /tasks/{task_id}`

## Documentation

Start at `docs/START_HERE.md` and `docs/DOCUMENTATION_INDEX.md`.
