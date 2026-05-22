"""Media upload endpoints on Zernio.

Two upload paths exist on Zernio v1:

- ``POST /v1/media/presign`` — returns a presigned URL the caller PUTs the
  file to directly. Use for files up to 5GB. Two round-trips.
- ``POST /v1/media/upload-direct`` — multipart upload (≤25MB). One round-trip.

Both return a ``publicUrl`` that goes into ``mediaItems[].url`` on
``POST /v1/posts``. We do not implement the actual PUT for presign here —
the caller controls that (it might be httpx, aiofiles, or a worker
streaming from GCS). Keeping the client lean.
"""
from __future__ import annotations

from typing import Any


# Allowed contentTypes per OpenAPI enum on /v1/media/presign.
# Server-side caps (kept in sync with OpenAPI). Validated client-side so
# the caller fails fast instead of doing a doomed upload over the wire.
PRESIGN_MAX_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB
DIRECT_UPLOAD_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


ALLOWED_CONTENT_TYPES = (
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/avi",
    "video/x-msvideo",
    "video/webm",
    "video/x-m4v",
    "application/pdf",
)


class _MediaMixin:
    """``/v1/media/presign`` and ``/v1/media/upload-direct``."""

    async def presign_media(
        self,
        filename: str,
        content_type: str,
        size: int | None = None,
    ) -> dict[str, Any]:
        """Get a presigned upload URL (≤5GB path).

        Caller then PUTs the file bytes to ``uploadUrl`` (expires in 1 hour),
        and uses ``publicUrl`` in the post payload.
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"unsupported content_type={content_type!r}; "
                f"allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
            )
        if size is not None and size > PRESIGN_MAX_BYTES:
            raise ValueError(
                f"size={size} exceeds Zernio presign cap of {PRESIGN_MAX_BYTES} bytes (5GB)"
            )
        body: dict[str, Any] = {"filename": filename, "contentType": content_type}
        if size is not None:
            body["size"] = size
        return await self._post("/media/presign", json=body)

    async def upload_media_direct(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        """One-shot multipart upload (≤25MB). Files auto-delete after 7 days.

        Returns ``{url, filename, contentType, size}``; ``url`` is the
        public URL usable in posts / inbox attachments.
        """
        if len(file_bytes) > DIRECT_UPLOAD_MAX_BYTES:
            raise ValueError(
                f"file_bytes ({len(file_bytes)} bytes) exceeds Zernio upload-direct "
                f"cap of {DIRECT_UPLOAD_MAX_BYTES} bytes (25MB); use presign_media instead"
            )
        files = {"file": (filename, file_bytes, content_type)}
        data = {"contentType": content_type}
        return await self._post_multipart("/media/upload-direct", files=files, data=data)
