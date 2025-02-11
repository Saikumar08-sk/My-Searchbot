import os
from datetime import datetime
import streamlit as st
import pandas as pd
from helper import ChatBot, current_year, save_to_audio

# Only need GROQ API key now
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Front-end
st.set_page_config(layout="wide")
st.title("SearchBot 🤖")

# Front-end: Sidebar
with st.sidebar:
    with st.expander("Instruction Manual"):
        st.markdown(
            """
            ## SearchBot 🤖
            This Streamlit app allows you to search anything using DuckDuckGo search engine and Llama model.

            ### How to Use:
            1. **Number of Results**: Select number of results to display.
            2. **Response**: The app will display search results and an AI-generated response.
            3. **Chat History**: Previous conversations will be shown and can be cleared using "Clear Session" button.
            """
        )

    # Example queries
    st.success("Example: Latest news about AI technology")
    st.success("Example: Current weather in New York")
    st.success("Example: Top tech companies in 2024")

    # Input settings
    num_results = st.number_input(
        "Number of results to display", 
        value=7, 
        min_value=1,
        max_value=20,
        step=1
    )
    
    only_use_chatbot = st.checkbox("Only use AI (no search)")

    # Clear session button
    if st.button("Clear Session"):
        st.session_state.messages = []
        st.rerun()

    # Credit
    year = current_year()
    st.markdown(
        f"""
            <h6 style='text-align: left;'>Copyright © 2010-{year} Present Yiqiao Yin</h6>
        """,
        unsafe_allow_html=True,
    )

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Ensure messages are valid
if not isinstance(st.session_state.messages, list):
    st.session_state.messages = []
if not all(isinstance(msg, dict) for msg in st.session_state.messages):
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Only display the main response, not the references
        content = message["content"].split("\n\n")[0] if message["role"] == "assistant" else message["content"]
        st.markdown(content)

# Handle user input
if prompt := st.chat_input(
    "😉 Ask any question or try the examples from the sidebar"
):
    # Display user message
    st.chat_message("user").markdown(prompt)

    # Add to chat history
    st.session_state.messages.append(
        {
            "role": "system",
            "content": f"You are a helpful assistant. Current year is {year}",
        }
    )
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        with st.spinner("Searching..."):
            # Initialize chatbot
            bot = ChatBot()
            
            if only_use_chatbot:
                search_results = "<empty>"
                ref_table = pd.DataFrame()
            else:
                # Use DuckDuckGo search
                results = bot.search_engine.search(prompt, num_results)
                
                if isinstance(results, dict) and "data" in results:
                    search_results = results["data"]
                    
                    # Create a DataFrame for the references
                    ref_data = []
                    for idx, result in enumerate(search_results, 1):
                        ref_data.append({
                            'No.': idx,
                            'Title': result['title'],
                            'Summary': result['snippet'],
                            'URL': result['link'],
                            'Rating': result.get('rating', 'Not rated')
                        })
                    ref_table = pd.DataFrame(ref_data)
                else:
                    search_results = "<empty>"
                    ref_table = pd.DataFrame()

            # Generate AI response
            bot.history = st.session_state.messages.copy()
            
            response = bot.generate_response(
                f"""
                User question: {prompt}
                Search results: {search_results}

                Please provide a helpful response based on the search results.
                If search results are empty, use your knowledge to answer.
                Be concise but informative.
                """
            )

            # Save and display response
            if response:
                save_to_audio(response)

            with st.chat_message("assistant"):
                # Display only the main response
                st.markdown(response, unsafe_allow_html=True)
                st.audio("output.mp3", format="audio/mpeg", loop=True)
                
                # Display references in a table format
                with st.expander("References", expanded=False):
                    if not ref_table.empty:
                        st.dataframe(
                            ref_table,
                            column_config={
                                'No.': st.column_config.NumberColumn(width=50),
                                'Title': st.column_config.TextColumn(width=200),
                                'Summary': st.column_config.TextColumn(width=300),
                                'URL': st.column_config.LinkColumn(width=150),
                                'Rating': st.column_config.TextColumn(width=100)
                            },
                            hide_index=True
                        )
                    else:
                        st.write("No references available")

            # Add to chat history
            final_response = f"{response}\n\n{ref_table.to_string() if not ref_table.empty else 'No references available'}"
            st.session_state.messages.append(
                {"role": "assistant", "content": final_response}
            )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.session_state.messages.append(
            {"role": "assistant", "content": "Sorry, I encountered an error. Please try again."}
        )