# Start Here

This project now runs with LLM-driven routing, a two-agent JD→resume pipeline, and session-based chat memory.

## What is fixed in current version

- Resume tailoring uses two agents in sequence:
  1. `jd_extractor`
  2. `resume_rewrite`
- JD extraction supports URL input and prefers structured JSON-LD JobPosting when available.
- Resume output returns downloadable artifact metadata.
- Chat memory supports follow-up commands for last query/conversation/JD link/JD details.

## Fast start

```bash
./scripts/run_full_stack.sh
```

Then open:
- Frontend: http://localhost:8501
- Backend: http://127.0.0.1:8000

## First test sequence

Use same `session_id` in all calls.

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"find the jd from https://apply.careers.microsoft.com/careers/job/1970393556640618","session_id":"demo"}' | jq

curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"tell me the jd link","session_id":"demo"}' | jq

curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"what is the jd of the link I gave last time","session_id":"demo"}' | jq
```

## API contract (current)

### Request

```json
{
  "query": "string",
  "session_id": "default"
}
```

### Chat response

```json
{
  "response": "string",
  "error": null,
  "resume_download_url": "/artifacts/resume/<file>.pdf",
  "resume_file_name": "<file>.pdf"
}
```

### Debug response
Includes `status`, `selected_flow`, `result`, and `error` details.

## Key files

- Routing/orchestration: `modules/multi_agent/client_agent.py`
- JD extractor: `modules/multi_agent/agents/jd_extractor_agent.py`
- Resume generation: `modules/core/cv/cv_engine.py`
- Chat memory/state: `backend/api/state.py`
- Chat APIs: `backend/api/chat_routes.py`
- Frontend chat: `frontend/chat_frontend.py`

## Common issue

If changes do not appear, restart backend/frontend processes. Long-running servers keep old code loaded until restarted.
