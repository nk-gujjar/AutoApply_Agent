# Quick Start

## 1) Start the app

```bash
./scripts/run_full_stack.sh
```

- Backend: http://127.0.0.1:8000
- Frontend: http://localhost:8501

## 2) Core query patterns

### Fetch jobs
- `fetch 3 jobs`
- `find remote python roles`

### Extract JD from link
- `find the jd from https://apply.careers.microsoft.com/careers/job/1970393556640618`

### Tailor resume
- `tailor my resume for this jd <paste jd or link>`

Current resume flow is always:
1. `jd_extractor`
2. `resume_rewrite`

### Apply workflows
- `apply on naukri`
- `run full pipeline`

## 3) Session memory commands

Use same `session_id` to get memory-aware responses.

- `tell me my last query`
- `tell me my last conversation`
- `tell me the jd link`
- `what is the jd of the link I gave last time`

## 4) Chat API examples

### Normal chat

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"find the jd from https://apply.careers.microsoft.com/careers/job/1970393556640618","session_id":"demo"}' | jq
```

### Follow-up using memory

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"what is the jd of the link I gave last time","session_id":"demo"}' | jq
```

### Debug endpoint

```bash
curl -s -X POST http://127.0.0.1:8000/chat/debug \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch 2 jobs","session_id":"demo"}' | jq
```

## 5) Resume artifacts

When a resume is generated, `/chat` response includes:
- `resume_download_url`
- `resume_file_name`

Use URL:
- `GET /artifacts/resume/{file_name}`

## 6) Notes

- `session_id` defaults to `default` if not provided.
- If memory answers look wrong, ensure you are using the same session id for all related prompts.
