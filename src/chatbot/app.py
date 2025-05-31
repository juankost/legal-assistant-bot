import os
import sys
import gc
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(ROOT_DIR, "src"))

import streamlit as st
from chatbot.agent import SAGAFTRAAgent, ALL_MODELS

# Page configuration
st.set_page_config(page_title="SAG-AFTRA Agreement Assistant", page_icon="📜", layout="wide")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "current_model" not in st.session_state:
    st.session_state.current_model = None

# UI Layout
st.title("📜 SAG-AFTRA Agreement Assistant")
st.markdown("Ask questions about SAG-AFTRA agreements with temporal awareness")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")

    # Model selection
    pretty_model_name = st.selectbox(
        "Select Model", ["Claude 4.0 Sonnet", "Gemini 2.5 Pro", "OpenAI GPT-4.1"]
    )

    # Check if model has changed
    if st.session_state.current_model != pretty_model_name:
        st.session_state.current_model = pretty_model_name
        if (
            st.session_state.agent is not None
            and hasattr(st.session_state.agent, "retrieval_tool")
            and st.session_state.agent.retrieval_tool is not None
            and hasattr(st.session_state.agent.retrieval_tool, "db")
            and st.session_state.agent.retrieval_tool.db is not None
            and hasattr(st.session_state.agent.retrieval_tool.db, "client")
        ):
            st.session_state.agent.retrieval_tool.db.client.close()
            del st.session_state.agent.retrieval_tool.db.client  # Ensure client is removed
            del st.session_state.agent.retrieval_tool.db  # Ensure db is removed
            del st.session_state.agent.retrieval_tool  # Ensure retrieval_tool is removed
        st.session_state.agent = None  # Reset agent when model changes
        # TODO: Problem: Qdrant DB is already being used by the agent, so we need to explicitly close it when the model changes
        gc.collect()

    # Date context helper
    st.subheader("Temporal Context")
    use_specific_date = st.checkbox("Search for specific date")
    search_date = None
    if use_specific_date:
        search_date = st.date_input("Select date", datetime.now())
        st.info(f"Searching for agreements valid on: {search_date}")

    # Example questions
    st.subheader("Example Questions")
    examples = [
        "What were the minimum wage requirements in 2018?",
        "How have overtime rules changed since 2015?",
        "What are the current meal penalty provisions?",
        "Show me pension contribution rates valid in January 2020",
    ]

    for example in examples:
        if st.button(example, key=f"ex_{examples.index(example)}"):
            st.session_state.messages.append({"role": "user", "content": example})
            st.rerun()

# Initialize agent if not already done or if model changed
if st.session_state.agent is None:
    qdrant_path = os.path.join(ROOT_DIR, "data", "qdrant_db")
    try:
        st.session_state.agent = SAGAFTRAAgent(
            qdrant_path=qdrant_path, pretty_model_name=pretty_model_name
        )
        st.session_state.agent_initialized = True
        st.success(f"Agent initialized with {pretty_model_name}")
    except Exception as e:
        st.error(f"Failed to initialize agent: {str(e)}")
        st.session_state.agent_initialized = False

# Check if agent is initialized
if not st.session_state.get("agent_initialized", False):
    st.error("Agent not initialized. Please check the error message above.")
    st.stop()
else:
    st.success("Agent initialized successfully")

# Main chat interface
chat_container = st.container()

with chat_container:
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about SAG-AFTRA agreements..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching agreements..."):
                try:
                    # Add date context if specified
                    if use_specific_date and search_date:
                        prompt += f" (as of {search_date})"

                    # Get agent response
                    response = st.session_state.agent.answer(prompt)

                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Error processing query: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Footer
st.markdown("---")
st.caption("This assistant uses temporal filtering to search through SAG-AFTRA agreement history.")
st.caption("Powered by smolagents and Qdrant vector database.")
