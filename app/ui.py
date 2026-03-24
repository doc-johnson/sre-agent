import json

import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="SRE Investigation Agent", layout="wide", page_icon="🔍")

st.markdown("""
<style>
    .stApp {
        background-color: #0a0e14;
        color: #b3b1ad;
    }
    header[data-testid="stHeader"] {
        background-color: #0a0e14;
    }
    section[data-testid="stSidebar"] {
        background-color: #0d1117;
        border-right: 1px solid #1a2332;
    }
    h1 {
        color: #39ff14 !important;
        font-family: 'Courier New', monospace !important;
    }
    h2, h3 {
        color: #4ecca3 !important;
    }
    .stChatInput > div {
        background-color: #1a2332 !important;
        border: 1px solid #2d4a3e !important;
    }
    .stChatInput textarea {
        color: #39ff14 !important;
    }
    div[data-testid="stExpander"] {
        background-color: #111921;
        border: 1px solid #1a2332;
        border-radius: 4px;
    }
    .stCodeBlock {
        background-color: #0d1117 !important;
    }
    div.stButton > button {
        background-color: #1a2332;
        color: #4ecca3;
        border: 1px solid #2d4a3e;
    }
    div.stButton > button:hover {
        background-color: #2d4a3e;
        color: #39ff14;
        border: 1px solid #39ff14;
    }
    .stSelectbox > div > div {
        background-color: #1a2332;
        color: #b3b1ad;
    }
    div[data-testid="stAlert"] {
        background-color: #1a2332;
    }
    .stDivider {
        border-color: #1a2332 !important;
    }
    .element-container .stCaption {
        color: #636e7b !important;
    }
</style>
""", unsafe_allow_html=True)

if "investigation_id" not in st.session_state:
    st.session_state.investigation_id = None
if "provider" not in st.session_state:
    st.session_state.provider = "groq"
if "model" not in st.session_state:
    st.session_state.model = None


def _fetch_providers() -> dict:
    try:
        return requests.get(f"{API_URL}/providers", timeout=5).json()
    except Exception:
        return {}


def _fetch_history() -> list:
    try:
        return requests.get(f"{API_URL}/history", timeout=5).json()
    except Exception:
        return []


providers = _fetch_providers()

with st.sidebar:
    st.header("Settings")

    provider = st.selectbox("Provider", list(providers.keys()) if providers else ["groq"])
    st.session_state.provider = provider

    if providers and provider in providers:
        models = providers[provider]["models"]
        default = providers[provider]["default_model"]
        model = st.selectbox("Model", models, index=models.index(default) if default in models else 0)
        st.session_state.model = model

    st.divider()
    st.header("History")

    history = _fetch_history()
    for inv in history:
        label = inv["alert"][:50]
        if st.button(label, key=f"inv_{inv['id']}", use_container_width=True):
            st.session_state.investigation_id = inv["id"]
            st.rerun()


st.title("> SRE Investigation Agent")
st.caption("$ investigate --mode=react --stream=sse")

alert = st.chat_input("Describe the alert (e.g., 'HTTP 500 error rate spiked on api-service')")

if alert:
    st.session_state.investigation_id = None

    with st.container():
        st.subheader(f"Investigating: {alert}")
        status_area = st.empty()
        content_area = st.container()

        try:
            resp = requests.post(
                f"{API_URL}/investigate",
                json={
                    "alert": alert,
                    "provider": st.session_state.provider,
                    "model": st.session_state.model,
                },
                stream=True,
                timeout=120,
            )

            thought_count = 0

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue

                data = json.loads(line[6:])
                event_type = data.get("type")

                if event_type == "thought":
                    thought_count += 1
                    with content_area:
                        with st.expander(f"Thought #{thought_count}", expanded=True):
                            st.markdown(data["content"])

                elif event_type == "tool_call":
                    with content_area:
                        args_str = json.dumps(data.get("arguments", {}), indent=2)
                        st.code(f"Tool: {data['tool']}\nArgs: {args_str}", language="json")

                elif event_type == "tool_result":
                    with content_area:
                        result = data.get("result", {})
                        with st.expander(f"Result: {data['tool']}", expanded=False):
                            st.json(result)

                elif event_type == "conclusion":
                    with content_area:
                        st.divider()
                        st.subheader("Conclusion")
                        st.markdown(data["content"])

                elif event_type == "error":
                    with content_area:
                        st.error(data.get("content", "Unknown error"))

                elif event_type == "done":
                    status_area.success("Investigation complete")

        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to agent API. Make sure the backend is running on port 8000.")
        except Exception as e:
            st.error(f"Error: {e}")

elif st.session_state.investigation_id:
    try:
        inv = requests.get(
            f"{API_URL}/investigations/{st.session_state.investigation_id}",
            timeout=5,
        ).json()

        st.subheader(f"Investigation: {inv['alert']}")
        st.caption(f"Date: {inv['created_at']}")

        for event_data in inv.get("events", []):
            event = event_data.get("data", event_data)
            event_type = event.get("type")

            if event_type == "thought":
                with st.expander("Thought", expanded=False):
                    st.markdown(event["content"])
            elif event_type == "tool_call":
                args_str = json.dumps(event.get("arguments", {}), indent=2)
                st.code(f"Tool: {event['tool']}\nArgs: {args_str}", language="json")
            elif event_type == "tool_result":
                with st.expander(f"Result: {event['tool']}", expanded=False):
                    st.json(event.get("result", {}))
            elif event_type == "conclusion":
                st.divider()
                st.subheader("Conclusion")
                st.markdown(event["content"])

    except Exception:
        st.error("Failed to load investigation")
else:
    st.info("Enter an alert description to start an investigation.")
