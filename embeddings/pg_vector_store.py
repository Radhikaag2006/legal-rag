"""
Postgres + pgvector backed store for judgment chunks, replacing the local
ChromaDB PersistentClient. Lives in the same `chunks` table that
`rag/uploads.py` also writes to (distinguished by `source_type`).
"""
from psycopg.rows import dict_row

from embeddings.embedding_model import EMBED_DIM
from storage.db import get_pool

COLLECTION_NAME = "legal_judgements"

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chat_id TEXT,
    file_id TEXT,
    source_type TEXT NOT NULL DEFAULT 'corpus',
    chunk_id INTEGER,
    text TEXT NOT NULL,
    case_title TEXT,
    court TEXT,
    date TEXT,
    filename TEXT,
    page INTEGER,
    embedding VECTOR({EMBED_DIM}) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_source_type_idx ON chunks (source_type);
CREATE INDEX IF NOT EXISTS chunks_chat_id_idx ON chunks (chat_id);
CREATE INDEX IF NOT EXISTS chunks_file_id_idx ON chunks (file_id);
"""

# HNSW index creation is split out because it must run after the table
# exists and can be slow to build on a large corpus.
HNSW_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
ON chunks USING hnsw (embedding vector_cosine_ops);
"""


class PgVectorStore:
    """Vector store for the main judgment corpus (source_type='corpus')."""

    def __init__(self):
        self.pool = get_pool()
        with self.pool.connection() as c:
            c.execute(SCHEMA)
            c.execute(HNSW_INDEX)

    # ---------------------------------------------------------
    # Add
    # ---------------------------------------------------------

    def add_document(self, document_id: str, embedding, text: str, metadata: dict):
        self.add_documents([document_id], [embedding], [text], [metadata])

    def add_documents(self, ids: list[str], embeddings, documents: list[str], metadatas: list[dict]):
        rows = [
            (
                doc_id,
                meta.get("document_id"),
                meta.get("chunk_id"),
                text,
                meta.get("case_title"),
                meta.get("court"),
                meta.get("date"),
                list(embedding),
            )
            for doc_id, embedding, text, meta in zip(ids, embeddings, documents, metadatas)
        ]
        with self.pool.connection() as c:
            with c.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO chunks
                        (id, document_id, chunk_id, text, case_title, court, date, embedding, source_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'corpus')
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        case_title = EXCLUDED.case_title,
                        court = EXCLUDED.court,
                        date = EXCLUDED.date,
                        embedding = EXCLUDED.embedding
                    """,
                    rows,
                )

    # ---------------------------------------------------------
    # Query
    # ---------------------------------------------------------

    def query(self, embedding, top_k: int = 5) -> list[dict]:
        with self.pool.connection() as c:
            with c.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, document_id, chunk_id, text, case_title, court, date,
                           embedding <=> %s AS distance
                    FROM chunks
                    WHERE source_type = 'corpus'
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (list(embedding), list(embedding), top_k),
                )
                return cur.fetchall()

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def count(self) -> int:
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT count(*) FROM chunks WHERE source_type = 'corpus'"
            ).fetchone()
            return row[0]

    def delete_collection(self):
        with self.pool.connection() as c:
            c.execute("DELETE FROM chunks WHERE source_type = 'corpus'")

    def corpus_stats(self) -> dict:
        """Replaces the old `_corpus_info` use of `collection.get(...)` in app.py."""
        with self.pool.connection() as c:
            with c.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        array_agg(DISTINCT court) FILTER (WHERE court IS NOT NULL AND court <> '') AS courts,
                        count(DISTINCT document_id) AS judgments,
                        count(*) AS passages
                    FROM chunks WHERE source_type = 'corpus'
                    """
                )
                row = cur.fetchone()
                cur.execute(
                    """
                    SELECT date FROM chunks
                    WHERE source_type = 'corpus' AND date ~ '(19|20)[0-9]{2}'
                    """
                )
                years = []
                import re

                for r in cur.fetchall():
                    m = re.search(r"(?:19|20)\d{2}", r["date"] or "")
                    if m:
                        years.append(int(m.group()))

        return {
            "courts": sorted(row["courts"] or []),
            "judgments": row["judgments"] or 0,
            "passages": row["passages"] or 0,
            "year_min": min(years) if years else 1950,
            "year_max": max(years) if years else 2025,
        }
