# Fetch Jobs Cache Behavior

`FetchJobsAgent` is cache-first by default.

1. Load from `data/naukri_jobs.txt` using `load_cached_jobs`.
2. If unavailable/empty/invalid, fallback to live scrape.
3. Agent data includes `source` as `cache` or `live_scrape`.

Payload keys:
- `max_jobs`
- `roles`
- `filters`
- `include_filtered`
- `use_cache` (default `true`)
