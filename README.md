# AutoApply Multi-Agent System (A2A)

This project is organized as a multi-agent system where a **client agent** receives a user query, communicates with specialized agents, uses tools/MCP when needed, and returns a single response.

## 📚 Documentation

All documentation is organized in the [`docs/`](docs/) folder. [**Start here →**](docs/START_HERE.md)

**Quick Links:**
- 🚀 [Quick Start Guide](docs/QUICK_START_LLM.md)
- 🏗️ [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- 🧠 [LLM Intelligent Routing](docs/LLM_INTELLIGENT_ROUTING.md)
- 📖 [Full Documentation Index](docs/DOCUMENTATION_INDEX.md)

## Agents

- `naukri_scraper` → Scrapes Naukri jobs (`modules/core/scrapers/naukri_scraper.py`)
- `fetch_jobs` → Streams and filters jobs (`modules/core/scrapers/fetch_job.py`)
- `resume_rewrite` → Generates tailored resumes/CVs (`modules/core/cv/cv_engine.py`)
- `naukri_applier` → Applies on Naukri (`modules/core/appliers/naukri_applier.py`)
- `external_applier` → Applies on external company sites (`modules/core/appliers/external_apply.py`)

The client orchestrator is in `modules/multi_agent/client_agent.py` and entrypoint is `main.py`.
Core implementations are organized under `modules/core/*`.

## A2A Communication Flow

1. User sends a query to `ClientAgent`
2. `ClientAgent` creates an A2A message with `correlation_id`
3. `A2ACoordinator` uses A2A HTTP+JSON (`/message:send`) to communicate with one or more specialized agents
4. Agents execute tasks and return structured results
5. Client agent aggregates agent/tool outputs and returns one final response

The local A2A implementation also publishes per-agent cards at:
- `/.well-known/agent-card.json`

Core A2A files:
- `modules/multi_agent/a2a.py`
- `modules/multi_agent/client_agent.py`
- `modules/multi_agent/models.py`
- `modules/multi_agent/agent_catalog.py`

Scalable onboarding:
- Add new agents once in `modules/multi_agent/config/agent_catalog.yaml`
- Client orchestration, routing hints, and agent-card metadata are auto-derived from the catalog
- No manual hardcoding in backend card list required
- `modules/multi_agent/agent_catalog.py` now loads and validates this YAML at startup

Backend modularization:
- `backend/api/schemas.py` -> shared request/response schemas
- `backend/api/chat_routes.py` -> chat endpoints
- `backend/api/a2a_routes.py` -> A2A endpoints
- `backend/api/state.py` -> app state (client agent + task store)
- `backend/api/app.py` -> FastAPI assembly
- `backend/server.py` -> minimal entrypoint

## Project Structure

```text
AutoApply_Agent/
├── main.py
├── modules/
│   └── core/
│       ├── config/settings.py
│       ├── scrapers/
│       │   ├── naukri_scraper.py
│       │   └── fetch_job.py
│       ├── appliers/
│       │   ├── naukri_applier.py
│       │   └── external_apply.py
│       ├── cv/cv_engine.py
│       ├── forms/fill_form.py
│       └── profile/human_loop.py
│
│   └── multi_agent/
│       ├── a2a.py
│       ├── client_agent.py
│       ├── agents/
│       ├── mcp/
│       └── tools/
├── data/
├── output/
├── logs/
└── requirements.txt
```

## Setup

1. Create/activate virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

Optional (if Streamlit was not installed by requirements):

```bash
pip install streamlit
```

3. Configure `.env` (required keys)

```env
NAUKRI_EMAIL=your_email
NAUKRI_PASSWORD=your_password
GROQ_API_KEY=optional_if_using_groq
GEMINI_API_KEY=optional_if_using_gemini
```

4. Update profile details in `personal.txt`.

## How to Run

### 1) Full pipeline (recommended)

```bash
python main.py --mode pipeline --max-jobs 10
```

### 1.1) Query mode (client agent talks to other agents)

```bash
python main.py --mode query --query "fetch jobs"
python main.py --mode query --query "rewrite resume"
python main.py --mode query --query "apply on naukri"
python main.py --mode query --query "external apply"
python main.py --mode query --query "run full pipeline" --max-jobs 10
python main.py --mode a2a-cards
```

## Backend + Frontend (Recommended)

Do not run individual agents directly. Run the backend server once, then send all user queries from frontend.

### Start backend server

```bash
./scripts/run_backend_server.sh
```

Backend endpoints:
- `GET http://127.0.0.1:8000/health`
- `POST http://127.0.0.1:8000/chat`
- `GET http://127.0.0.1:8000/.well-known/agent-card.json` (A2A discovery)
- Returns client agent card + `agentCards` list (naukri_scraper, fetch_jobs, resume_rewrite, naukri_applier, external_applier)
- `GET http://127.0.0.1:8000/agent-cards` (direct list response)
- `POST http://127.0.0.1:8000/message:send` (A2A send message)
- `GET http://127.0.0.1:8000/tasks/{id}` (A2A get task)
- `GET http://127.0.0.1:8000/tasks` (A2A list tasks)

### A2A quick test (external agent style)

```bash
curl -s http://127.0.0.1:8000/.well-known/agent-card.json | jq
curl -s http://127.0.0.1:8000/agent-cards | jq

curl -s -X POST http://127.0.0.1:8000/message:send \
	-H 'Content-Type: application/json' \
	-H 'A2A-Version: 1.0' \
	-d '{
		"message": {
			"messageId": "msg-1",
			"role": "ROLE_USER",
			"parts": [{"text": "fetch 2 jobs with descriptions"}]
		}
	}' | jq
```

### Start frontend chat UI

```bash
./scripts/run_frontend.sh
```

In the UI, ask natural queries. Backend routes to required agent(s) automatically.

### Start full stack with one command

```bash
./scripts/run_full_stack.sh
```

`run_backend_server.sh` and `run_full_stack.sh` now auto-clear stale processes on port `8000` before startup.

### 1.2) Chat Frontend (simple UI like chat model)

Run:

```bash
streamlit run frontend/chat_frontend.py
```

Then open the local URL shown by Streamlit (usually `http://localhost:8501`) and ask queries in chat.

Example queries:
- `fetch jobs`
- `rewrite resume`
- `apply on naukri`
- `run full pipeline`

Frontend now supports:
- Chat API mode (`/chat`, `/chat/debug`)
- A2A API mode (`/message:send`)
- Live agent registry view from `/agent-cards`

## Final Run Commands

```bash
cd /Users/niteshkumar/Documents/other/AutoApply_Agent

# 1) Start backend
./scripts/run_backend_server.sh

# 2) In another terminal, start frontend
./scripts/run_frontend.sh

# 3) Validate A2A cards
curl -s http://127.0.0.1:8000/.well-known/agent-card.json | jq '{managedAgents:.metadata.managedAgents,count:.agentCardsCount}'

# 4) Validate A2A message flow
curl -s -X POST http://127.0.0.1:8000/message:send \
	-H "Content-Type: application/json" \
	-H "A2A-Version: 1.0" \
	-d '{"message":{"messageId":"msg-1","role":"ROLE_USER","parts":[{"text":"fetch 2 jobs with descriptions"}]}}' | jq
```

If LLM connectivity is down, backend/frontend return a clean failure response instead of crashing.

Example response includes:
- `selected_flow`
- `response`
- `correlation_id` or A2A conversation `result`
- step-by-step agent execution data

### 2) Run individual agents

```bash
python main.py --mode naukri-scraper --max-jobs 10
python main.py --mode fetch-jobs --max-jobs 10
python main.py --mode resume-rewrite
python main.py --mode naukri-apply
python main.py --mode external-apply
```

### 3) MCP mode

List MCP tools:

```bash
python main.py --mode mcp-tools
```

Run through MCP routing:

```bash
python main.py --mode pipeline --mcp
```

## Useful Notes

- Output/job files are written under `data/`.
- Generated resumes are saved under `output/`.
- Logs are in `logs/autoapply.log`.
- If browser automation fails, run with visible browser from underlying scripts where applicable.
- For MCP routing, add `--mcp` to supported modes.
