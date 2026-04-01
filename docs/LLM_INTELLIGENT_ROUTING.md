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

Normalization includes payload key filtering, defaults merge, and type cleanup.
