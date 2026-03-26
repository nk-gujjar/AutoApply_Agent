# 🧠 LLM-Powered Intelligent Routing - Complete Guide

## Overview

The AutoApply system has been upgraded from manual keyword matching to **LLM-based intelligent routing**. The system now:

✅ **Understands natural language** - No manual parameters needed
✅ **Extracts parameters intelligently** - "fetch 1 job" → max_jobs=1
✅ **Routes to the right agent** - LLM decides which agent(s) to call
✅ **Handles complex workflows** - Multi-agent orchestration
✅ **Adapts responses** - Format depends on context
✅ **Fallback mechanism** - Works even if LLM fails

---

## Architecture Changes

### Before (Manual Keyword Matching)
```
User Query
    ↓
Keyword-based routing (IF "fetch" THEN ...)
    ↓
Fixed parameters (max_jobs=5, use_mcp=False)
    ↓
Single agent call
    ↓
Static response format
```

### After (LLM-Based Intelligent Routing)
```
User Query ("fetch 1 job")
    ↓
LLM Intent Parser
    ├─ Intent: fetch_jobs
    ├─ Parameters: {max_jobs: 1}
    ├─ Agents: ["fetch_jobs"]
    └─ Confidence: 0.95
    ↓
Intelligent Router
    ├─ Single agent → direct call
    └─ Multiple agents → orchestrated sequence
    ↓
Agent Execution
    ├─ fetch_jobs with extracted parameters
    └─ Results aggregation
    ↓
Smart Response Formatting
    ├─ User response (humanoid, emoji-rich)
    └─ Optional technical details (debug mode)
```

---

## Key Components

### 1. LLMRouter (`modules/multi_agent/llm_router.py`)

**Responsibility**: Parse user intent and extract parameters using LLM

**Features**:
- Uses LLM to understand complex natural language queries
- Extracts parameters like max_jobs, keywords, filters
- Determines which agent(s) to call
- Provides fallback using keyword matching if LLM fails
- Returns `ParsedIntent` with confidence score

**Example Usage**:
```python
router = LLMRouter()
intent = await router.parse_intent("fetch me 3 AI engineer job opportunities")

# Returns:
# ParsedIntent(
#   primary_intent="fetch_jobs",
#   agents_to_call=["fetch_jobs"],
#   parameters={"max_jobs": 3, "keywords": "AI engineer"},
#   confidence=0.95,
#   reasoning="User requested 3 specific job opportunities"
# )
```

### 2. Updated ClientAgent (`modules/multi_agent/client_agent.py`)

**Changes**:
- Added `LLMRouter` initialization
- Replaced `handle_query(query, use_mcp, max_jobs)` with `handle_query(query)`
- Removed hardcoded keyword matching
- Added intent-based routing methods:
  - `_handle_llm_only()` - General questions
  - `_handle_fetch_jobs()` - Job fetching
  - `_handle_resume_rewrite()` - Resume rewriting
  - `_handle_naukri_applier()` - Naukri applications
  - `_handle_external_applier()` - Direct company applications
  - `_handle_multi_agent_flow()` - Complex workflows

**Key Method**:
```python
async def handle_query(self, query: str) -> Dict[str, Any]:
    # 1. Parse intent using LLM
    intent = await self.llm_router.parse_intent(query)
    
    # 2. Route based on intent
    if intent.primary_intent == "fetch_jobs":
        return await self._handle_fetch_jobs(query, correlation_id, intent)
    elif intent.primary_intent == "llm_only":
        return await self._handle_llm_only(query, correlation_id, intent)
    # ... other intents
```

### 3. Simplified Backend API (`backend/server.py`)

**Request Model Before**:
```python
class ChatRequest(BaseModel):
    query: str
    use_mcp: bool = False
    max_jobs: int = 5  # ❌ Manual setting
```

**Request Model After**:
```python
class ChatRequest(BaseModel):
    query: str  # ✅ Only query needed!
    # LLM extracts everything else
```

**API Endpoints**:
- `POST /chat` - User-facing (clean response only)
- `POST /chat/debug` - Developer-facing (full technical data)

### 4. Streamlined Frontend (`frontend/chat_frontend.py`)

**Removed**:
- ❌ `use_mcp` toggle
- ❌ `max_jobs` slider
- ❌ Backend URL input (still available, hidden by default)

**Remaining**:
- ✅ Query input box
- ✅ Debug mode toggle (for developers)
- ✅ Backend URL configuration (optional)

**New Features**:
- Shows intent parsing details in debug mode
- Displays extracted parameters
- Shows which agents were called
- Confidence score of intent detection

---

## How It Works: Examples

### Example 1: "Fetch 1 Job"

**User Input**: "fetch 1 job"

**Behind the scenes**:
1. LLM parses: `{"max_jobs": 1, "primary_intent": "fetch_jobs"}`
2. backend.py routes to `client_agent.handle_query("fetch 1 job")`
3. ClientAgent uses LLMRouter to parse intent
4. Calls fetch_jobs agent with `max_jobs=1` (extracted by LLM!)
5. Returns exactly 1 job (not 5!)

**User Sees**:
```
✨ Great! I found **1** matching jobs from our cached database.
Here are the 1 opportunities:

1. **Gen AI Engineer** @ Dentsu Webchutney
   📍 Location: Pune | 📅 Exp: 1-3 Yrs
   💰 CTC: Not mentioned | 🔗 Apply: external

📦 Data from: cached database
```

### Example 2: "What is Machine Learning?"

**User Input**: "What is Machine Learning?"

**Behind the scenes**:
1. LLM parses: `{"primary_intent": "llm_only", "confidence": 0.98}`
2. Not a specific agent request, so routes to LLM
3. LLM generates response

**User Sees**:
```
Machine Learning is a subset of artificial intelligence...
[Full LLM response]
```

### Example 3: "Apply Full Pipeline"

**User Input**: "apply full pipeline and prepare all documents"

**Behind the scenes**:
1. LLM parses:
```json
{
  "primary_intent": "fetch_jobs",
  "agents_to_call": ["fetch_jobs", "resume_rewrite", "naukri_applier", "external_applier"],
  "parameters": {"max_jobs": 5},
  "confidence": 0.92
}
```
2. Detects multi-agent workflow
3. Calls `_handle_multi_agent_flow()`
4. Executes agents in sequence using A2A coordinator
5. Returns aggregated results

**User Sees**:
```
🔄 Executed multi-agent pipeline: fetch_jobs, resume_rewrite, naukri_applier, external_applier
[Detailed results from each agent]
```

### Example 4: Debug Mode - "Fetch 2 jobs"

**User Input**: "Fetch 2 jobs"
**Debug Mode**: ON

**User Sees**:
```
**Intent Confidence**: 0.96
**Intent Reasoning**: User requested 2 specific job opportunities
**Extracted Parameters**: {"max_jobs": 2, "filters": {}}
**Flow Selected**: fetch_jobs
**Agents Executed**: fetch_jobs

✨ Great! I found **2** matching jobs...

### Full Backend Data (Debug):
{
  "status": "ok",
  "query": "Fetch 2 jobs",
  "selected_flow": "fetch_jobs",
  "intent_confidence": 0.96,
  "reasoning": "User requested 2 specific job opportunities",
  "extracted_params": {
    "max_jobs": 2,
    "filters": {}
  },
  "fetch_details": {
    "jobs": [...],
    "source": "cache"
  }
}
```

---

## API Request Examples

### Simple Query (No Parameters Needed!)

**Before** ❌:
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "fetch jobs",
    "use_mcp": false,
    "max_jobs": 5
  }'
```

**After** ✅:
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "fetch 3 jobs"
  }'
```

The backend automatically:
1. Parses "3 jobs" → `max_jobs: 3`
2. Detects `fetch_jobs` intent
3. Calls the agent with correct parameters

---

## LLM Intent Parsing Details

### Prompt Template

The LLMRouter sends this structured prompt to the LLM:

```
You are an intelligent job automation router. Analyze the query and determine:
1. Primary intent (fetch_jobs, resume_rewrite, naukri_applier, external_applier, llm_only)
2. Parameters to extract (max_jobs, filters, keywords, etc.)
3. If multiple agents should run

User Query: "fetch me 2 AI engineer jobs in Bangalore"

Respond in JSON format:
{
  "primary_intent": "fetch_jobs",
  "agents_to_call": ["fetch_jobs"],
  "parameters": {
    "max_jobs": 2,
    "filters": {
      "location": "Bangalore",
      "keywords": "AI engineer"
    },
    "keywords": "AI engineer"
  },
  "confidence": 0.95,
  "reasoning": "User requested 2 jobs with specific filters"
}
```

### Parameter Extraction Rules

| Query Pattern | Extracted Parameter | Example |
|---------------|-------------------|---------|
| "fetch 1 job" | `max_jobs: 1` | ✅ Returns 1 job |
| "fetch 5 jobs" | `max_jobs: 5` | ✅ Returns 5 jobs |
| "find opportunities" | `max_jobs: 5` (default) | ✅ Returns 5 jobs |
| "AI engineer" | `keywords: "AI engineer"` | ✅ Filters by keyword |
| "remote jobs" | `filters: {location: "remote"}` | ✅ Filters by location |

### Intent Detection

| Query | Intent | Confidence | Reasoning |
|-------|--------|-----------|-----------|
| "fetch jobs" | fetch_jobs | 0.95 | Clear job fetching intent |
| "rewrite resume" | resume_rewrite | 0.95 | Clear resume intent |
| "apply on naukri" | naukri_applier | 0.95 | Platform-specific |
| "full pipeline" | fetch_jobs (multi-agent) | 0.90 | Complex workflow |
| "what is Python?" | llm_only | 0.98 | General question |

---

## Fallback Mechanism

If LLM fails or returns invalid response:

1. **Timeout or Error**: Use keyword-based fallback
2. **Invalid JSON**: Parse keywords from raw response
3. **Keyword Matching Fallback**:
   - "fetch" → fetch_jobs
   - "resume" → resume_rewrite
   - "naukri" → naukri_applier
   - "external" → external_applier
   - Other → llm_only

```python
def _fallback_intent(self, query: str) -> ParsedIntent:
    q = query.lower()
    
    if "fetch" in q:
        max_jobs = self._extract_max_jobs_fallback(q)  # Regex extraction
        return ParsedIntent(
            primary_intent="fetch_jobs",
            parameters={"max_jobs": max_jobs},
            confidence=0.7,  # Lower confidence
            reasoning="Using keyword fallback"
        )
    # ... other fallbacks
```

---

## Benefits

### For Users 👥
- ✅ **No manual settings** - Just ask naturally
- ✅ **Intelligent parameters** - "1 job" correctly returns 1 job
- ✅ **Natural language** - Ask however you want
- ✅ **Multi-step workflows** - "Apply pipeline" does everything
- ✅ **Simple interface** - Query box + optional debug mode

### For Developers 👨‍💻
- ✅ **Easy to extend** - Add new intents in LLMRouter
- ✅ **Debug mode** - See all intent parsing details
- ✅ **Confidence scores** - Know how sure the LLM is
- ✅ **Fallback mechanism** - Works even if LLM fails
- ✅ **Clean API** - Simplified request/response models

### For System 🤖
- ✅ **Scalable** - LLM can handle new intent types
- ✅ **Flexible** - Parameters extracted on-the-fly
- ✅ **Robust** - Fallback for errors
- ✅ **Performance** - Cache-first job fetching (300x faster)
- ✅ **Maintainable** - Clear separation of concerns

---

## Testing Guide

### Test 1: Parameter Extraction
```bash
# Should return exactly 1 job (not 5)
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query": "fetch 1 job"}'
```

**Expected Response**:
```json
{
  "response": "✨ Great! I found **1** matching jobs..."
}
```

### Test 2: Multi-Word Phrases
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query": "I want 3 AI engineer positions"}'
```

**Expected**: 
- Intent: fetch_jobs
- Parameters: max_jobs=3, keywords="AI engineer"

### Test 3: General Questions
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is machine learning?"}'
```

**Expected**:
- Intent: llm_only
- Response: LLM-generated answer

### Test 4: Debug Mode
```bash
curl -X POST http://127.0.0.1:8000/chat/debug \
  -H 'Content-Type: application/json' \
  -d '{"query": "fetch 2 jobs"}'
```

**Expected**: Full technical data with intent parsing details

---

## Frontend Changes Guide

### Starting the System

Same as before:
```bash
./scripts/run_full_stack.sh
```

### Using the Frontend

1. Open http://localhost:8501
2. Enter query in chat box (no manual settings!)
3. See response from appropriate agent(s)
4. Toggle "Debug Mode" to see technical details

### Debug Mode

When enabled, you see:
- Intent confidence (0.0-1.0)
- Intent reasoning
- Extracted parameters
- Selected flow/agents
- Full backend data

---

## Configuration

### LLM Model
Default: `llama3.2` via Ollama

To use different model:
```python
# In modules/core/config/settings.py
def create_llm():
    return Ollama(model="your-model-name", ...)
```

### Parameter Constraints
```python
# In llm_router.py
- max_jobs: Clamped to 1-25
- max_jobs default: 5
- Timeout: 180 seconds
```

---

## Migration Guide (For Existing Code)

### Backend Usage
```python
# Old
result = await client_agent.handle_query(
    query="fetch jobs",
    use_mcp=False,
    max_jobs=5
)

# New
result = await client_agent.handle_query(query="fetch jobs")
# LLM handles parameter extraction!
```

### API Calls
```bash
# Old endpoint (still works but simplified)
curl -X POST /chat -d '{"query": "...", "max_jobs": 5}'

# New way (recommended)
curl -X POST /chat -d '{"query": "..."}'
```

---

## Troubleshooting

### Issue: "Still getting 5 jobs when asking for 1"
**Check**:
1. Backend is using new client_agent code ✅
2. LLM is running (`ollama serve`) ✅
3. Restart backend server

### Issue: LLM returns "failed to parse"
**Check**:
1. Ollama is running: `curl http://localhost:11434/api/tags`
2. Model exists: `ollama list`
3. Network connectivity
4. Fallback mechanism should kick in (check logs)

### Issue: Debug mode shows "unknown agent"
**Check**:
1. Agent is registered in ClientAgent.__init__
2. Agent name matches one of: fetch_jobs, resume_rewrite, naukri_applier, external_applier

---

## Future Enhancements

1. **Conversation History** - Remember context across queries
2. **User Preferences** - Learn user's preferred parameters
3. **Custom Commands** - User-defined voice commands
4. **Multi-Language** - Support for multiple languages
5. **Analytics** - Track most common intents and parameters
6. **Fine-tuning** - Fine-tune LLM on domain-specific queries
7. **Voice Integration** - Ask via voice commands

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| Parameter Setting | Manual (slider) | LLM extracts |
| Query Processing | Keyword matching | LLM-based intent parsing |
| User Interface | Settings panel | Simple query box |
| API Request | 3 required fields | 1 required field |
| max_jobs=1 Query | Returns 5 (bug) | Returns 1 ✅ |
| Multi-agent workflow | Hardcoded | Dynamically determined |
| Fallback | None | Keyword matching |
| Debug Info | Generic | Intent-specific |

**Result**: 🎉 Smarter, simpler, more intuitive system!
