from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict

from langchain_core.chat_history import InMemoryChatMessageHistory

from modules.multi_agent import ClientAgent

from .schemas import A2ATask

client_agent = ClientAgent()
a2a_tasks: Dict[str, A2ATask] = {}
chat_memories: Dict[str, InMemoryChatMessageHistory] = {}
LAST_QUERY_PATTERN = re.compile(r"^\s*tell\s+me\s+my\s+last\s+query\s*[?.!]*\s*$", re.IGNORECASE)


def get_chat_memory(session_id: str) -> InMemoryChatMessageHistory:
    key = (session_id or "default").strip() or "default"
    if key not in chat_memories:
        chat_memories[key] = InMemoryChatMessageHistory()
    return chat_memories[key]


def get_last_user_query(session_id: str) -> str | None:
    memory = get_chat_memory(session_id)
    for message in reversed(memory.messages):
        if message.type != "human":
            continue
        content = str(message.content).strip()
        if content and not LAST_QUERY_PATTERN.match(content):
            return content
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
