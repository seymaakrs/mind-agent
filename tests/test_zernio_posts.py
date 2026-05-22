"""Tests for Zernio Posts + Media mixins (Faz 1 of Late→Zernio migration).

Covers only the new ``src/infra/zernio/{posts,media}.py`` surfaces. The
tool layer and Late client are untouched in this phase — those land in
later PRs.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


def _mock_response(status: int, json_body: Any = None, text_body: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text_body or (str(json_body) if json_body else "")
    resp.json = MagicMock(return_value=json_body if json_body is not None else {})
    return resp


def _patch_async_client(method: str, response: MagicMock):
    return patch.object(
        httpx.AsyncClient, method, new=AsyncMock(return_value=response)
    )


def _client():
    from src.infra.zernio import ZernioClient

    return ZernioClient(
        api_key="sk_test_123",
        account_id="wa_acc_id",
        base_url="https://api.zernio.com/v1",
    )


# ---------------------------------------------------------------------------
# Posts mixin
# ---------------------------------------------------------------------------


class TestCreatePost:
    @pytest.mark.asyncio
    async def test_publish_now_omits_scheduled_and_draft_keys(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(200, {"post": {"_id": "p1", "status": "published"}})
        ) as mock_post:
            await client.create_post(
                content="hello",
                platforms=[{"platform": "twitter", "accountId": "acc1"}],
                publish_now=True,
            )

        url = mock_post.await_args.args[0]
        assert url.endswith("/posts")
        body = mock_post.await_args.kwargs["json"]
        assert body["content"] == "hello"
        assert body["publishNow"] is True
        assert body["timezone"] == "UTC"
        assert "scheduledFor" not in body
        assert "isDraft" not in body
        assert "mediaItems" not in body

    @pytest.mark.asyncio
    async def test_scheduled_with_media_and_hashtags(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(200, {"post": {"_id": "p2"}})
        ) as mock_post:
            await client.create_post(
                content="launch",
                platforms=[
                    {"platform": "instagram", "accountId": "ig1"},
                    {"platform": "linkedin", "accountId": "li1"},
                ],
                media_items=[{"type": "image", "url": "https://cdn.example/x.jpg"}],
                scheduled_for="2026-06-01T10:00:00Z",
                timezone="Europe/Istanbul",
                hashtags=["launch", "ai"],
                title="Big launch",
                tags=["product"],
            )

        body = mock_post.await_args.kwargs["json"]
        assert body["scheduledFor"] == "2026-06-01T10:00:00Z"
        assert body["timezone"] == "Europe/Istanbul"
        assert body["mediaItems"][0]["url"] == "https://cdn.example/x.jpg"
        assert body["hashtags"] == ["launch", "ai"]
        assert body["title"] == "Big launch"
        assert body["tags"] == ["product"]
        assert body["platforms"][0]["platform"] == "instagram"
        assert body["platforms"][1]["platform"] == "linkedin"
        assert "publishNow" not in body
        assert "isDraft" not in body

    @pytest.mark.asyncio
    async def test_draft_without_content_keeps_payload_minimal(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(200, {"post": {"_id": "p3", "status": "draft"}})
        ) as mock_post:
            await client.create_post(
                content=None,
                platforms=[{"platform": "twitter", "accountId": "acc1"}],
                is_draft=True,
            )

        body = mock_post.await_args.kwargs["json"]
        assert body["isDraft"] is True
        assert "content" not in body  # None must NOT be sent


class TestGetAndListPosts:
    @pytest.mark.asyncio
    async def test_get_post_hits_post_id_path(self):
        client = _client()
        with _patch_async_client(
            "get", _mock_response(200, {"post": {"_id": "abc"}})
        ) as mock_get:
            result = await client.get_post("abc")

        assert result["post"]["_id"] == "abc"
        url = mock_get.await_args.args[0]
        assert url.endswith("/posts/abc")

    @pytest.mark.asyncio
    async def test_list_posts_only_sends_set_filters(self):
        client = _client()
        with _patch_async_client(
            "get", _mock_response(200, {"posts": [], "pagination": {}})
        ) as mock_get:
            await client.list_posts(
                status="scheduled",
                platform="twitter",
                page=2,
                limit=25,
                sort_by="created-desc",
            )

        params = mock_get.await_args.kwargs["params"]
        assert params == {
            "page": 2,
            "limit": 25,
            "status": "scheduled",
            "platform": "twitter",
            "sortBy": "created-desc",
        }
        url = mock_get.await_args.args[0]
        assert url.endswith("/posts")


class TestRetryAndUnpublish:
    @pytest.mark.asyncio
    async def test_retry_post_posts_empty_body(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(200, {"message": "ok", "post": {"_id": "p9"}})
        ) as mock_post:
            await client.retry_post("p9")

        url = mock_post.await_args.args[0]
        assert url.endswith("/posts/p9/retry")
        assert mock_post.await_args.kwargs["json"] == {}

    @pytest.mark.asyncio
    async def test_unpublish_post_sends_platform(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(200, {"success": True, "message": "deleted"})
        ) as mock_post:
            await client.unpublish_post("p5", "twitter")

        url = mock_post.await_args.args[0]
        assert url.endswith("/posts/p5/unpublish")
        assert mock_post.await_args.kwargs["json"] == {"platform": "twitter"}

    @pytest.mark.asyncio
    async def test_unpublish_rejects_instagram_client_side(self):
        client = _client()
        with pytest.raises(ValueError, match="instagram"):
            await client.unpublish_post("p5", "instagram")

    @pytest.mark.asyncio
    async def test_unpublish_rejects_tiktok_client_side(self):
        client = _client()
        with pytest.raises(ValueError, match="tiktok"):
            await client.unpublish_post("p5", "tiktok")


# ---------------------------------------------------------------------------
# Media mixin
# ---------------------------------------------------------------------------


class TestPresignMedia:
    @pytest.mark.asyncio
    async def test_presign_sends_filename_and_content_type(self):
        client = _client()
        with _patch_async_client(
            "post",
            _mock_response(
                200,
                {
                    "uploadUrl": "https://upload.example/x",
                    "publicUrl": "https://media.zernio.com/x",
                    "key": "temp/x",
                    "type": "video",
                },
            ),
        ) as mock_post:
            result = await client.presign_media(
                "clip.mp4", "video/mp4", size=12345
            )

        assert result["publicUrl"].startswith("https://media.zernio.com")
        url = mock_post.await_args.args[0]
        assert url.endswith("/media/presign")
        body = mock_post.await_args.kwargs["json"]
        assert body == {
            "filename": "clip.mp4",
            "contentType": "video/mp4",
            "size": 12345,
        }

    @pytest.mark.asyncio
    async def test_presign_rejects_unknown_content_type(self):
        client = _client()
        with pytest.raises(ValueError, match="content_type"):
            await client.presign_media("x.heic", "image/heic")


class TestPresignSizeCap:
    @pytest.mark.asyncio
    async def test_presign_rejects_over_5gb(self):
        from src.infra.zernio.media import PRESIGN_MAX_BYTES

        client = _client()
        with pytest.raises(ValueError, match="5GB"):
            await client.presign_media("big.mp4", "video/mp4", size=PRESIGN_MAX_BYTES + 1)


class TestUploadMediaDirect:
    @pytest.mark.asyncio
    async def test_upload_direct_uses_multipart(self):
        client = _client()
        with _patch_async_client(
            "post",
            _mock_response(
                200,
                {
                    "url": "https://media.zernio.com/abc.jpg",
                    "filename": "abc.jpg",
                    "contentType": "image/jpeg",
                    "size": 1234,
                },
            ),
        ) as mock_post:
            result = await client.upload_media_direct(
                b"\xff\xd8\xff\xe0fakebytes",
                "abc.jpg",
                "image/jpeg",
            )

        assert result["url"].endswith("abc.jpg")
        kwargs = mock_post.await_args.kwargs
        # multipart goes through files/data, NOT json
        assert "json" not in kwargs
        assert "files" in kwargs
        assert kwargs["files"]["file"][0] == "abc.jpg"
        assert kwargs["files"]["file"][2] == "image/jpeg"
        assert kwargs["data"] == {"contentType": "image/jpeg"}
        # Auth header must NOT carry Content-Type: application/json for multipart
        headers = kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk_test_123"
        assert "Content-Type" not in headers
        url = mock_post.await_args.args[0]
        assert url.endswith("/media/upload-direct")

    @pytest.mark.asyncio
    async def test_upload_direct_rejects_over_25mb(self):
        from src.infra.zernio.media import DIRECT_UPLOAD_MAX_BYTES

        client = _client()
        big = b"\x00" * (DIRECT_UPLOAD_MAX_BYTES + 1)
        with pytest.raises(ValueError, match="25MB"):
            await client.upload_media_direct(big, "x.jpg", "image/jpeg")


# ---------------------------------------------------------------------------
# Base layer — error handling + multipart plumbing
# ---------------------------------------------------------------------------


class TestBaseErrorHandling:
    @pytest.mark.asyncio
    async def test_4xx_on_create_post_raises_service_error(self):
        from src.infra.errors import ServiceError

        client = _client()
        with _patch_async_client(
            "post", _mock_response(400, text_body="bad platform")
        ):
            with pytest.raises(ServiceError) as exc:
                await client.create_post(
                    content="x",
                    platforms=[{"platform": "twitter", "accountId": "a"}],
                    publish_now=True,
                )

        assert exc.value.status_code == 400
        assert exc.value.service == "zernio"

    @pytest.mark.asyncio
    async def test_5xx_on_get_post_raises_service_error(self):
        from src.infra.errors import ServiceError

        client = _client()
        with _patch_async_client(
            "get", _mock_response(503, text_body="upstream down")
        ):
            with pytest.raises(ServiceError) as exc:
                await client.get_post("abc")

        assert exc.value.status_code == 503

