import json
from typing import Any, Dict

import httpx
import streamlit as st


def run_client_query(query: str, backend_url: str, debug: bool = False) -> Dict[str, Any]:
    """
    Query the backend API with natural language.
    
    Args:
        query: User's natural language query
        backend_url: Backend URL
        debug: If True, use /chat/debug endpoint for full technical data
    
    Returns:
        Response dictionary with 'response' and optional 'error' fields
    """
    try:
        endpoint = "/chat/debug" if debug else "/chat"
        response = httpx.post(
            f"{backend_url.rstrip('/')}{endpoint}",
            json={"query": query},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {
            "response": "Backend is unreachable or failed to process the request.",
            "error": str(exc),
        }


def result_to_text(result: Dict[str, Any]) -> str:
    """Format result into displayable text (clean format for users)."""
    response_text = result.get("response", "No response generated")
    error_text = result.get("error")
    
    output = response_text
    if error_text:
        output += f"\n\n⚠️ Error: {error_text}"
    
    return output


def result_to_debug_text(result: Dict[str, Any]) -> str:
    """Format result with full technical details for debugging."""
    lines = []
    
    # Add intent parsing details
    if "intent_confidence" in result:
        lines.append(f"**Intent Confidence**: {result['intent_confidence']:.1%}")
    if "reasoning" in result:
        lines.append(f"**Intent Reasoning**: {result['reasoning']}")
    if "extracted_params" in result:
        lines.append(f"**Extracted Parameters**: {json.dumps(result['extracted_params'], indent=2)}")
    if "selected_flow" in result:
        lines.append(f"**Flow Selected**: {result['selected_flow']}")
    if "agents_executed" in result:
        lines.append(f"**Agents Executed**: {', '.join(result['agents_executed'])}")
    
    lines.append("---")
    lines.append(result.get("response", "No response"))
    
    if result.get("error"):
        lines.append(f"\n⚠️ **Error**: {result['error']}")
    
    if result.get("result"):
        lines.append("\n### Full Backend Data (Debug):")
        lines.append("```json")
        lines.append(json.dumps(result["result"], indent=2, default=str)[:10000])
        lines.append("```")
    
    return "\n".join(lines)


st.set_page_config(page_title="AutoApply AI Agent", page_icon="🤖", layout="wide")
st.title("🤖 AutoApply AI Agent")
st.caption("Ask natural questions - LLM decides which agents to call and how to respond")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hi! I'm your AutoApply AI assistant powered by intelligent LLM routing.\n\n"
                "I understand natural language and automatically route your requests to the right tools:\n\n"
                "**Job Management:**\n"
                "- 'fetch 3 jobs', 'find me 5 opportunities', 'search for AI engineer roles'\n"
                "- 'show me remote jobs', 'Python developer positions'\n\n"
                "**Resume & Applications:**\n"
                "- 'rewrite my resume', 'tailor my CV', 'prepare resume for tech roles'\n"
                "- 'apply on naukri', 'submit applications', 'apply to external companies'\n\n"
                "**Full Automation:**\n"
                "- 'run full pipeline', 'end to end automation', 'complete job search workflow'\n\n"
                "**General Questions:**\n"
                "- 'what is Python?', 'how to prepare for interviews?', 'best practices for resumes?'\n\n"
                "**SmartFeatures:**\n"
                "🧠 LLM intelligently parses your intent\n"
                "🔢 Extracts parameters from natural language (e.g., '1 job' → max_jobs=1)\n"
                "🔄 Calls multiple agents if needed\n"
                "📝 Formats responses based on context\n\n"
                "Try asking me something! 🚀"
            ),
        }
    ]

with st.sidebar:
    st.header("⚙️ Settings")
    backend_url = st.text_input("Backend URL", value="http://127.0.0.1:8000", key="backend_url")
    debug_mode = st.toggle("Debug Mode (Show Intent & Parameters)", value=False, help="See LLM intent parsing, extracted parameters, and full technical details")
    
    st.divider()
    st.markdown(
        """
        ### 📡 System Architecture
        
        **Frontend Smart Features:**
        - 🧠 LLM-based intent parsing
        - 🔢 Automatic parameter extraction
        - 🔄 Multi-agent orchestration
        - 📝 Context-aware response formatting
        
        **Supported Intents:**
        - `fetch_jobs` - Job discovery
        - `resume_rewrite` - Resume tailoring
        - `naukri_applier` - Naukri applications
        - `external_applier` - Direct company applications
        - `llm_only` - General questions
        
        ### 💡 How It Works
        1. You enter a natural language query
        2. LLM parses your intent
        3. LLM extracts parameters (like max_jobs)
        4. Appropriate agent(s) are called
        5. Response formatted & shown to you
        
        **No manual settings needed!** 🎯
        """
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Ask me anything... (e.g., 'fetch 3 jobs', 'rewrite resume', 'what is Python?')")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("🤖 Using LLM to understand your request..."):
            result = run_client_query(
                query=query,
                backend_url=backend_url,
                debug=debug_mode,
            )
            
            # Format response based on debug mode
            if debug_mode:
                answer = result_to_debug_text(result)
            else:
                answer = result_to_text(result)
            
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

