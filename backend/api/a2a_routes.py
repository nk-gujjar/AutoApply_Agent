from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .schemas import A2AArtifact, A2AMessage, A2APart, A2ASendMessageRequest, A2ATask, A2ATaskStatus
from .state import a2a_tasks, client_agent, utc_now_iso

router = APIRouter()


def _extract_query_from_a2a(request: A2ASendMessageRequest) -> str:
    query = request.metadata.get("query") or request.message.metadata.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()

    text_parts = [part.text.strip() for part in request.message.parts if isinstance(part.text, str) and part.text.strip()]
    if text_parts:
        return "\n".join(text_parts)

    for part in request.message.parts:
        if isinstance(part.data, dict) and isinstance(part.data.get("query"), str):
            q = part.data.get("query", "").strip()
            if q:
                return q

    return ""


def _client_agent_card() -> Dict[str, Any]:
    return {
        "name": "autoapply-client-agent",
        "description": "Orchestrator agent for end-to-end job automation. It understands natural language requests and delegates work to specialized agents for scraping, fetching, resume tailoring, and applications.",
        "supportedInterfaces": [
            {
                "url": "http://127.0.0.1:8000",
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
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "query-routing",
                "name": "Natural Language Multi-Agent Orchestration",
                "description": "Parses intent from user queries, selects the right specialized agents, runs single or multi-step workflows, and returns unified responses.",
                "tags": ["jobs", "automation", "a2a", "orchestration", "intent-routing", "workflow"],
                "examples": [
                    "fetch 5 jobs for python developer",
                    "rewrite resume for backend roles",
                    "run full pipeline",
                ],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain", "application/json"],
            }
        ],
        "metadata": {
            "managedAgents": sorted(list(client_agent.agents.keys()))
        },
    }


async def _collect_specialized_agent_cards() -> list[Dict[str, Any]]:
    async def _one(agent_name: str, a2a_client: Any) -> Dict[str, Any]:
        try:
            card = await a2a_client.fetch_agent_card()
            card["agentId"] = agent_name
            return card
        except Exception as exc:
            return {
                "agentId": agent_name,
                "name": agent_name,
                "error": str(exc),
            }

    tasks = [
        _one(agent_name, a2a_client)
        for agent_name, a2a_client in client_agent.a2a_clients.items()
    ]
    cards = await asyncio.gather(*tasks)
    cards.sort(key=lambda item: item.get("agentId", ""))
    return cards


@router.get("/.well-known/agent-card.json")
async def a2a_agent_card() -> JSONResponse:
    card = _client_agent_card()
    child_cards = await _collect_specialized_agent_cards()
    card["agentCards"] = child_cards
    card["agentCardsCount"] = len(child_cards)
    return JSONResponse(content=card, media_type="application/a2a+json")


@router.get("/agent-cards")
async def a2a_agent_cards() -> JSONResponse:
    client_card = _client_agent_card()
    child_cards = await _collect_specialized_agent_cards()
    payload = {
        "clientAgentCard": client_card,
        "agentCards": child_cards,
        "count": len(child_cards),
    }
    return JSONResponse(content=payload, media_type="application/a2a+json")


@router.post("/message:send")
async def a2a_send_message(request: A2ASendMessageRequest) -> JSONResponse:
    query = _extract_query_from_a2a(request)
    if not query:
        response = {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "A2A message did not include a valid query in metadata.query or text parts.",
            }
        }
        return JSONResponse(status_code=400, content=response, media_type="application/a2a+json")

    result = await client_agent.handle_query(query=query)
    task_id = str(uuid4())
    context_id = request.message.contextId or str(uuid4())
    succeeded = result.get("status") == "ok"

    agent_msg = A2AMessage(
        messageId=str(uuid4()),
        contextId=context_id,
        taskId=task_id,
        role="ROLE_AGENT",
        parts=[A2APart(text=result.get("response", ""), mediaType="text/plain")],
        metadata={
            "status": result.get("status"),
            "selected_flow": result.get("selected_flow"),
            "correlation_id": result.get("correlation_id"),
        },
    )

    task = A2ATask(
        id=task_id,
        contextId=context_id,
        status=A2ATaskStatus(
            state="TASK_STATE_COMPLETED" if succeeded else "TASK_STATE_FAILED",
            message=agent_msg,
            timestamp=utc_now_iso(),
        ),
        artifacts=[
            A2AArtifact(
                artifactId=str(uuid4()),
                name="autoapply_result",
                parts=[
                    A2APart(
                        text=json.dumps(result, default=str),
                        mediaType="application/json",
                    )
                ],
                metadata={"query": query},
            )
        ],
        history=[request.message, agent_msg],
        metadata={"query": query},
    )
    a2a_tasks[task_id] = task
    return JSONResponse(content={"task": task.model_dump(exclude_none=True)}, media_type="application/a2a+json")


@router.get("/tasks/{task_id}")
async def a2a_get_task(task_id: str) -> JSONResponse:
    task = a2a_tasks.get(task_id)
    if not task:
        response = {
            "error": {
                "code": 404,
                "status": "NOT_FOUND",
                "message": f"Task '{task_id}' not found",
            }
        }
        return JSONResponse(status_code=404, content=response, media_type="application/a2a+json")
    return JSONResponse(content=task.model_dump(exclude_none=True), media_type="application/a2a+json")


@router.get("/tasks")
async def a2a_list_tasks(contextId: Optional[str] = None, pageSize: int = 50) -> JSONResponse:
    tasks = list(a2a_tasks.values())
    if contextId:
        tasks = [task for task in tasks if task.contextId == contextId]

    page_size = max(1, min(pageSize, 100))
    tasks_page = tasks[:page_size]
    payload = {
        "tasks": [task.model_dump(exclude_none=True) for task in tasks_page],
        "nextPageToken": "" if len(tasks) <= page_size else "more",
        "pageSize": page_size,
        "totalSize": len(tasks),
    }
    return JSONResponse(content=payload, media_type="application/a2a+json")
