import streamlit as st
import sys
from pathlib import Path

# ---------------------------------------
# Add Project Root
# ---------------------------------------

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rag.rag_pipeline import RAGPipeline

# ---------------------------------------
# Page Configuration
# ---------------------------------------

st.set_page_config(
    page_title="Indian Legal Assistant",
    page_icon="⚖️",
    layout="centered",
)

# ---------------------------------------
# Load CSS
# ---------------------------------------

with open("frontend/styles.css") as f:
    st.markdown(
        f"<style>{f.read()}</style>",
        unsafe_allow_html=True,
    )

# ---------------------------------------
# Load RAG Pipeline
# ---------------------------------------

@st.cache_resource
def load_pipeline():
    return RAGPipeline()


rag = load_pipeline()

# ---------------------------------------
# Header
# ---------------------------------------

st.markdown(
    """
    <div class="title">
        Indian Legal Assistant
    </div>

    <div class="subtitle">
        Search Indian legal judgments using Retrieval-Augmented Generation powered by Gemini and ChromaDB.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------
# Question Input
# ---------------------------------------

question = st.text_area(
    "",
    placeholder="Ask anything about Indian legal judgments...",
    height=150,
    label_visibility="collapsed",
)

# ---------------------------------------
# Ask Button
# ---------------------------------------

search = st.button(
    "Ask Question",
    use_container_width=True,
)

# ---------------------------------------
# Search
# ---------------------------------------

if search:

    if not question.strip():

        st.warning("Please enter a legal question.")

    else:

        with st.spinner("Searching legal judgments..."):

            response = rag.ask(question)

        # ---------------------------------------
        # Answer
        # ---------------------------------------

        st.divider()

        st.markdown(
            """
            <div class="section-title">
                Answer
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(response["answer"])

        # ---------------------------------------
        # Sources
        # ---------------------------------------

        st.divider()

        st.markdown(
            """
            <div class="section-title">
                Source Cases
            </div>
            """,
            unsafe_allow_html=True,
        )

        for source in response["sources"]:

            st.markdown(
                f"""
                <div class="source-card">

                <h4 style="margin-top:0;">
                    {source["case_title"]}
                </h4>

                <b>Court:</b> {source["court"]}<br>

                <b>Date:</b> {source["date"]}<br>

                <b>Document ID:</b> {source["document_id"]}<br>

                <b>Chunk ID:</b> {source["chunk_id"]}

                </div>
                """,
                unsafe_allow_html=True,
            )