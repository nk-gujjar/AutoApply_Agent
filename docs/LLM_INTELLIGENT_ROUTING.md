# LLM Intelligent Routing

`ClientAgent` uses `LLMRouter` to parse:
- `primary_intent`
- `agents_to_call`
- `parameters`
- `confidence`
- `reasoning`

Routing combines:
1. LLM JSON output.
2. Catalog constraints from `agent_catalog.yaml`.
3. Keyword fallback when parsing fails.

Normalization includes:
- payload key filtering by agent `allowed_payload_keys`
- defaults merge from catalog `default_payload`
- type cleanup and safe bounds for numeric values

Notable current behavior:
- Resume-tailoring requests bias to `jd_extractor -> resume_rewrite`.
- Telegram requests route to `telegram_scraper`.
- Telegram job count prefers `max_jobs` from query over default `limit`.
