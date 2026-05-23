"""brand_aware_prompt builder testleri.

Deterministik helper — LLM yok. Brand identity + brief -> ImagePrompt dict.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.infra.brand_identity import (
    BrandBasics,
    BrandIdentity,
    BrandVisual,
    BrandVoice,
)
from src.tools.image.brand_aware_prompt import (
    BrandAwareImagePromptBuilder,
    build_brand_aware_image_prompt,
)


def _full_brand() -> BrandIdentity:
    return BrandIdentity(
        business_id="biz_full",
        basics=BrandBasics(name="Slowdays", industry="butik otel"),
        visual=BrandVisual(
            primary_colors=["#E8D5B7", "#2B4A3E"],
            secondary_colors=["#C0BFBF"],
            visual_style="organic, warm, natural",
            photography_style="natural light, human-focused",
            image_dos=["soft shadow", "human theme"],
            image_donts=["stock look", "harsh studio"],
        ),
        voice=BrandVoice(
            personality=["calm", "premium", "authentic"],
        ),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_topic_raises():
    with pytest.raises(ValueError):
        build_brand_aware_image_prompt(brand=None, topic="")


def test_whitespace_topic_raises():
    with pytest.raises(ValueError):
        build_brand_aware_image_prompt(brand=None, topic="   ")


# ---------------------------------------------------------------------------
# Brand olmadan (fallback) çalışma
# ---------------------------------------------------------------------------


def test_no_brand_returns_fallback():
    out = build_brand_aware_image_prompt(brand=None, topic="bir konu").to_dict()
    assert out["style"]
    assert out["lighting"]
    assert out["colors"] == ["#FFFFFF", "#000000"]
    assert "bir konu" in out["subject"]


def test_no_brand_no_additional_details_unless_pillar():
    out = build_brand_aware_image_prompt(brand=None, topic="konu").to_dict()
    assert "additional_details" not in out


def test_no_brand_pillar_appears_in_details():
    out = build_brand_aware_image_prompt(
        brand=None, topic="konu", content_pillar="sakin yaşam"
    ).to_dict()
    assert "Content pillar: sakin yaşam" in out["additional_details"]


# ---------------------------------------------------------------------------
# Brand ile (happy path)
# ---------------------------------------------------------------------------


def test_brand_style_used():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="Bodrum sabahı"
    ).to_dict()
    assert out["style"] == "organic, warm, natural"


def test_brand_lighting_uses_photography_style():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="konu"
    ).to_dict()
    assert "natural light" in out["lighting"]


def test_brand_colors_primary_plus_secondary():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="konu"
    ).to_dict()
    # Pydantic hex validator hepsini upper'lar — primary_colors test fixture
    # zaten upper olarak gönderiyor.
    assert "#E8D5B7" in out["colors"]
    assert "#2B4A3E" in out["colors"]
    assert "#C0BFBF" in out["colors"]  # secondary
    assert len(out["colors"]) <= 6


def test_brand_subject_includes_brand_name_and_industry():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="sakin sabah"
    ).to_dict()
    assert "Slowdays" in out["subject"]
    assert "butik otel" in out["subject"]
    assert "sakin sabah" in out["subject"]


def test_brand_mood_from_personality():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="konu"
    ).to_dict()
    assert "calm" in out["mood"]
    assert "premium" in out["mood"]


def test_brand_image_dos_and_donts_in_additional():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(), topic="konu", content_pillar="sakin yaşam"
    ).to_dict()
    details = out["additional_details"]
    assert "Content pillar: sakin yaşam" in details
    assert "DO: soft shadow" in details
    assert "AVOID (DO NOT): stock look" in details


def test_scene_hint_used_when_provided():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(),
        topic="konu",
        scene_hint="early morning fog over still sea",
    ).to_dict()
    assert "early morning fog" in out["scene"]
    # subject de scene_hint'i içerir
    assert "early morning fog" in out["subject"]


def test_composition_hint_used():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(),
        topic="konu",
        composition_hint="diagonal lines, off-center subject",
    ).to_dict()
    assert "diagonal lines" in out["composition"]


def test_text_elements_passed_through():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(),
        topic="konu",
        text_elements="YENİ SEZON",
    ).to_dict()
    assert out["text_elements"] == "YENİ SEZON"


def test_extra_details_appended():
    out = build_brand_aware_image_prompt(
        brand=_full_brand(),
        topic="konu",
        content_pillar="doğa",
        extra_details="9:16 vertical for stories",
    ).to_dict()
    assert "9:16 vertical" in out["additional_details"]


# ---------------------------------------------------------------------------
# Output ImagePrompt'a uyumlu mu? (Pydantic validation)
# ---------------------------------------------------------------------------


def test_output_validates_as_image_prompt():
    """Builder çıktısı ImagePrompt Pydantic model'iyle valide olmalı."""
    from src.models.prompts import ImagePrompt

    out = build_brand_aware_image_prompt(
        brand=_full_brand(),
        topic="sakin sabah",
        content_pillar="sakin yaşam",
    ).to_dict()
    # Bu çağrı raise etmiyorsa schema uyumlu demektir.
    ImagePrompt.model_validate(out)
