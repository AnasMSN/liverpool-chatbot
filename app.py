"""
Streamlit front-end for the Liverpool FC RAG chatbot.

Run with:  streamlit run app.py
"""

import streamlit as st
from rag.query_engine import RAGEngine
from rag.web_search import web_search_status

st.set_page_config(page_title="Liverpool FC Chatbot", page_icon="⚽", layout="centered")

st.title("⚽ Liverpool FC Chatbot")
st.caption("Ask about Liverpool's history, players, and recent results — answered from a local RAG pipeline.")

with st.sidebar:
    st.subheader("Web search")
    status = web_search_status()
    if not status["configured"] or not status["enabled"]:
        st.caption("Off — set WEB_SEARCH_ENABLED=true and TAVILY_API_KEY in .env to enable.")
    elif status["exceeded"]:
        st.warning(
            f"Monthly quota reached ({status['used']}/{status['limit']} searches). "
            "Answering from local data only until it resets next month."
        )
    else:
        st.caption(f"{status['used']} / {status['limit']} searches used this month")
        st.progress(min(status["used"] / status["limit"], 1.0))


@st.cache_resource
def load_engine() -> RAGEngine:
    return RAGEngine()


engine = load_engine()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Ask something about Liverpool FC...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # keep only the last few turns as history to stay within context
            history = st.session_state.messages[-6:-1]
            result = engine.answer(question, history=history)

            st.markdown(result["answer"])
            if result["sources"]:
                with st.expander("Sources"):
                    for src in result["sources"]:
                        st.markdown(f"- {src}")

    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
