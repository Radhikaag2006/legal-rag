"""
Per-chat document uploads.

Uploaded files are split into page-aware chunks, embedded with the same model
as the legal corpus, and stored in the shared `chunks` table (source_type
='upload') so they can be searched alongside (but never mixed into) the
judgment corpus, scoped by chat_id.
"""
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from psycopg.rows import dict_row

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

logger = logging.getLogger(__name__)


class UploadError(ValueError):
    """Raised when an uploaded file cannot be used."""


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages(path: Path):
    """Return a list of (page_number | 0, text). 0 means 'no page concept'."""
    ext = path.suffix.lower()

    if ext == ".pdf":
        try:
            with fitz.open(path) as doc:
                return [(i + 1, _clean(p.get_text())) for i, p in enumerate(doc)]
        except Exception as e:
            raise UploadError(f"Could not read this PDF: {e}")

    if ext == ".docx":
        import docx

        try:
            d = docx.Document(str(path))
        except Exception as e:
            raise UploadError(f"Could not read this Word file: {e}")
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return [(0, _clean("\n".join(parts)))]

    if ext == ".txt":
        return [(0, _clean(path.read_text(encoding="utf-8", errors="replace")))]

    raise UploadError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")


class UploadStore:

    def __init__(self, pool, embedding_model):
        self.pool = pool
        self.embedder = embedding_model
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )

    # ------------------------------------------------------------

    def add_file(self, chat_id: str, file_id: str, filename: str, path: Path):
        pages = extract_pages(path)

        texts, metas = [], []
        for page_no, page_text in pages:
            if not page_text:
                continue
            for piece in self.splitter.split_text(page_text):
                metas.append({"page": page_no, "chunk_id": len(texts)})
                texts.append(piece)

        if not texts:
            raise UploadError(
                "No readable text was found in this file. "
                "Scanned PDFs (images) are not supported yet."
            )

        embeddings = self.embedder.embed_texts(texts)
        rows = [
            (
                f"{file_id}_{i}",
                f"upload:{file_id}",
                chat_id,
                file_id,
                meta["chunk_id"],
                text,
                filename,
                meta["page"],
                list(embedding),
            )
            for i, (text, meta, embedding) in enumerate(zip(texts, metas, embeddings))
        ]
        with self.pool.connection() as c:
            with c.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO chunks
                        (id, document_id, chat_id, file_id, chunk_id, text, filename, page, embedding, source_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'upload')
                    ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text
                    """,
                    rows,
                )
        logger.info(f"Indexed upload {filename}: {len(pages)} pages, {len(texts)} chunks")
        return {"pages": len(pages), "chunks": len(texts)}

    # ------------------------------------------------------------

    def has_files(self, chat_id: str) -> bool:
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT 1 FROM chunks WHERE source_type='upload' AND chat_id=%s LIMIT 1",
                (chat_id,),
            ).fetchone()
        return row is not None

    def query(self, chat_id: str, embedding, k: int = 15):
        with self.pool.connection() as c:
            with c.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT text, document_id, chunk_id, filename, file_id, chat_id, page,
                           embedding <=> %s AS distance
                    FROM chunks
                    WHERE source_type='upload' AND chat_id=%s
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (list(embedding), chat_id, list(embedding), k),
                )
                rows = cur.fetchall()

        return [
            {
                "text": row["text"],
                "document_id": row["document_id"],
                "chunk_id": row["chunk_id"],
                "case_title": row["filename"],
                "court": "Uploaded document",
                "date": "",
                "distance": row["distance"],
                "source_type": "upload",
                "file_id": row["file_id"],
                "chat_id": row["chat_id"],
                "page": row["page"] or None,
            }
            for row in rows
        ]

    def delete_file(self, file_id: str):
        with self.pool.connection() as c:
            c.execute("DELETE FROM chunks WHERE source_type='upload' AND file_id=%s", (file_id,))

    def delete_chat(self, chat_id: str):
        with self.pool.connection() as c:
            c.execute("DELETE FROM chunks WHERE source_type='upload' AND chat_id=%s", (chat_id,))
