import json
from typing import Any, Dict
from uuid import uuid4

import httpx
import streamlit as st


def run_client_query(
    query: str,
    backend_url: str,
    debug: bool = False,
    session_id: str = "default",
) -> Dict[str, Any]:
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
            json={"query": query, "session_id": session_id},
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
        output += f"\n\nError: {error_text}"
    
    return output


def result_to_debug_text(result: Dict[str, Any]) -> str:
    """Show full backend response JSON in debug mode."""
    payload = json.dumps(result, indent=2, default=str)[:15000]
    return f"```json\n{payload}\n```"


st.set_page_config(page_title="AutoApply Chatbot", layout="centered")
st.title("AutoApply Chatbot")
st.caption("Simple chat UI for AutoApply backend with one-turn memory")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi. Ask anything related to jobs, resume rewriting, or applications. "
                "Use Debug Mode if you want technical details."
            ),
        }
    ]

if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = str(uuid4())

with st.sidebar:
    debug_mode = st.toggle("Debug Mode", value=False)

backend_url = "http://127.0.0.1:8000"

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Ask me anything...")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            result = run_client_query(
                query=query,
                backend_url=backend_url,
                debug=debug_mode,
                session_id=st.session_state.chat_session_id,
            )
            if debug_mode:
                answer = result_to_debug_text(result)
            else:
                answer = result_to_text(result)
            
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

