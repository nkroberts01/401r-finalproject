import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_INGEST_URL = os.getenv("API_INGEST_URL")  # deployed AWS Lambda ingest URL
API_QUERY_URL = os.getenv("API_QUERY_URL")    # deployed AWS Lambda query URL

st.title("🌐 Doc-er")

# Session state for chat messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Session state for current URL
if "url" not in st.session_state:
    st.session_state.url = ""

# Step 1: Enter URL
st.subheader("1. Ingest Documentation URL")
url_input = st.text_input("Enter a documentation URL", value=st.session_state.url)
if st.button("Ingest URL"):
    if url_input:
        with st.spinner("Ingesting and indexing the webpage..."):
            try:
                response = requests.post(API_INGEST_URL, json={"url": url_input})
                data = response.json()
                if response.status_code == 200 and data.get("success"):
                    st.success("✅ URL successfully ingested!")
                    st.session_state.url = url_input
                else:
                    st.error(f"Failed to ingest URL: {data}")
            except Exception as e:
                st.error(f"Request error: {e}")
    else:
        st.warning("Please enter a URL.")

# Step 2: Ask a question
if st.session_state.url:
    st.subheader("2. Ask a Question")
    prompt = st.chat_input("Ask a question about the documentation")

    if prompt:
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Add to session history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Call backend query endpoint
        with st.spinner("Searching and generating answer..."):
            try:
                response = requests.post(API_QUERY_URL, json={
                    "query": prompt,
                    "url": st.session_state.url
                })
                data = response.json()
                answer = data.get("answer", "No answer returned.")

                with st.chat_message("assistant"):
                    st.markdown(answer)

                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Error during query: {e}")