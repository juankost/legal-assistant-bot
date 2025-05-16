import streamlit as st
from st_app import launch_bot
import uuid

import nest_asyncio
import asyncio

# Setup for HTTP API Calls to Amplitude Analytics
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())

if "feedback_key" not in st.session_state:
    st.session_state.feedback_key = 0

if __name__ == "__main__":
    st.set_page_config(page_title="Legal Assistant", layout="wide")
    nest_asyncio.apply()
    asyncio.run(launch_bot())
