"""
Legal research API + web app.

Entrypoint lives at the project root because Vercel's Python runtime only
looks for app.py/index.py/main.py/etc. at the root (or in src/ or app/),
never inside api/ (that folder is reserved for file-based functions).

Run locally from the project root:
    python -m uvicorn app:app --port 8000
then open http://localhost:8000
"""
import logging
import os
import re
import sys
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from api import db, export
from api.pdfs import find_page, pdf_url
from rag.rag_pipeline import RAGPipeline
from rag.summary import NothingToSummarise, generate_summary
from rag.uploads import ALLOWED_EXTENSIONS, UploadError
from storage.blob import delete as blob_delete
from storage.blob import put as blob_put

logger = logging.getLogger("api")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PUBLIC_DIR = PROJECT_ROOT / "public"

state = {"rag": None, "info": None, "startup_error": None}


# ---------------------------------------------------------------
# Startup
# ---------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    try:
        state["rag"] = RAGPipeline()
        state["info"] = state["rag"].retriever.vector_db.corpus_stats()
    except Exception as e:  # keep the server up so /api/health can explain
        logger.exception("Pipeline failed to start")
        state["startup_error"] = str(e)
    yield


app = FastAPI(title="Indian Case-Law Research Assistant", lifespan=lifespan)


def get_rag() -> RAGPipeline:
    if state["rag"] is None:
        raise HTTPException(
            503,
            "The research engine is not available. "
            + (state["startup_error"] or "It is still starting up — try again shortly."),
        )
    return state["rag"]


# ---------------------------------------------------------------
# Models
# ---------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    mode: Literal["lawyer", "student"] = "lawyer"
    courts: list[str] | None = None
    year_min: int | None = Field(None, ge=1800, le=2100)
    year_max: int | None = Field(None, ge=1800, le=2100)
    top_k: int = Field(5, ge=3, le=10)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question must not be empty")
        if not re.search(r"[A-Za-z0-9]", v):
            raise ValueError("Question must contain words or numbers")
        return v


class ExportAuthority(BaseModel):
    number: int
    case_title: str = Field(..., max_length=500)
    court: str = Field("", max_length=200)
    date: str = Field("", max_length=60)
    source_type: str = Field("corpus", max_length=20)
    page: int | None = None
    external_url: str | None = Field(None, max_length=300)
    cited: bool = True


class ExportRequest(BaseModel):
    title: str = Field("Research", max_length=200)
    summary: str = Field(..., min_length=1, max_length=40000)
    authorities: list[ExportAuthority] = Field(default_factory=list, max_length=100)


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


# ---------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------

@app.get("/api/health")
def health():
    rag = state["rag"]
    db_ok, count = False, 0
    if rag:
        try:
            count = rag.retriever.vector_db.count()
            db_ok = count > 0
        except Exception:
            db_ok = False
    return {
        "status": "ok" if (rag and db_ok) else "degraded",
        "vector_db": db_ok,
        "passages": count,
        "error": state["startup_error"],
    }


@app.get("/api/info")
def info():
    get_rag()
    return state["info"]


# ---------------------------------------------------------------
# Chats
# ---------------------------------------------------------------

def _chat_or_404(chat_id: str):
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


def _file_view(chat_id: str, f: dict):
    ext = Path(f["stored_name"]).suffix.lower()
    return {
        "id": f["id"],
        "filename": f["filename"],
        "pages": f["pages"],
        "url": f"/files/{chat_id}/{f['id']}",
        "viewable": ext in (".pdf", ".txt") and bool(f.get("blob_url")),
    }


@app.get("/api/chats")
def list_chats():
    return db.list_chats()


@app.post("/api/chats")
def create_chat():
    return db.create_chat()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = _chat_or_404(chat_id)
    return {
        "id": chat["id"],
        "title": chat["title"],
        "messages": db.get_messages(chat_id),
        "files": [_file_view(chat_id, f) for f in db.list_files(chat_id)],
    }


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: RenameRequest):
    _chat_or_404(chat_id)
    db.rename_chat(chat_id, body.title.strip())
    return {"ok": True}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    _chat_or_404(chat_id)
    if state["rag"]:
        state["rag"].uploads.delete_chat(chat_id)
    db.delete_chat(chat_id)
    return {"ok": True}


# ---------------------------------------------------------------
# Asking
# ---------------------------------------------------------------

def _present_sources(chat_id: str, sources: list[dict]):
    """Attach PDF links (and page numbers) to each source for the UI."""
    out = []
    for s in sources:
        view = {
            "number": s["number"],
            "case_title": s["case_title"],
            "court": s["court"],
            "date": s["date"],
            "document_id": s["document_id"],
            "cited": s.get("cited", False),
            "relevance": s.get("relevance"),
            "excerpts": s["excerpts"],
            "source_type": s["source_type"],
            "pdf_url": None,
            "viewable": False,
            "page": None,
            "external_url": s.get("url"),
        }
        if s["source_type"] == "upload":
            f = db.get_file(chat_id, s["file_id"])
            if f:
                fv = _file_view(chat_id, f)
                view.update(pdf_url=fv["url"], viewable=fv["viewable"], page=s.get("page"))
        elif pdf_url(s["document_id"]):
            view.update(
                pdf_url=f"/pdf/{s['document_id']}",
                viewable=True,
                page=find_page(s["document_id"], s["excerpts"][0]),
            )
        out.append(view)
    return out


@app.post("/api/chats/{chat_id}/messages")
def ask(chat_id: str, body: AskRequest):
    chat = _chat_or_404(chat_id)
    rag = get_rag()

    # Controlled error if the legal database is missing or empty
    try:
        if rag.retriever.vector_db.count() == 0:
            raise RuntimeError("empty")
    except Exception:
        raise HTTPException(
            503,
            "The legal database is unavailable or empty. "
            "Check that the Postgres `chunks` table has been populated (see "
            "preprocessing/reindex_to_postgres.py).",
        )

    year_range = None
    if body.year_min or body.year_max:
        year_range = (
            body.year_min or state["info"]["year_min"],
            body.year_max or state["info"]["year_max"],
        )

    history = db.recent_turns(chat_id, 3)

    try:
        result = rag.ask(
            body.question,
            top_k=body.top_k,
            mode=body.mode,
            courts=body.courts or None,
            year_range=year_range,
            history=history,
            chat_id=chat_id,
        )
    except RuntimeError as e:  # e.g. Gemini unreachable
        raise HTTPException(503, str(e))
    except Exception:
        logger.exception("Unexpected error while answering")
        raise HTTPException(500, "Something went wrong while researching this question.")

    payload = {
        "answer": result["answer"],
        "answered": result["answered"],
        "mode": result["mode"],
        "standalone_question": result["standalone_question"],
        "timings": {k: round(v, 2) for k, v in result["timings"].items()},
        "sources": _present_sources(chat_id, result["sources"]),
    }

    db.add_message(chat_id, "user", body.question)
    msg_id = db.add_message(chat_id, "assistant", result["answer"], payload)

    if chat["title"] == "New chat":
        title = body.question if len(body.question) <= 56 else body.question[:53].rstrip() + "…"
        db.rename_chat(chat_id, title)

    return {"id": msg_id, "role": "assistant", "content": result["answer"], "payload": payload}


# ---------------------------------------------------------------
# Summary + export
# ---------------------------------------------------------------

@app.post("/api/chats/{chat_id}/summary")
def summarise(chat_id: str):
    chat = _chat_or_404(chat_id)
    rag = get_rag()
    try:
        result = generate_summary(rag.gemini, db.get_messages(chat_id))
    except NothingToSummarise as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception:
        logger.exception("Summary failed")
        raise HTTPException(500, "Something went wrong while writing the summary.")

    # Keep links for the viewer; the export payload only needs the plain fields
    for a in result["authorities"]:
        a["viewable"] = bool(a.get("viewable") and a.get("pdf_url"))
    result["title"] = chat["title"]
    return result


EXPORTS = {
    "pdf": (export.to_pdf, "application/pdf"),
    "docx": (
        export.to_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
}


@app.post("/api/export/{fmt}")
def export_summary(fmt: str, body: ExportRequest):
    if fmt not in EXPORTS:
        raise HTTPException(404, "Unknown format. Use pdf or docx.")
    render, media = EXPORTS[fmt]
    try:
        data = render(body.title, body.summary, [a.model_dump() for a in body.authorities])
    except Exception:
        logger.exception("Export failed")
        raise HTTPException(500, "Could not create the document.")
    name = re.sub(r"[^\w\- ]", "", body.title, flags=re.ASCII).strip()[:50] or "research"
    return Response(
        data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="Summary - {name}.{fmt}"'},
    )


# ---------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------

def _safe_name(name: str) -> str:
    name = Path(name or "document").name
    return re.sub(r"[^\w.\- ()]", "_", name)[:120] or "document"


@app.post("/api/chats/{chat_id}/files")
async def upload_file(chat_id: str, file: UploadFile = File(...)):
    _chat_or_404(chat_id)
    rag = get_rag()

    filename = _safe_name(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Unsupported file type. Upload a PDF, DOCX or TXT file.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large (limit 20 MB).")
    if not data:
        raise HTTPException(400, "The file is empty.")

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}{ext}"

    # Extraction needs a real file on disk; /tmp is writable even on Vercel.
    tmp_path = Path(tempfile.gettempdir()) / stored_name
    tmp_path.write_bytes(data)

    try:
        stats = rag.uploads.add_file(chat_id, file_id, filename, tmp_path)
    except UploadError as e:
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("Upload indexing failed")
        raise HTTPException(500, "Could not process this file.")
    finally:
        tmp_path.unlink(missing_ok=True)

    media = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8"}.get(
        ext, "application/octet-stream"
    )
    blob_url = blob_put(f"uploads/{chat_id}/{stored_name}", data, media)

    db.add_file(chat_id, file_id, filename, stored_name, stats["pages"], stats["chunks"], blob_url)
    db.touch_chat(chat_id)
    return _file_view(chat_id, db.get_file(chat_id, file_id))


@app.delete("/api/chats/{chat_id}/files/{file_id}")
def remove_file(chat_id: str, file_id: str):
    f = db.get_file(chat_id, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    if state["rag"]:
        state["rag"].uploads.delete_file(file_id)
    if f.get("blob_url"):
        try:
            blob_delete(f["blob_url"])
        except Exception:
            logger.warning("Could not delete blob for file %s", file_id)
    db.delete_file(file_id)
    return {"ok": True}


# ---------------------------------------------------------------
# Documents (inline so they open inside the viewer panel)
# ---------------------------------------------------------------

@app.get("/pdf/{document_id}")
def judgment_pdf(document_id: str):
    url = pdf_url(document_id)
    if not url:
        raise HTTPException(404, "The PDF for this judgment is not available.")
    return RedirectResponse(url)


@app.get("/files/{chat_id}/{file_id}")
def uploaded_file(chat_id: str, file_id: str):
    f = db.get_file(chat_id, file_id)
    if not f or not f.get("blob_url"):
        raise HTTPException(404, "File not found")
    return RedirectResponse(f["blob_url"])


# ---------------------------------------------------------------
# Frontend (local dev only — on Vercel, public/ is served by the CDN
# directly and never reaches this app, so mounting it there would be
# both unreachable and a waste of a cold start).
# ---------------------------------------------------------------

if PUBLIC_DIR.is_dir() and not os.getenv("VERCEL"):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
