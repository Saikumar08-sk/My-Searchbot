import os
import streamlit as st

from helper import ChatBot, current_year

# ----------------------------
# UI helpers
# ----------------------------
def display_intro():
    st.caption(f"SearchBot (Q&A + Memory + Answer Modes) • {current_year()}")

def configure_sidebar() -> dict:
    st.sidebar.header("Settings")

    mode = st.sidebar.selectbox(
        "Answer mode",
        ["Short", "Detailed", "Bullet points", "Explain like I'm 5", "Interview answer"],
        index=0
    )

    memory_turns = st.sidebar.slider("Memory (last N messages)", 2, 20, 10)
    enable_tts = st.sidebar.checkbox("Enable speech (TTS)", value=True)

    st.sidebar.divider()
    st.sidebar.subheader("Quick Questions")
    quick = st.sidebar.radio(
        "Pick one",
        [
            "Explain K-Means in simple terms.",
            "What is the difference between Ridge and Lasso?",
            "Give me interview answer: Why do you want this role?",
            "Summarize overfitting vs underfitting.",
        ],
        index=0
    )
    ask_quick = st.sidebar.button("Ask selected question")

    return {
        "mode": mode,
        "memory_turns": memory_turns,
        "enable_tts": enable_tts,
        "quick_question": quick,
        "ask_quick": ask_quick,
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
# TTS (safe)
# ----------------------------
def text_to_speech(text: str, out_path: str = "output.mp3") -> bool:
    """
    Generates output.mp3 using gTTS if available.
    Returns True if created successfully, else False.
    """
    try:
        from gtts import gTTS
        tts = gTTS(text=text)
        tts.save(out_path)
        return True
    except Exception:
        return False

# ----------------------------
# Memory helper
# ----------------------------
def get_memory_slice(messages, last_n: int):
    """
    Return last_n messages (user+assistant) for context.
    """
    if not messages:
        return []
    return messages[-last_n:]

# ----------------------------
# Main
# ----------------------------
def run_app():
    st.set_page_config(layout="wide", page_title="SearchBot")
    st.title("SearchBot 🤖")
    display_intro()

    settings = configure_sidebar()
    initialize_chat()
    show_chat_history()

    # If user clicks sidebar quick question, prefill it
    prefill = settings["quick_question"] if settings["ask_quick"] else ""

    user_input = st.chat_input("Ask a question...")
    if not user_input and prefill:
        user_input = prefill

    if not user_input:
        return

    # --- Show user message + store
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # --- Build memory slice for the model (A: conversation memory)
    memory = get_memory_slice(st.session_state.messages, settings["memory_turns"])

    # --- Generate answer (B: answer modes)
    bot = ChatBot()
    answer = bot.generate_response(
        user_input=user_input,
        history=memory,
        mode=settings["mode"],
        extra_context=""  # keep empty (no search)
    )

    # --- Show assistant answer + store
    with st.chat_message("assistant"):
        st.markdown(answer, unsafe_allow_html=True)

        # Speech
        if settings["enable_tts"]:
            ok = text_to_speech(answer, out_path="output.mp3")
            audio_path = "output.mp3"
            if ok and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                st.audio(audio_path, format="audio/mpeg", loop=False)
            else:
                st.caption("Audio not available.")

    st.session_state.messages.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    run_app()
