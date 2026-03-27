from __future__ import annotations

import re
from typing import Any, Dict

from fastapi import APIRouter

from .schemas import ChatRequest, ChatResponse, DebugChatResponse
from .state import client_agent, get_chat_memory, get_last_user_query

router = APIRouter()

LAST_QUERY_PATTERN = re.compile(r"^\s*tell\s+me\s+my\s+last\s+query\s*[?.!]*\s*$", re.IGNORECASE)


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "autoapply-backend"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    memory = get_chat_memory(request.session_id)
    query = request.query.strip()

    try:
        if LAST_QUERY_PATTERN.match(query):
            last_query = get_last_user_query(request.session_id)
            response_text = (
                f"Your last query was: {last_query}"
                if last_query
                else "I don't have any previous query in memory yet."
            )
            memory.add_user_message(query)
            memory.add_ai_message(response_text)
            return ChatResponse(response=response_text, error=None)

        result = await client_agent.handle_query(query=query)
        response_text = result.get("response", "")
        memory.add_user_message(query)
        memory.add_ai_message(response_text)

        return ChatResponse(
            response=response_text,
            error=result.get("error"),
        )
    except Exception as exc:
        fallback = "I encountered an error processing your query. Please try again."
        memory.add_user_message(query)
        memory.add_ai_message(fallback)
        return ChatResponse(
            response=fallback,
            error=str(exc),
        )


@router.post("/chat/debug", response_model=DebugChatResponse)
async def chat_debug(request: ChatRequest) -> DebugChatResponse:
    memory = get_chat_memory(request.session_id)
    query = request.query.strip()

    try:
        if LAST_QUERY_PATTERN.match(query):
            last_query = get_last_user_query(request.session_id)
            response_text = (
                f"Your last query was: {last_query}"
                if last_query
                else "I don't have any previous query in memory yet."
            )
            memory.add_user_message(query)
            memory.add_ai_message(response_text)
            return DebugChatResponse(
                status="ok",
                query=query,
                selected_flow="chat_memory",
                response=response_text,
                result={
                    "session_id": request.session_id,
                    "memory_length": len(memory.messages),
                    "last_query": last_query,
                },
                error=None,
            )

        result = await client_agent.handle_query(query=query)
        response_text = result.get("response", "")
        memory.add_user_message(query)
        memory.add_ai_message(response_text)
        return DebugChatResponse(
            response=result.get("response", ""),
            status=result.get("status", "ok"),
            query=result.get("query", query),
            selected_flow=result.get("selected_flow"),
            result=result.get("result", {}),
            error=result.get("error"),
        )
    except Exception as exc:
        fallback = "Backend failed to process the query."
        memory.add_user_message(query)
        memory.add_ai_message(fallback)
        return DebugChatResponse(
            status="failed",
            query=query,
            selected_flow="backend_error",
            response=fallback,
            result={
                "session_id": request.session_id,
                "memory_length": len(memory.messages),
            },
            error=str(exc),
        )
