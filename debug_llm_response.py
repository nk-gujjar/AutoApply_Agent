#!/usr/bin/env python3
"""Debug script to see raw LLM responses."""

import asyncio
import json
import re
from modules.core.config.settings import create_llm, logger


async def debug_llm_response():
    """Debug the raw LLM responses for query parsing."""
    llm = create_llm()
    
    test_queries = [
        "fetch 1 job",
        "fetch 2 Job and there description",
        "fetch 3 jobs please",
    ]
    
    print("\n" + "="*80)
    print("Debugging Raw LLM Responses")
    print("="*80 + "\n")
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 80)
        
        prompt = f"""You are an intelligent job automation assistant router. Analyze the user's query and determine:
1. The primary intent (fetch_jobs, resume_rewrite, naukri_applier, external_applier, or llm_only)
2. Any parameters needed (max_jobs, filters, etc.)

User Query: "{query}"

Respond in this EXACT JSON format:
{{
    "primary_intent": "fetch_jobs|resume_rewrite|naukri_applier|external_applier|llm_only",
    "agents_to_call": ["agent1"],
    "parameters": {{
        "max_jobs": <number or null>,
        "filters": {{}},
        "include_descriptions": true
    }},
    "confidence": <0.0 to 1.0>,
    "reasoning": "Brief explanation"
}}

IMPORTANT RULES:
- If user says "fetch 1 job", set max_jobs to 1
- If user says "fetch 2 jobs", set max_jobs to 2
- If user says "fetch 2 Job" (typo), set max_jobs to 2
- If user says "fetch 3 jobs", set max_jobs to 3
- Always respond with valid JSON only"""
        
        try:
            message = await asyncio.to_thread(llm.invoke, prompt)
            response_text = message.content if hasattr(message, 'content') else str(message)
            
            print(f"Raw Response:\\n{response_text}\\n")
            
            # Try to extract JSON
            json_match = re.search(r'\\{.*\\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                    print(f"Parsed JSON:\\n{json.dumps(data, indent=2)}\\n")
                    max_jobs = data.get('parameters', {}).get('max_jobs')
                    print(f"✅ max_jobs extracted: {max_jobs}")
                except json.JSONDecodeError as e:
                    print(f"❌ JSON Parse Error: {e}")
            else:
                print("❌ No JSON found in response")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            logger.exception("Debug error")


if __name__ == "__main__":
    try:
        asyncio.run(debug_llm_response())
    except Exception as e:
        print(f"\\nError: {e}")
        logger.exception("Script error")
