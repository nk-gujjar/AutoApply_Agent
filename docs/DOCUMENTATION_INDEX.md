# Documentation Index

## Start here
- [START_HERE.md](START_HERE.md): Current architecture and first verification flow.

## User quick guides
- [QUICK_START_LLM.md](QUICK_START_LLM.md): Run, query patterns, API examples.
- [CHATBOT_FEATURE.md](CHATBOT_FEATURE.md): Chat routing, memory commands, debug behavior.

## Technical references
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md): System-level architecture.
- [LLM_INTELLIGENT_ROUTING.md](LLM_INTELLIGENT_ROUTING.md): LLM routing internals and evolution notes.
- [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md): Historical migration notes.

## Current must-know behavior

- Resume tailoring flow: `jd_extractor -> resume_rewrite`
- Chat request fields: `query`, `session_id`
- Memory commands supported:
  - `tell me my last query`
  - `tell me my last conversation`
  - `tell me the jd link`
  - `what is the jd of the link I gave last time`
- Resume artifact metadata returned from `/chat`:
  - `resume_download_url`
  - `resume_file_name`

## Runtime scripts

- [../scripts/run_full_stack.sh](../scripts/run_full_stack.sh): backend + frontend
- [../scripts/run_backend_server.sh](../scripts/run_backend_server.sh): backend only
- [../scripts/run_frontend.sh](../scripts/run_frontend.sh): frontend only
- [../scripts/run_backend_query.sh](../scripts/run_backend_query.sh): CLI call to `/chat` with `session_id`
