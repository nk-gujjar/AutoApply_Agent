from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent_catalog import get_agent_card_profiles
from .models import A2AConversationResult

DispatchCallable = Callable[[str, Dict[str, Any], bool], Awaitable[Dict[str, Any]]]


AGENT_CARD_PROFILES: Dict[str, Dict[str, Any]] = get_agent_card_profiles()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class A2APart(BaseModel):
    text: str | None = None
    raw: str | None = None
    url: str | None = None
    data: Any | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    filename: str | None = None
    mediaType: str | None = None


class A2AMessagePayload(BaseModel):
    messageId: str
    contextId: str | None = None
    taskId: str | None = None
    role: str
    parts: List[A2APart]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    referenceTaskIds: List[str] = Field(default_factory=list)


class A2ASendMessageConfiguration(BaseModel):
    acceptedOutputModes: List[str] = Field(default_factory=list)
    historyLength: int | None = None
    returnImmediately: bool = False


class A2ASendMessageRequest(BaseModel):
    tenant: str | None = None
    message: A2AMessagePayload
    configuration: A2ASendMessageConfiguration | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class A2ATaskStatus(BaseModel):
    state: str
    message: A2AMessagePayload | None = None
    timestamp: str = Field(default_factory=_utc_now_iso)


class A2AArtifact(BaseModel):
    artifactId: str
    name: str | None = None
    description: str | None = None
    parts: List[A2APart]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extensions: List[str] = Field(default_factory=list)


class A2ATask(BaseModel):
    id: str
    contextId: str
    status: A2ATaskStatus
    artifacts: List[A2AArtifact] = Field(default_factory=list)
    history: List[A2AMessagePayload] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class A2ASendMessageResponse(BaseModel):
    task: A2ATask | None = None
    message: A2AMessagePayload | None = None


class LocalA2AAgentServer:
    """Minimal A2A HTTP+JSON server for an in-process agent.

    Implements:
    - GET /.well-known/agent-card.json
    - POST /message:send
    - GET /tasks/{id}
    """

    def __init__(
        self,
        agent_name: str,
        execute_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        description: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.execute_fn = execute_fn
        self.description = description or f"A2A wrapper for {agent_name}"
        self.tasks: Dict[str, A2ATask] = {}
        self.app = FastAPI(title=f"A2A Agent: {agent_name}", version="1.0.0")
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.get("/.well-known/agent-card.json")
        async def get_agent_card() -> Dict[str, Any]:
            profile = AGENT_CARD_PROFILES.get(self.agent_name, {})
            display_name = profile.get("display_name", self.agent_name)
            description = profile.get("description", self.description)
            skill_name = profile.get("skill_name", display_name)
            skill_description = profile.get("skill_description", description)
            tags = profile.get("tags", ["autoapply", "agent", self.agent_name])
            examples = profile.get("examples", [])

            return {
                "name": display_name,
                "description": description,
                "supportedInterfaces": [
                    {
                        "url": f"http://{self.agent_name}.local",
                        "protocolBinding": "HTTP+JSON",
                        "protocolVersion": "1.0",
                    }
                ],
                "version": "1.0.0",
                "capabilities": {
                    "streaming": False,
                    "pushNotifications": False,
                    "extendedAgentCard": False,
                },
                "defaultInputModes": ["application/json", "text/plain"],
                "defaultOutputModes": ["application/json", "text/plain"],
                "skills": [
                    {
                        "id": self.agent_name,
                        "name": skill_name,
                        "description": skill_description,
                        "tags": tags,
                        "examples": examples,
                        "inputModes": ["application/json", "text/plain"],
                        "outputModes": ["application/json", "text/plain"],
                    }
                ],
            }

        @self.app.post("/message:send")
        async def send_message(request: A2ASendMessageRequest) -> Dict[str, Any]:
            payload = request.metadata or request.message.metadata or {}
            correlation_id = payload.get("correlation_id")

            result = await self.execute_fn(payload)
            task_id = str(uuid4())
            context_id = request.message.contextId or str(uuid4())
            status_state = "TASK_STATE_COMPLETED" if result.get("success", False) else "TASK_STATE_FAILED"

            artifact = A2AArtifact(
                artifactId=str(uuid4()),
                name=f"{self.agent_name}_result",
                parts=[
                    A2APart(
                        text=json.dumps(result, default=str),
                        mediaType="application/json",
                    )
                ],
            )

            task = A2ATask(
                id=task_id,
                contextId=context_id,
                status=A2ATaskStatus(state=status_state),
                artifacts=[artifact],
                history=[request.message],
                metadata={"agent": self.agent_name, "correlation_id": correlation_id},
            )
            self.tasks[task_id] = task
            response = A2ASendMessageResponse(task=task)
            return response.model_dump(exclude_none=True)

        @self.app.get("/tasks/{task_id}")
        async def get_task(task_id: str) -> Dict[str, Any]:
            task = self.tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task.model_dump(exclude_none=True)


class A2AHttpClient:
    """A2A HTTP+JSON client (minimal binding for local agent communication)."""

    def __init__(self, name: str, http_client: httpx.AsyncClient, version: str = "1.0") -> None:
        self.name = name
        self.http_client = http_client
        self.version = version
        self.agent_card: Dict[str, Any] | None = None

    async def fetch_agent_card(self) -> Dict[str, Any]:
        response = await self.http_client.get("/.well-known/agent-card.json")
        response.raise_for_status()
        self.agent_card = response.json()
        return self.agent_card

    async def send_message(
        self,
        *,
        text: str,
        metadata: Dict[str, Any],
        context_id: str | None = None,
    ) -> Dict[str, Any]:
        if self.agent_card is None:
            await self.fetch_agent_card()

        message = {
            "messageId": str(uuid4()),
            "contextId": context_id,
            "role": "ROLE_USER",
            "parts": [{"text": text}],
            "metadata": metadata,
        }
        payload = {
            "message": message,
            "metadata": metadata,
            "configuration": {
                "acceptedOutputModes": ["application/json", "text/plain"],
                "returnImmediately": False,
            },
        }
        headers = {
            "A2A-Version": self.version,
            "Content-Type": "application/a2a+json",
            "Accept": "application/a2a+json",
        }
        response = await self.http_client.post("/message:send", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


class A2ACoordinator:
    def __init__(self, clients: Dict[str, A2AHttpClient], dispatcher: DispatchCallable | None = None) -> None:
        self.clients = clients
        self.dispatcher = dispatcher

    @staticmethod
    def new_correlation_id() -> str:
        return str(uuid4())

    async def ask_agent(
        self,
        sender: str,
        agent_name: str,
        intent: str,
        payload: Dict[str, Any],
        use_mcp: bool,
        correlation_id: str,
    ) -> Dict[str, Any]:
        message = {
            "messageId": str(uuid4()),
            "sender": sender,
            "receiver": agent_name,
            "intent": intent,
            "payload": payload,
            "correlation_id": correlation_id,
            "role": "ROLE_USER",
        }

        if use_mcp and self.dispatcher:
            result = await self.dispatcher(agent_name, payload, use_mcp)
            return {"message": message, "result": result}

        client = self.clients.get(agent_name)
        if not client:
            return {
                "message": message,
                "result": {
                    "ok": False,
                    "error": f"Unknown A2A agent: {agent_name}",
                    "result": {"success": False, "agent": agent_name, "error": f"Unknown A2A agent: {agent_name}"},
                },
            }

        try:
            raw_response = await client.send_message(
                text=intent,
                metadata={**payload, "correlation_id": correlation_id, "sender": sender},
                context_id=correlation_id,
            )
        except Exception as exc:
            return {
                "message": message,
                "result": {
                    "ok": False,
                    "error": str(exc),
                    "result": {
                        "agent": agent_name,
                        "success": False,
                        "error": str(exc),
                    },
                },
            }

        task = raw_response.get("task", {})
        artifacts = task.get("artifacts", [])
        decoded_result: Dict[str, Any] = {"agent": agent_name, "success": False, "error": "No artifact returned"}
        if artifacts:
            parts = artifacts[0].get("parts", [])
            if parts and parts[0].get("text"):
                try:
                    decoded_result = json.loads(parts[0]["text"])
                except json.JSONDecodeError:
                    decoded_result = {
                        "agent": agent_name,
                        "success": False,
                        "error": "Invalid JSON artifact returned by A2A server",
                    }

        result = {
            "ok": bool(decoded_result.get("success", False)),
            "result": decoded_result,
            "a2a": {
                "task": task,
                "protocol": "A2A_HTTP_JSON_1.0",
            },
        }
        return {
            "message": message,
            "result": result,
        }

    async def run_sequence(
        self,
        query: str,
        sequence: List[Dict[str, Any]],
        use_mcp: bool,
        correlation_id: str,
    ) -> A2AConversationResult:
        steps: List[Dict[str, Any]] = []
        aggregate: Dict[str, Any] = {}

        for item in sequence:
            step = await self.ask_agent(
                sender="client_agent",
                agent_name=item["agent"],
                intent=item.get("intent", item["agent"]),
                payload=item.get("payload", {}),
                use_mcp=use_mcp,
                correlation_id=correlation_id,
            )
            steps.append(step)
            aggregate[item["agent"]] = step.get("result")

            if not step.get("result", {}).get("ok", True):
                return A2AConversationResult(
                    status="failed",
                    query=query,
                    response=f"Agent '{item['agent']}' failed while processing the query.",
                    steps=steps,
                    data=aggregate,
                    correlation_id=correlation_id,
                )

        return A2AConversationResult(
            status="ok",
            query=query,
            response="Client agent completed the multi-agent conversation successfully.",
            steps=steps,
            data=aggregate,
            correlation_id=correlation_id,
        )
