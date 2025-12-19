import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any
import streamlit as st
from gtts import gTTS
from helper import ChatBot, current_year, invoke_duckduckgo_news_search
import time
import streamlit as st
import asyncio
import inspect
def resolve_maybe_async(value):
    """If value is a coroutine, run it and return the real result."""
    if inspect.iscoroutine(value):
        return asyncio.run(value)
    return value

# ----------------------------
# OPT 1: Real-time search + TTL cache
# ----------------------------
_SEARCH_CACHE = {}  # { query: (timestamp, results) }
SEARCH_TTL_SEC = 60  # cache window (adjust 30–120 as needed)

def get_search_results_realtime(query: str):
    """Fetch fresh search results, but cache briefly to reduce repeated calls."""
    q = (query or "").strip()
    if not q:
        return []

    now = time.time()

    if q in _SEARCH_CACHE:
        ts, results = _SEARCH_CACHE[q]
        if (now - ts) < SEARCH_TTL_SEC:
            return results

    # Use your existing search function
    results = invoke_duckduckgo_news_search(q)

    _SEARCH_CACHE[q] = (now, results)
    return results


# ----------------------------
# OPT 2: Stream output (typing / incremental display)
# ----------------------------
def stream_markdown(text: str, delay: float = 0.008):
    """Stream text to the UI for a 'real-time' typing effect."""
    placeholder = st.empty()
    out = ""
    for ch in text:
        out += ch
        placeholder.markdown(out)
        time.sleep(delay)
    return out  # optional

# ============================ UTILITY FUNCTIONS ============================

def text_to_speech(text: str, filename: str = "output.mp3"):
    """Convert text to speech and save it as an audio file."""
    try:
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        st.success("✅ Audio response generated successfully!")
    except Exception as e:
        st.warning(f"⚠️ Error generating audio: {e}")

def configure_sidebar() -> Dict[str, Any]:
    """Configure the sidebar and return user input values."""
    with st.sidebar:
        st.header("🔧 SearchBot Settings")
        st.markdown("Configure your search and chatbot preferences below.")
        num_results = st.number_input("🔍 Number of results", min_value=1, max_value=10, value=5)
        region = st.text_input("🌎 Location Code (e.g., us-en, in-en)", value="us-en")
        time_range = st.selectbox("⏳ Time Range", ["Past Day", "Past Week", "Past Month", "Past Year"], index=1)
        only_chatbot = st.checkbox("💬 Use Chatbot Only (No Search)")
        
        time_mapping = {"Past Day": "d", "Past Week": "w", "Past Month": "m", "Past Year": "y"}
        time_filter = time_mapping[time_range]
        
        if st.button("🧹 Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
        
        return {"num": num_results, "location": region, "time_filter": time_filter, "only_chatbot": only_chatbot}

def initialize_chat():
    """Ensure chat history is initialized properly."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    st.info("💬 Chat history initialized.")

def show_chat_history():
    """Display existing chat history."""
    if not st.session_state.messages:
        st.info("📝 No chat history available.")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

def fetch_search_results(query: str, settings: Dict[str, Any]) -> str:
    """Fetch news articles based on the search query."""
    search_summary = "**No search results available.**"
    
    try:
        with st.spinner("🔎 Searching for news articles..."):
            if settings["only_chatbot"]:
                return "No search performed."
            
            results = asyncio.run(
                invoke_duckduckgo_news_search(query=query, location=settings["location"], num=settings["num"], time_filter=settings["time_filter"])
            )
            
            if results["status"] == "success":
                search_summary = format_results(results["results"])
                return search_summary
    except Exception as err:
        st.error(f"❌ Search error: {err}")
    
    return search_summary

def format_results(results: List[Dict[str, Any]]) -> str:
    """Format search results into a Markdown table."""
    table_md = "| # | Title | Summary |\n|---|------|---------|\n"
    for index, res in enumerate(results, start=1):
        title = f"[{res['title']}]({res['link']})" if res.get('link', '').startswith("http") else res['title']
        summary = res.get('summary', '')[:100] + "..." if len(res.get('summary', '')) > 100 else res.get('summary', '')
        table_md += f"| {index} | {title} | {summary} |\n"
    return table_md

import asyncio
import inspect

def get_chat_response(user_input, search_results):
    """
    Robust response builder:
    - Accepts search_results as string/HTML or coroutine
    - Never returns 'No search results available.' as the assistant response
    - Works even if ChatBot uses different method names
    """

    # --- Resolve async search_results if needed ---
    if inspect.iscoroutine(search_results):
        search_results = asyncio.run(search_results)

    # --- Normalize context ---
    ctx = "" if search_results is None else str(search_results).strip()
    if "no search results available" in ctx.lower():
        ctx = ""  # treat placeholder as empty context

    # --- Build response using ChatBot, regardless of method name ---
    chat_ai = ChatBot()

    # Try common method names (your repo may use any one of these)
    candidate_methods = ["respond", "get_response", "generate_response", "chat", "run", "invoke"]

    resp = None
    last_err = None

    for m in candidate_methods:
        if hasattr(chat_ai, m):
            try:
                fn = getattr(chat_ai, m)

                # Some implementations accept (user_input, ctx), some only (user_input)
                try:
                    resp = fn(user_input, ctx)
                except TypeError:
                    resp = fn(user_input)

                if inspect.iscoroutine(resp):
                    resp = asyncio.run(resp)

                break
            except Exception as e:
                last_err = e
                resp = None

    # If none of the methods worked, fallback
    if resp is None:
        return "I can help—please ask a specific question (example: 'weather in Hyderabad today', 'latest Apple news')."

    resp = str(resp).strip()

    # --- HARD GUARDS: never show placeholder as the assistant answer ---
    if not resp or "no search results available" in resp.lower():
        return "I can help—please ask a specific question (example: 'weather in Hyderabad today', 'latest Apple news')."

    # Optional: remove template wrapper if your bot returns it
    if "AI Response to:" in resp and "Context:" in resp:
        # Keep only the content after Context:
        resp = resp.split("Context:", 1)[-1].strip()
        if not resp:
            return "I can help—please ask a specific question (example: 'weather in Hyderabad today', 'latest Apple news')."

    return resp

def display_searchbot_intro():
    """Display an introduction message for the chatbot."""
    st.markdown(
        """
        ## 🤖 Welcome to SearchBot!
        - **Ask about latest news and research** 📡
        - **Get summarized insights** 🔍
        - **Listen to AI-generated audio responses** 🎧
        - **Filter results based on time and location** 🌍
        """
    )

def run_app():
    """Run the Streamlit SearchBot app."""
    import os
    import asyncio
    import inspect

    def resolve_maybe_async(value):
        if inspect.iscoroutine(value):
            return asyncio.run(value)
        return value

    def is_placeholder_no_results(text):
        t = "" if text is None else str(text).strip().lower()
        return (t == "") or ("no search results available" in t)

    st.set_page_config(layout="wide")
    st.title("SearchBot 🤖")
    display_searchbot_intro()

    user_settings = configure_sidebar()
    initialize_chat()
    show_chat_history()

    user_input = st.chat_input("Ask a question...")

    if user_input:
        # User message
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Search
        with st.spinner("Searching the web..."):
            search_results = fetch_search_results(user_input, user_settings)
            search_results = resolve_maybe_async(search_results)

        search_results_str = "" if search_results is None else str(search_results)
        if is_placeholder_no_results(search_results_str):
            search_results_str = ""

        # Assistant (REAL-TIME STREAM)
        with st.chat_message("assistant"):
            final_answer = st.write_stream(
                ChatBot().stream_answer(user_input, search_results_str)
            )

            # Generate TTS AFTER we have final_answer
            try:
                text_to_speech(final_answer)
            except Exception:
                pass

            # ✅ SAFE AUDIO: only play if file exists + non-empty
            audio_path = "output.mp3"
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                st.audio(audio_path, format="audio/mpeg", loop=True)
            else:
                st.caption("🔇 Audio not available for this response.")

            # References (only if real)
            if search_results_str.strip():
                with st.expander("📚 References:", expanded=True):
                    st.markdown(search_results_str, unsafe_allow_html=True)

        # Save history
        st.session_state.messages.append(
            {"role": "assistant", "content": f"{final_answer}\n\n{search_results_str}".strip()}
        )

if __name__ == "__main__":
    run_app()

# ============================ END OF FILE ============================
