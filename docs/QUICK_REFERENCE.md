# Quick Reference: Clean Response API

## 🎯 What Changed?

**Old API**: Returns confusing JSON with all backend data  
**New API**: Returns ONLY the message the user should see

---

## 📡 Two Endpoints

### User-Facing (Main)
```bash
POST /chat
Response: { "response": "user message", "error": null }
```

### Developer Debug
```bash
POST /chat/debug
Response: { "status", "query", "response", "result", "error" }
```

---

## 💡 Usage Examples

### Simple Query
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch jobs","max_jobs":3}'
```

**Response:**
```json
{
  "response": "✨ Great! I found **3** matching jobs...",
  "error": null
}
```

### Display in Python
```python
import requests
response = requests.post("http://127.0.0.1:8000/chat", 
    json={"query": "fetch jobs"}).json()
print(response["response"])  # Shows formatted message
```

---

## 🔍 Debug When Needed
```bash
curl -X POST http://127.0.0.1:8000/chat/debug \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch jobs","max_jobs":3}'
```

**Response includes**: Full technical data for troubleshooting

---

## ✅ Response Fields

### Main Endpoint `/chat`
| Field | Type | Description |
|-------|------|-------------|
| response | string | Humanoid formatted message |
| error | string\|null | Error message if any |

### Debug Endpoint `/chat/debug`
| Field | Type | Description |
|-------|------|-------------|
| status | string | "ok" or "failed" |
| query | string | Original query |
| selected_flow | string | Agent/flow used |
| response | string | Humanoid message |
| result | object | Full backend data |
| error | string\|null | Error message |

---

## 🚀 Quick Test

```bash
# Test fetch jobs
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"fetch jobs"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['response'])"
```

---

## 📋 Request Format

All requests send:
```json
{
  "query": "your query",
  "use_mpc": false,
  "max_jobs": 5
}
```

---

## 🎯 No More Technical JSON!

```
BEFORE (Cluttered):
{status, query, selected_flow, response, result{...}, error}

AFTER (Clean):
{response, error} ← Only what you need!
```

---

## ✨ Examples

### Fetch Jobs
Topic: fetch jobs  
Response: ✨ Great! I found **X** jobs...

### LLM Question
Topic: what is python?  
Response: Python is a high-level...

### Error Case
Topic: (empty query)  
Response: I encountered an error...  
Error: Query is empty

---

**Status**: ✅ Ready to use!
