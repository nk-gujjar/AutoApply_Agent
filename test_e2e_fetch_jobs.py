#!/usr/bin/env python3
"""End-to-end integration test for the fetch jobs query."""

import asyncio
import json
from modules.multi_agent import ClientAgent


async def test_fetch_jobs_query():
    """Test the complete flow for fetching jobs with descriptions."""
    client = ClientAgent()
    
    test_queries = [
        ("fetch 2 Job and there description", "Typo version (your query)"),
        ("fetch 2 jobs and their description", "Corrected version"),
        ("fetch 2 jobs with descriptions", "Alternative wording"),
    ]
    
    print("\n" + "="*80)
    print("End-to-End Integration Test: Fetch Jobs with Descriptions")
    print("="*80 + "\n")
    
    for query, description in test_queries:
        print(f"\n📌 Test: {description}")
        print(f"🔍 Query: \"{query}\"")
        print("-" * 80)
        
        try:
            result = await client.handle_query(query)
            
            # Print status
            status = result.get("status", "unknown")
            print(f"✅ Status: {status}")
            
            # Print extracted params
            if "extracted_params" in result:
                params = result["extracted_params"]
                print(f"📊 Extracted Parameters:")
                print(f"   • max_jobs: {params.get('max_jobs', 'N/A')}")
                print(f"   • filters: {params.get('filters', {})}")
            
            if "intent_confidence" in result:
                print(f"🎯 Confidence: {result['intent_confidence']:.1%}")
            
            # Print reasoning
            if "reasoning" in result:
                print(f"💭 Reasoning: {result['reasoning']}")
            
            # Print response summary
            response = result.get("response", "")
            if response:
                print(f"\\n📝 Response:\\n{response}")
            
            # Print jobs details if available
            if "fetch_details" in result and "jobs" in result["fetch_details"]:
                jobs = result["fetch_details"]["jobs"]
                print(f"\\n📋 Jobs Found: {len(jobs)}")
                for idx, job in enumerate(jobs, 1):
                    print(f"\\n   Job {idx}:")
                    print(f"     • Title: {job.get('title', 'N/A')}")
                    print(f"     • Company: {job.get('company', 'N/A')}")
                    if "description" in job:
                        desc = job["description"][:100] + ("..." if len(job["description"]) > 100 else "")
                        print(f"     • Description: {desc}")
                    else:
                        print(f"     • Description: Not included")
            
            if result.get("error"):
                print(f"\\n⚠️  Error: {result['error']}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
        
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test_fetch_jobs_query())
        print("\n✨ End-to-end test completed!")
    except Exception as e:
        print(f"\\nTest failed: {e}")
        import traceback
        traceback.print_exc()
