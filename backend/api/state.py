from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any, Dict

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from modules.core.config.settings import config
from modules.multi_agent import ClientAgent

from .schemas import A2ATask

client_agent = ClientAgent()
a2a_tasks: Dict[str, A2ATask] = {}
chat_memories: Dict[str, InMemoryChatMessageHistory] = {}
chat_session_context: Dict[str, Dict[str, Any]] = {}
_memory_lock = RLock()

CHAT_MEMORY_DIR = config.DATA_DIR / "chat_memory"
CHAT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

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


def _safe_session_file_name(session_id: str) -> str:
    key = _session_key(session_id)
    return re.sub(r"[^a-zA-Z0-9._-]", "_", key)


def _session_memory_path(session_id: str) -> Path:
    return CHAT_MEMORY_DIR / f"{_safe_session_file_name(session_id)}.json"


def _serialize_messages(memory: InMemoryChatMessageHistory) -> list[Dict[str, str]]:
    rows: list[Dict[str, str]] = []
    for message in memory.messages:
        msg_type = str(getattr(message, "type", ""))
        if msg_type not in {"human", "ai"}:
            continue
        rows.append(
            {
                "type": msg_type,
                "content": str(getattr(message, "content", "")),
            }
        )
    return rows


def _save_session_state(session_id: str) -> None:
    key = _session_key(session_id)
    memory = chat_memories.get(key)
    context = chat_session_context.get(key, {})

    payload = {
        "messages": _serialize_messages(memory) if memory else [],
        "context": context if isinstance(context, dict) else {},
    }

    path = _session_memory_path(session_id)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_session_state(session_id: str) -> tuple[InMemoryChatMessageHistory, Dict[str, Any]]:
    memory = InMemoryChatMessageHistory()
    context: Dict[str, Any] = {
        "last_jd_link": "",
        "last_jd": {},
        "last_jd_source": "",
    }

    path = _session_memory_path(session_id)
    if not path.exists():
        return memory, context

    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return memory, context

    rows = data.get("messages", []) if isinstance(data, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            msg_type = str(row.get("type") or "").strip().lower()
            content = str(row.get("content") or "")
            if msg_type == "human":
                memory.add_message(HumanMessage(content=content))
            elif msg_type == "ai":
                memory.add_message(AIMessage(content=content))

    raw_context = data.get("context", {}) if isinstance(data, dict) else {}
    if isinstance(raw_context, dict):
        context.update(raw_context)

    return memory, context


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
    with _memory_lock:
        if key not in chat_session_context:
            if key not in chat_memories:
                loaded_memory, loaded_context = _load_session_state(session_id)
                chat_memories[key] = loaded_memory
                chat_session_context[key] = loaded_context
            else:
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

    with _memory_lock:
        _save_session_state(session_id)


def get_chat_memory(session_id: str) -> InMemoryChatMessageHistory:
    key = _session_key(session_id)
    with _memory_lock:
        if key not in chat_memories:
            loaded_memory, loaded_context = _load_session_state(session_id)
            chat_memories[key] = loaded_memory
            chat_session_context.setdefault(key, loaded_context)
        return chat_memories[key]


def add_user_chat_message(session_id: str, content: str) -> None:
    with _memory_lock:
        memory = get_chat_memory(session_id)
        memory.add_user_message(content)
        _save_session_state(session_id)


def add_ai_chat_message(session_id: str, content: str) -> None:
    with _memory_lock:
        memory = get_chat_memory(session_id)
        memory.add_ai_message(content)
        _save_session_state(session_id)


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
