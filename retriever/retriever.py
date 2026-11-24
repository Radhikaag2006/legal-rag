from embeddings.embedding_model import EmbeddingModel
from embeddings.pg_vector_store import PgVectorStore
from reranker.reranker import Reranker

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


class Retriever:
    """
    Retrieves the most relevant chunks from Postgres/pgvector.
    """

    def __init__(self):

        logger.info("Initializing Retriever...\n")

        self.embedding_model = EmbeddingModel()

        self.vector_db = PgVectorStore()

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

        rows = self.vector_db.query(
            embedding=query_embedding,
            top_k=top_k
        )

        return [
            {
                "text": row["text"],
                "document_id": row["document_id"],
                "chunk_id": row["chunk_id"],
                "case_title": row["case_title"],
                "court": row["court"],
                "date": row["date"],
                "distance": row["distance"],
            }
            for row in rows
        ]
