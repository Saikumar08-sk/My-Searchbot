import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any
import streamlit as st
from gtts import gTTS
from helper import ChatBot, current_year, invoke_duckduckgo_news_search

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

def get_chat_response(prompt: str, context: str) -> str:
    """Get response from the chatbot."""
    chat_ai = ChatBot()
    chat_ai.history = st.session_state.messages.copy()
    return chat_ai.generate_response(f"User: {prompt}\nContext: {context}")

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
    st.set_page_config(layout="wide")
    st.title("SearchBot 🤖")
    display_searchbot_intro()
    
    user_settings = configure_sidebar()
    initialize_chat()
    show_chat_history()
    
    if user_input := st.chat_input("Ask a question..."):
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        search_results = fetch_search_results(user_input, user_settings)
        bot_response = get_chat_response(user_input, search_results)
        
        text_to_speech(bot_response)
        
        with st.chat_message("assistant"):
            st.markdown(bot_response, unsafe_allow_html=True)
            st.audio("output.mp3", format="audio/mpeg", loop=True)
            with st.expander("📚 References:", expanded=True):
                st.markdown(search_results, unsafe_allow_html=True)
        
        st.session_state.messages.append({"role": "assistant", "content": f"{bot_response}\n\n{search_results}"})

if __name__ == "__main__":
    run_app()

# ============================ END OF FILE ============================
