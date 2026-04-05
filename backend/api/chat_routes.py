from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

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

router = APIRouter()


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

    try:
        if LAST_QUERY_PATTERN.match(query):
            last_query = get_last_user_query(request.session_id)
            response_text = (
                f"Your last query was: {last_query}"
                if last_query
                else "I don't have any previous query in memory yet."
            )
            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return ChatResponse(response=response_text, error=None)

        if LAST_CONVERSATION_PATTERN.match(query):
            last_conversation = get_last_conversation(request.session_id)
            response_text = (
                "Your last conversation was:\n"
                f"You: {last_conversation['user']}\n"
                f"Assistant: {last_conversation['assistant']}"
                if last_conversation
                else "I don't have any previous conversation in memory yet."
            )
            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return ChatResponse(response=response_text, error=None)

        if LAST_JD_DETAILS_PATTERN.match(query):
            last_jd = get_last_jd(request.session_id)
            if last_jd:
                title = str(last_jd.get("title") or "Not specified").strip()
                description = str(last_jd.get("description") or "").strip()
                qualifications = str(last_jd.get("qualifications") or "").strip()
                skills = last_jd.get("skills_required") or []
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
                response_text = "\n".join(lines)
            else:
                response_text = "I don't have any extracted JD in memory yet. Please share a JD link or JD text first."

            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return ChatResponse(response=response_text, error=None)

        if LAST_JD_LINK_PATTERN.match(query):
            last_jd_link = get_last_jd_link(request.session_id)
            response_text = (
                f"Your last JD link was: {last_jd_link}"
                if last_jd_link
                else "I don't have any JD link in memory yet."
            )
            add_user_chat_message(request.session_id, query)
            add_ai_chat_message(request.session_id, response_text)
            return ChatResponse(response=response_text, error=None)

        result = await client_agent.handle_query(query=query)
        response_text = result.get("response", "")
        resume_path = _extract_resume_path(result)
        resume_download_url = f"/artifacts/resume/{resume_path.name}" if resume_path else None
        resume_file_name = resume_path.name if resume_path else None
        update_session_jd_context(request.session_id, query, result)

        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, response_text)

        return ChatResponse(
            response=response_text,
            error=result.get("error"),
            resume_download_url=resume_download_url,
            resume_file_name=resume_file_name,
        )
    except Exception as exc:
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

    try:
        if LAST_QUERY_PATTERN.match(query):
            last_query = get_last_user_query(request.session_id)
            response_text = (
                f"Your last query was: {last_query}"
                if last_query
                else "I don't have any previous query in memory yet."
            )
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
                    "last_query": last_query,
                },
                error=None,
            )

        if LAST_CONVERSATION_PATTERN.match(query):
            last_conversation = get_last_conversation(request.session_id)
            response_text = (
                "Your last conversation was:\n"
                f"You: {last_conversation['user']}\n"
                f"Assistant: {last_conversation['assistant']}"
                if last_conversation
                else "I don't have any previous conversation in memory yet."
            )
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
                    "last_conversation": last_conversation,
                },
                error=None,
            )

        if LAST_JD_DETAILS_PATTERN.match(query):
            last_jd = get_last_jd(request.session_id)
            if last_jd:
                title = str(last_jd.get("title") or "Not specified").strip()
                description = str(last_jd.get("description") or "").strip()
                qualifications = str(last_jd.get("qualifications") or "").strip()
                skills = last_jd.get("skills_required") or []
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
                response_text = "\n".join(lines)
            else:
                response_text = "I don't have any extracted JD in memory yet. Please share a JD link or JD text first."

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
                    "last_jd": last_jd,
                },
                error=None,
            )

        if LAST_JD_LINK_PATTERN.match(query):
            last_jd_link = get_last_jd_link(request.session_id)
            response_text = (
                f"Your last JD link was: {last_jd_link}"
                if last_jd_link
                else "I don't have any JD link in memory yet."
            )
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
                    "last_jd_link": last_jd_link,
                },
                error=None,
            )

        result = await client_agent.handle_query(query=query)
        response_text = result.get("response", "")
        update_session_jd_context(request.session_id, query, result)
        add_user_chat_message(request.session_id, query)
        add_ai_chat_message(request.session_id, response_text)
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
