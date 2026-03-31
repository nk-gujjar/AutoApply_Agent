from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict

from langchain_core.chat_history import InMemoryChatMessageHistory

from modules.multi_agent import ClientAgent

from .schemas import A2ATask

client_agent = ClientAgent()
a2a_tasks: Dict[str, A2ATask] = {}
chat_memories: Dict[str, InMemoryChatMessageHistory] = {}
chat_session_context: Dict[str, Dict[str, Any]] = {}

URL_PATTERN = re.compile(r"https?://[^\s)]+", re.IGNORECASE)
LAST_QUERY_PATTERN = re.compile(
    r"^\s*tell\s+me\s+(?:my\s+)?last\s+query\s*[?.!]*\s*$",
    re.IGNORECASE,
)
LAST_CONVERSATION_PATTERN = re.compile(
    r"^\s*(tell|show)\s+me\s+(?:my\s+)?last\s+conversation\s*[?.!]*\s*$",
    re.IGNORECASE,
)
LAST_JD_LINK_PATTERN = re.compile(
    r"^\s*(tell|show|what(?:'s|\s+is))\b.*\b(jd|job\s*description)\b.*\blink\b.*$",
    re.IGNORECASE,
)
LAST_JD_DETAILS_PATTERN = re.compile(
    r"^\s*(tell|show|what(?:'s|\s+is))\b.*\b(jd|job\s*description)\b.*\b(last|previous|gave|given|before)\b.*$",
    re.IGNORECASE,
)


def _session_key(session_id: str) -> str:
    return (session_id or "default").strip() or "default"


def _first_url(text: str) -> str | None:
    match = URL_PATTERN.search(text or "")
    return match.group(0).strip() if match else None


def _extract_jd_data_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {}

    # Single agent flow: output.result.result.data
    single_data = result.get("result", {}).get("result", {}).get("data", {})
    if isinstance(single_data, dict) and isinstance(single_data.get("job"), dict):
        return single_data

    # Two-agent pipeline flow: output.pipeline.jd_extractor.result.data
    pipeline_data = (
        result.get("pipeline", {})
        .get("jd_extractor", {})
        .get("result", {})
        .get("data", {})
    )
    if isinstance(pipeline_data, dict) and isinstance(pipeline_data.get("job"), dict):
        return pipeline_data

    return {}


def get_session_context(session_id: str) -> Dict[str, Any]:
    key = _session_key(session_id)
    if key not in chat_session_context:
        chat_session_context[key] = {
            "last_jd_link": "",
            "last_jd": {},
            "last_jd_source": "",
        }
    return chat_session_context[key]


def update_session_jd_context(session_id: str, query: str, result: Dict[str, Any]) -> None:
    ctx = get_session_context(session_id)

    query_url = _first_url(query)
    if query_url:
        ctx["last_jd_link"] = query_url

    jd_data = _extract_jd_data_from_result(result)
    if not jd_data:
        return

    job = jd_data.get("job")
    if isinstance(job, dict):
        ctx["last_jd"] = job

    url = str(jd_data.get("url") or "").strip()
    if url:
        ctx["last_jd_link"] = url

    source = str(jd_data.get("source") or "").strip()
    if source:
        ctx["last_jd_source"] = source


def get_chat_memory(session_id: str) -> InMemoryChatMessageHistory:
    key = _session_key(session_id)
    if key not in chat_memories:
        chat_memories[key] = InMemoryChatMessageHistory()
    return chat_memories[key]


def get_last_user_query(session_id: str) -> str | None:
    memory = get_chat_memory(session_id)
    for message in reversed(memory.messages):
        if message.type != "human":
            continue
        content = str(message.content).strip()
        if (
            content
            and not LAST_QUERY_PATTERN.match(content)
            and not LAST_CONVERSATION_PATTERN.match(content)
            and not LAST_JD_LINK_PATTERN.match(content)
            and not LAST_JD_DETAILS_PATTERN.match(content)
        ):
            return content
    return None


def get_last_conversation(session_id: str) -> Dict[str, str] | None:
    memory = get_chat_memory(session_id)
    messages = list(memory.messages)

    for index in range(len(messages) - 2, -1, -1):
        user_message = messages[index]
        assistant_message = messages[index + 1]

        if user_message.type != "human" or assistant_message.type != "ai":
            continue

        user_text = str(user_message.content).strip()
        assistant_text = str(assistant_message.content).strip()

        if (
            not user_text
            or LAST_QUERY_PATTERN.match(user_text)
            or LAST_CONVERSATION_PATTERN.match(user_text)
            or LAST_JD_LINK_PATTERN.match(user_text)
            or LAST_JD_DETAILS_PATTERN.match(user_text)
        ):
            continue

        return {
            "user": user_text,
            "assistant": assistant_text,
        }

    return None


def get_last_jd_link(session_id: str) -> str | None:
    ctx = get_session_context(session_id)
    link = str(ctx.get("last_jd_link") or "").strip()
    if link:
        return link

    memory = get_chat_memory(session_id)
    for message in reversed(memory.messages):
        if message.type != "human":
            continue
        url = _first_url(str(message.content or ""))
        if url:
            return url
    return None


def get_last_jd(session_id: str) -> Dict[str, Any] | None:
    ctx = get_session_context(session_id)
    jd = ctx.get("last_jd")
    if isinstance(jd, dict) and jd:
        return jd
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
