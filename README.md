# AutoApply Agent

AutoApply Agent is a multi-agent job automation system with FastAPI backend, Streamlit frontend, and specialized agents for:

- Telegram job scraping
- Naukri scraping
- JD extraction
- Resume rewriting/tailoring
- Naukri Easy Apply automation
- External apply automation

## Architecture Diagram

![Architecture Diagram](files/archi_diagram.png)

## Architecture Overview

Core flow:

1. User sends query to backend `/chat`.
2. `ClientAgent` uses `LLMRouter` to detect intent and required agents.
3. Request is dispatched through the A2A coordinator to one or more agents.
4. Agent outputs are summarized and returned to frontend/API caller.
5. Optional artifacts (resume PDF) are exposed via `/artifacts/resume/{file_name}`.

Main runtime components:

- Backend API: FastAPI app in `backend/`
- Frontend: Streamlit app in `frontend/chat_frontend.py`
- Multi-agent orchestrator: `modules/multi_agent/`
- Domain logic (scrapers/appliers/CV): `modules/core/`
- Runtime output/log/data: `data/`, `logs/`, `output/`

## API Endpoints

- `GET /health`
- `POST /chat`
- `POST /chat/debug`
- `GET /artifacts/resume/{file_name}`
- `GET /.well-known/agent-card.json`
- `GET /agent-cards`
- `POST /message:send`
- `GET /tasks`
- `GET /tasks/{task_id}`

## Setup

### 1) Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure `.env`

Create `.env` in project root using the parameter-only template in `docs/PROJECT_STRUCTURE_AND_ARCH.md`.

### 4) Configure `personal.txt`

Use the parameter-only sample template in `docs/PROJECT_STRUCTURE_AND_ARCH.md`.

## Run Commands

Run full stack:

```bash
./scripts/run_full_stack.sh
```

Run backend only:

```bash
./scripts/run_backend_server.sh
```

Run frontend only:

```bash
./scripts/run_frontend.sh
```

Send one backend query from terminal:

```bash
./scripts/run_backend_query.sh "fetch 3 jobs with descriptions" "demo-session"
```

## Notes

- LLM provider is Groq-only in current architecture.
- Sessions and generated artifacts are persisted under `data/` and `output/`.
- Logs are written to `logs/autoapply.log`.

## Detailed Technical Doc

For folder-by-folder structure, architecture internals, `.env` parameter format, and `personal.txt` parameter format, see:

- `docs/PROJECT_STRUCTURE_AND_ARCH.md`
