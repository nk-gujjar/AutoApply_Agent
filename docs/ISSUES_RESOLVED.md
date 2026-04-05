# Issues Resolved and Current Limitations

## Resolved

1. Docs/API payload mismatch.
2. Routing docs drift from catalog-driven implementation.
3. Missing resume artifact behavior in docs.
4. Memory prompt coverage drift.
5. Chat memory persistence gap (now persisted by `session_id`).
6. Telegram bot-session failures in scraper flow (user-session fallback and retries added).

## Current limitations

1. Intent quality depends on active LLM provider/model.
2. Live scraping reliability varies by target site changes/latency.
3. Telegram extraction quality can vary under LLM rate limits.
4. Some root utility tests can lag behind interface changes.
