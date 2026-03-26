# Chatbot LLM & Agent Integration

## Overview
The chatbot now intelligently routes queries:
- **LLM Response**: For generic queries that don't match agent keywords
- **Agent Routing**: For specific job-related queries (fetch, resume, apply, etc.)

## How It Works

### 1. Query Analysis
When a user sends a query to `/chat` endpoint:
```
POST /chat
{
  "query": "your query here",
  "use_mcp": false,
  "max_jobs": 5
}
```

### 2. Flow Decision
The `ClientAgent.handle_query()` method checks if the query contains agent keywords:

**Agent Keywords** (requires agent):
- `fetch_jobs`: "fetch", "scrape", "jobs list", "find jobs"
- `resume_rewrite`: "resume", "cv", "rewrite"
- `naukri_applier`: "naukri apply", "apply naukri", "apply on naukri"
- `external_applier`: "external apply", "company site", "external"
- `full pipeline`: "full", "pipeline", "all agents", "end to end"

**No Keywords** (uses LLM):
Any other query without above keywords → LLM generates response

### 3. Response Format

#### Example 1: LLM Response (Generic Query)
**Request:**
```json
{
  "query": "tell me about python programming",
  "use_mcp": false
}
```

**Response:**
```json
{
  "status": "ok",
  "query": "tell me about python programming",
  "selected_flow": "llm",
  "response": "Python is a high-level, interpreted programming language...",
  "result": {
    "type": "llm_response",
    "content": "Python is a high-level, interpreted programming language..."
  },
  "error": null
}
```

#### Example 2: Agent Response (Job Fetch Query)
**Request:**
```json
{
  "query": "fetch jobs",
  "use_mcp": false,
  "max_jobs": 1
}
```

**Response:**
```json
{
  "status": "ok",
  "query": "fetch jobs",
  "selected_flow": "fetch_jobs",
  "response": "Found 1 jobs. Showing top 1:\n1. SSR-200-AI Engineer at S S Rana & Co | New Delhi(Adhchini) | 0-2 Yrs | easy_apply",
  "correlation_id": "bbe4f444-3bd4-4b45-aedf-c23a51149cd6",
  "fetch_details": {
    "summary": "Found 1 jobs. Showing top 1:...",
    "jobs": [...]
  },
  "result": {...}
}
```

## Features

### ✅ Implemented
1. **LLM-Based Generic Responses** - Uses Ollama (llama3.2) for queries without agent keywords
2. **Intelligent Agent Routing** - Keyword-based routing to appropriate agents
3. **Hybrid Flow** - Agents handle job-specific tasks, LLM handles general knowledge
4. **Formatted Responses** - Job details are reformatted for readability
5. **Error Handling** - Graceful fallback when LLM fails

### 🔄 Architecture
```
┌─────────────────────┐
│  User Query         │
│  (via Frontend)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│ ClientAgent.handle_query()      │
│ - Check query keywords          │
└──────────┬──────────┬───────────┘
           │          │
    Agent Match  No Match
           │          │
           ▼          ▼
    ┌─────────┐  ┌──────────┐
    │ Agent   │  │ LLM      │
    │ Routing │  │ Response │
    │ System  │  │ Generator│
    └─────────┘  └──────────┘
           │          │
           └────┬─────┘
                ▼
        ┌──────────────┐
        │ Formatted    │
        │ Response     │
        └──────────────┘
```

## Testing

### Test 1: LLM Response
```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"how to write clean code","use_mcp":false}'
```
Expected: Returns LLM-generated response with `"selected_flow": "llm"`

### Test 2: Agent Query
```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch jobs","use_mcp":false,"max_jobs":1}'
```
Expected: Calls fetch_jobs agent with `"selected_flow": "fetch_jobs"`

### Test 3: Resume Query
```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"rewrite my resume","use_mcp":false}'
```
Expected: Routes to resume_rewrite agent with `"selected_flow": "resume_rewrite"`

## Configuration

### LLM Settings
- **Provider**: Ollama (local)
- **Model**: llama3.2
- **Base URL**: http://localhost:11434
- **Temperature**: 0 (deterministic)

### Agent Keywords
Located in: `modules/multi_agent/client_agent.py`
- Method: `_requires_agent()`
- Easily customizable for new agents

## Usage Examples

### In Python
```python
from modules.multi_agent import ClientAgent

agent = ClientAgent()

# Generic query
result = await agent.handle_query("What is artificial intelligence?")
# Returns LLM response

# Agent query
result = await agent.handle_query("fetch jobs", max_jobs=5)
# Returns agent result with formatted jobs
```

### Via REST API
User can use any HTTP client to send queries to the `/chat` endpoint.

## Future Enhancements
1. LLM-based intent recognition (instead of keyword matching)
2. Response formatting for all agent types (not just fetch_jobs)
3. Context-aware responses using conversation history
4. Streaming responses for long-running agents
5. Agent selection using LLM (like ReAct pattern)

## Troubleshooting

### Backend Returns 500 Error
- Check if Ollama is running: `curl http://localhost:11434/api/tags`
- Start Ollama: `bash scripts/start_ollama_safe.sh`

### LLM Times Out
- Ollama might be processing. Try with a simpler query first.
- Check Ollama status: `ollama list`

### Agent Query Returns Empty Response
- Make sure .env credentials are set (NAUKRI_EMAIL, NAUKRI_PASSWORD)
- Check backend logs for detailed errors
