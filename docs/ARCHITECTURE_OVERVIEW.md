# Architecture Overview

## Layers

1. Frontend ([frontend/chat_frontend.py](frontend/chat_frontend.py))
- Streamlit chat UI.
- Sends `{query, session_id}` to backend.

2. API ([backend/api](backend/api))
- [backend/api/chat_routes.py](backend/api/chat_routes.py): `/health`, `/chat`, `/chat/debug`, `/artifacts/resume/{file_name}`.
- [backend/api/a2a_routes.py](backend/api/a2a_routes.py): A2A card/message/task endpoints.
- [backend/api/state.py](backend/api/state.py): chat state, JD context, and persistence helpers.

3. Orchestrator ([modules/multi_agent/client_agent.py](modules/multi_agent/client_agent.py))
- Loads agent instances from catalog.
- Uses [modules/multi_agent/llm_router.py](modules/multi_agent/llm_router.py) for intent parsing.
- Executes:
	- `llm_only`
	- single-agent flow
	- two-agent resume flow (`jd_extractor -> resume_rewrite`)
	- multi-agent A2A sequence when needed.

4. Agents ([modules/multi_agent/agents](modules/multi_agent/agents))
- `fetch_jobs`
- `telegram_scraper`
- `jd_extractor`
- `resume_rewrite`
- `naukri_applier`
- `external_applier`
- `naukri_scraper`

## Routing source

- Catalog file: [modules/multi_agent/config/agent_catalog.yaml](modules/multi_agent/config/agent_catalog.yaml)
- Routing manifest is generated from catalog metadata (intent hints, defaults, allowed payload keys).

## Telegram scraping flow

- Agent: [modules/multi_agent/agents/telegram_scraper_agent.py](modules/multi_agent/agents/telegram_scraper_agent.py)
- Core scraper: [modules/core/scrapers/telegram_job_scraper.py](modules/core/scrapers/telegram_job_scraper.py)
- Behavior:
	- Uses user Telegram session (not bot session) for channel history.
	- Retries up to 5 attempts on agent-level failures.
	- Supports multi-job extraction from a single Telegram message.

## Chat memory persistence

- Runtime memory object: `InMemoryChatMessageHistory`.
- Persistence location: [data/chat_memory](data/chat_memory).
- One JSON file per `session_id`.
- Memory survives backend restarts when same `session_id` is reused.

## A2A backend endpoints

- `GET /.well-known/agent-card.json`
- `GET /agent-cards`
- `POST /message:send`
- `GET /tasks`
- `GET /tasks/{task_id}`
