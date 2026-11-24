import html
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

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
    page_title="Nyaya Research · Indian Case-Law Assistant",
    page_icon="⚖️",
    layout="wide",
)

css = (project_root / "frontend" / "styles.css").read_text(encoding="utf-8")
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ---------------------------------------
# Cached resources
# ---------------------------------------


@st.cache_resource(show_spinner="Loading models and legal corpus...")
def load_pipeline():
    return RAGPipeline()


@st.cache_data(show_spinner=False)
def corpus_info():
    """Courts, year range and counts from the vector store metadata."""
    store = rag.retriever.vector_db
    metas = store.collection.get(include=["metadatas"])["metadatas"]
    courts = sorted({m["court"] for m in metas if m.get("court")})
    docs = {m["document_id"] for m in metas}
    years = [
        int(y.group())
        for m in metas
        if (y := re.search(r"(?:19|20)\d{2}", m.get("date", "") or ""))
    ]
    return courts, len(docs), len(metas), (min(years), max(years)) if years else (1950, 2025)


rag = load_pipeline()
courts_all, n_docs, n_chunks, (y_min, y_max) = corpus_info()

# ---------------------------------------
# Session state
# ---------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = None

# ---------------------------------------
# Sidebar
# ---------------------------------------

with st.sidebar:
    st.markdown(
        '<div class="side-brand">⚖ Nyaya Research</div>'
        '<div class="side-sub">Citation-backed Indian case-law assistant</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="stat-row"><div class="stat"><b>{n_docs:,}</b><span>Judgments</span></div>'
        f'<div class="stat"><b>{n_chunks:,}</b><span>Passages</span></div></div>',
        unsafe_allow_html=True,
    )

    mode_label = st.radio(
        "I am a...",
        ["Lawyer / Researcher", "Law Student"],
        help="Lawyers get an Issue-Rule-Analysis memo with caveats. "
        "Students get a plain-language explanation with key terms and exam pointers.",
    )
    mode = "lawyer" if mode_label.startswith("Lawyer") else "student"

    st.markdown("##### Filters")
    sel_courts = st.multiselect("Court", courts_all, placeholder="All courts")
    year_range = st.slider("Year", y_min, y_max, (y_min, y_max))
    top_k = st.slider("Passages to analyse", 3, 10, 5)

    if st.button("🗑  New research session", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ---------------------------------------
# Helpers
# ---------------------------------------


def render_answer(text):
    """Turn [S1] tags into styled citation badges."""
    text = re.sub(r"\[S(\d+)\]", r'<sup class="cite">[\1]</sup>', text)
    st.markdown(f'<div class="answer-card">\n\n{text}\n\n</div>', unsafe_allow_html=True)


def render_sources(sources):
    if not sources:
        return
    cited = [s for s in sources if s.get("cited")]
    st.markdown(f"**Authorities** · {len(cited)} cited · {len(sources)} retrieved")

    for s in sorted(sources, key=lambda x: (not x.get("cited"), x["number"])):
        pct = int((s.get("relevance") or 0) * 100)
        badge = (
            '<span class="badge green">Cited in answer</span>'
            if s.get("cited")
            else '<span class="badge amber">Retrieved, not cited</span>'
        )
        st.markdown(
            f"""
            <div class="src-card {'' if s.get('cited') else 'uncited'}">
              <div class="src-title"><span class="src-num">{s['number']}</span>{html.escape(s['case_title'])}</div>
              <div class="src-meta">{html.escape(s['court'])} · {html.escape(s['date'])} · ID {s['document_id']}</div>
              {badge}
              <span class="badge">relevance {pct}%</span>
              <span class="meter"><div style="width:{pct}%"></div></span>
              &nbsp;&nbsp;<a href="{s['url']}" target="_blank">Read full judgment ↗</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Show supporting passage(s)"):
            for ex in s["excerpts"]:
                st.markdown(
                    f'<div class="excerpt">{html.escape(ex.strip())}</div>',
                    unsafe_allow_html=True,
                )


def build_memo(turn):
    lines = [
        "# Legal Research Memo",
        f"*Generated {date.today():%d %B %Y} · Nyaya Research*",
        "",
        f"**Question:** {turn['question']}",
        "",
        turn["answer"],
        "",
        "---",
        "## Authorities",
    ]
    for s in turn["sources"]:
        mark = "cited" if s.get("cited") else "retrieved"
        lines.append(
            f"- **[S{s['number']}]** {s['case_title']} — {s['court']}, {s['date']} "
            f"({mark}) — {s['url']}"
        )
    lines += [
        "",
        "> AI-generated research aid. Verify every authority against the official "
        "report before relying on it. Not legal advice.",
    ]
    return "\n".join(lines)


def render_turn(turn, idx):
    with st.chat_message("user", avatar="🧑‍⚖️"):
        st.markdown(turn["question"])
        if turn["standalone_question"] != turn["question"]:
            st.caption(f"Searched as: *{turn['standalone_question']}*")

    with st.chat_message("assistant", avatar="⚖️"):
        t = turn["timings"]
        tags = f'<span class="badge gold">{"Lawyer memo" if turn["mode"] == "lawyer" else "Study mode"}</span>'
        if t.get("total"):
            tags += f'<span class="badge">{t["total"]:.1f}s total</span>'
        if not turn["answered"]:
            tags += '<span class="badge amber">Not found in corpus</span>'
        st.markdown(tags, unsafe_allow_html=True)

        render_answer(turn["answer"])

        if turn["sources"]:
            st.divider()
            render_sources(turn["sources"])
            st.download_button(
                "⬇ Download as research memo (.md)",
                build_memo(turn),
                file_name=f"research_memo_{idx + 1}.md",
                key=f"dl_{idx}",
            )


# ---------------------------------------
# Hero / empty state
# ---------------------------------------

if not st.session_state.history:
    st.markdown(
        """
        <div class="hero">
            <h1>Research Indian case law, <em>with citations you can check</em></h1>
            <p>Every statement is tied to a numbered judgment and the exact passage behind it.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    examples = [
        "What is the Basic Structure Doctrine and which cases established it?",
        "How have courts interpreted the doctrine of reasonable classification under Article 14?",
        "Can Parliament amend Fundamental Rights?",
        "What are the grounds on which anticipatory bail may be granted?",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.pending = ex
            st.rerun()

# ---------------------------------------
# Conversation
# ---------------------------------------

for i, turn in enumerate(st.session_state.history):
    render_turn(turn, i)

prompt = st.chat_input("Ask a legal question, or a follow-up to the previous answer...")
question = prompt or st.session_state.pending
st.session_state.pending = None

if question:
    with st.spinner("Searching judgments, reranking, drafting with citations..."):
        try:
            result = rag.ask(
                question,
                top_k=top_k,
                mode=mode,
                courts=sel_courts or None,
                year_range=year_range if year_range != (y_min, y_max) else None,
                history=st.session_state.history,
            )
            st.session_state.history.append(result)
            st.rerun()
        except Exception as e:
            st.error(f"Something went wrong: {e}")

st.markdown(
    '<div class="disclaimer">AI-generated research aid based only on the indexed judgments. '
    "It can make mistakes — verify every authority against the official report. "
    "Not legal advice.</div>",
    unsafe_allow_html=True,
)
