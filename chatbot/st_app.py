from PIL import Image
import sys
import re

import streamlit as st
from streamlit_pills import pills
from streamlit_feedback import streamlit_feedback

from utils import thumbs_feedback, escape_dollars_outside_latex, send_amplitude_data

from vectara_agentic.agent import AgentStatusType
from agent import initialize_agent, get_agent_config

initial_prompt = "How can I help you today?"


def format_log_msg(log_msg: str):
    max_log_msg_size = 500
    return log_msg if len(log_msg) <= max_log_msg_size else log_msg[:max_log_msg_size] + "..."


def agent_progress_callback(status_type: AgentStatusType, msg: str):
    output = f'<span style="color:blue;">{status_type.value}</span>: {msg}'
    st.session_state.log_messages.append(output)
    if "status" in st.session_state:
        latest_message = ""
        if status_type == AgentStatusType.TOOL_CALL:
            match = re.search(r"'([^']*)'", msg)
            tool_name = match.group(1) if match else "Unknown tool"
            latest_message = f"Calling tool {tool_name}..."
        elif status_type == AgentStatusType.TOOL_OUTPUT:
            latest_message = "Analyzing tool output..."
        elif status_type == AgentStatusType.AGENT_UPDATE:
            if "Thought:" in msg:
                latest_message = "Thinking..."
            else:
                latest_message = "Updating agent..."
        else:
            print(f"callback with {status_type} and {msg}")
            return

        st.session_state.status.update(label=latest_message)

        with st.session_state.status:
            for log_msg in st.session_state.log_messages:
                st.markdown(format_log_msg(log_msg), unsafe_allow_html=True)


def show_example_questions():
    if len(st.session_state.example_messages) > 0 and st.session_state.first_turn:
        selected_example = pills("Queries to Try:", st.session_state.example_messages, index=None)
        if selected_example:
            st.session_state.ex_prompt = selected_example
            st.session_state.first_turn = False
            return True
    return False


@st.dialog(title="Agent logs", width="large")
def show_modal():
    for log_msg in st.session_state.log_messages:
        st.markdown(format_log_msg(log_msg), unsafe_allow_html=True)


async def launch_bot():
    def reset():
        st.session_state.messages = [
            {"role": "assistant", "content": initial_prompt, "avatar": "🦖"}
        ]
        st.session_state.log_messages = []
        st.session_state.prompt = None
        st.session_state.ex_prompt = None
        st.session_state.first_turn = True
        st.session_state.show_logs = False
        if "agent" not in st.session_state:
            st.session_state.agent = initialize_agent(
                cfg, agent_progress_callback=agent_progress_callback
            )
        else:
            st.session_state.agent.clear_memory()

    if "cfg" not in st.session_state:
        cfg = get_agent_config()
        st.session_state.cfg = cfg
        st.session_state.ex_prompt = None
        example_messages = (
            [example.strip() for example in cfg.examples.split(";")] if cfg.examples else []
        )
        st.session_state.example_messages = [em for em in example_messages if len(em) > 0]
        reset()

    cfg = st.session_state.cfg

    # left side content
    with st.sidebar:
        image = Image.open("Vectara-logo.png")
        st.image(image, width=175)
        st.markdown(f"## {cfg['demo_welcome']}")
        st.markdown(f"{cfg['demo_description']}")

        st.markdown("\n\n")
        bc1, bc2 = st.columns([1, 1])
        with bc1:
            if st.button("Start Over"):
                reset()
                st.rerun()
        with bc2:
            if st.button("Show Logs"):
                show_modal()

        st.divider()
        st.markdown(
            "## How this works?\n"
            "This app was built with [Vectara](https://vectara.com).\n\n"
            "It demonstrates the use of Agentic RAG functionality with Vectara"
        )

    if "messages" not in st.session_state.keys():
        reset()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=message["avatar"]):
            st.write(message["content"])

    example_container = st.empty()
    with example_container:
        if show_example_questions():
            example_container.empty()
            st.session_state.first_turn = False
            st.rerun()

    # User-provided prompt
    if st.session_state.ex_prompt:
        prompt = st.session_state.ex_prompt
    else:
        prompt = st.chat_input()
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt, "avatar": "🧑‍💻"})
        st.session_state.prompt = prompt
        st.session_state.log_messages = []
        st.session_state.show_logs = False
        with st.chat_message("user", avatar="🧑‍💻"):
            print(f"Starting new question: {prompt}\n")
            st.write(prompt)
        st.session_state.ex_prompt = None

    # Generate a new response if last message is not from assistant
    if st.session_state.prompt:
        with st.chat_message("assistant", avatar="🤖"):
            st.session_state.status = st.status("Processing...", expanded=False)
            response = st.session_state.agent.chat(st.session_state.prompt)
            res = escape_dollars_outside_latex(response.response)
            message = {"role": "assistant", "content": res, "avatar": "🤖"}
            st.session_state.messages.append(message)
            st.markdown(res)

        send_amplitude_data(
            user_query=st.session_state.messages[-2]["content"],
            bot_response=st.session_state.messages[-1]["content"],
            demo_name=cfg["demo_name"],
        )

        st.session_state.ex_prompt = None
        st.session_state.prompt = None
        st.session_state.first_turn = False
        st.rerun()

    # Record user feedback
    if (st.session_state.messages[-1]["role"] == "assistant") & (
        st.session_state.messages[-1]["content"] != initial_prompt
    ):
        if "feedback_key" not in st.session_state:
            st.session_state.feedback_key = 0
        streamlit_feedback(
            feedback_type="thumbs",
            on_submit=thumbs_feedback,
            key=str(st.session_state.feedback_key),
            kwargs={
                "user_query": st.session_state.messages[-2]["content"],
                "bot_response": st.session_state.messages[-1]["content"],
                "demo_name": cfg["demo_name"],
            },
        )

    sys.stdout.flush()
