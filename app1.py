# app.py
import os
import streamlit as st

from helper import (
    ChatBot,
    current_year,
    invoke_duckduckgo_news_search,
    format_news_results_html,
)

# ----------------------------
# Sidebar + UI helpers
# ----------------------------
def display_searchbot_intro():
    st.caption(f"Live Search + Real-time AI Streaming • {current_year()}")

def configure_sidebar() -> dict:
    st.sidebar.header("Settings")
    num_results = st.sidebar.slider("News results", 1, 10, 5)
    location = st.sidebar.selectbox("Region", ["us-en", "in-en", "uk-en", "ca-en"], index=0)
    time_filter = st.sidebar.selectbox("Time filter", ["d", "w", "m", "y"], index=1)
    show_refs = st.sidebar.checkbox("Show references", value=True)
    enable_tts = st.sidebar.checkbox("Enable audio (TTS)", value=False)
    return {
        "num_results": num_results,
        "location": location,
        "time_filter": time_filter,
        "show_refs": show_refs,
        "enable_tts": enable_tts,
    }

def initialize_chat():
    if "messages" not in st.session_state:
        st.session_state.messages = []

def show_chat_history():
    for msg in st.session_state.messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.markdown(content, unsafe_allow_html=True)

# ----------------------------
# Search (SYNC) – no asyncio here
# ----------------------------
def fetch_search_results(user_input: str, user_settings: dict) -> str:
    """
    Returns HTML string for references. Never returns a coroutine.
    If DuckDuckGo fails or returns no results, returns "".
    """
    payload = invoke_duckduckgo_news_search(
        query=user_input,
        num=int(user_settings.get("num_results", 5)),
        location=user_settings.get("location", "us-en"),
        time_filter=user_settings.get("time_filter", "w"),
    )

    if payload.get("status") != "success":
        # Do NOT propagate placeholders into the UI or model context
        return ""

    return format_news_results_html(payload)

# ----------------------------
# TTS (optional, safe)
# ----------------------------
def text_to_speech(text: str, out_path: str = "output.mp3") -> bool:
    """
    Optional TTS. If gTTS isn't installed or fails, return False safely.
    """
    try:
        from gtts import gTTS  # requires gTTS in requirements.txt
        tts = gTTS(text=text)
        tts.save(out_path)
        return True
    except Exception:
        return False

# ----------------------------
# Main app
# ----------------------------
def run_app():
    st.set_page_config(layout="wide", page_title="SearchBot")
    st.title("SearchBot 🤖")
    display_searchbot_intro()

    user_settings = configure_sidebar()
    initialize_chat()
    show_chat_history()

    user_input = st.chat_input("Ask a question...")

    if not user_input:
        return

    # ---- User message
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # ---- Search (SYNC; returns HTML or "")
    with st.spinner("Searching the web..."):
        search_results_html = fetch_search_results(user_input, user_settings)

    # IMPORTANT: context passed to the LLM must be a STRING (not dict/coroutine)
    context_for_llm = search_results_html or ""

    # ---- Assistant (TRUE real-time streaming from OpenAI)
    bot = ChatBot()
    with st.chat_message("assistant"):
        try:
            final_answer = st.write_stream(
                bot.stream_answer(user_input, context_for_llm)
            )
        except Exception:
            # Fallback to non-stream if anything goes wrong
            final_answer = bot.generate_response(user_input, context_for_llm)
            st.markdown(final_answer, unsafe_allow_html=True)

        # ---- Audio (optional; never crash if file missing)
        if user_settings.get("enable_tts"):
            ok = text_to_speech(final_answer)
            audio_path = "output.mp3"
            if ok and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                st.audio(audio_path, format="audio/mpeg", loop=False)
            else:
                st.caption("Audio not available.")

        # ---- References (only if real)
        if user_settings.get("show_refs") and search_results_html.strip():
            with st.expander("📚 References", expanded=True):
                st.markdown(search_results_html, unsafe_allow_html=True)

    # ---- Save history
    combined = final_answer
    if search_results_html.strip():
        combined = f"{final_answer}\n\n---\n\n{search_results_html}"
    st.session_state.messages.append({"role": "assistant", "content": combined})


# Streamlit runs the script top-to-bottom; this is still fine:
if __name__ == "__main__":
    run_app()
