"""Locate judgment PDFs (in Vercel Blob) and the page a passage appears on."""
import re
from functools import lru_cache

import fitz  # PyMuPDF

from api import db
from storage.blob import get_bytes

_ID = re.compile(r"^\d+$")


def pdf_url(document_id) -> str | None:
    """Blob URL of the judgment PDF, or None if it isn't stored."""
    document_id = str(document_id)
    if not _ID.match(document_id):  # blocks lookups on malformed ids
        return None
    return db.get_pdf_url(document_id)


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


@lru_cache(maxsize=64)
def _page_texts(url: str):
    data = get_bytes(url)
    with fitz.open(stream=data, filetype="pdf") as doc:
        return tuple(_norm(p.get_text()) for p in doc)


def find_page(document_id, excerpt: str) -> int | None:
    """
    Best-effort: find the 1-based page containing the excerpt by matching
    short word windows (robust to cleaning differences in the stored text).
    """
    url = pdf_url(document_id)
    if not url or not excerpt:
        return None

    words = _norm(excerpt).split()
    if len(words) < 6:
        return None

    try:
        pages = _page_texts(url)
    except Exception:
        return None

    window = 7
    for start in range(0, max(1, len(words) - window), 9):
        needle = " ".join(words[start:start + window])
        for i, page_text in enumerate(pages, start=1):
            if needle in page_text:
                return i
    return None
