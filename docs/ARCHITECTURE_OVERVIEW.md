# 🏗️ Architecture - LLM Intelligent Routing System

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│                  (Streamlit Frontend)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Query Input:                                        │  │
│  │  "fetch 1 job"                                       │  │
│  │                                                      │  │
│  │  Settings (Optional):                               │  │
│  │  • Backend URL (default: 127.0.0.1:8000)           │  │
│  │  • Debug Mode (off by default)                      │  │
│  │                                                      │  │
│  │  NO Manual Settings:                                │  │
│  │  ✗ max_jobs slider (REMOVED)                        │  │
│  │  ✗ use_mcp toggle (REMOVED)                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────│──────────────────────────────────────┘
                      │ HTTP POST /chat {"query": "..."}
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                    API Server Layer                          │
│                   (FastAPI Backend)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  server.py                                           │  │
│  │                                                      │  │
│  │  POST /chat                                          │  │
│  │  • Request: {"query": "fetch 1 job"}                │  │
│  │  • Response: {response: "...", error: null}         │  │
│  │                                                      │  │
│  │  POST /chat/debug                                    │  │
│  │  • Returns: Full technical details                   │  │
│  │    (intent_confidence, reasoning, extracted_params)  │  │
│  └────────────────────────┬─────────────────────────────┘  │
└────────────────────────────│──────────────────────────────┘
                             │ client_agent.handle_query()
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              Intelligent Routing Layer                       │
│               (ClientAgent + LLMRouter)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Parse Intent Using LLM                          │  │
│  │     "fetch 1 job"                                    │  │
│  │        ↓                                              │  │
│  │     LLMRouter.parse_intent()                         │  │
│  │        ↓                                              │  │
│  │  2. LLM Returns:                                     │  │
│  │     {                                                │  │
│  │       "primary_intent": "fetch_jobs",               │  │
│  │       "agents_to_call": ["fetch_jobs"],            │  │
│  │       "parameters": {"max_jobs": 1},               │  │
│  │       "confidence": 0.95,                          │  │
│  │       "reasoning": "User req. 1 opportunity"     │  │
│  │     }                                                │  │
│  │        ↓                                              │  │
│  │  3. Route Based on Intent:                          │  │
│  │     ├─ fetch_jobs → _handle_fetch_jobs()           │  │
│  │     ├─ resume_rewrite → _handle_resume_rewrite()   │  │
│  │     ├─ naukri_applier → _handle_naukri_applier()   │  │
│  │     ├─ external_applier → _handle_external...()    │  │
│  │     └─ llm_only → _handle_llm_only()               │  │
│  │        ↓                                              │  │
│  │  4. Check if Multi-Agent Needed:                    │  │
│  │     ├─ Single agent: Direct call                    │  │
│  │     └─ Multiple: Use A2A Coordinator               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ↓             ↓             ↓              ↓
  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │   LLM     │ │  Agent   │ │  Agent   │ │  Agent   │
  │  (Ollama  │ │(Fetch    │ │(Resume   │ │(Naukri   │
  │ llama3.2) │ │ Jobs)    │ │Rewrite)  │ │Applier)  │
  │           │ │          │ │          │ │          │
  │ Intent    │ │Send to   │ │Process   │ │Apply to  │
  │ Parsing   │ │Agent:    │ │Jobs:     │ │Naukri:   │
  │           │ │max_jobs=1│ │Review CV │ │Submit    │
  │           │ │          │ │          │ │          │
  │ Response  │ │Get back: │ │Get back: │ │Get back: │
  │ Format    │ │Jobs[]    │ │Resume[]  │ │Applied#  │
  └───────────┘ └──────────┘ └──────────┘ └──────────┘
        │             │             │              │
        └─────────────┼─────────────┴──────────────┘
                      │
                      ↓
        ┌─────────────────────────────┐
        │  Aggregated Results         │
        │  {                          │
        │    "status": "ok",          │
        │    "response": "✨ Great...",│
        │    "intent_confidence": 0.95│
        │  }                          │
        └──────────────┬──────────────┘
                       │
                       ↓
            ┌────────────────────────┐
            │  Response to Frontend   │
            │  (Clean or Debug)       │
            │                        │
            │  User sees:            │
            │  "✨ Great! I found    │
            │   **1** matching jobs" │
            └────────────────────────┘
```

---

## Component Responsibilities

### Frontend Layer (chat_frontend.py)

**Responsibilities**:
1. Accept user queries
2. Display responses
3. Optional debug mode toggle
4. Optional backend URL configuration

**What It Does**:
- Takes natural language input
- Sends only query to backend
- Displays humanoid responses
- Shows debug details if enabled

**What It Doesn't Do**:
- ✗ Set max_jobs (removed)
- ✗ Set use_mcp (removed)
- ✗ Decide which agent to call (backend decides)
- ✗ Extract parameters (LLM does it)

---

### API Layer (server.py)

**Endpoints**:
- `GET /health` - Health check
- `POST /chat` - User-facing API
- `POST /chat/debug` - Developer API

**Request Model**:
```python
class ChatRequest(BaseModel):
    query: str  # Only this!
```

**Response Models**:
```python
class ChatResponse(BaseModel):
    response: str           # User-friendly message
    error: Optional[str]    # Error if any

class DebugChatResponse(BaseModel):
    status: str
    query: str
    selected_flow: str
    response: str
    result: Dict[str, Any]
    error: Optional[str]
```

**What It Does**:
- Route requests to ClientAgent
- Normalize request format
- Format responses appropriately
- Error handling

---

### LLMRouter (llm_router.py)

**Core Method**:
```python
async def parse_intent(query: str) -> ParsedIntent
```

**Returns**:
```python
@dataclass
class ParsedIntent:
    primary_intent: str              # fetch_jobs, resume_rewrite, etc.
    agents_to_call: list[str]        # Which agents to execute
    parameters: Dict[str, Any]       # Extracted parameters
    confidence: float                # 0.0 to 1.0
    reasoning: str                   # Why this intent
```

**How It Works**:
1. Takes user query
2. Creates structured prompt for LLM
3. Sends prompt to Ollama
4. Parses JSON response
5. Validates & clamps parameters
6. Returns ParsedIntent
7. Falls back to keyword matching on error

**Parameter Extraction Examples**:
```
"fetch 1 job" 
  → {max_jobs: 1}

"find 5 opportunities"
  → {max_jobs: 5}

"AI engineer in remote"
  → {keywords: "AI engineer", filters: {location: "remote"}}
```

---

### ClientAgent (client_agent.py)

**Main Method**:
```python
async def handle_query(query: str) -> Dict[str, Any]
```

**Flow**:
1. Parse intent using LLMRouter
2. Route to appropriate handler
3. Handler executes agents
4. Format and return response

**Handler Methods**:
```python
async def _handle_llm_only(...)
async def _handle_fetch_jobs(...)
async def _handle_resume_rewrite(...)
async def _handle_naukri_applier(...)
async def _handle_external_applier(...)
async def _handle_multi_agent_flow(...)
```

**What It Does**:
- Orchestrates routing
- Manages agent execution
- Aggregates results
- Formats responses

---

### Agent Layer (existing agents)

**Available Agents**:
- `FetchJobsAgent` - Fetches job listings
- `ResumeRewriteAgent` - Tailors resumes
- `NaukriApplierAgent` - Applies on Naukri
- `ExternalApplierAgent` - Applies on company sites

**What They Do**:
- Execute specific tasks
- Return structured results
- Handle errors gracefully

**What Changed**:
- Now called with extracted parameters (not defaults)
- Parameter values come from LLM parsing
- Exact counts/filters respected

---

## Data Flow Examples

### Example 1: Simple Query

```
User Input: "fetch 1 job"
    ↓
Frontend: POST /chat {"query": "fetch 1 job"}
    ↓
server.py: route to ClientAgent
    ↓
ClientAgent.handle_query("fetch 1 job")
    ↓
LLMRouter.parse_intent() → ParsedIntent(
    primary_intent="fetch_jobs",
    parameters={"max_jobs": 1}
)
    ↓
_handle_fetch_jobs() 
    ↓
FetchJobsAgent.execute({"max_jobs": 1})
    ↓
Returns: 1 job ✅
    ↓
Frontend displays: "✨ Great! I found **1** matching jobs"
```

### Example 2: Multi-Agent Query

```
User Input: "run full automation"
    ↓
LLMRouter.parse_intent() → ParsedIntent(
    primary_intent="fetch_jobs",
    agents_to_call=[
        "fetch_jobs",
        "resume_rewrite", 
        "naukri_applier",
        "external_applier"
    ]
)
    ↓
_handle_multi_agent_flow()
    ↓
A2A Coordinator runs sequence:
    1. fetch_jobs(max_jobs=5)
    2. resume_rewrite()
    3. naukri_applier()
    4. external_applier()
    ↓
Returns: Aggregated results ✅
```

### Example 3: General Question

```
User Input: "What is Python?"
    ↓
LLMRouter.parse_intent() → ParsedIntent(
    primary_intent="llm_only",
    confidence=0.98
)
    ↓
_handle_llm_only()
    ↓
Call LLM directly for answer
    ↓
Returns: LLM-generated response ✅
```

---

## Error Handling & Fallbacks

### Level 1: LLM Parsing Fails
```
LLMRouter.parse_intent() raises exception
    ↓
Catch exception
    ↓
Use keyword-based fallback
    ↓
Continue with reduced confidence
```

### Level 2: Agent Execution Fails
```
Agent.execute() raises exception
    ↓
Catch in handler
    ↓
Return error response
    ↓
Frontend displays: "⚠️ Error: ..."
```

### Level 3: Backend Unavailable
```
Frontend can't reach backend
    ↓
Catch httpx exception
    ↓
Return: "Backend is unreachable..."
```

---

## Parameter Flow

### Before Parameter Extraction (Old Way)
```
"fetch 1 job"
    ↓
Frontend slider: 5 (default, user didn't move it)
    ↓
Backend receives: max_jobs=5
    ↓
Ignores "1" in query!
    ↓
Returns: 5 jobs ❌
```

### After Parameter Extraction (New Way)
```
"fetch 1 job"
    ↓
LLM reads: "1"
    ↓
Extracts: max_jobs=1
    ↓
Backend receives: max_jobs=1
    ↓
Honors request!
    ↓
Returns: 1 job ✅
```

---

## Confidence Scoring

### How Confidence Works

```python
ParsedIntent(
    primary_intent="fetch_jobs",
    confidence=0.95  # 95% sure
)

0.0 ─────────────────── 1.0
Very unlikely        Certain
   (Fallback)      (Trust LLM)
```

### Confidence Levels

| Range | Meaning | Action |
|-------|---------|--------|
| 0.9-1.0 | Very confident | Use as-is |
| 0.7-0.9 | Confident | Use normally |
| 0.5-0.7 | Somewhat sure | Use with caution |
| <0.5 | Unsure | Consider fallback |

---

## Async/Await Usage

### Why Async?

1. **Non-blocking I/O**: LLM calls don't block
2. **Concurrency**: Handle multiple requests
3. **Performance**: Don't wait for slow operations

### Key Async Points

```python
# LLMRouter - Async parsing
async def parse_intent(query: str) -> ParsedIntent:
    response = await asyncio.to_thread(self.llm.invoke, prompt)
    # ↑ Runs LLM in thread pool

# ClientAgent - Async routing
async def handle_query(query: str):
    intent = await self.llm_router.parse_intent(query)
    # ↑ Awaits LLM parsing result

# Handler methods - Async agent calls
async def _handle_fetch_jobs(...):
    step = await self.a2a.ask_agent(...)
    # ↑ Awaits agent execution
```

---

## Summary

### Architecture Principles

1. **Separation of Concerns**
   - Frontend: UI only
   - API: Request routing
   - Routing: Intent & parameter extraction
   - Agents: Task execution

2. **Intelligence Layer**
   - LLM handles understanding
   - Parameter extraction from text
   - Multi-agent orchestration

3. **Robustness**
   - Fallback mechanisms
   - Error handling at each level
   - Async for performance

4. **Maintainability**
   - Clear responsibilities
   - Well-documented
   - Easy to extend

---

## Integration Points

### With Existing System

```
LLMRouter ← Uses → Ollama (LLM)
    ↓
ClientAgent ← Uses → A2A Coordinator
    ↓               ↓
Services         Agents
    ↓
Results
```

### Backward Compatibility

- ✅ All existing agents work
- ✅ All existing tools compatible
- ✅ Response format unchanged
- ⚠️ Frontend simplified (improvement)

---

## Performance Characteristics

### Latency

```
LLM Intent Parsing:  ~2 seconds
Agent Execution:     ~100ms to 30+ seconds
Response Formatting: <100ms

Total: 2.1s to 32s (depending on agent)
```

### Throughput

```
Sequential requests: One at a time
Concurrent requests: Handled by async
Max jobs per query: 1-25 (configurable)
```

### Scalability

```
LLM Local (Ollama):  Scales with hardware
Agents:               Already scalable
Frontend:             Streamlit handles load
```

---

**Architecture Status**: ✅ Complete and optimized
