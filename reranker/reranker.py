import os

import cohere
from dotenv import load_dotenv

load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
RERANK_MODEL = "rerank-v3.5"


class Reranker:

    def __init__(self):
        self.client = cohere.ClientV2(api_key=COHERE_API_KEY)

    def rerank(self, query, retrieved_chunks):
        if not retrieved_chunks:
            return retrieved_chunks

        response = self.client.rerank(
            model=RERANK_MODEL,
            query=query,
            documents=[chunk["text"] for chunk in retrieved_chunks],
            top_n=len(retrieved_chunks),
        )

        ranked = []
        for result in response.results:
            chunk = retrieved_chunks[result.index]
            chunk["rerank_score"] = float(result.relevance_score)
            chunk["relevance"] = float(result.relevance_score)
            ranked.append(chunk)

        return ranked
