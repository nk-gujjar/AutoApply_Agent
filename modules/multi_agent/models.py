from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


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
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass(slots=True)
class A2AMessage:
    sender: str
    receiver: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass(slots=True)
class A2AConversationResult:
    status: str
    query: str
    response: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
