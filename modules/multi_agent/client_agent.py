from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Dict

from modules.core.config.settings import logger, create_llm

from .a2a import A2ACoordinator
from .agents import (
    ExternalApplierAgent,
    FetchJobsAgent,
    NaukriApplierAgent,
    NaukriScraperAgent,
    ResumeRewriteAgent,
)
from .llm_router import LLMRouter, ParsedIntent
from .mcp import MCPClient, MCPServer
from .models import A2AConversationResult, AgentResult
from .tools import ToolRegistry, WorkspaceIOTools


class ClientAgent:
    def __init__(self) -> None:
        self.agents = {
            "naukri_scraper": NaukriScraperAgent(),
            "fetch_jobs": FetchJobsAgent(),
            "resume_rewrite": ResumeRewriteAgent(),
            "naukri_applier": NaukriApplierAgent(),
            "external_applier": ExternalApplierAgent(),
        }

        self.tools = ToolRegistry()
        self.tools.register("load_naukri_jobs_file", WorkspaceIOTools.load_naukri_jobs_file)
        self.tools.register("save_json", WorkspaceIOTools.save_json)

        self.mcp_server = MCPServer()
        self._register_mcp_tools()
        self.mcp_client = MCPClient(self.mcp_server)
        self.a2a = A2ACoordinator(self.route)
        self.llm = create_llm()
        self.llm_router = LLMRouter()
    
    def _requires_agent(self, query: str) -> bool:
        """Check if query requires agent involvement based on keywords."""
        q = (query or "").strip().lower()
        agent_keywords = {
            "full pipeline": ["full", "pipeline", "all agents", "end to end"],
            "fetch_jobs": ["fetch", "scrape", "jobs list", "find jobs"],
            "resume_rewrite": ["resume", "cv", "rewrite"],
            "naukri_applier": ["naukri apply", "apply naukri", "apply on naukri"],
            "external_applier": ["external apply", "company site", "external"],
        }
        
        for agent, keywords in agent_keywords.items():
            if any(key in q for key in keywords):
                return True
        return False
    
    async def _get_llm_response(self, query: str, correlation_id: str) -> Dict[str, Any]:
        """Get LLM response for queries not requiring agents."""
        try:
            message = self.llm.invoke(query)
            response_text = message.content if hasattr(message, 'content') else str(message)
            
            return {
                "status": "ok",
                "query": query,
                "selected_flow": "llm",
                "response": response_text,
                "correlation_id": correlation_id,
                "result": {
                    "type": "llm_response",
                    "content": response_text,
                },
            }
        except Exception as exc:
            logger.exception("LLM response generation failed for query: %s", query)
            return {
                "status": "failed",
                "query": query,
                "selected_flow": "llm",
                "response": "I couldn't generate a response. Please try again.",
                "correlation_id": correlation_id,
                "error": str(exc),
                "result": {
                    "type": "llm_error",
                    "error": str(exc),
                },
            }

    def _extract_jobs(self, route_result: Dict[str, Any]) -> list[Dict[str, Any]]:
        return route_result.get("result", {}).get("data", {}).get("jobs", [])

    def _rewrite_fetch_details(
        self, jobs: list[Dict[str, Any]], max_items: int = 5, source: str = "unknown", include_descriptions: bool = False
    ) -> Dict[str, Any]:
        """
        Reformat job list into humanoid, conversational response.
        Includes source information (cache vs live scrape).
        Optionally includes job descriptions from jd_summary.
        """
        trimmed = jobs[:max_items]
        concise_jobs = []

        for job in trimmed:
            job_entry = {
                "title": job.get("title", "N/A"),
                "company": job.get("company", "N/A"),
                "location": job.get("location", "N/A"),
                "experience": job.get("experience", "N/A"),
                "apply_type": job.get("apply_type", "N/A"),
                "apply_status": job.get("apply_status", "N/A"),
                "ctc": job.get("ctc", "Not mentioned"),
                "link": job.get("link", "N/A"),
            }
            # Add description if requested and available
            if include_descriptions and "jd_summary" in job:
                job_entry["description"] = job.get("jd_summary", "")
            concise_jobs.append(job_entry)

        if not concise_jobs:
            return {
                "summary": "😔 No jobs found matching your criteria. Try adjusting your filters or check back later!",
                "jobs": concise_jobs,
                "source": source,
            }

        # Build humanoid response
        source_emoji = "📦" if source == "cache" else "🔄"
        source_text = "cached database" if source == "cache" else "live scraping"
        
        lines = [
            f"✨ Great! I found **{len(jobs)}** matching jobs from our {source_text}.",
            f"Here are the top {len(concise_jobs)} opportunities:\n",
        ]
        
        for index, job in enumerate(concise_jobs, start=1):
            lines.append(
                f"{index}. **{job['title']}** @ {job['company']}\n"
                f"   📍 Location: {job['location']} | 📅 Exp: {job['experience']}\n"
                f"   💰 CTC: {job['ctc']} | 🔗 Apply: {job['apply_type']}\n"
            )
            # Add description if available
            if include_descriptions and "description" in job and job["description"]:
                # Truncate long descriptions to 200 chars
                desc = job["description"][:200] + ("..." if len(job["description"]) > 200 else "")
                lines.append(f"   📝 Description: {desc}\n")
        
        lines.append(f"\n{source_emoji} Data from: {source_text}")
        lines.append("💡 Pro tip: Use 'fetch jobs' with filters to narrow down results!")

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

            # Route based on primary intent
            if intent.primary_intent == "llm_only":
                # General question - use LLM directly
                return await self._handle_llm_only(q, correlation_id, intent)
            
            elif intent.primary_intent == "fetch_jobs":
                # Use LLM-extracted parameters (max_jobs, filters, keywords)
                return await self._handle_fetch_jobs(q, correlation_id, intent)
            
            elif intent.primary_intent == "resume_rewrite":
                # Resume rewriting - multiple agents if needed
                return await self._handle_resume_rewrite(q, correlation_id, intent)
            
            elif intent.primary_intent == "naukri_applier":
                return await self._handle_naukri_applier(q, correlation_id, intent)
            
            elif intent.primary_intent == "external_applier":
                return await self._handle_external_applier(q, correlation_id, intent)
            
            else:
                # Fallback to LLM
                return await self._handle_llm_only(q, correlation_id, intent)

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

    async def _handle_fetch_jobs(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle job fetching with LLM-extracted parameters."""
        try:
            max_jobs = intent.parameters.get("max_jobs", 5)
            filters = intent.parameters.get("filters", {})
            
            # Check if multiple agents are needed (e.g., fetch + apply)
            if len(intent.agents_to_call) > 1:
                return await self._handle_multi_agent_flow(query, correlation_id, intent)
            
            # Single agent: fetch_jobs
            step = await self.a2a.ask_agent(
                sender="client_agent",
                agent_name="fetch_jobs",
                intent="discover_jobs",
                payload={"max_jobs": max_jobs, "filters": filters, "use_cache": True},
                use_mcp=False,
                correlation_id=correlation_id,
            )
            
            result = step["result"]
            jobs = self._extract_jobs(result) if result.get("ok") else []
            source = result.get("result", {}).get("data", {}).get("source", "unknown")
            
            # Format with LLM-extracted max_jobs (should now return exact count)
            include_descriptions = intent.parameters.get("include_descriptions", False)
            rewritten = self._rewrite_fetch_details(jobs, max_items=len(jobs), source=source, include_descriptions=include_descriptions)
            
            return {
                "status": "ok" if result.get("ok") else "failed",
                "query": query,
                "selected_flow": "fetch_jobs",
                "response": rewritten["summary"] if result.get("ok") else "Failed to fetch jobs.",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "extracted_params": {
                    "max_jobs": max_jobs,
                    "filters": filters,
                },
                "fetch_details": rewritten,
                "result": result,
            }
        except Exception as exc:
            logger.exception("Fetch jobs failed: %s", exc)
            return {
                "status": "failed",
                "response": "Failed to fetch jobs. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_resume_rewrite(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle resume rewriting."""
        try:
            # Check if resume tailoring is needed with fetched jobs
            if len(intent.agents_to_call) > 1:
                return await self._handle_multi_agent_flow(query, correlation_id, intent)
            
            step = await self.a2a.ask_agent(
                sender="client_agent",
                agent_name="resume_rewrite",
                intent="tailor_resume",
                payload={},
                use_mcp=False,
                correlation_id=correlation_id,
            )
            
            result = step["result"]
            count = result.get("result", {}).get("data", {}).get("count", 0) if result.get("ok") else 0
            
            return {
                "status": "ok" if result.get("ok") else "failed",
                "query": query,
                "selected_flow": "resume_rewrite",
                "response": f"✨ Generated {count} tailored resume output(s).",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "result": result,
            }
        except Exception as exc:
            logger.exception("Resume rewrite failed: %s", exc)
            return {
                "status": "failed",
                "response": "Failed to rewrite resume. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_naukri_applier(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle Naukri applications."""
        try:
            step = await self.a2a.ask_agent(
                sender="client_agent",
                agent_name="naukri_applier",
                intent="apply_naukri",
                payload={},
                use_mcp=False,
                correlation_id=correlation_id,
            )
            
            result = step["result"]
            applied = result.get("result", {}).get("data", {}).get("applied", 0) if result.get("ok") else 0
            
            return {
                "status": "ok" if result.get("ok") else "failed",
                "query": query,
                "selected_flow": "naukri_applier",
                "response": f"🚀 Applied to {applied} jobs on Naukri!",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "result": result,
            }
        except Exception as exc:
            logger.exception("Naukri apply failed: %s", exc)
            return {
                "status": "failed",
                "response": "Failed to apply on Naukri. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_external_applier(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle external (direct company) applications."""
        try:
            step = await self.a2a.ask_agent(
                sender="client_agent",
                agent_name="external_applier",
                intent="apply_external",
                payload={"dry_run": False},
                use_mcp=False,
                correlation_id=correlation_id,
            )
            
            result = step["result"]
            applied = result.get("result", {}).get("data", {}).get("applied", 0) if result.get("ok") else 0
            
            return {
                "status": "ok" if result.get("ok") else "failed",
                "query": query,
                "selected_flow": "external_applier",
                "response": f"🎯 Applied to {applied} companies directly!",
                "correlation_id": correlation_id,
                "intent_confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "result": result,
            }
        except Exception as exc:
            logger.exception("External apply failed: %s", exc)
            return {
                "status": "failed",
                "response": "Failed to apply externally. Please try again.",
                "error": str(exc),
                "correlation_id": correlation_id,
            }

    async def _handle_multi_agent_flow(
        self, query: str, correlation_id: str, intent: ParsedIntent
    ) -> Dict[str, Any]:
        """Handle multiple agent calls (e.g., fetch jobs -> apply to them -> rewrite resume)."""
        try:
            sequence = []
            params = intent.parameters
            
            # Build sequence based on agents to call
            if "fetch_jobs" in intent.agents_to_call:
                sequence.append({
                    "agent": "fetch_jobs",
                    "intent": "discover_jobs",
                    "payload": {
                        "max_jobs": params.get("max_jobs", 5),
                        "filters": params.get("filters", {}),
                    },
                })
            
            if "resume_rewrite" in intent.agents_to_call:
                sequence.append({
                    "agent": "resume_rewrite",
                    "intent": "tailor_resume",
                    "payload": {},
                })
            
            if "naukri_applier" in intent.agents_to_call:
                sequence.append({
                    "agent": "naukri_applier",
                    "intent": "apply_naukri",
                    "payload": {},
                })
            
            if "external_applier" in intent.agents_to_call:
                sequence.append({
                    "agent": "external_applier",
                    "intent": "apply_external",
                    "payload": {"dry_run": False},
                })
            
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
