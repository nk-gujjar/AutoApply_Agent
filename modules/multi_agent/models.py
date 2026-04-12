from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class AgentTask:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    use_mcp: bool = False
    correlation_id: str = ""


@dataclass(slots=True)
class AgentResult:
    agent: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass(slots=True)
class A2AMessage:
    sender: str
    receiver: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass(slots=True)
class A2AConversationResult:
    status: str
    query: str
    response: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
