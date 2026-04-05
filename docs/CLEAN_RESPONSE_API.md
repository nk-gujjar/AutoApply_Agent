# Clean Response API Contract

## `POST /chat`

Request:

```json
{
  "query": "fetch 2 jobs",
  "session_id": "demo"
}
```

Response:

```json
{
  "response": "Found 2 jobs...",
  "error": null,
  "resume_download_url": null,
  "resume_file_name": null
}
```

Notes:
- `session_id` controls per-session conversation memory.
- Chat memory is persisted on disk in [data/chat_memory](data/chat_memory).

## `POST /chat/debug`

Response includes: `status`, `query`, `selected_flow`, `response`, `result`, `error`.

Typical `selected_flow` values:
- `llm_only`
- `fetch_jobs`
- `telegram_scraper`
- `jd_extractor`
- `resume_rewrite`
- `multi_agent_pipeline`

## Resume artifacts

When a resume is generated, use:
- `GET /artifacts/resume/{file_name}`