from __future__ import annotations

from dataclasses import asdict
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4

from .models import A2AConversationResult, A2AMessage

DispatchCallable = Callable[[str, Dict[str, Any], bool], Awaitable[Dict[str, Any]]]


class A2ACoordinator:
    def __init__(self, dispatcher: DispatchCallable) -> None:
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
        message = A2AMessage(
            sender=sender,
            receiver=agent_name,
            intent=intent,
            payload=payload,
            correlation_id=correlation_id,
        )
        result = await self.dispatcher(agent_name, payload, use_mcp)
        return {
            "message": asdict(message),
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
