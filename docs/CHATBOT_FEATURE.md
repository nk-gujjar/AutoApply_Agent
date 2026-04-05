# Chatbot Features

## Supported flows

1. General Q and A (`llm_only`).
2. Job discovery (`fetch_jobs`).
3. Telegram job scraping (`telegram_scraper`).
4. JD extraction (`jd_extractor`).
5. Resume tailoring (`jd_extractor -> resume_rewrite`).
6. Apply flows (`naukri_applier`, `external_applier`).
7. Multi-agent pipeline execution when intent requires it.

## Memory behavior

- Conversation memory is session-based using `session_id`.
- Messages are persisted per session in [data/chat_memory](data/chat_memory).
- The assistant can recall:
  - last query
  - last conversation
  - last JD link
  - last extracted JD details

## Request shape

```json
{
  "query": "give me 5 jobs from @jobs_and_internships_updates",
  "session_id": "demo"
}
```
