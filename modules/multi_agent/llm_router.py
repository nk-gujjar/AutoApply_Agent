"""LLM-based intent parser and router for intelligent agent selection."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from modules.core.config.settings import logger, create_llm


@dataclass
class ParsedIntent:
    """Result of LLM intent parsing."""
    primary_intent: str  # fetch_jobs, telegram_scraper, jd_extractor, resume_rewrite, naukri_applier, external_applier, llm_only
    agents_to_call: list[str]  # If multiple agents needed
    parameters: Dict[str, Any]  # Extracted parameters (max_jobs, filters, etc.)
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this intent was chosen


class LLMRouter:
    """Uses LLM to intelligently parse intent and extract parameters from user queries."""

    MAX_QUERY_CHARS = 1800
    MAX_HISTORY_MESSAGES = 4
    MAX_HISTORY_MESSAGE_CHARS = 180
    
    def __init__(self, routing_manifest: Dict[str, Dict[str, Any]]):
        self.llm = create_llm()
        self.routing_manifest = routing_manifest
        self.agents = list(routing_manifest.keys())

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + " ...[truncated]"
    
    async def parse_intent(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> ParsedIntent:
        """
        Use LLM to understand user intent and extract parameters.
        
        Args:
            query: The user's current query
            chat_history: Recent messages as [{"role": "human"|"ai", "content": "..."}]
        
        Returns:
            ParsedIntent with detected intent, agents to call, and extracted parameters
        """
        try:
            logger.info("━" * 55)
            logger.info("  🧠 LLM Router — Parsing intent")
            logger.info(f"  📝 Query: \"{query[:120]}{'...' if len(query) > 120 else ''}\"")
            if chat_history:
                logger.info(f"  💬 Chat history: {len(chat_history)} messages provided")
            
            # Create a structured prompt for the LLM
            prompt = self._create_routing_prompt(query, chat_history)
            logger.info("  📏 Intent prompt length: %s chars", len(prompt))
            
            # Run LLM in thread pool to avoid blocking event loop
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"  📨 LLM raw response: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
            
            # Parse LLM response
            parsed = self._parse_llm_response(response_text, query)
            
            logger.info(f"  🎯 Intent: {parsed.primary_intent} (confidence: {parsed.confidence:.2f})")
            logger.info(f"  🤖 Agents: {parsed.agents_to_call}")
            logger.info(f"  📦 Params: {parsed.parameters}")
            logger.info(f"  💡 Reason: {parsed.reasoning}")
            logger.info("━" * 55)
            
            return parsed
            
        except Exception as exc:
            logger.exception("  ❌ LLM intent parsing failed: %s", exc)
            # Fallback: return llm_only intent
            return ParsedIntent(
                primary_intent="llm_only",
                agents_to_call=[],
                parameters={},
                confidence=0.0,
                reasoning=f"Failed to parse intent: {str(exc)}",
            )
    
    def _create_routing_prompt(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Create a structured prompt for LLM to parse intent."""
        compact_query = self._truncate_text(query, self.MAX_QUERY_CHARS)
        agent_profiles = {
            agent: {
                "description": details.get("description", ""),
                "allowed_payload_keys": details.get("allowed_payload_keys", []),
                "default_payload": details.get("default_payload", {}),
                "hints": details.get("hints", []),
            }
            for agent, details in self.routing_manifest.items()
        }
        agent_ids = "|".join(self.agents)

        # Build chat history section
        history_section = ""
        if chat_history:
            history_lines = []
            recent_history = chat_history[-self.MAX_HISTORY_MESSAGES :]
            for msg in recent_history:
                role = "User" if msg.get("role") == "human" else "Assistant"
                content = self._truncate_text(str(msg.get("content", "")), self.MAX_HISTORY_MESSAGE_CHARS)
                history_lines.append(f"  {role}: {content}")
            history_section = (
                "\n\nRecent Conversation Context (use this to resolve references like 'those', 'them', 'it', 'apply to those'):\n"
                + "\n".join(history_lines)
            )

        return f"""You are an intelligent job automation assistant router. Analyze the user's query and determine:
1. The primary intent ({agent_ids} or llm_only)
2. Any parameters needed (max_jobs, filters, etc.)
3. If multiple agents should be called in sequence
{history_section}

Available agents and capabilities:
{json.dumps(agent_profiles, indent=2)}

User Query: "{compact_query}"

Respond in this EXACT JSON format:
{{
    "primary_intent": "<one of: {agent_ids}|llm_only>",
    "agents_to_call": ["agent1", "agent2"],
    "parameters": {{
        "max_jobs": <number or null>,
        "filters": {{}},
        "dry_run": <boolean or null>,
        "keywords": <string or null>,
        "include_descriptions": true,
        "jd_text": <string or null>,
        "jd_url": <string or null>,
        "query": <string or null>
    }},
    "confidence": <0.0 to 1.0>,
    "reasoning": "Brief explanation of why this intent was chosen"
}}

IMPORTANT RULES:
- Choose `llm_only` when no automation agent call is required.
- `agents_to_call` must contain only relevant agents from the available list.
- Parameters should match selected agents' capabilities and can be omitted when not needed.
- "Apply pipeline" or "full automation" can use multiple agents in logical order.
- Resume tailoring requests should prefer `jd_extractor` then `resume_rewrite`.
- When the user says "apply", "apply to jobs", or "auto apply", use `naukri_applier` (Easy Apply only). Do NOT use `external_applier` unless the user explicitly says "external apply" or "company site apply".
- Tolerate typos and infer intent from semantics, not grammar.
- Use conversation history to resolve pronouns and references (e.g., "apply to those" means apply to previously fetched jobs).
- If unsure, choose `llm_only`.
- Always respond with valid JSON only, no extra text"""
    
    def _parse_llm_response(self, response_text: str, query: str) -> ParsedIntent:
        """Parse LLM's JSON response and extract intent."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning("  ⚠️  No JSON found in LLM response, falling back to keyword matching")
                return self._fallback_intent(query)
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            # Validate and extract fields
            intent = data.get("primary_intent", "llm_only")
            agents = data.get("agents_to_call", [])
            params = data.get("parameters", {})
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "No reasoning provided")
            
            # Validate intent
            if intent not in [*self.agents, "llm_only"]:
                logger.info(f"  ⚠️  Unknown intent '{intent}', defaulting to llm_only")
                intent = "llm_only"

            agents = [agent for agent in agents if agent in self.agents]
            if intent != "llm_only" and not agents:
                agents = [intent]
            
            # Clean up parameters
            cleaned_params = self._clean_parameters(intent, agents, params)
            
            return ParsedIntent(
                primary_intent=intent,
                agents_to_call=agents,
                parameters=cleaned_params,
                confidence=min(max(confidence, 0.0), 1.0),
                reasoning=reasoning,
            )
            
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("  ⚠️  Failed to parse LLM JSON response: %s", exc)
            return self._fallback_intent(query)
    
    def _clean_parameters(self, intent: str, agents: list[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted parameters."""
        if intent == "llm_only":
            return {}

        raw_params = params if isinstance(params, dict) else {}

        selected_agents = [agent for agent in agents if agent in self.routing_manifest]
        if not selected_agents and intent in self.routing_manifest:
            selected_agents = [intent]

        allowed_keys: set[str] = set()
        defaults: Dict[str, Any] = {}
        for agent in selected_agents:
            manifest_entry = self.routing_manifest.get(agent, {})
            allowed_keys.update(manifest_entry.get("allowed_payload_keys", []))
            for key, value in manifest_entry.get("default_payload", {}).items():
                defaults.setdefault(str(key), value)

        cleaned = {
            key: value
            for key, value in raw_params.items()
            if not allowed_keys or key in allowed_keys
        }

        for key, value in defaults.items():
            cleaned.setdefault(key, value)

        if "max_jobs" in cleaned and cleaned["max_jobs"] is not None:
            try:
                cleaned["max_jobs"] = max(1, min(int(cleaned["max_jobs"]), 25))
            except (ValueError, TypeError):
                cleaned["max_jobs"] = defaults.get("max_jobs", 5)

        if "filters" in cleaned and not isinstance(cleaned.get("filters"), dict):
            cleaned["filters"] = {}

        if "include_descriptions" in cleaned:
            cleaned["include_descriptions"] = bool(cleaned["include_descriptions"])

        if "dry_run" in cleaned:
            cleaned["dry_run"] = bool(cleaned["dry_run"])

        return cleaned
    
    def _fallback_intent(self, query: str) -> ParsedIntent:
        """Fallback intent detection using keyword matching."""
        q = (query or "").strip().lower()
        logger.info("  🔄 Using keyword-based fallback intent detection")
        
        # Check for full pipeline
        if any(key in q for key in ["full", "pipeline", "all agents", "end to end", "complete automation"]):
            pipeline_agents = [
                agent
                for agent in ["fetch_jobs", "resume_rewrite", "naukri_applier"]
                if agent in self.agents
            ]
            primary = pipeline_agents[0] if pipeline_agents else "llm_only"
            logger.info(f"  🔄 Fallback: full pipeline detected → {pipeline_agents}")
            return ParsedIntent(
                primary_intent=primary,
                agents_to_call=pipeline_agents,
                parameters={"max_jobs": 5},
                confidence=0.7,
                reasoning="User requested full automation pipeline",
            )

        # Check catalog-defined hints
        for agent, details in self.routing_manifest.items():
            hints = [str(h).lower() for h in details.get("hints", [])]
            if any(hint in q for hint in hints if hint):
                params: Dict[str, Any] = {}
                if agent == "fetch_jobs":
                    params["max_jobs"] = self._extract_max_jobs_fallback(q)

                if agent == "resume_rewrite" and "jd_extractor" in self.agents:
                    logger.info(f"  🔄 Fallback: resume keywords → jd_extractor + resume_rewrite pipeline")
                    return ParsedIntent(
                        primary_intent="jd_extractor",
                        agents_to_call=["jd_extractor", "resume_rewrite"],
                        parameters=params,
                        confidence=0.8,
                        reasoning="Resume tailoring query mapped to jd_extractor -> resume_rewrite pipeline",
                    )

                logger.info(f"  🔄 Fallback: matched hint for agent '{agent}'")
                return ParsedIntent(
                    primary_intent=agent,
                    agents_to_call=[agent],
                    parameters=params,
                    confidence=0.75,
                    reasoning=f"Matched query with routing hints for {agent}",
                )
        
        # Default: LLM only for general queries
        logger.info("  🔄 Fallback: no agent matched, using llm_only")
        return ParsedIntent(
            primary_intent="llm_only",
            agents_to_call=[],
            parameters={},
            confidence=0.5,
            reasoning="Could not determine specific intent, using LLM for response",
        )
    
    def _extract_max_jobs_fallback(self, query_lower: str) -> int:
        """Extract max_jobs number from query using regex fallback."""
        # Look for patterns like "1 job", "5 jobs", "fetch 3", etc.
        patterns = [
            r'(\d+)\s*jobs?',
            r'fetch\s*(\d+)',
            r'(\d+)\s*opportunities',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    num = int(match.group(1))
                    return max(1, min(num, 25))  # Clamp between 1-25
                except (ValueError, IndexError):
                    pass
        
        return 5  # Default

