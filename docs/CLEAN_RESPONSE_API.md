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

## `POST /chat/debug`

Response includes `status`, `selected_flow`, `response`, `result`, `error`.

## Resume artifacts

When a resume is generated, use:
- `GET /artifacts/resume/{file_name}`