"""Tests for the PublisherClient adapter layer (Faz 2).

Three coverage axes:

1. PublishResult dataclass — shape + serialization.
2. LatePublisher — delegates to LateClient and normalizes the dict.
3. ZernioPublisher — builds the canonical /v1/posts payload and
   normalizes the response.
4. Factory — env var + explicit-arg precedence.

The tool layer is not exercised here. It will be in Faz 3.
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
    return patch.object(httpx.AsyncClient, method, new=AsyncMock(return_value=response))


# Sample successful response from /v1/posts (mirrors Zernio + Late shape).
SUCCESS_POST = {
    "post": {
        "_id": "p_123",
        "status": "published",
        "platforms": [
            {
                "platform": "instagram",
                "status": "published",
                "platformPostId": "ig_abc",
                "platformPostUrl": "https://instagram.com/p/abc",
            }
        ],
    }
}


# ---------------------------------------------------------------------------
# PublishResult
# ---------------------------------------------------------------------------


class TestPublishResult:
    def test_to_dict_success_omits_error_fields(self):
        from src.infra.publisher import PublishResult

        r = PublishResult(
            success=True,
            post_id="p1",
            platform_post_id="ig1",
            platform_post_url="https://ig/p/1",
            status="published",
            type="image",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["post_id"] == "p1"
        assert d["platform_post_id"] == "ig1"
        assert d["type"] == "image"
        assert "error" not in d
        assert "status_code" not in d

    def test_to_dict_failure_includes_error(self):
        from src.infra.publisher import PublishResult

        r = PublishResult(
            success=False,
            error="bad request",
            status_code=400,
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "bad request"
        assert d["status_code"] == 400


# ---------------------------------------------------------------------------
# ZernioPublisher
# ---------------------------------------------------------------------------


def _zernio_publisher(account_id: str = "acc_ig"):
    """Build a ZernioPublisher with ZERNIO_API_KEY stubbed."""
    os.environ.setdefault("ZERNIO_API_KEY", "sk_test")
    from src.infra.publisher import ZernioPublisher

    return ZernioPublisher(account_id=account_id)


class TestZernioInstagram:
    @pytest.mark.asyncio
    async def test_post_image_publish_now(self):
        pub = _zernio_publisher()
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            result = await pub.instagram_post(
                media_url="https://cdn/x.jpg",
                caption="hello",
                media_type="image",
            )

        assert result.success is True
        assert result.post_id == "p_123"
        assert result.platform_post_id == "ig_abc"
        assert result.platform_post_url == "https://instagram.com/p/abc"
        assert result.status == "published"
        assert result.type == "image"

        body = mock_post.await_args.kwargs["json"]
        assert body["content"] == "hello"
        assert body["publishNow"] is True
        assert body["mediaItems"] == [{"type": "image", "url": "https://cdn/x.jpg"}]
        assert body["platforms"] == [
            {"platform": "instagram", "accountId": "acc_ig"}
        ]

    @pytest.mark.asyncio
    async def test_post_story_overrides_content_and_sets_story_flag(self):
        pub = _zernio_publisher()
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            result = await pub.instagram_post(
                media_url="https://cdn/x.mp4",
                caption="ignored for stories",
                media_type="video",
                is_story=True,
                first_comment="should_be_ignored_for_stories",
            )

        assert result.type == "story"
        body = mock_post.await_args.kwargs["json"]
        assert body["content"] == "."  # caption replaced
        psd = body["platforms"][0]["platformSpecificData"]
        assert psd == {"contentType": "story"}  # no firstComment on stories

    @pytest.mark.asyncio
    async def test_video_with_thumbnail_and_first_comment(self):
        pub = _zernio_publisher()
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            await pub.instagram_post(
                media_url="https://cdn/r.mp4",
                caption="hi",
                media_type="video",
                thumbnail_url="https://cdn/t.jpg",
                first_comment="boom",
            )
        body = mock_post.await_args.kwargs["json"]
        psd = body["platforms"][0]["platformSpecificData"]
        assert psd["firstComment"] == "boom"
        assert psd["instagramThumbnail"] == "https://cdn/t.jpg"

    @pytest.mark.asyncio
    async def test_carousel_validates_size(self):
        pub = _zernio_publisher()
        r = await pub.instagram_carousel(
            media_items=[{"url": "u1", "type": "image"}], caption="x"
        )
        assert r.success is False
        assert "2-10" in r.error

    @pytest.mark.asyncio
    async def test_carousel_payload(self):
        pub = _zernio_publisher()
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            r = await pub.instagram_carousel(
                media_items=[
                    {"url": "https://cdn/a.jpg", "type": "image"},
                    {"url": "https://cdn/b.jpg", "type": "image"},
                ],
                caption="multi",
                first_comment="thanks!",
            )
        assert r.success is True
        assert r.type == "carousel"
        assert r.item_count == 2
        body = mock_post.await_args.kwargs["json"]
        assert len(body["mediaItems"]) == 2
        assert body["platforms"][0]["platformSpecificData"] == {"firstComment": "thanks!"}


class TestZernioTikTok:
    @pytest.mark.asyncio
    async def test_video_uses_top_level_tiktok_settings(self):
        pub = _zernio_publisher(account_id="acc_tt")
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            await pub.tiktok_video(
                video_url="https://cdn/v.mp4",
                content="hi",
                privacy_level="PUBLIC_TO_EVERYONE",
                allow_duet=False,
                video_made_with_ai=True,
            )

        body = mock_post.await_args.kwargs["json"]
        assert "tiktokSettings" in body
        s = body["tiktokSettings"]
        assert s["privacyLevel"] == "PUBLIC_TO_EVERYONE"
        assert s["allowDuet"] is False
        assert s["allowStitch"] is True  # default
        assert s["videoMadeWithAi"] is True
        assert s["mediaType"] == "video"
        assert s["contentPreviewConfirmed"] is True
        # platformSpecificData should NOT carry tt settings (top-level only)
        assert "platformSpecificData" not in body["platforms"][0]

    @pytest.mark.asyncio
    async def test_carousel_uses_photo_media_type(self):
        pub = _zernio_publisher(account_id="acc_tt")
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            await pub.tiktok_carousel(
                media_items=[
                    {"url": "https://cdn/a.jpg", "type": "image"},
                    {"url": "https://cdn/b.jpg", "type": "image"},
                ],
                content="hi",
                privacy_level="PUBLIC_TO_EVERYONE",
                description="long desc",
                photo_cover_index=1,
                auto_add_music=True,
            )

        body = mock_post.await_args.kwargs["json"]
        s = body["tiktokSettings"]
        assert s["mediaType"] == "photo"
        assert s["description"] == "long desc"
        assert s["photoCoverIndex"] == 1
        assert s["autoAddMusic"] is True


class TestZernioLinkedIn:
    @pytest.mark.asyncio
    async def test_post_with_org_urn_and_first_comment(self):
        pub = _zernio_publisher(account_id="acc_li")
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            await pub.linkedin_post(
                content="hi",
                media_url="https://cdn/x.jpg",
                media_type="image",
                first_comment="thanks",
                organization_urn="urn:li:organization:123",
                disable_link_preview=True,
            )
        body = mock_post.await_args.kwargs["json"]
        assert body["content"] == "hi"
        psd = body["platforms"][0]["platformSpecificData"]
        assert psd["firstComment"] == "thanks"
        assert psd["organizationUrn"] == "urn:li:organization:123"
        assert psd["disableLinkPreview"] is True

    @pytest.mark.asyncio
    async def test_carousel_rejects_single_item(self):
        pub = _zernio_publisher(account_id="acc_li")
        r = await pub.linkedin_carousel(
            media_items=[{"url": "u1", "type": "image"}], content="x"
        )
        assert r.success is False
        assert "2-20" in r.error


class TestZernioYouTube:
    @pytest.mark.asyncio
    async def test_youtube_passes_psd_and_tags_and_thumbnail(self):
        pub = _zernio_publisher(account_id="acc_yt")
        with _patch_async_client("post", _mock_response(200, SUCCESS_POST)) as mock_post:
            await pub.youtube_video(
                video_url="https://cdn/v.mp4",
                title="My Video",
                description="long desc",
                visibility="unlisted",
                made_for_kids=False,
                tags=["foo", "bar"],
                thumbnail_url="https://cdn/t.jpg",
                first_comment="pinned",
            )
        body = mock_post.await_args.kwargs["json"]
        assert body["content"] == "long desc"
        assert body["tags"] == ["foo", "bar"]
        item = body["mediaItems"][0]
        assert item["thumbnail"] == {"url": "https://cdn/t.jpg"}
        psd = body["platforms"][0]["platformSpecificData"]
        assert psd["title"] == "My Video"
        assert psd["visibility"] == "unlisted"
        assert psd["madeForKids"] is False
        assert psd["firstComment"] == "pinned"


class TestZernioErrorPath:
    @pytest.mark.asyncio
    async def test_4xx_returns_failed_publish_result(self):
        pub = _zernio_publisher()
        with _patch_async_client("post", _mock_response(400, text_body="bad")):
            r = await pub.instagram_post(
                media_url="u", caption="x", media_type="image"
            )
        assert r.success is False
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# LatePublisher (delegates to LateClient)
# ---------------------------------------------------------------------------


def _late_client_stub(method_name: str, return_value: dict):
    """Patch the relevant method on LateClient instances created via get_late_client."""
    # We patch get_late_client to return a MagicMock whose method returns the dict.
    fake_client = MagicMock()
    setattr(fake_client, method_name, AsyncMock(return_value=return_value))
    return patch("src.infra.late.get_late_client", return_value=fake_client), fake_client


class TestLatePublisherDelegates:
    @pytest.mark.asyncio
    async def test_instagram_post_delegates_to_post_media(self):
        ctx, fake = _late_client_stub("post_media", {
            "success": True,
            "post_id": "p1",
            "platform_post_id": "ig1",
            "platform_post_url": "https://ig/p/1",
            "status": "published",
            "type": "image",
        })
        with ctx:
            # Need to re-import so the patched factory is used at construction.
            from src.infra.publisher import LatePublisher

            pub = LatePublisher(account_id="acc_ig")
            r = await pub.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

        assert r.success is True
        assert r.post_id == "p1"
        assert r.platform_post_id == "ig1"
        assert r.type == "image"
        fake.post_media.assert_awaited_once_with(
            media_url="u",
            caption="c",
            media_type="image",
            thumbnail_url=None,
            first_comment=None,
            is_story=False,
        )

    @pytest.mark.asyncio
    async def test_late_failure_dict_becomes_failed_publish_result(self):
        ctx, _ = _late_client_stub("post_media", {
            "success": False,
            "error": "boom",
            "status_code": 502,
        })
        with ctx:
            from src.infra.publisher import LatePublisher

            pub = LatePublisher(account_id="acc_ig")
            r = await pub.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

        assert r.success is False
        assert r.error == "boom"
        assert r.status_code == 502


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestZernioAnalytics:
    @pytest.mark.asyncio
    async def test_list_mode_normalizes_id_field_and_wraps_success(self):
        pub = _zernio_publisher(account_id="prof_x")
        raw = {
            "overview": {"impressions": 100},
            "posts": [
                {"_id": "p_1", "analytics": {"likes": 5}},
                {"postId": "p_2", "_id": "ignored", "analytics": {"likes": 3}},
            ],
            "pagination": {"total": 2, "page": 1, "limit": 50, "totalPages": 1},
        }
        with _patch_async_client("get", _mock_response(200, raw)) as mock_get:
            r = await pub.get_analytics(profile_id="prof_x")

        assert r["success"] is True
        assert r["overview"] == {"impressions": 100}
        assert r["posts"][0]["postId"] == "p_1"  # injected from _id
        assert r["posts"][1]["postId"] == "p_2"  # preserved
        params = mock_get.await_args.kwargs["params"]
        assert params["profileId"] == "prof_x"
        assert params["platform"] == "instagram"

    @pytest.mark.asyncio
    async def test_single_post_mode_wraps_in_post_envelope(self):
        pub = _zernio_publisher(account_id="prof_x")
        raw = {
            "postId": "p_1",
            "latePostId": None,
            "status": "published",
            "analytics": {"impressions": 1000, "engagementRate": 2.5},
        }
        with _patch_async_client("get", _mock_response(200, raw)) as mock_get:
            r = await pub.get_analytics(profile_id="prof_x", post_id="p_1")

        assert r["success"] is True
        assert r["post"]["postId"] == "p_1"
        assert r["post"]["analytics"]["engagementRate"] == 2.5
        params = mock_get.await_args.kwargs["params"]
        assert params["postId"] == "p_1"
        # profile filter NOT sent when querying single post
        assert "profileId" not in params

    @pytest.mark.asyncio
    async def test_error_returns_failed_envelope(self):
        pub = _zernio_publisher(account_id="prof_x")
        with _patch_async_client("get", _mock_response(403, text_body="forbidden")):
            r = await pub.get_analytics(profile_id="prof_x")
        assert r["success"] is False
        assert r["status_code"] == 403


class TestLatePublisherAnalytics:
    @pytest.mark.asyncio
    async def test_get_analytics_uses_strip_prefix_false(self):
        """Analytics path must call get_late_client with strip_prefix=False."""
        fake_client = MagicMock()
        fake_client.get_analytics = AsyncMock(
            return_value={"success": True, "posts": [], "pagination": {}}
        )
        with patch(
            "src.infra.late.get_late_client", return_value=fake_client
        ) as mock_factory:
            from src.infra.publisher import LatePublisher

            pub = LatePublisher(account_id="prof_raw")
            await pub.get_analytics(profile_id="prof_raw_2")

        # First call: __init__ with default strip_prefix=True
        # Second call: get_analytics with strip_prefix=False AND override profile_id
        analytics_calls = [c for c in mock_factory.call_args_list
                           if c.kwargs.get("strip_prefix") is False]
        assert len(analytics_calls) == 1
        assert analytics_calls[0].args[0] == "prof_raw_2"


class TestProtocolConformance:
    """Both adapters must satisfy the runtime_checkable PublisherClient."""

    def test_late_publisher_is_publisher_client(self):
        from src.infra.publisher import LatePublisher, PublisherClient

        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = LatePublisher(account_id="acc_x")
        assert isinstance(pub, PublisherClient)

    def test_zernio_publisher_is_publisher_client(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test")
        from src.infra.publisher import PublisherClient, ZernioPublisher

        pub = ZernioPublisher(account_id="acc_x")
        assert isinstance(pub, PublisherClient)

    def test_both_publishers_expose_same_method_set(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test")
        from src.infra.publisher import LatePublisher, ZernioPublisher

        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            late_methods = {m for m in dir(LatePublisher) if not m.startswith("_")}
        zernio_methods = {m for m in dir(ZernioPublisher) if not m.startswith("_")}
        # The intersection must contain every publish-surface method.
        required = {
            "instagram_post",
            "instagram_carousel",
            "linkedin_post",
            "linkedin_carousel",
            "tiktok_video",
            "tiktok_carousel",
            "youtube_video",
            "backend",
        }
        assert required.issubset(late_methods)
        assert required.issubset(zernio_methods)


class TestFactory:
    def test_default_backend_is_late(self, monkeypatch):
        from src.infra.publisher import LatePublisher, get_publisher

        monkeypatch.delenv("PUBLISHER_BACKEND", raising=False)
        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x")
        assert isinstance(pub, LatePublisher)
        assert pub.backend == "late"

    def test_env_var_selects_zernio(self, monkeypatch):
        from src.infra.publisher import ZernioPublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_BACKEND", "zernio")
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test")
        pub = get_publisher("acc_x")
        assert isinstance(pub, ZernioPublisher)
        assert pub.backend == "zernio"

    def test_explicit_arg_overrides_env(self, monkeypatch):
        from src.infra.publisher import LatePublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_BACKEND", "zernio")
        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x", backend="late")
        assert isinstance(pub, LatePublisher)

    def test_unknown_env_falls_back_to_default(self, monkeypatch):
        from src.infra.publisher import LatePublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_BACKEND", "rabid_squirrel")
        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x")
        assert isinstance(pub, LatePublisher)
