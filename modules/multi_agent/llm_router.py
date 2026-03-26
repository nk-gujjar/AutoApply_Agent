"""LLM-based intent parser and router for intelligent agent selection."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from modules.core.config.settings import logger, create_llm


@dataclass
class ParsedIntent:
    """Result of LLM intent parsing."""
    primary_intent: str  # fetch_jobs, resume_rewrite, naukri_applier, external_applier, llm_only
    agents_to_call: list[str]  # If multiple agents needed
    parameters: Dict[str, Any]  # Extracted parameters (max_jobs, filters, etc.)
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this intent was chosen


class LLMRouter:
    """Uses LLM to intelligently parse intent and extract parameters from user queries."""
    
    def __init__(self):
        self.llm = create_llm()
        self.agents = ["fetch_jobs", "resume_rewrite", "naukri_applier", "external_applier"]
    
    async def parse_intent(self, query: str) -> ParsedIntent:
        """
        Use LLM to understand user intent and extract parameters.
        
        Returns:
            ParsedIntent with detected intent, agents to call, and extracted parameters
        """
        try:
            # Create a structured prompt for the LLM
            prompt = self._create_routing_prompt(query)
            
            # Run LLM in thread pool to avoid blocking event loop
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse LLM response
            parsed = self._parse_llm_response(response_text, query)
            return parsed
            
        except Exception as exc:
            logger.exception("LLM intent parsing failed: %s", exc)
            # Fallback: return llm_only intent
            return ParsedIntent(
                primary_intent="llm_only",
                agents_to_call=[],
                parameters={},
                confidence=0.0,
                reasoning=f"Failed to parse intent: {str(exc)}",
            )
    
    def _create_routing_prompt(self, query: str) -> str:
        """Create a structured prompt for LLM to parse intent."""
        return f"""You are an intelligent job automation assistant router. Analyze the user's query and determine:
1. The primary intent (fetch_jobs, resume_rewrite, naukri_applier, external_applier, or llm_only)
2. Any parameters needed (max_jobs, filters, etc.)
3. If multiple agents should be called in sequence

User Query: "{query}"

Respond in this EXACT JSON format:
{{
    "primary_intent": "fetch_jobs|resume_rewrite|naukri_applier|external_applier|llm_only",
    "agents_to_call": ["agent1", "agent2"],
    "parameters": {{
        "max_jobs": <number or null>,
        "filters": {{}},
        "dry_run": <boolean or null>,
        "keywords": <string or null>,
        "include_descriptions": true
    }},
    "confidence": <0.0 to 1.0>,
    "reasoning": "Brief explanation of why this intent was chosen"
}}

IMPORTANT RULES:
- If user says "fetch 1 job", set max_jobs to 1
- If user says "fetch 5 jobs", set max_jobs to 5
- If user says "fetch 2 job" or "fetch 2 Job" (typo), set max_jobs to 2
- If user says "fetch jobs", set max_jobs to 5 (default)
- If user mentions "description" or "details", set include_descriptions to true
- Extract keywords like "AI engineer", "Python developer", "remote" for filters
- "Apply pipeline" or "full automation" means call multiple agents: [fetch_jobs, resume_rewrite, naukri_applier]
- Use llm_only for general questions like "what is Python?", "how to prepare for interviews?"
- TOLERATE TYPOS: "Job" = "jobs", "there" = "their", etc. - Focus on intent not grammar
- If unsure, use llm_only to ask clarifying questions
- Always respond with valid JSON only, no extra text"""
    
    def _parse_llm_response(self, response_text: str, query: str) -> ParsedIntent:
        """Parse LLM's JSON response and extract intent."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in LLM response, falling back to llm_only")
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
            if intent not in ["fetch_jobs", "resume_rewrite", "naukri_applier", "external_applier", "llm_only"]:
                intent = "llm_only"
            
            # Clean up parameters
            cleaned_params = self._clean_parameters(intent, params)
            
            return ParsedIntent(
                primary_intent=intent,
                agents_to_call=agents,
                parameters=cleaned_params,
                confidence=min(max(confidence, 0.0), 1.0),
                reasoning=reasoning,
            )
            
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM JSON response: %s", exc)
            return self._fallback_intent(query)
    
    def _clean_parameters(self, intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted parameters."""
        cleaned = {}
        
        # Extract max_jobs
        if "max_jobs" in params and params["max_jobs"] is not None:
            try:
                max_jobs = int(params["max_jobs"])
                cleaned["max_jobs"] = max(1, min(max_jobs, 25))  # Clamp between 1-25
            except (ValueError, TypeError):
                cleaned["max_jobs"] = 5  # Default
        else:
            cleaned["max_jobs"] = 5  # Default
        
        # Extract filters
        if "filters" in params and isinstance(params["filters"], dict):
            cleaned["filters"] = params["filters"]
        else:
            cleaned["filters"] = {}
        
        # Extract keywords
        if "keywords" in params and params["keywords"]:
            cleaned["keywords"] = str(params["keywords"]).strip()
        
        # Extract dry_run
        if "dry_run" in params and params["dry_run"] is not None:
            cleaned["dry_run"] = bool(params["dry_run"])
        
        # Extract include_descriptions flag
        if "include_descriptions" in params and params["include_descriptions"] is not None:
            cleaned["include_descriptions"] = bool(params["include_descriptions"])
        else:
            cleaned["include_descriptions"] = False
        
        return cleaned
    
    def _fallback_intent(self, query: str) -> ParsedIntent:
        """Fallback intent detection using keyword matching."""
        q = (query or "").strip().lower()
        
        # Check for full pipeline
        if any(key in q for key in ["full", "pipeline", "all agents", "end to end", "complete automation"]):
            return ParsedIntent(
                primary_intent="fetch_jobs",
                agents_to_call=["fetch_jobs", "resume_rewrite", "naukri_applier", "external_applier"],
                parameters={"max_jobs": 5},
                confidence=0.7,
                reasoning="User requested full automation pipeline",
            )
        
        # Check for fetch jobs
        if any(key in q for key in ["fetch", "scrape", "jobs", "find opportunities", "search"]):
            max_jobs = self._extract_max_jobs_fallback(q)
            return ParsedIntent(
                primary_intent="fetch_jobs",
                agents_to_call=["fetch_jobs"],
                parameters={"max_jobs": max_jobs},
                confidence=0.8,
                reasoning="User requested job fetching",
            )
        
        # Check for resume
        if any(key in q for key in ["resume", "cv", "rewrite", "tailor"]):
            return ParsedIntent(
                primary_intent="resume_rewrite",
                agents_to_call=["resume_rewrite"],
                parameters={},
                confidence=0.8,
                reasoning="User requested resume rewriting",
            )
        
        # Check for naukri apply
        if any(key in q for key in ["naukri", "apply naukri", "apply on naukri"]):
            return ParsedIntent(
                primary_intent="naukri_applier",
                agents_to_call=["naukri_applier"],
                parameters={},
                confidence=0.8,
                reasoning="User requested Naukri applications",
            )
        
        # Check for external apply
        if any(key in q for key in ["external", "company site", "direct application"]):
            return ParsedIntent(
                primary_intent="external_applier",
                agents_to_call=["external_applier"],
                parameters={},
                confidence=0.8,
                reasoning="User requested external applications",
            )
        
        # Default: LLM only for general queries
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
