# AutoApply Multi-Agent System

AutoApply is a FastAPI + Streamlit application that routes user queries through a multi-agent system for job fetch, JD extraction, resume tailoring, and application automation.

## Current Architecture

### Core Agents
- `jd_extractor`: Extracts structured JD from URL/text/query (prefers JSON-LD JobPosting when available).
- `resume_rewrite`: Builds tailored resume PDF using extracted JD.
- `fetch_jobs`: Fetches and summarizes jobs.
- `naukri_applier`: Applies on Naukri flows.
- `external_applier`: Handles external apply flows.

### Resume Flow (Current)
For resume-tailoring queries, system uses two-agent pipeline:
1. `jd_extractor`
2. `resume_rewrite`

This is orchestrated in `modules/multi_agent/client_agent.py`.

### Chat Memory (Current)
Session-aware memory is handled in `backend/api/state.py` and used by `/chat` and `/chat/debug`.

Supported memory queries:
- `tell me my last query`
- `tell me last query`
- `tell me my last conversation`
- `show me my last conversation`
- JD memory follow-ups such as:
  - `tell me the jd link`
  - `what is the jd of the link I gave last time`

## Project Layout

```text
AutoApply_Agent/
├── backend/
│   ├── server.py
│   └── api/
│       ├── app.py
│       ├── chat_routes.py
│       ├── a2a_routes.py
│       ├── schemas.py
│       └── state.py
├── frontend/
│   └── chat_frontend.py
├── modules/
│   ├── core/
│   │   ├── cv/cv_engine.py
│   │   ├── scrapers/
│   │   └── appliers/
│   └── multi_agent/
│       ├── client_agent.py
│       ├── llm_router.py
│       ├── a2a.py
│       ├── agent_catalog.py
│       └── agents/
├── scripts/
└── docs/
```

## Setup

1. Create and activate virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

3. Configure `.env`:

```env
NAUKRI_EMAIL=your_email
NAUKRI_PASSWORD=your_password
GROQ_API_KEY=optional
GEMINI_API_KEY=optional
```

4. Update your profile in `personal.txt`.

## Run

### Full stack (recommended)

```bash
./scripts/run_full_stack.sh
```

### Backend only

```bash
./scripts/run_backend_server.sh
```

### Frontend only

```bash
./scripts/run_frontend.sh
```

## APIs

### Health
- `GET /health`

### Chat
- `POST /chat`
- `POST /chat/debug`

Request shape:

```json
{
  "query": "find jd from https://...",
  "session_id": "user-1"
}
```

### Resume artifacts
- `GET /artifacts/resume/{file_name}`

When resume is generated, `/chat` response includes:
- `resume_download_url`
- `resume_file_name`

## Quick Test

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"find jd from https://apply.careers.microsoft.com/careers/job/1970393556640618","session_id":"demo"}' | jq

curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"what is the jd of the link I gave last time","session_id":"demo"}' | jq
```

## Notes

- Generated resumes are stored under `output/`.
- Runtime data files are under `data/`.
- Backend and full-stack scripts clear stale process on port `8000` before startup.
- If LLM provider is unavailable, API returns graceful failure response instead of crashing.
