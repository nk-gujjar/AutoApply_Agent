# Chatbot Features

## Supported flows

1. General Q and A (`llm_only`).
2. Job discovery (`fetch_jobs`).
3. JD extraction (`jd_extractor`).
4. Resume tailoring (`jd_extractor -> resume_rewrite`).
5. Apply flows (`naukri_applier`, `external_applier`).
6. Multi-agent pipeline execution when intent requires it.

## Request shape

```json
{
  "query": "tailor resume for this jd https://...",
  "session_id": "demo"
}
```
