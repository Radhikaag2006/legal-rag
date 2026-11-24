"""Postgres storage for chat history, uploaded-file records, and judgment PDFs."""
import json
import time
import uuid

from psycopg.rows import dict_row

from storage.db import get_pool

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created DOUBLE PRECISION NOT NULL,
    updated DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    payload TEXT,
    created DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    blob_url TEXT,
    pages INTEGER,
    chunks INTEGER,
    created DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS judgment_pdfs (
    document_id TEXT PRIMARY KEY,
    blob_url TEXT NOT NULL
);
"""


def init():
    with get_pool().connection() as c:
        c.execute(SCHEMA)


# ---------------- chats ----------------

def create_chat(title="New chat"):
    chat_id = uuid.uuid4().hex
    now = time.time()
    with get_pool().connection() as c:
        c.execute(
            "INSERT INTO chats (id, title, created, updated) VALUES (%s,%s,%s,%s)",
            (chat_id, title, now, now),
        )
    return {"id": chat_id, "title": title, "updated": now}


def list_chats():
    with get_pool().connection() as c:
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, title, updated FROM chats ORDER BY updated DESC")
            return cur.fetchall()


def get_chat(chat_id):
    with get_pool().connection() as c:
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM chats WHERE id=%s", (chat_id,))
            return cur.fetchone()


def rename_chat(chat_id, title):
    with get_pool().connection() as c:
        c.execute("UPDATE chats SET title=%s WHERE id=%s", (title, chat_id))


def touch_chat(chat_id):
    with get_pool().connection() as c:
        c.execute("UPDATE chats SET updated=%s WHERE id=%s", (time.time(), chat_id))


def delete_chat(chat_id):
    with get_pool().connection() as c:
        c.execute("DELETE FROM chats WHERE id=%s", (chat_id,))


# ---------------- messages ----------------

def add_message(chat_id, role, content, payload=None):
    with get_pool().connection() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (chat_id, role, content, payload, created) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (chat_id, role, content, json.dumps(payload) if payload else None, time.time()),
            )
            msg_id = cur.fetchone()[0]
            cur.execute("UPDATE chats SET updated=%s WHERE id=%s", (time.time(), chat_id))
    return msg_id


def get_messages(chat_id):
    with get_pool().connection() as c:
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, role, content, payload, created FROM messages "
                "WHERE chat_id=%s ORDER BY id",
                (chat_id,),
            )
            rows = cur.fetchall()
    for r in rows:
        r["payload"] = json.loads(r["payload"]) if r["payload"] else None
    return rows


def recent_turns(chat_id, n=3):
    """Last n (question, answer) pairs, oldest first, for follow-up rewriting."""
    msgs = get_messages(chat_id)
    turns, pending = [], None
    for m in msgs:
        if m["role"] == "user":
            pending = m["content"]
        elif m["role"] == "assistant" and pending is not None:
            turns.append({"question": pending, "answer": m["content"]})
            pending = None
    return turns[-n:]


# ---------------- files ----------------

def add_file(chat_id, file_id, filename, stored_name, pages, chunks, blob_url=None):
    with get_pool().connection() as c:
        c.execute(
            "INSERT INTO files (id, chat_id, filename, stored_name, blob_url, pages, chunks, created) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (file_id, chat_id, filename, stored_name, blob_url, pages, chunks, time.time()),
        )


def list_files(chat_id):
    with get_pool().connection() as c:
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, filename, stored_name, blob_url, pages, chunks FROM files "
                "WHERE chat_id=%s ORDER BY created",
                (chat_id,),
            )
            return cur.fetchall()


def get_file(chat_id, file_id):
    with get_pool().connection() as c:
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM files WHERE id=%s AND chat_id=%s", (file_id, chat_id)
            )
            return cur.fetchone()


def delete_file(file_id):
    with get_pool().connection() as c:
        c.execute("DELETE FROM files WHERE id=%s", (file_id,))


# ---------------- judgment PDFs ----------------

def get_pdf_url(document_id):
    with get_pool().connection() as c:
        row = c.execute(
            "SELECT blob_url FROM judgment_pdfs WHERE document_id=%s", (document_id,)
        ).fetchone()
    return row[0] if row else None


def set_pdf_url(document_id, blob_url):
    with get_pool().connection() as c:
        c.execute(
            "INSERT INTO judgment_pdfs (document_id, blob_url) VALUES (%s,%s) "
            "ON CONFLICT (document_id) DO UPDATE SET blob_url = EXCLUDED.blob_url",
            (document_id, blob_url),
        )
