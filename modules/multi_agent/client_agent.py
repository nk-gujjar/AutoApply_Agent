from __future__ import annotations

import asyncio
import re
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


RESUME_PIPELINE_PATTERN = re.compile(r"\b(resume|cv|tailor|tailored|rewrite)\b", re.IGNORECASE)


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

    async def _run_resume_with_jd_extraction(
        self,
        query: str,
        correlation_id: str,
        intent: ParsedIntent,
    ) -> Dict[str, Any]:
        extract_payload = {
            "query": query,
            **({k: v for k, v in intent.parameters.items() if k in {"jd_text", "jd_url"}} if isinstance(intent.parameters, dict) else {}),
        }

        extract_step = await self.a2a.ask_agent(
            sender="client_agent",
            agent_name="jd_extractor",
            intent=self._agent_intent_name("jd_extractor"),
            payload=extract_payload,
            use_mcp=False,
            correlation_id=correlation_id,
        )

        extract_result = extract_step["result"]
        if not extract_result.get("ok"):
            return {
                "status": "failed",
                "query": query,
                "selected_flow": "jd_extractor",
                "response": "Failed to extract job description for resume tailoring.",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "result": extract_result,
            }

        extracted_job = extract_result.get("result", {}).get("data", {}).get("job")
        if not isinstance(extracted_job, dict):
            return {
                "status": "failed",
                "query": query,
                "selected_flow": "jd_extractor",
                "response": "JD extractor did not return a valid structured job payload.",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "result": extract_result,
            }

        rewrite_step = await self.a2a.ask_agent(
            sender="client_agent",
            agent_name="resume_rewrite",
            intent=self._agent_intent_name("resume_rewrite"),
            payload={"job": extracted_job},
            use_mcp=False,
            correlation_id=correlation_id,
        )

        rewrite_result = rewrite_step["result"]
        ok = bool(rewrite_result.get("ok"))

        generated = rewrite_result.get("result", {}).get("data", {}).get("generated", [])
        cv_path = ""
        if isinstance(generated, list) and generated and isinstance(generated[0], dict):
            cv_path = str(generated[0].get("cv_path") or "")

        response = "Executed two-agent resume pipeline: jd_extractor -> resume_rewrite."
        if ok and cv_path:
            response = (
                "Executed two-agent resume pipeline: jd_extractor -> resume_rewrite.\n"
                f"Resume generated: {cv_path}"
            )

        return {
            "status": "ok" if ok else "failed",
            "query": query,
            "selected_flow": "resume_rewrite",
            "response": response,
            "correlation_id": correlation_id,
            "intent_confidence": intent.confidence,
            "reasoning": intent.reasoning,
            "agents_executed": ["jd_extractor", "resume_rewrite"],
            "result": rewrite_result,
            "pipeline": {
                "jd_extractor": extract_result,
                "resume_rewrite": rewrite_result,
            },
        }

    async def _run_single_agent_from_intent(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        target_agent = intent.primary_intent if intent.primary_intent in self.agents else ""
        if not target_agent and intent.agents_to_call:
            target_agent = intent.agents_to_call[0]

        if target_agent not in self.agents:
            return await self._handle_llm_only(query, correlation_id, intent)

        if target_agent == "resume_rewrite":
            return await self._run_resume_with_jd_extraction(query, correlation_id, intent)

        payload = self._build_agent_payload(target_agent, intent)
        if target_agent == "jd_extractor" and not payload.get("query"):
            payload["query"] = query

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
        jd_details: Dict[str, Any] | None = None
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

        if target_agent == "jd_extractor" and ok:
            jd_data = result.get("result", {}).get("data", {})
            job = jd_data.get("job") if isinstance(jd_data, dict) else {}
            if isinstance(job, dict):
                title = str(job.get("title") or "Not specified").strip()
                description = str(job.get("description") or "").strip()
                qualifications = str(job.get("qualifications") or "").strip()
                skills = job.get("skills_required") or []
                if isinstance(skills, str):
                    skills_list = [s.strip() for s in skills.split(",") if s.strip()]
                elif isinstance(skills, list):
                    skills_list = [str(s).strip() for s in skills if str(s).strip()]
                else:
                    skills_list = []

                bullets: list[str] = []
                if description:
                    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", description) if s.strip()]
                    for sentence in sentences[:4]:
                        bullets.append(sentence[:260])

                if qualifications:
                    q_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", qualifications) if s.strip()]
                    if q_sentences:
                        bullets.append("Qualifications: " + q_sentences[0][:220])
                    else:
                        bullets.append("Qualifications: " + qualifications[:220])

                if skills_list:
                    bullets.append("Key Skills: " + ", ".join(skills_list[:12]))

                source = str(jd_data.get("source") or "unknown")
                response_lines = [f"JD Key Points ({source})", f"Title: {title}"]
                for bullet in bullets[:6]:
                    response_lines.append(f"- {bullet}")
                response = "\n".join(response_lines)
                jd_details = {"title": title, "skills": skills_list, "source": source}

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
        if jd_details is not None:
            output["jd_details"] = jd_details
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

            if (
                intent.primary_intent == "llm_only"
                and "jd_extractor" in self.agents
                and "resume_rewrite" in self.agents
                and RESUME_PIPELINE_PATTERN.search(q)
            ):
                forced_intent = ParsedIntent(
                    primary_intent="jd_extractor",
                    agents_to_call=["jd_extractor", "resume_rewrite"],
                    parameters={"query": q},
                    confidence=max(intent.confidence, 0.8),
                    reasoning="Deterministic fallback: resume keywords detected, forcing jd_extractor -> resume_rewrite pipeline",
                )
                return await self._run_resume_with_jd_extraction(q, correlation_id, forced_intent)

            if intent.primary_intent == "llm_only" or not intent.agents_to_call:
                return await self._handle_llm_only(q, correlation_id, intent)

            if "resume_rewrite" in intent.agents_to_call and "jd_extractor" in self.agents:
                return await self._run_resume_with_jd_extraction(q, correlation_id, intent)

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
