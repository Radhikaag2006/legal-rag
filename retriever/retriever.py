from embeddings.embedding_model import EmbeddingModel
from embeddings.chroma_store import ChromaStore

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


class Retriever:
    """
    Retrieves the most relevant chunks from ChromaDB.
    """

    def __init__(self):

        logger.info("Initializing Retriever...\n")

        self.embedding_model = EmbeddingModel()

        self.vector_db = ChromaStore()

        logger.info("Retriever Ready.\n")

    def retrieve(
        self,
        query: str,
        top_k: int = 5
    ):
        """
        Retrieve top-k most relevant chunks.
        """

        query_embedding = self.embedding_model.embed_text(query)

        results = self.vector_db.query(
            embedding=query_embedding,
            top_k=top_k
        )

        retrieved_chunks = []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances
        ):

            retrieved_chunks.append(
                {
                    "text": document,
                    "document_id": metadata.get("document_id"),
                    "chunk_id": metadata.get("chunk_id"),
                    "case_title": metadata.get("case_title"),
                    "court": metadata.get("court"),
                    "date": metadata.get("date"),
                    "distance": distance
                }
            )

        return retrieved_chunks