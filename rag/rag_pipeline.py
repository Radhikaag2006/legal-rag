import logging
import re
import time

from retriever.retriever import Retriever
from llm.gemini_client import GeminiClient
from reranker.reranker import Reranker
from rag.uploads import UploadStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

NOT_FOUND = "I could not find this information in the retrieved legal documents."

KANOON_URL = "https://indiankanoon.org/doc/{}/"

# ---------------------------------------------------------
# Answer styles
# ---------------------------------------------------------

LAWYER_FORMAT = """
## Short Answer
(2-3 sentences. Direct answer to the question.)

## Issue
(The precise legal question(s) raised.)

## Rule / Ratio Decidendi
(The legal principles laid down by the courts, each with a citation like [S1].
Quote short key phrases from the judgment in quotation marks where useful.)

## Analysis
(How the principles apply. Note where courts agree, distinguish, or differ.
Cite every proposition with [S#].)

## Conclusion
(One or two sentences.)

## Gaps & Caveats
(What the retrieved judgments do NOT cover, and what a lawyer should verify
before relying on this.)
"""

STUDENT_FORMAT = """
## In Simple Words
(A plain-language explanation a first-year law student can follow.)

## Key Terms
(Bullet list of important legal terms/doctrines with one-line meanings.)

## How the Courts Explained It
(Walk through the judgments step by step, citing each with [S#].)

## Remember for Exams
(3-4 crisp bullet points a student could memorise, citing [S#].)

## Related Topics to Study Next
(2-3 related doctrines or Articles that appear in the judgments.)
"""


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAG Pipeline...\n")

        self.retriever = Retriever()
        self.reranker = Reranker()
        self.gemini = GeminiClient()
        self.uploads = UploadStore(
            self.retriever.vector_db.pool,
            self.retriever.embedding_model,
        )

        logger.info("RAG Pipeline Ready.\n")

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _year(date_str):
        match = re.search(r"(?:19|20)\d{2}", date_str or "")
        return int(match.group()) if match else None

    def _apply_filters(self, chunks, courts, year_range):
        if not courts and not year_range:
            return chunks

        filtered = []
        for chunk in chunks:
            if courts and chunk["court"] not in courts:
                continue
            if year_range:
                year = self._year(chunk["date"])
                if year is None or not (year_range[0] <= year <= year_range[1]):
                    continue
            filtered.append(chunk)
        return filtered

    def _condense_question(self, question, history):
        """Rewrite a follow-up question into a standalone search query."""
        if not history:
            return question

        turns = ""
        for turn in history[-3:]:
            turns += f"User: {turn['question']}\nAssistant: {turn['answer'][:400]}\n\n"

        prompt = f"""Given the conversation below and a follow-up question, rewrite the
follow-up as ONE standalone legal question that can be understood without the
conversation. Keep case names, Articles and statutes. Output only the question.

Conversation:
{turns}
Follow-up: {question}

Standalone question:"""

        try:
            rewritten = self.gemini.generate(prompt).strip()
            return rewritten or question
        except Exception as e:
            logger.warning(f"Condense failed, using original question: {e}")
            return question

    @staticmethod
    def _select(ranked, top_k):
        """
        Take the top_k chunks. If the user uploaded documents and they are
        clearly relevant, guarantee they get a few slots so a question about
        "my document" is not crowded out by case law.
        """
        selected = ranked[:top_k]
        uploads = [c for c in ranked if c.get("source_type") == "upload"]

        if not uploads or uploads[0].get("relevance", 0) < 0.1:
            return selected

        want = min(3, len(uploads))
        have = [c for c in selected if c.get("source_type") == "upload"]
        if len(have) >= want:
            return selected

        extra = [c for c in uploads if c not in have][: want - len(have)]
        corpus = [c for c in selected if c.get("source_type") != "upload"]
        corpus = corpus[: max(0, top_k - len(have) - len(extra))]
        merged = have + extra + corpus
        return sorted(merged, key=lambda c: c["rerank_score"], reverse=True)

    @staticmethod
    def _group_sources(chunks):
        """Group chunks by judgment and number them S1, S2, ... by relevance."""
        grouped = {}
        for chunk in chunks:
            doc_id = chunk["document_id"]
            is_upload = chunk.get("source_type") == "upload"
            if doc_id not in grouped:
                grouped[doc_id] = {
                    "number": len(grouped) + 1,
                    "document_id": doc_id,
                    "chunk_id": chunk["chunk_id"],
                    "case_title": chunk["case_title"],
                    "court": chunk["court"],
                    "date": chunk["date"],
                    "url": None if is_upload else KANOON_URL.format(doc_id),
                    "relevance": chunk.get("relevance"),
                    "source_type": "upload" if is_upload else "corpus",
                    "file_id": chunk.get("file_id"),
                    "page": chunk.get("page"),
                    "excerpts": [],
                }
            grouped[doc_id]["excerpts"].append(chunk["text"])
        return list(grouped.values())

    @staticmethod
    def _build_context(sources):
        context = ""
        for s in sources:
            excerpts = "\n\n".join(s["excerpts"])
            if s.get("source_type") == "upload":
                header = f"""Type       : USER DOCUMENT (uploaded by the user)
File       : {s['case_title']}"""
            else:
                header = f"""Type       : Reported judgment
Case Title : {s['case_title']}
Court      : {s['court']}
Date       : {s['date']}"""
            context += f"""
==================== [S{s['number']}] ====================
{header}

Extracts:
{excerpts}

"""
        return context

    @staticmethod
    def _build_prompt(question, context, mode):
        role = (
            "You are a senior Indian legal research assistant helping practising advocates."
            if mode == "lawyer"
            else "You are a patient law professor helping Indian law students understand case law."
        )
        fmt = LAWYER_FORMAT if mode == "lawyer" else STUDENT_FORMAT

        return f"""
{role}

Answer ONLY using the retrieved judgment extracts below.

Rules:
1. Do NOT use outside knowledge, and never invent case names, citations or quotes.
2. Cite every legal proposition inline using the source tags, e.g. [S1] or [S2][S3].
   Only use tags that appear in the context.
3. If the answer is not present in the context, reply exactly:
"{NOT_FOUND}"
4. If sources conflict, say so explicitly.
5. Be precise and concise. Do not repeat the question.
6. Extracts marked USER DOCUMENT come from a file the user uploaded. Treat them as
   the user's own material (facts, contract, notice, draft), not as binding authority,
   and keep them clearly distinct from reported judgments. Cite them like any other source.

Your response MUST follow this format:
{fmt}

==================== CONTEXT ====================
{context}
=================================================

Question:
{question}

Answer:
"""

    # ---------------------------------------------------------
    # Main entry point
    # ---------------------------------------------------------

    def ask(
        self,
        question,
        top_k=5,
        mode="lawyer",
        courts=None,
        year_range=None,
        history=None,
        chat_id=None,
    ):
        timings = {}
        t_start = time.perf_counter()

        standalone = self._condense_question(question, history)

        # ---- Retrieve (over-fetch when filtering) ----
        t0 = time.perf_counter()
        fetch_k = 100 if (courts or year_range) else 30
        chunks = self.retriever.retrieve(query=standalone, top_k=fetch_k)
        chunks = self._apply_filters(chunks, courts, year_range)
        # ---- Documents uploaded in this chat ----
        upload_chunks = []
        if chat_id and self.uploads.has_files(chat_id):
            query_emb = self.retriever.embedding_model.embed_text(standalone)
            upload_chunks = self.uploads.query(chat_id, query_emb, k=15)
        timings["retrieval"] = time.perf_counter() - t0

        if not chunks and not upload_chunks:
            return {
                "question": question,
                "standalone_question": standalone,
                "answer": "No relevant legal documents found for these filters.",
                "sources": [],
                "answered": False,
                "mode": mode,
                "timings": timings,
            }

        # ---- Rerank ----
        t0 = time.perf_counter()
        ranked = self.reranker.rerank(standalone, chunks + upload_chunks)
        chunks = self._select(ranked, top_k)
        timings["rerank"] = time.perf_counter() - t0

        sources = self._group_sources(chunks)
        prompt = self._build_prompt(
            standalone, self._build_context(sources), mode
        )

        # ---- Generate ----
        t0 = time.perf_counter()
        answer = self.gemini.generate(prompt)
        timings["generation"] = time.perf_counter() - t0
        timings["total"] = time.perf_counter() - t_start

        # Which sources did the model actually cite?
        cited = {int(n) for n in re.findall(r"\[S(\d+)\]", answer)}
        for s in sources:
            s["cited"] = s["number"] in cited

        return {
            "question": question,
            "standalone_question": standalone,
            "answer": answer,
            "sources": sources,
            "answered": NOT_FOUND not in answer,
            "mode": mode,
            "timings": timings,
        }

    def retrieve(self, question, top_k=10):
        """Retrieve + rerank without generating an answer."""
        chunks = self.retriever.retrieve(query=question, top_k=30)
        if not chunks:
            return []
        return self.reranker.rerank(question, chunks)[:top_k]
