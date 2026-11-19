"""Storage of the media produced in a turn (maps, PDF bulletins, videos).

The tools return media as bytes inside the agent output. Web clients need
links instead, so each item is stored and replaced by a URL:

- ``GcsMediaStore`` (``PASTO_BACANO_MEDIA_BUCKET`` set): uploads to Cloud
  Storage and returns a short lived V4 signed URL. Used on Cloud Run, where
  the agent service is private and the user's browser cannot reach it.
- ``MemoryMediaStore`` (default): keeps the bytes in memory for a while and
  serves them from ``GET /api/media/{media_id}`` on this service. Used locally.

``collect_attachments`` turns an agent output into the website's attachment
list and does not depend on the store used.
"""

from __future__ import annotations

import mimetypes
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Protocol

from semente.logging import log_error

from app.api.models import Attachment

_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "video/mp4": ".mp4",
}


@dataclass
class MediaItem:
    """Bytes of one output item and how to show it."""

    content: bytes
    mime_type: str
    kind: str  # "image", "document" or "video"
    title: str = ""


class MediaStore(Protocol):
    """Stores one item and returns a URL the client can open."""

    def save(self, item: MediaItem, base_url: str) -> str: ...


class MemoryMediaStore:
    """In-memory store served by this service (local development)."""

    def __init__(self, ttl_seconds: int = 3600, max_items: int = 200) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: dict[str, tuple[float, MediaItem]] = {}
        self._lock = threading.Lock()

    def save(self, item: MediaItem, base_url: str) -> str:
        media_id = uuid.uuid4().hex + _EXTENSIONS.get(item.mime_type, "")
        now = time.time()
        with self._lock:
            self._items = {k: v for k, v in self._items.items() if now - v[0] < self.ttl_seconds}
            while len(self._items) >= self.max_items:
                self._items.pop(next(iter(self._items)))
            self._items[media_id] = (now, item)
        return f"{base_url.rstrip('/')}/api/media/{media_id}"

    def get(self, media_id: str) -> Optional[MediaItem]:
        with self._lock:
            entry = self._items.get(media_id)
        if entry is None or time.time() - entry[0] >= self.ttl_seconds:
            return None
        return entry[1]


class GcsMediaStore:
    """Cloud Storage store with signed URLs (Cloud Run).

    Signing uses the IAM signBlob API with the service's own identity, so no
    key file is needed. The service account needs ``roles/storage.objectAdmin``
    (or objectCreator plus objectViewer) on the bucket and
    ``roles/iam.serviceAccountTokenCreator`` on itself.
    """

    def __init__(self, bucket: str, prefix: str = "media", expiration_minutes: int = 60) -> None:
        from google.cloud import storage

        self.bucket_name = bucket
        self.prefix = prefix.strip("/")
        self.expiration = timedelta(minutes=expiration_minutes)
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    def _signing_credentials(self) -> dict[str, Any]:
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(Request())
        email = getattr(credentials, "service_account_email", None)
        if not email or email == "default":
            email = os.getenv("PASTO_BACANO_SERVICE_ACCOUNT", "")
        return {"service_account_email": email, "access_token": credentials.token}

    def save(self, item: MediaItem, base_url: str) -> str:
        name = f"{self.prefix}/{time.strftime('%Y/%m/%d')}/{uuid.uuid4().hex}{_EXTENSIONS.get(item.mime_type, '')}"
        blob = self._bucket.blob(name)
        blob.upload_from_string(item.content, content_type=item.mime_type)
        return blob.generate_signed_url(
            version="v4", expiration=self.expiration, method="GET", **self._signing_credentials()
        )


def media_store_from_env() -> MediaStore:
    """Chooses the store: Cloud Storage when ``PASTO_BACANO_MEDIA_BUCKET`` is set, memory otherwise."""
    bucket = os.getenv("PASTO_BACANO_MEDIA_BUCKET", "").strip()
    return GcsMediaStore(bucket) if bucket else MemoryMediaStore()


def _bytes_of(obj: Any) -> Optional[bytes]:
    content = getattr(obj, "content", None)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    filepath = getattr(obj, "filepath", None)
    if filepath and Path(filepath).is_file():
        return Path(filepath).read_bytes()
    return None


def _mime_of(obj: Any, default: str) -> str:
    mime = getattr(obj, "mime_type", None)
    if mime:
        return mime
    fmt = getattr(obj, "format", None)
    if fmt:
        guessed = mimetypes.guess_type(f"x.{fmt}")[0]
        if guessed:
            return guessed
    return default


def _title_of(obj: Any) -> str:
    for attr in ("name", "filename", "alt_text"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    return ""


def collect_attachments(output: Any, store: MediaStore, base_url: str) -> list[Attachment]:
    """Stores the images, files and videos of an agent output and returns their links.

    Items that already have an ``https`` URL are passed through. Audio is
    skipped: voice replies are a WhatsApp feature and the text is already in
    the reply. A failed upload drops that item and is logged; the text reply
    is never lost because of media.

    Args:
        output: The ``StepOutput`` of ``Harness.run``.
        store (MediaStore): Where to put the bytes.
        base_url (str): Public base URL of this service (memory store links).

    Returns:
        list[Attachment]: The attachments in output order.
    """
    groups = (
        ("image", getattr(output, "images", None) or [], "image/png"),
        ("document", getattr(output, "files", None) or [], "application/octet-stream"),
        ("video", getattr(output, "videos", None) or [], "video/mp4"),
    )
    attachments: list[Attachment] = []
    for kind, items, default_mime in groups:
        for obj in items:
            url = getattr(obj, "url", None)
            title = _title_of(obj)
            try:
                if isinstance(url, str) and url.startswith("https://"):
                    mime = _mime_of(obj, default_mime)
                    attachments.append(Attachment(type=kind, url=url, title=title, mime_type=mime))
                    continue
                content = _bytes_of(obj)
                if content is None:
                    continue
                mime = _mime_of(obj, default_mime)
                item = MediaItem(content=content, mime_type=mime, kind=kind, title=title)
                attachments.append(Attachment(type=kind, url=store.save(item, base_url), title=title, mime_type=mime))
            except Exception as error:  # noqa: BLE001 — media never breaks the reply
                log_error(f"api.media: could not store an attachment: {error}")
    return attachments
