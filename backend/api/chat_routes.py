from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from modules.core.config.settings import config
from .schemas import ChatRequest, ChatResponse, DebugChatResponse
from .state import (
    LAST_CONVERSATION_PATTERN,
    LAST_JD_DETAILS_PATTERN,
    LAST_JD_LINK_PATTERN,
    LAST_QUERY_PATTERN,
    add_ai_chat_message,
    add_user_chat_message,
    client_agent,
    get_chat_memory,
    get_last_conversation,
    get_last_jd,
    get_last_jd_link,
    get_last_user_query,
    update_session_jd_context,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Max messages to send as context to LLM router ──────────────
CHAT_HISTORY_WINDOW = 6


def _extract_resume_path(result: Dict[str, Any]) -> Path | None:
    generated = (
        result.get("result", {})
        .get("result", {})
        .get("data", {})
        .get("generated", [])
    )

    if not isinstance(generated, list) or not generated:
        return None

    first = generated[0] if isinstance(generated[0], dict) else {}
    path_value = first.get("cv_path")
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    try:
        resolved = Path(path_value).resolve()
    except Exception:
        return None

    output_root = config.OUTPUT_DIR.resolve()
    if output_root == resolved.parent or output_root in resolved.parents:
        return resolved
    return None


def _extract_chat_history(session_id: str) -> List[Dict[str, str]]:
    """Extract recent messages from session memory for LLM context."""
    memory = get_chat_memory(session_id)
    messages = list(memory.messages)

    # Take the last CHAT_HISTORY_WINDOW messages
    recent = messages[-CHAT_HISTORY_WINDOW:] if len(messages) > CHAT_HISTORY_WINDOW else messages

    history: List[Dict[str, str]] = []
    for msg in recent:
        msg_type = str(getattr(msg, "type", ""))
        content = str(getattr(msg, "content", ""))
        if msg_type == "human":
            history.append({"role": "human", "content": content})
        elif msg_type == "ai":
            history.append({"role": "ai", "content": content})
    return history


def _format_jd_details(jd: Dict[str, Any]) -> str:
    """Format JD data into a readable string."""
    title = str(jd.get("title") or "Not specified").strip()
    description = str(jd.get("description") or "").strip()
    qualifications = str(jd.get("qualifications") or "").strip()
    skills = jd.get("skills_required") or []
    if isinstance(skills, str):
        skills_text = skills
    elif isinstance(skills, list):
        skills_text = ", ".join(str(s).strip() for s in skills if str(s).strip())
    else:
        skills_text = ""

    lines = ["Your last extracted JD was:", f"Title: {title}"]
    if description:
        lines.append(f"Description: {description[:900]}")
    if qualifications:
        lines.append(f"Qualifications: {qualifications[:500]}")
    if skills_text:
        lines.append(f"Skills: {skills_text}")
    return "\n".join(lines)


def _handle_memory_query(
    query: str, session_id: str
) -> Optional[Dict[str, Any]]:
    """
    Check if the query is a memory recall command.
    Returns a dict with {response_text, memory_type, extra_data} or None.
    """
    if LAST_QUERY_PATTERN.match(query):
        last_query = get_last_user_query(session_id)
        return {
            "response_text": (
                f"Your last query was: {last_query}"
                if last_query
                else "I don't have any previous query in memory yet."
            ),
            "memory_type": "last_query",
            "extra_data": {"last_query": last_query},
        }

    if LAST_CONVERSATION_PATTERN.match(query):
        last_conversation = get_last_conversation(session_id)
        return {
            "response_text": (
                "Your last conversation was:\n"
                f"You: {last_conversation['user']}\n"
                f"Assistant: {last_conversation['assistant']}"
                if last_conversation
                else "I don't have any previous conversation in memory yet."
            ),
            "memory_type": "last_conversation",
            "extra_data": {"last_conversation": last_conversation},
        }

    if LAST_JD_DETAILS_PATTERN.match(query):
        last_jd = get_last_jd(session_id)
        return {
            "response_text": (
                _format_jd_details(last_jd)
                if last_jd
                else "I don't have any extracted JD in memory yet. Please share a JD link or JD text first."
            ),
            "memory_type": "last_jd_details",
            "extra_data": {"last_jd": last_jd},
        }

    if LAST_JD_LINK_PATTERN.match(query):
        last_jd_link = get_last_jd_link(session_id)
        return {
            "response_text": (
                f"Your last JD link was: {last_jd_link}"
                if last_jd_link
                else "I don't have any JD link in memory yet."
            ),
            "memory_type": "last_jd_link",
            "extra_data": {"last_jd_link": last_jd_link},
        }

    return None


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "autoapply-backend"}


@router.get("/artifacts/resume/{file_name}")
async def get_resume_artifact(file_name: str) -> FileResponse:
    target = (config.OUTPUT_DIR / file_name).resolve()
    output_root = config.OUTPUT_DIR.resolve()

    if not (output_root == target.parent or output_root in target.parents):
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path=target, media_type="application/pdf", filename=target.name)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    memory = get_chat_memory(request.session_id)
    query = request.query.strip()

    logger.info(f"📩 /chat request | session={request.session_id[:12]}... | query=\"{query[:80]}...\"")

    try:
        # Check memory recall patterns
        memory_result = _handle_memory_query(query, request.session_id)
        if memory_result:
            response_text = memory_result["response_text"]
            logger.info(f"  💬 Memory hit: {memory_result['memory_type']}")
            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return ChatResponse(response=response_text, error=None)

        # Extract recent chat history for LLM context
        chat_history = _extract_chat_history(request.session_id)
        logger.info(f"  📚 Chat history: {len(chat_history)} messages for context")

        result = await client_agent.handle_query(query=query, chat_history=chat_history)
        response_text = result.get("response", "")
        resume_path = _extract_resume_path(result)
        resume_download_url = f"/artifacts/resume/{resume_path.name}" if resume_path else None
        resume_file_name = resume_path.name if resume_path else None
        update_session_jd_context(request.session_id, query, result)

        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, response_text)

        logger.info(f"  ✅ Response sent | flow={result.get('selected_flow', 'unknown')}")

        return ChatResponse(
            response=response_text,
            error=result.get("error"),
            resume_download_url=resume_download_url,
            resume_file_name=resume_file_name,
        )
    except Exception as exc:
        logger.exception(f"  ❌ /chat error: {exc}")
        fallback = "I encountered an error processing your query. Please try again."
        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, fallback)
        return ChatResponse(
            response=fallback,
            error=str(exc),
        )


@router.post("/chat/debug", response_model=DebugChatResponse)
async def chat_debug(request: ChatRequest) -> DebugChatResponse:
    memory = get_chat_memory(request.session_id)
    query = request.query.strip()

    logger.info(f"📩 /chat/debug request | session={request.session_id[:12]}... | query=\"{query[:80]}...\"")

    try:
        # Check memory recall patterns
        memory_result = _handle_memory_query(query, request.session_id)
        if memory_result:
            response_text = memory_result["response_text"]
            logger.info(f"  💬 Memory hit: {memory_result['memory_type']}")
            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return DebugChatResponse(
                status="ok",
                query=query,
                selected_flow="chat_memory",
                response=response_text,
                result={
                    "session_id": request.session_id,
                    "memory_length": len(memory.messages),
                    **memory_result["extra_data"],
                },
                error=None,
            )

        # Extract recent chat history for LLM context
        chat_history = _extract_chat_history(request.session_id)
        logger.info(f"  📚 Chat history: {len(chat_history)} messages for context")

        result = await client_agent.handle_query(query=query, chat_history=chat_history)
        response_text = result.get("response", "")
        update_session_jd_context(request.session_id, query, result)
        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, response_text)

        logger.info(f"  ✅ Debug response sent | flow={result.get('selected_flow', 'unknown')}")

        return DebugChatResponse(
            response=result.get("response", ""),
            status=result.get("status", "ok"),
            query=result.get("query", query),
            selected_flow=result.get("selected_flow"),
            result=result.get("result", {}),
            error=result.get("error"),
        )
    except Exception as exc:
        logger.exception(f"  ❌ /chat/debug error: {exc}")
        fallback = "Backend failed to process the query."
        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, fallback)
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

