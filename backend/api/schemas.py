from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's natural language query")
    session_id: str = Field(default="default", description="Chat session id for in-memory history")


class ChatResponse(BaseModel):
    response: str
    error: Optional[str] = None


class DebugChatResponse(BaseModel):
    status: str
    query: str
    selected_flow: Optional[str] = None
    response: str
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class A2APart(BaseModel):
    text: Optional[str] = None
    raw: Optional[str] = None
    url: Optional[str] = None
    data: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    filename: Optional[str] = None
    mediaType: Optional[str] = None


class A2AMessage(BaseModel):
    messageId: str
    contextId: Optional[str] = None
    taskId: Optional[str] = None
    role: str
    parts: list[A2APart]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    referenceTaskIds: list[str] = Field(default_factory=list)


class A2ASendMessageRequest(BaseModel):
    tenant: Optional[str] = None
    message: A2AMessage
    configuration: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class A2ATaskStatus(BaseModel):
    state: str
    message: Optional[A2AMessage] = None
    timestamp: str


class A2AArtifact(BaseModel):
    artifactId: str
    name: Optional[str] = None
    description: Optional[str] = None
    parts: list[A2APart]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extensions: list[str] = Field(default_factory=list)


class A2ATask(BaseModel):
    id: str
    contextId: str
    status: A2ATaskStatus
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    history: list[A2AMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
