from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from modules.multi_agent import ClientAgent


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's natural language query")


class ChatResponse(BaseModel):
    """Clean response shown to user - no technical backend data"""
    response: str
    error: Optional[str] = None


class DebugChatResponse(BaseModel):
    """Full response with backend data (for debugging only)"""
    status: str
    query: str
    selected_flow: Optional[str] = None
    response: str
    result: Dict[str, Any] = {}
    error: Optional[str] = None


app = FastAPI(title="AutoApply Backend", version="1.0.0")
client_agent = ClientAgent()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "autoapply-backend"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.
    
    LLM intelligently decides:
    - Which agent to call based on user intent
    - What parameters to extract from the query
    - How to format the response
    
    No manual settings required - just ask a natural language question!
    """
    try:
        result = await client_agent.handle_query(query=request.query)
        return ChatResponse(
            response=result.get("response", ""),
            error=result.get("error"),
        )
    except Exception as exc:
        return ChatResponse(
            response="I encountered an error processing your query. Please try again.",
            error=str(exc),
        )


@app.post("/chat/debug", response_model=DebugChatResponse)
async def chat_debug(request: ChatRequest) -> DebugChatResponse:
    """
    Debug endpoint - returns full backend data for troubleshooting.
    Shows LLM intent parsing, extracted parameters, agent routing, etc.
    """
    try:
        result = await client_agent.handle_query(query=request.query)
        return DebugChatResponse(
            status=result.get("status", "ok"),
            query=result.get("query", request.query),
            selected_flow=result.get("selected_flow"),
            response=result.get("response", ""),
            result=result.get("result", {}),
            error=result.get("error"),
        )
    except Exception as exc:
        return DebugChatResponse(
            status="failed",
            query=request.query,
            selected_flow="backend_error",
            response="Backend failed to process the query.",
            result={},
            error=str(exc),
        )
