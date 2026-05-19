"""Tests for src.infra.brand_identity Pydantic schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.infra.brand_identity import (
    BRAND_IDENTITY_SCHEMA_VERSION,
    BrandAudience,
    BrandAudiencePrimary,
    BrandBasics,
    BrandBusinessContext,
    BrandContentStrategy,
    BrandIdentity,
    BrandVisual,
    BrandVoice,
)


class TestBrandBasics:
    def test_empty_valid(self):
        b = BrandBasics()
        assert b.name is None
        assert b.languages == []

    def test_languages_lowercased(self):
        b = BrandBasics(languages=["TR", "  EN  "])
        assert b.languages == ["tr", "en"]

    def test_founded_year_bounds(self):
        with pytest.raises(ValidationError):
            BrandBasics(founded_year=1800)
        with pytest.raises(ValidationError):
            BrandBasics(founded_year=3000)
        # Within bounds
        BrandBasics(founded_year=2024)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            BrandBasics(unknown_field="x")  # type: ignore[call-arg]


class TestBrandVisual:
    def test_hex_colors_uppercased(self):
        v = BrandVisual(primary_colors=["#c1ff72", "#221F5F"])
        assert v.primary_colors == ["#C1FF72", "#221F5F"]

    def test_invalid_hex_rejected(self):
        with pytest.raises(ValidationError):
            BrandVisual(primary_colors=["red"])
        with pytest.raises(ValidationError):
            BrandVisual(primary_colors=["#GGGGGG"])  # invalid length OK but not hex
        with pytest.raises(ValidationError):
            BrandVisual(primary_colors=["#12"])  # too short

    def test_primary_color_max_5(self):
        with pytest.raises(ValidationError):
            BrandVisual(primary_colors=["#000"] * 6)

    def test_short_hex_allowed(self):
        v = BrandVisual(primary_colors=["#FFF"])
        assert v.primary_colors == ["#FFF"]


class TestBrandVoice:
    def test_cta_style_validation(self):
        BrandVoice(cta_style="soft")
        BrandVoice(cta_style="hard")
        with pytest.raises(ValidationError):
            BrandVoice(cta_style="aggressive")  # type: ignore[arg-type]

    def test_personality_max_8(self):
        with pytest.raises(ValidationError):
            BrandVoice(personality=["x"] * 9)

    def test_avoid_words_list(self):
        v = BrandVoice(avoid_words=["devrim niteliginde", "muthis"])
        assert "muthis" in v.avoid_words


class TestBrandAudience:
    def test_primary_optional(self):
        a = BrandAudience()
        assert a.primary is None

    def test_pain_points_max_10(self):
        with pytest.raises(ValidationError):
            BrandAudiencePrimary(pain_points=["x"] * 11)


class TestBrandIdentity:
    def test_empty_identity_valid(self):
        bi = BrandIdentity(business_id="abc123")
        assert bi.schema_version == BRAND_IDENTITY_SCHEMA_VERSION
        assert bi.source == "manual"
        assert bi.is_substantially_filled() is False

    def test_substantially_filled_with_name_and_colors(self):
        bi = BrandIdentity(
            business_id="abc",
            basics=BrandBasics(name="Mind-id"),
            visual=BrandVisual(primary_colors=["#000000"]),
        )
        assert bi.is_substantially_filled() is True

    def test_substantially_filled_with_name_and_voice(self):
        bi = BrandIdentity(
            business_id="abc",
            basics=BrandBasics(name="Mind-id"),
            voice=BrandVoice(tone="samimi"),
        )
        assert bi.is_substantially_filled() is True

    def test_not_substantially_filled_without_name(self):
        bi = BrandIdentity(
            business_id="abc",
            visual=BrandVisual(primary_colors=["#000000"]),
        )
        assert bi.is_substantially_filled() is False

    def test_business_id_required(self):
        with pytest.raises(ValidationError):
            BrandIdentity()  # type: ignore[call-arg]

    def test_source_enum(self):
        BrandIdentity(business_id="x", source="ai_synthesis")
        with pytest.raises(ValidationError):
            BrandIdentity(business_id="x", source="wrong")  # type: ignore[arg-type]


class TestPromptSummary:
    def test_empty_returns_empty(self):
        bi = BrandIdentity(business_id="x")
        assert bi.prompt_summary() == ""

    def test_full_summary_has_key_parts(self):
        bi = BrandIdentity(
            business_id="x",
            basics=BrandBasics(
                name="Mind-id", tagline="AI içerik", industry="B2B SaaS"
            ),
            visual=BrandVisual(
                primary_colors=["#C1FF72"],
                visual_style="modern, minimal",
                image_donts=["stock"],
            ),
            voice=BrandVoice(
                tone="samimi ama profesyonel",
                avoid_words=["devrim niteliginde"],
            ),
        )
        s = bi.prompt_summary()
        assert "Mind-id" in s
        assert "B2B SaaS" in s
        assert "modern, minimal" in s
        assert "#C1FF72" in s
        assert "DON'T: stock" in s
        assert "samimi ama profesyonel" in s
        assert "devrim niteliginde" in s

    def test_truncation_at_max_chars(self):
        bi = BrandIdentity(
            business_id="x",
            basics=BrandBasics(name="X"),
            voice=BrandVoice(tone="t" * 1000),
        )
        s = bi.prompt_summary(max_chars=100)
        assert len(s) == 100
        assert s.endswith("...")

    def test_skips_none_fields(self):
        bi = BrandIdentity(
            business_id="x",
            basics=BrandBasics(name="Mind-id"),
        )
        s = bi.prompt_summary()
        # Sadece name var, hicbir secondary alan eklenmemeli
        assert s == "Brand: Mind-id"


class TestSerialization:
    def test_to_dict_roundtrip(self):
        bi = BrandIdentity(
            business_id="abc",
            basics=BrandBasics(name="X"),
            visual=BrandVisual(primary_colors=["#FFF"]),
        )
        data = bi.model_dump()
        assert data["business_id"] == "abc"
        assert data["basics"]["name"] == "X"
        assert data["visual"]["primary_colors"] == ["#FFF"]

        bi2 = BrandIdentity.model_validate(data)
        assert bi2.business_id == "abc"
        assert bi2.basics.name == "X"

    def test_schema_version_persisted(self):
        bi = BrandIdentity(business_id="x")
        data = bi.model_dump()
        assert data["schema_version"] == BRAND_IDENTITY_SCHEMA_VERSION
