# Changelog

## 2026-04-06 Architecture and Docs Sync

- Updated docs to include `telegram_scraper` in architecture and routing.
- Added Telegram agent behavior notes: user-session auth, multi-job parsing, retry support.
- Updated chat memory docs from in-memory-only to persistent per-session storage in [data/chat_memory](data/chat_memory).
- Updated query examples and quick-start references to current flows.
- Confirmed catalog-driven routing documentation against [modules/multi_agent/config/agent_catalog.yaml](modules/multi_agent/config/agent_catalog.yaml).

## 2026-04-01 Documentation Sync

- Updated backend/frontend/orchestrator behavior documentation.
- Standardized request examples to `{query, session_id}`.
- Added A2A endpoint coverage.
- Aligned resume flow docs to `jd_extractor -> resume_rewrite`.
- Aligned fetch docs to cache-first with live fallback.
