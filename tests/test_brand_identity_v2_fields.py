"""Tests for Faz A2: BrandIdentity'e Seyma'nin listesinden eklenen 10
yeni alan. Tum yeni alanlar opsiyonel — geri uyum bozulmaz.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.infra.brand_identity import (
    BrandIdentity,
    BrandBasics,
    BrandVoice,
    BrandAudiencePrimary,
    BrandContentStrategy,
    BrandBusinessContext,
)


class TestBasicsKeywords:
    def test_keywords_default_empty(self):
        b = BrandBasics()
        assert b.keywords == []

    def test_keywords_accepts_list(self):
        b = BrandBasics(keywords=["yerel", "premium", "ai-destekli", "bodrum", "sezonluk"])
        assert len(b.keywords) == 5

    def test_keywords_max_length_10(self):
        with pytest.raises(ValidationError):
            BrandBasics(keywords=[f"k{i}" for i in range(11)])


class TestVoiceNewFields:
    def test_agent_role_optional(self):
        v = BrandVoice()
        assert v.agent_role is None

    def test_agent_role_set(self):
        v = BrandVoice(agent_role="Kidemli Copywriter")
        assert v.agent_role == "Kidemli Copywriter"

    def test_address_form_literal_valid(self):
        assert BrandVoice(address_form="siz").address_form == "siz"
        assert BrandVoice(address_form="sen").address_form == "sen"

    def test_address_form_literal_invalid(self):
        with pytest.raises(ValidationError):
            BrandVoice(address_form="biz")  # type: ignore

    def test_emoji_usage_literal(self):
        for v in ["bol", "az", "yok", "secili"]:
            assert BrandVoice(emoji_usage=v).emoji_usage == v
        with pytest.raises(ValidationError):
            BrandVoice(emoji_usage="cok")  # type: ignore

    def test_hook_style_freetext(self):
        v = BrandVoice(hook_style="kisa soru")
        assert v.hook_style == "kisa soru"

    def test_cta_templates_list(self):
        v = BrandVoice(cta_templates=["Profildeki linke tikla", "DM ile ulas"])
        assert len(v.cta_templates) == 2

    def test_cta_templates_max_10(self):
        with pytest.raises(ValidationError):
            BrandVoice(cta_templates=[f"cta {i}" for i in range(11)])

    def test_avoid_topics_list(self):
        v = BrandVoice(avoid_topics=["siyaset", "saglik"])
        assert v.avoid_topics == ["siyaset", "saglik"]


class TestAudienceNewFields:
    def test_gender_optional(self):
        p = BrandAudiencePrimary()
        assert p.gender is None

    def test_gender_set(self):
        assert BrandAudiencePrimary(gender="kadin").gender == "kadin"

    def test_ses_set(self):
        assert BrandAudiencePrimary(ses="A").ses == "A"

    def test_motivations_default_empty(self):
        p = BrandAudiencePrimary()
        assert p.motivations == []

    def test_motivations_list(self):
        p = BrandAudiencePrimary(motivations=["statu", "zaman tasarrufu"])
        assert len(p.motivations) == 2

    def test_motivations_max_10(self):
        with pytest.raises(ValidationError):
            BrandAudiencePrimary(motivations=[f"m{i}" for i in range(11)])


class TestContentStrategyRequiredHashtags:
    def test_required_hashtags_default(self):
        c = BrandContentStrategy()
        assert c.required_hashtags == []

    def test_required_hashtags_list(self):
        c = BrandContentStrategy(required_hashtags=["#SlowdaysAI", "#BodrumOtel"])
        assert "#SlowdaysAI" in c.required_hashtags

    def test_required_hashtags_max_10(self):
        with pytest.raises(ValidationError):
            BrandContentStrategy(required_hashtags=[f"#h{i}" for i in range(11)])


class TestBusinessContextPriceSegment:
    def test_price_segment_optional(self):
        b = BrandBusinessContext()
        assert b.price_segment is None

    def test_price_segment_valid_literals(self):
        for v in ["ekonomik", "orta", "premium", "luks"]:
            assert BrandBusinessContext(price_segment=v).price_segment == v

    def test_price_segment_invalid(self):
        with pytest.raises(ValidationError):
            BrandBusinessContext(price_segment="ucuz")  # type: ignore


class TestPromptSummaryIncludesNewFields:
    """prompt_summary() yeni alanlari hangi durumlarda yansitiyor?"""

    def _build(self, **kwargs) -> BrandIdentity:
        return BrandIdentity(business_id="t", **kwargs)

    def test_agent_role_appears(self):
        bi = self._build(voice=BrandVoice(agent_role="Kidemli Copywriter"))
        assert "Agent role: Kidemli Copywriter" in bi.prompt_summary()

    def test_keywords_appear(self):
        bi = self._build(basics=BrandBasics(keywords=["yerel", "premium"]))
        assert "Keywords: yerel, premium" in bi.prompt_summary()

    def test_address_form_appears(self):
        bi = self._build(voice=BrandVoice(address_form="siz"))
        assert "Address form: siz" in bi.prompt_summary()

    def test_emoji_usage_appears(self):
        bi = self._build(voice=BrandVoice(emoji_usage="az"))
        assert "Emoji usage: az" in bi.prompt_summary()

    def test_hook_style_appears(self):
        bi = self._build(voice=BrandVoice(hook_style="kisa soru"))
        assert "Hook style: kisa soru" in bi.prompt_summary()

    def test_cta_templates_appear(self):
        bi = self._build(voice=BrandVoice(cta_templates=["Profile bak", "DM at"]))
        s = bi.prompt_summary()
        assert "CTA templates" in s
        assert "Profile bak" in s
        assert "DM at" in s

    def test_avoid_topics_appear(self):
        bi = self._build(voice=BrandVoice(avoid_topics=["siyaset"]))
        assert "AVOID topics: siyaset" in bi.prompt_summary()

    def test_motivations_appear(self):
        from src.infra.brand_identity import BrandAudience
        bi = self._build(
            audience=BrandAudience(
                primary=BrandAudiencePrimary(role="Otel sahibi", motivations=["doluluk"])
            )
        )
        s = bi.prompt_summary()
        assert "Motivations: doluluk" in s

    def test_gender_ses_appear_in_audience(self):
        from src.infra.brand_identity import BrandAudience
        bi = self._build(
            audience=BrandAudience(
                primary=BrandAudiencePrimary(
                    role="Otel sahibi", age_range="28-58", gender="karma", ses="B"
                )
            )
        )
        s = bi.prompt_summary()
        assert "Otel sahibi" in s
        assert "28-58" in s
        assert "karma" in s
        assert "SES B" in s

    def test_price_segment_appears(self):
        bi = self._build(business_context=BrandBusinessContext(price_segment="premium"))
        assert "Price segment: premium" in bi.prompt_summary()

    def test_required_hashtags_appear(self):
        bi = self._build(
            content_strategy=BrandContentStrategy(
                required_hashtags=["#SlowdaysAI", "#Bodrum"]
            )
        )
        assert "Required hashtags: #SlowdaysAI #Bodrum" in bi.prompt_summary()


class TestBackwardsCompat:
    """Eski yazilmis brand_identity'ler hala valid mi?"""

    def test_minimal_brand_identity(self):
        bi = BrandIdentity(business_id="abc")
        assert bi.business_id == "abc"
        assert bi.basics.keywords == []
        assert bi.voice.agent_role is None
        assert bi.business_context.price_segment is None

    def test_old_payload_still_parses(self):
        """Faz A doneminden kalmis bir payload hala valid."""
        old = {
            "business_id": "abc",
            "schema_version": 1,
            "source": "manual",
            "basics": {"name": "X", "industry": "Y"},
            "voice": {"tone": "samimi"},
        }
        bi = BrandIdentity.model_validate(old)
        assert bi.basics.name == "X"
        assert bi.voice.tone == "samimi"
