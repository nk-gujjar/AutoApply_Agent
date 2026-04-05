# Fetch Jobs Cache Behavior

`FetchJobsAgent` is cache-first by default.

1. Load from `data/naukri_jobs.txt` using `load_cached_jobs`.
2. If unavailable/empty/invalid, fallback to live scrape.
3. Agent data includes `source` as `cache` or `live_scrape`.
4. `max_jobs` is clamped and applied before response rendering.

Payload keys:
- `max_jobs`
- `roles`
- `filters`
- `include_filtered`
- `use_cache` (default `true`)

Response fields:
- `jobs`: list of normalized job objects
- `count`: number of jobs returned
- `source`: `cache` or `live_scrape`
