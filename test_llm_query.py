#!/usr/bin/env python3
"""Test script to verify LLM query parsing."""

import asyncio
import sys
from modules.multi_agent.llm_router import LLMRouter
from modules.core.config.settings import logger


async def test_queries():
    """Test various query formats to verify parsing."""
    router = LLMRouter()
    
    test_cases = [
        "fetch 2 Job and there description",
        "fetch 2 jobs and their description",
        "fetch 2 jobs with descriptions",
        "fetch 1 job",
        "fetch 5 jobs",
        "find me 3 opportunities with details",
    ]
    
    print("\n" + "="*80)
    print("Testing LLM Query Parsing")
    print("="*80 + "\n")
    
    for query in test_cases:
        print(f"Query: {query}")
        try:
            intent = await router.parse_intent(query)
            print(f"  ✅ Intent: {intent.primary_intent}")
            print(f"  📊 Confidence: {intent.confidence:.1%}")
            print(f"  📋 Parameters: {intent.parameters}")
            print(f"  💭 Reasoning: {intent.reasoning}")
            print(f"  👥 Agents: {intent.agents_to_call}")
            
            # Validate max_jobs
            max_jobs = intent.parameters.get("max_jobs", 5)
            include_desc = intent.parameters.get("include_descriptions", False)
            print(f"  🎯 Expected max_jobs extracted correctly: {max_jobs}")
            print(f"  📝 Include descriptions: {include_desc}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test_queries())
        print("\n✨ All tests completed!")
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test error")
        sys.exit(1)
