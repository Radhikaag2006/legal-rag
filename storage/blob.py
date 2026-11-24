"""
Thin client for Vercel Blob storage, used in place of local disk.

Uses Vercel Blob's REST API directly (the same endpoint the official
@vercel/blob JS SDK calls) so no Node dependency is needed. Requires
BLOB_READ_WRITE_TOKEN (create a Blob store in the Vercel dashboard / via
`vercel blob store add`, then pull the token with `vercel env pull`).
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BLOB_API_BASE = "https://blob.vercel-storage.com"
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

REQUEST_TIMEOUT = 30


def _headers(extra: dict | None = None) -> dict:
    if not BLOB_READ_WRITE_TOKEN:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set.")
    headers = {
        "authorization": f"Bearer {BLOB_READ_WRITE_TOKEN}",
        "x-api-version": "7",
    }
    if extra:
        headers.update(extra)
    return headers


def put(pathname: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to Blob storage and return the public URL."""
    resp = requests.put(
        f"{BLOB_API_BASE}/{pathname}",
        data=data,
        headers=_headers(
            {
                "content-type": content_type,
                "x-content-type": content_type,
                "x-add-random-suffix": "0",
            }
        ),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def get_bytes(url: str) -> bytes:
    """Download a blob's bytes by its public URL."""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def delete(url: str) -> None:
    resp = requests.delete(
        f"{BLOB_API_BASE}/delete",
        json={"urls": [url]},
        headers=_headers({"content-type": "application/json"}),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
