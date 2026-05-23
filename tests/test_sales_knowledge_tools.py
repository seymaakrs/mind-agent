"""Sales knowledge tools — ürün/hedef-kitle/ses/USP/playbook read testleri.

Pattern: src/tools/brand/load_brand_identity mock'lanır, tool _impl
fonksiyonları doğrudan await edilir.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.infra.brand_identity import (
    BrandAudience,
    BrandAudiencePrimary,
    BrandBasics,
    BrandBusinessContext,
    BrandContentStrategy,
    BrandIdentity,
    BrandVoice,
)
from src.tools.sales import knowledge_tools as kt


def _full_brand(business_id: str = "biz_full") -> BrandIdentity:
    """Tam dolu örnek brand — happy path testleri için."""
    return BrandIdentity(
        business_id=business_id,
        basics=BrandBasics(
            name="Slowdays",
            tagline="Sade kal, yavaş yaşa",
            industry="butik otel",
        ),
        voice=BrandVoice(
            tone="sıcak ama profesyonel",
            personality=["uzman", "yardımsever"],
            avoid_words=["müthiş", "devrim"],
            preferred_words=["güçlü", "verimli"],
            cta_style="soft",
        ),
        audience=BrandAudience(
            primary=BrandAudiencePrimary(
                role="35-50 yaş seyahat seven profesyonel",
                age_range="35-50",
                pain_points=["aşırı kalabalık", "klişe oteller"],
            ),
            geo=["TR", "Bodrum"],
            languages=["tr", "en"],
        ),
        content_strategy=BrandContentStrategy(
            pillars=["sakin yaşam", "doğa", "yerel lezzet"],
        ),
        business_context=BrandBusinessContext(
            products=["3-gece konaklama paketi", "yoga retreat"],
            usp="Bodrum'da kalabalıktan uzak 8 odalı tek otel",
            competitors=["Maçakızı", "Mandarin Oriental"],
            seo_keywords=["bodrum butik otel", "sakin tatil"],
        ),
    )


# ---------------------------------------------------------------------------
# Validation: business_id zorunlu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "impl",
    [
        kt._get_product_catalog_impl,
        kt._get_target_audience_impl,
        kt._get_brand_voice_impl,
        kt._get_unique_value_proposition_impl,
        kt._get_sales_playbook_impl,
    ],
)
@pytest.mark.asyncio
async def test_empty_business_id_rejected(impl):
    out = await impl("")
    assert out["success"] is False
    assert "business_id" in out["error"]


@pytest.mark.parametrize(
    "impl",
    [
        kt._get_product_catalog_impl,
        kt._get_target_audience_impl,
        kt._get_brand_voice_impl,
        kt._get_unique_value_proposition_impl,
        kt._get_sales_playbook_impl,
    ],
)
@pytest.mark.asyncio
async def test_whitespace_business_id_rejected(impl):
    out = await impl("   ")
    assert out["success"] is False


# ---------------------------------------------------------------------------
# Brand identity yok → exists=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_brand_identity_returns_exists_false(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: None)
    out = await kt._get_product_catalog_impl("biz_x")
    assert out["success"] is True
    assert out["exists"] is False
    assert "tanımlanmamış" in out["summary_tr"]


@pytest.mark.asyncio
async def test_missing_brand_all_tools(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: None)
    for impl in (
        kt._get_target_audience_impl,
        kt._get_brand_voice_impl,
        kt._get_unique_value_proposition_impl,
        kt._get_sales_playbook_impl,
    ):
        out = await impl("biz_x")
        assert out["exists"] is False, f"{impl.__name__} should report exists=False"


# ---------------------------------------------------------------------------
# Happy path: tam dolu brand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_catalog_happy(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _full_brand())
    out = await kt._get_product_catalog_impl("biz_full")
    assert out["success"] is True
    assert out["exists"] is True
    assert out["has_product_data"] is True
    assert out["brand_name"] == "Slowdays"
    assert out["industry"] == "butik otel"
    assert "3-gece konaklama paketi" in out["products"]
    assert "Bodrum" in out["usp"]
    assert "Slowdays" in out["summary_tr"]


@pytest.mark.asyncio
async def test_target_audience_happy(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _full_brand())
    out = await kt._get_target_audience_impl("biz_full")
    assert out["has_audience_data"] is True
    assert out["age_range"] == "35-50"
    assert "aşırı kalabalık" in out["pain_points"]
    assert "TR" in out["geo"]


@pytest.mark.asyncio
async def test_brand_voice_happy(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _full_brand())
    out = await kt._get_brand_voice_impl("biz_full")
    assert out["has_voice_data"] is True
    assert out["tone"] == "sıcak ama profesyonel"
    assert "müthiş" in out["avoid_words"]
    assert out["cta_style"] == "soft"


@pytest.mark.asyncio
async def test_uvp_happy(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _full_brand())
    out = await kt._get_unique_value_proposition_impl("biz_full")
    assert out["has_uvp_data"] is True
    assert out["tagline"] == "Sade kal, yavaş yaşa"
    assert "Maçakızı" in out["competitors"]
    assert "sakin yaşam" in out["content_pillars"]


@pytest.mark.asyncio
async def test_sales_playbook_happy(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _full_brand())
    out = await kt._get_sales_playbook_impl("biz_full")
    assert out["success"] is True
    assert out["completeness_score"] == 5
    assert out["is_ready_for_outreach"] is True
    assert out["brand_name"] == "Slowdays"
    assert out["audience"]["age_range"] == "35-50"
    assert out["voice"]["tone"] == "sıcak ama profesyonel"


# ---------------------------------------------------------------------------
# Edge case: brand identity var ama tüm alt-alanlar boş
# ---------------------------------------------------------------------------


def _empty_brand() -> BrandIdentity:
    return BrandIdentity(business_id="biz_empty")


@pytest.mark.asyncio
async def test_empty_brand_product_catalog(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _empty_brand())
    out = await kt._get_product_catalog_impl("biz_empty")
    assert out["exists"] is True
    assert out["has_product_data"] is False
    assert "uydurma" in out["summary_tr"]


@pytest.mark.asyncio
async def test_empty_brand_playbook(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _empty_brand())
    out = await kt._get_sales_playbook_impl("biz_empty")
    assert out["completeness_score"] == 0
    assert out["is_ready_for_outreach"] is False
    assert "eksik" in out["summary_tr"]


# ---------------------------------------------------------------------------
# Registry / factory
# ---------------------------------------------------------------------------


def test_get_knowledge_tools_returns_5_tools():
    tools = kt.get_knowledge_tools()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "get_product_catalog",
        "get_target_audience",
        "get_brand_voice",
        "get_unique_value_proposition",
        "get_sales_playbook",
    }
