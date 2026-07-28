from retriever.retriever import Retriever
from llm.gemini_client import GeminiClient

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAG Pipeline...\n")

        self.retriever = Retriever()
        self.gemini = GeminiClient()

        logger.info("RAG Pipeline Ready.\n")

    def _build_context(self, retrieved_chunks):

        context = ""

        for i, chunk in enumerate(retrieved_chunks, start=1):

            context += f"""
==================== DOCUMENT {i} ====================

Case Title : {chunk['case_title']}
Court      : {chunk['court']}
Date       : {chunk['date']}

Content:
{chunk['text']}

"""

        return context

    def _build_prompt(self, question, context):

        prompt = f"""
You are an AI Legal Assistant specializing in Indian law.

Answer ONLY using the retrieved legal documents below.

Rules:
1. Do NOT use outside knowledge.
2. If the answer is not present in the context, reply exactly:
"I could not find this information in the retrieved legal documents."
3. Keep the answer factual and concise.

Your response MUST follow this format:

## Summary
(Brief answer)

## Legal Explanation
(Explain using the retrieved context only.)

## Relevant Judgments
(List the judgments you relied upon.)

## Conclusion
(One or two concluding sentences.)

==================== CONTEXT ====================

{context}

=================================================

Question:
{question}

Answer:
"""

        return prompt

    def ask(self, question, top_k=5):

        logger.info("Searching relevant legal documents...\n")

        retrieved_chunks = self.retriever.retrieve(
            query=question,
            top_k=top_k
        )

        if len(retrieved_chunks) == 0:

            return {
                "answer": "No relevant legal documents found.",
                "sources": []
            }

        context = self._build_context(retrieved_chunks)

        prompt = self._build_prompt(
            question=question,
            context=context
        )

        logger.info("Generating answer using Gemini...\n")

        answer = self.gemini.generate(prompt)

        sources = []

        seen = set()

        for chunk in retrieved_chunks:

            title = chunk["case_title"]

            if title not in seen:

                seen.add(title)

                sources.append(
                {
                    "document_id": chunk["document_id"],
                    "chunk_id": chunk["chunk_id"],
                    "case_title": chunk["case_title"],
                    "court": chunk["court"],
                    "date": chunk["date"]
                }
            )

        return {
            "question": question,
            "answer": answer,
            "sources": sources
        }