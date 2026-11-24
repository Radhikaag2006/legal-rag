"""
One-time local migration: read the existing local ChromaDB corpus
(`data/vector_db`, collection `legal_judgements`) and the local judgment
PDFs (`data/pdfs/*.pdf`), re-embed the chunk text with the new Google
embedding API, and write everything into the new Postgres/pgvector store
and Vercel Blob.

Run once, locally, against the new Neon DATABASE_URL:
    python -m preprocessing.reindex_to_postgres

Requires `chromadb` installed locally (not a deploy dependency anymore)
to read the legacy store: `pip install chromadb`.
"""
import logging
from pathlib import Path

import chromadb

from api import db
from embeddings.embedding_model import EmbeddingModel
from embeddings.pg_vector_store import PgVectorStore
from preprocessing.config import PDF_FOLDER, VECTOR_DB_PATH
from storage.blob import put as blob_put

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

OLD_COLLECTION_NAME = "legal_judgements"
BATCH_SIZE = 64


def reindex_chunks():
    client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    collection = client.get_or_create_collection(name=OLD_COLLECTION_NAME)

    total = collection.count()
    logger.info(f"Found {total} chunks in the legacy Chroma collection.")

    embedder = EmbeddingModel()
    store = PgVectorStore()

    offset = 0
    migrated = 0
    while offset < total:
        batch = collection.get(
            limit=BATCH_SIZE, offset=offset, include=["documents", "metadatas"]
        )
        ids, docs, metas = batch["ids"], batch["documents"], batch["metadatas"]
        if not ids:
            break

        embeddings = embedder.embed_texts(docs)
        store.add_documents(ids, embeddings, docs, metas)

        migrated += len(ids)
        offset += BATCH_SIZE
        logger.info(f"Migrated {migrated}/{total} chunks")

    logger.info("Chunk reindex complete.")


def reindex_pdfs():
    db.init()
    folder = Path(PDF_FOLDER)
    if not folder.is_dir():
        logger.warning(f"No local PDF folder at {folder}, skipping PDF upload.")
        return

    pdfs = sorted(folder.glob("*.pdf"))
    logger.info(f"Uploading {len(pdfs)} judgment PDFs to Vercel Blob...")

    for i, path in enumerate(pdfs, start=1):
        document_id = path.stem
        data = path.read_bytes()
        url = blob_put(f"judgments/{document_id}.pdf", data, "application/pdf")
        db.set_pdf_url(document_id, url)
        if i % 20 == 0 or i == len(pdfs):
            logger.info(f"Uploaded {i}/{len(pdfs)} PDFs")

    logger.info("PDF upload complete.")


if __name__ == "__main__":
    reindex_chunks()
    reindex_pdfs()
