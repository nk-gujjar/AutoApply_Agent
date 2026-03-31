# Chatbot Features (Current)

## Overview
The chatbot uses LLM intent parsing and agent orchestration. It supports plain Q&A, JD extraction, resume tailoring, and apply flows.

## Routing behavior

### LLM-only
General questions are answered directly by LLM.

Examples:
- `What is Python?`
- `How should I prepare for interviews?`

### Agent-driven
Job automation requests call agents.

Key flows:
- JD extraction: `jd_extractor`
- Resume tailoring: `jd_extractor -> resume_rewrite`
- Job fetching: `fetch_jobs`
- Apply flows: `naukri_applier`, `external_applier`

## Chat request format

```json
{
  "query": "tailor resume for this jd https://...",
  "session_id": "demo"
}
```

`session_id` enables in-chat memory for follow-up prompts.

## Memory features

Supported prompts:
- `tell me my last query`
- `tell me my last conversation`
- `tell me the jd link`
- `what is the jd of the link I gave last time`

JD memory stores:
- last extracted JD link
- last extracted structured JD data (title/description/qualifications/skills)

## Resume artifact support

When resume generation succeeds, chat response contains:
- `resume_download_url`
- `resume_file_name`

Frontend exposes View/Download actions using this metadata.

## Debug mode

`POST /chat/debug` returns:
- `selected_flow`
- `status`
- `response`
- `result` (flow-specific details)
- `error` (if any)

## Example tests

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
