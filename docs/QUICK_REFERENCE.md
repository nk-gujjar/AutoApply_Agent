# Quick Reference

## Run

```bash
./scripts/run_full_stack.sh
./scripts/run_backend_server.sh
./scripts/run_frontend.sh
```

## Main endpoints

- `GET /health`
- `POST /chat`
- `POST /chat/debug`
- `GET /artifacts/resume/{file_name}`
- `GET /.well-known/agent-card.json`
- `GET /agent-cards`
- `POST /message:send`
- `GET /tasks`
- `GET /tasks/{task_id}`

## `/chat` request

```json
{
  "query": "fetch 3 jobs",
  "session_id": "demo"
}
```
