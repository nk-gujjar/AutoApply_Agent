# Architecture Overview

## Layers

1. Frontend (`frontend/chat_frontend.py`)
- Streamlit UI.
- Sends `{query, session_id}` to backend.

2. API (`backend/api/*.py`)
- `chat_routes.py`: `/health`, `/chat`, `/chat/debug`, `/artifacts/resume/{file_name}`.
- `a2a_routes.py`: A2A card and message/task endpoints.
- `state.py`: in-memory chat and JD context per session.

3. Orchestrator (`modules/multi_agent/client_agent.py`)
- Loads agents from catalog.
- Uses `LLMRouter` for intent parsing.
- Runs single-agent, two-agent resume flow, or multi-agent A2A sequence.

4. Agents (`modules/multi_agent/agents/*.py`)
- `fetch_jobs`, `jd_extractor`, `resume_rewrite`, `naukri_applier`, `external_applier`, `naukri_scraper`.

## Routing source

Catalog file: `modules/multi_agent/config/agent_catalog.yaml`

## Resume flow

`jd_extractor -> resume_rewrite`

## A2A backend endpoints

- `GET /.well-known/agent-card.json`
- `GET /agent-cards`
- `POST /message:send`
- `GET /tasks`
- `GET /tasks/{task_id}`
