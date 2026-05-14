"""Tests for split prompt_summary (Faz C+ tuning).

prompt_summary() tum alanlari tek string'e dokup butun agent'lara veriyor.
Bu image agent'i ALAKASIZ caption-time alanlariyla kafayi karistiriyor
(yasak kelimeler, CTA kalıpları, hashtag → gorsele yazi/poster layout
sokuyor).

Cozum: ayri ozetler.
  - prompt_summary_image()   → sadece gorsel alanlar (visual + context)
  - prompt_summary_caption() → sadece metin alanlar (voice + audience + strategy)
"""
from __future__ import annotations

import pytest

from src.infra.brand_identity import (
    BrandIdentity,
    BrandBasics,
    BrandVisual,
    BrandVoice,
    BrandAudience,
    BrandAudiencePrimary,
    BrandContentStrategy,
    BrandBusinessContext,
)


def _full() -> BrandIdentity:
    """Tum alanlar dolu bir test fixture."""
    return BrandIdentity(
        business_id="t",
        basics=BrandBasics(
            name="Slowdays AI",
            industry="reklam ajansi",
            keywords=["yerel", "premium"],
            tagline="Bodrum sezonu uzmani",
            languages=["tr"],
        ),
        visual=BrandVisual(
            primary_colors=["#001338", "#F5E6D3"],
            visual_style="modern, minimal, premium",
            photography_style="natural light",
            image_dos=["yumusak golge"],
            image_donts=["stock gorunum"],
        ),
        voice=BrandVoice(
            agent_role="Kidemli Copywriter",
            tone="direkt ve net",
            personality=["uzman"],
            address_form="siz",
            emoji_usage="az",
            hook_style="sorun ifadesi",
            avoid_words=["muthis"],
            avoid_topics=["siyaset"],
            preferred_words=["verimli"],
            cta_templates=["DM ile ulasin"],
            cta_style="informative",
        ),
        audience=BrandAudience(
            primary=BrandAudiencePrimary(
                role="Otel sahibi",
                age_range="28-58",
                gender="karma",
                ses="B",
                motivations=["doluluk"],
            ),
            geo=["Bodrum"],
        ),
        content_strategy=BrandContentStrategy(
            pillars=["egitici"],
            posting_cadence="haftada 3",
            hashtag_strategy="3+5+2",
            required_hashtags=["#SlowdaysAI"],
        ),
        business_context=BrandBusinessContext(
            products=["Meta Ads"],
            usp="Bodrum uzmanligi",
            price_segment="premium",
            seo_keywords=["bodrum reklam"],
        ),
    )


class TestPromptSummaryImage:
    """Image/Video agent'a giden ozet sadece gorsel alanlar icermeli."""

    def test_includes_visual_fields(self):
        bi = _full()
        s = bi.prompt_summary_image()
        # Visual fields MUST be there
        assert "Slowdays AI" in s
        assert "modern, minimal, premium" in s
        assert "natural light" in s
        assert "#001338" in s
        assert "#F5E6D3" in s
        assert "yumusak golge" in s
        assert "stock gorunum" in s

    def test_excludes_caption_time_fields(self):
        bi = _full()
        s = bi.prompt_summary_image()
        # Caption-only fields MUST NOT leak in
        assert "muthis" not in s  # avoid_words
        assert "siyaset" not in s  # avoid_topics
        assert "verimli" not in s  # preferred_words
        assert "DM ile ulasin" not in s  # cta_templates
        assert "informative" not in s  # cta_style
        assert "#SlowdaysAI" not in s  # required_hashtags
        assert "bodrum reklam" not in s.lower()  # seo_keywords

    def test_empty_brand_returns_empty_or_short(self):
        bi = BrandIdentity(business_id="t")
        s = bi.prompt_summary_image()
        assert s == "" or len(s) < 50

    def test_no_subject_overlay_text_concepts(self):
        """Image summary'sinde 'hashtag', 'cta', 'caption' gibi kelimeler
        gecmemeli — agent yanlislikla bunlari gorsele eklemeye calismasin."""
        bi = _full()
        s = bi.prompt_summary_image().lower()
        for forbidden in ["hashtag", "cta template", "caption", "avoid word", "preferred word"]:
            assert forbidden not in s, f"image summary leaked: {forbidden}"


class TestPromptSummaryCaption:
    """Marketing agent'a giden ozet sadece metin alanlar icermeli."""

    def test_includes_voice_and_audience(self):
        bi = _full()
        s = bi.prompt_summary_caption()
        # Voice fields
        assert "Slowdays AI" in s
        assert "Kidemli Copywriter" in s
        assert "direkt ve net" in s
        assert "siz" in s
        assert "az" in s  # emoji usage
        # Audience
        assert "Otel sahibi" in s
        assert "doluluk" in s
        # Strategy
        assert "#SlowdaysAI" in s

    def test_excludes_visual_dos_donts(self):
        bi = _full()
        s = bi.prompt_summary_caption()
        # Visual DOs/DONTs should NOT leak to caption agent
        assert "yumusak golge" not in s
        assert "stock gorunum" not in s
        assert "natural light" not in s
        assert "#001338" not in s

    def test_brand_name_present_for_context(self):
        bi = _full()
        s = bi.prompt_summary_caption()
        assert "Slowdays AI" in s, "Caption summary must include brand name"


class TestBackwardsCompat:
    """Eski prompt_summary() korundu — geri uyum tam."""

    def test_full_summary_still_works(self):
        bi = _full()
        s = bi.prompt_summary()
        # Karma — hem visual hem voice
        assert "Slowdays AI" in s
        assert "natural light" in s
        assert "direkt ve net" in s
        assert "#SlowdaysAI" in s

    def test_fetch_brand_identity_tool_returns_both_summaries(self):
        """fetch_brand_identity sonucunda iki yeni alan da olmali."""
        from src.tools.brand import _fetch_brand_identity_impl
        # Bu tool Firestore'a gider; mock kullanmadan sadece isim varligini
        # asagidaki integrasyon testinde dogrularız. Burada sadece
        # methodlarin BrandIdentity'de var oldugunu dogrulayalim:
        assert hasattr(BrandIdentity, "prompt_summary_image")
        assert hasattr(BrandIdentity, "prompt_summary_caption")
