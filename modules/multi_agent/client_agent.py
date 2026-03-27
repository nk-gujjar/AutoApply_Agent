from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Dict

import httpx

from modules.core.config.settings import logger, create_llm

from .a2a import A2ACoordinator, A2AHttpClient, LocalA2AAgentServer
from .agent_catalog import get_routing_manifest, load_agent_instances
from .llm_router import LLMRouter, ParsedIntent
from .mcp import MCPClient, MCPServer
from .models import A2AConversationResult, AgentResult
from .tools import ToolRegistry, WorkspaceIOTools


class ClientAgent:
    def __init__(self) -> None:
        self.agents = load_agent_instances()
        self.routing_manifest = get_routing_manifest()

        self.tools = ToolRegistry()
        self.tools.register("load_naukri_jobs_file", WorkspaceIOTools.load_naukri_jobs_file)
        self.tools.register("save_json", WorkspaceIOTools.save_json)

        self.mcp_server = MCPServer()
        self._register_mcp_tools()
        self.mcp_client = MCPClient(self.mcp_server)
        self.a2a_clients = self._build_local_a2a_clients()
        self.a2a = A2ACoordinator(self.a2a_clients, dispatcher=self.route)
        self.llm = create_llm()
        self.llm_router = LLMRouter(routing_manifest=self.routing_manifest)

    def _build_local_a2a_clients(self) -> Dict[str, A2AHttpClient]:
        clients: Dict[str, A2AHttpClient] = {}

        for agent_name in self.agents.keys():
            async def _executor(payload: Dict[str, Any], name: str = agent_name) -> Dict[str, Any]:
                return await self._route_direct_dict(name, payload)

            server = LocalA2AAgentServer(
                agent_name=agent_name,
                execute_fn=_executor,
                description=f"AutoApply specialized agent '{agent_name}'",
            )
            http_client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=server.app),
                base_url=f"http://{agent_name}.local",
            )
            clients[agent_name] = A2AHttpClient(name=agent_name, http_client=http_client)

        return clients
    
    def _extract_jobs(self, route_result: Dict[str, Any]) -> list[Dict[str, Any]]:
        return route_result.get("result", {}).get("data", {}).get("jobs", [])

    def _rewrite_fetch_details(
        self, jobs: list[Dict[str, Any]], max_items: int = 5, source: str = "unknown", include_descriptions: bool = False
    ) -> Dict[str, Any]:
        """
        Reformat job list into minimal response with only name and description.
        """
        trimmed = jobs[:max_items]
        concise_jobs = []

        for job in trimmed:
            description = job.get("jd_summary") or job.get("description") or "Description not available"
            concise_jobs.append(
                {
                    "name": job.get("title", "N/A"),
                    "description": description,
                }
            )

        if not concise_jobs:
            return {
                "summary": "No jobs found.",
                "jobs": concise_jobs,
                "source": source,
            }

        lines = [f"Found {len(concise_jobs)} jobs:\n"]

        for index, job in enumerate(concise_jobs, start=1):
            desc = (job["description"] or "Description not available").strip()
            lines.append(f"{index}. {job['name']}\nDescription: {desc}\n")

        return {
            "summary": "".join(lines),
            "jobs": concise_jobs,
            "source": source,
        }

    def _register_mcp_tools(self) -> None:
        async def _agent_tool(agent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            result = await self._route_direct(agent_name, payload)
            return {
                "agent": result.agent,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "created_at": result.created_at,
            }

        for agent_name in self.agents.keys():
            async def _handler(payload: Dict[str, Any], name: str = agent_name) -> Dict[str, Any]:
                return await _agent_tool(name, payload)

            self.mcp_server.register_tool(agent_name, _handler)

    async def _route_direct(self, task: str, payload: Dict[str, Any]) -> AgentResult:
        agent = self.agents.get(task)
        if not agent:
            return AgentResult(agent=task, success=False, error=f"Unknown agent task: {task}")

        try:
            return await agent.execute(payload)
        except Exception as exc:
            logger.exception("Agent execution failed for %s", task)
            return AgentResult(agent=task, success=False, error=str(exc))

    async def _route_direct_dict(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._route_direct(task, payload)
        return {
            "agent": result.agent,
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "created_at": result.created_at,
        }

    async def route(self, task: str, payload: Dict[str, Any], use_mcp: bool = False) -> Dict[str, Any]:
        if use_mcp:
            return await self.mcp_client.call_tool(task, payload)

        result = await self._route_direct(task, payload)
        return {
            "ok": result.success,
            "result": {
                "agent": result.agent,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "created_at": result.created_at,
            },
        }

    async def run_pipeline(
        self,
        max_jobs: int = 10,
        filters: Dict[str, Any] | None = None,
        use_mcp: bool = False,
    ) -> Dict[str, Any]:
        fetch_result = await self.route(
            "fetch_jobs",
            {
                "max_jobs": max_jobs,
                "filters": filters or {},
            },
            use_mcp=use_mcp,
        )

        if not fetch_result.get("ok"):
            return {"status": "failed", "stage": "fetch_jobs", "error": fetch_result.get("error")}

        jobs = fetch_result["result"]["data"].get("jobs", [])
        if not jobs:
            return {"status": "no_jobs", "jobs": 0}

        rewrite_result = await self.route(
            "resume_rewrite",
            {"jobs": jobs[: min(len(jobs), 3)]},
            use_mcp=use_mcp,
        )

        naukri_apply_result = await self.route(
            "naukri_applier",
            {"jobs": jobs},
            use_mcp=use_mcp,
        )

        external_apply_result = await self.route(
            "external_applier",
            {"dry_run": False},
            use_mcp=use_mcp,
        )

        return {
            "status": "completed",
            "jobs_fetched": len(jobs),
            "resume_rewrite": rewrite_result,
            "naukri_apply": naukri_apply_result,
            "external_apply": external_apply_result,
        }

    def _build_agent_payload(self, agent_name: str, intent: ParsedIntent) -> Dict[str, Any]:
        manifest = self.routing_manifest.get(agent_name, {})
        defaults = dict(manifest.get("default_payload", {}))
        allowed_keys = set(manifest.get("allowed_payload_keys", []))

        params = intent.parameters if isinstance(intent.parameters, dict) else {}
        if allowed_keys:
            filtered = {key: value for key, value in params.items() if key in allowed_keys}
        else:
            filtered = dict(params)

        defaults.update(filtered)
        return defaults

    def _agent_intent_name(self, agent_name: str) -> str:
        manifest = self.routing_manifest.get(agent_name, {})
        return str(manifest.get("a2a_intent") or agent_name)

    async def _run_single_agent_from_intent(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        target_agent = intent.primary_intent if intent.primary_intent in self.agents else ""
        if not target_agent and intent.agents_to_call:
            target_agent = intent.agents_to_call[0]

        if target_agent not in self.agents:
            return await self._handle_llm_only(query, correlation_id, intent)

        payload = self._build_agent_payload(target_agent, intent)
        step = await self.a2a.ask_agent(
            sender="client_agent",
            agent_name=target_agent,
            intent=self._agent_intent_name(target_agent),
            payload=payload,
            use_mcp=False,
            correlation_id=correlation_id,
        )

        result = step["result"]
        ok = bool(result.get("ok"))

        response = f"Executed agent: {target_agent}."
        fetch_details: Dict[str, Any] | None = None
        if target_agent == "fetch_jobs" and ok:
            jobs = self._extract_jobs(result)
            source = result.get("result", {}).get("data", {}).get("source", "unknown")
            include_descriptions = bool(payload.get("include_descriptions", False))
            fetch_details = self._rewrite_fetch_details(
                jobs,
                max_items=len(jobs),
                source=source,
                include_descriptions=include_descriptions,
            )
            response = fetch_details["summary"]

        output = {
            "status": "ok" if ok else "failed",
            "query": query,
            "selected_flow": target_agent,
            "response": response,
            "correlation_id": correlation_id,
            "intent_confidence": intent.confidence,
            "reasoning": intent.reasoning,
            "extracted_params": payload,
            "result": result,
        }
        if fetch_details is not None:
            output["fetch_details"] = fetch_details
        return output

    async def handle_query(self, query: str) -> Dict[str, Any]:
        """
        Handle user query using LLM-based intent parsing.
        
        The LLM intelligently decides:
        - Which agent(s) to call
        - What parameters to use
        - How to format the response
        - Whether to call multiple agents in sequence
        """
        q = (query or "").strip()
        correlation_id = self.a2a.new_correlation_id()

        if not q:
            return {
                "status": "failed",
                "response": "Query is empty. Please ask me something!",
                "error": "Empty query",
                "correlation_id": correlation_id,
            }

        try:
            # Use LLM to parse intent and extract parameters
            intent = await self.llm_router.parse_intent(q)
            logger.info(
                "Parsed intent: %s (confidence: %.2f) - reasoning: %s",
                intent.primary_intent,
                intent.confidence,
                intent.reasoning,
            )

            if intent.primary_intent == "llm_only" or not intent.agents_to_call:
                return await self._handle_llm_only(q, correlation_id, intent)

            if len(intent.agents_to_call) > 1:
                return await self._handle_multi_agent_flow(q, correlation_id, intent)

            return await self._run_single_agent_from_intent(q, correlation_id, intent)

        except Exception as exc:
            logger.exception("Error handling query: %s", exc)
            return {
                "status": "failed",
                "response": "An error occurred while processing your query. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_llm_only(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle general questions using LLM only."""
        try:
            # Run LLM in thread pool to avoid blocking event loop
            message = await asyncio.to_thread(self.llm.invoke, query)
            response_text = message.content if hasattr(message, 'content') else str(message)
            
            return {
                "status": "ok",
                "query": query,
                "selected_flow": "llm_only",
                "response": response_text,
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
            }
        except Exception as exc:
            logger.exception("LLM response generation failed: %s", exc)
            return {
                "status": "failed",
                "response": "I couldn't generate a response at this moment. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_multi_agent_flow(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle multiple agent calls (e.g., fetch jobs -> apply to them -> rewrite resume)."""
        try:
            sequence = []

            for agent_name in intent.agents_to_call:
                if agent_name not in self.agents:
                    continue

                sequence.append({
                    "agent": agent_name,
                    "intent": self._agent_intent_name(agent_name),
                    "payload": self._build_agent_payload(agent_name, intent),
                })

            if not sequence:
                return await self._handle_llm_only(query, correlation_id, intent)
            
            # Run A2A sequence
            conversation = await self.a2a.run_sequence(
                query=query,
                sequence=sequence,
                use_mcp=False,
                correlation_id=correlation_id,
            )
            
            agent_names = ", ".join(intent.agents_to_call)
            return {
                "status": conversation.status,
                "query": query,
                "selected_flow": "multi_agent_pipeline",
                "response": f"🔄 Executed multi-agent pipeline: {agent_names}",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "agents_executed": intent.agents_to_call,
                "result": asdict(conversation),
            }
        except Exception as exc:
            logger.exception("Multi-agent flow failed: %s", exc)
            return {
                "status": "failed",
                "response": "Multi-agent pipeline failed. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }
