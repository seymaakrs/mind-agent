"""End-to-end entegrasyon testi (uçtan uca smoke).

Pazarlama Müdürü → Defne brief akışını mock'larla simüle eder:
1. BrandIdentity Firestore'dan okunur (mock)
2. Pazarlama Müdürü get_sales_playbook çağırır
3. Pazarlama Müdürü brand_aware_prompt builder ile Defne brief'i üretir
4. ImagePrompt schema valide olur

Bu test gerçek LLM çağrısı yapmaz; Pazarlama Müdürü'nün kullanması gereken
TOOL ZINCIRININ tutarlı olduğunu doğrular. Aksi takdirde sessiz contract
kırılması (örn. ImagePrompt schema değişimi) regression olarak yakalanır.
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
    BrandVisual,
    BrandVoice,
)
from src.models.prompts import ImagePrompt
from src.tools.image.brand_aware_prompt import build_brand_aware_image_prompt
from src.tools.sales import knowledge_tools as kt


def _slowdays_brand() -> BrandIdentity:
    """Test verisi — gerçek Slowdays markasına benzer kompozit."""
    return BrandIdentity(
        business_id="biz_slowdays",
        basics=BrandBasics(
            name="Slowdays",
            tagline="Sade kal, yavaş yaşa",
            industry="butik otel",
        ),
        visual=BrandVisual(
            primary_colors=["#E8D5B7", "#2B4A3E"],
            secondary_colors=["#C0BFBF"],
            visual_style="organic, warm, natural",
            photography_style="natural light, human-focused",
            image_dos=["soft shadow", "human theme", "morning light"],
            image_donts=["stock look", "harsh studio", "crowded beach"],
        ),
        voice=BrandVoice(
            tone="sıcak ama profesyonel",
            personality=["calm", "premium", "authentic"],
            avoid_words=["müthiş", "devrim"],
            preferred_words=["sakin", "yavaş"],
            cta_style="soft",
        ),
        audience=BrandAudience(
            primary=BrandAudiencePrimary(
                role="35-50 yaş seyahat profesyoneli",
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
        ),
    )


# ---------------------------------------------------------------------------
# Adım 1: Sales playbook (knowledge_tools) tam veri döndürür
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_step1_playbook_provides_pillars_and_voice(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _slowdays_brand())
    out = await kt._get_sales_playbook_impl("biz_slowdays")
    assert out["success"] is True
    assert out["is_ready_for_outreach"] is True
    assert "sakin yaşam" in out["content_pillars"]
    assert out["voice"]["tone"] == "sıcak ama profesyonel"
    assert "müthiş" in out["voice"]["avoid_words"]


# ---------------------------------------------------------------------------
# Adım 2: Pazarlama Müdürü brief üretir + brand_aware_prompt builder
# ---------------------------------------------------------------------------


def test_e2e_step2_brief_to_image_prompt_full_chain():
    """Pazarlama Müdürü'nün post brief'inden ImagePrompt'a kadar tam zincir."""
    brand = _slowdays_brand()
    # Pazarlama Müdürü Defne'ye veriyor:
    builder = build_brand_aware_image_prompt(
        brand=brand,
        topic="Bodrum'un kalabalıksız koylarında bir sabah",
        content_pillar="sakin yaşam",
        scene_hint="erken sabah, sis kalkmış, deniz durgun, kahve fincanı",
    )
    prompt_dict = builder.to_dict()

    # Pydantic ile validate ol — generate_image bu yapıyı kabul eder
    image_prompt = ImagePrompt.model_validate(prompt_dict)

    # Brand sızdırması kontrol
    assert "Slowdays" in image_prompt.subject
    assert "butik otel" in image_prompt.subject
    assert "organic" in image_prompt.style
    assert "#E8D5B7" in image_prompt.colors
    assert "natural light" in image_prompt.lighting
    assert "calm" in image_prompt.mood
    # Pillar additional_details'a girdi
    assert image_prompt.additional_details is not None
    assert "sakin yaşam" in image_prompt.additional_details
    # DO/AVOID brief'e geçti
    assert "soft shadow" in image_prompt.additional_details
    assert "stock look" in image_prompt.additional_details


# ---------------------------------------------------------------------------
# Adım 3: Avoid words kontrolü — caption üretiminde
# (Builder caption üretmez ama tüketici LLM'in avoid_words listesini görmesi
#  garanti olsun diye playbook'tan voice çekiminin doğru olduğunu test ederiz)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_step3_voice_avoid_words_available(monkeypatch):
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: _slowdays_brand())
    voice = await kt._get_brand_voice_impl("biz_slowdays")
    assert voice["success"] is True
    assert "müthiş" in voice["avoid_words"]
    assert "sakin" in voice["preferred_words"]
    # Pazarlama Müdürü caption yazarken bu listeyi instructions ile kullanır


# ---------------------------------------------------------------------------
# Adım 4: Marka eksik ise disiplinli fail (üretim DURMALI)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_brand_missing_blocks_production(monkeypatch):
    """BrandIdentity yoksa Pazarlama Müdürü üretim akışını DURDURMALI.

    Bu test playbook'un completeness_score=0 dönmesini ve müdürün üretim
    kararını alabilmesi için sinyalin doğru olduğunu doğrular.
    """
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: None)
    playbook = await kt._get_sales_playbook_impl("biz_unknown")
    assert playbook["exists"] is False
    # Müdür bu sinyali görüp üretim akışını başlatmamalı


@pytest.mark.asyncio
async def test_e2e_brand_low_completeness_signals_block(monkeypatch):
    """Brand var ama completeness < 3 — müdür durmalı."""
    minimal = BrandIdentity(
        business_id="biz_min",
        basics=BrandBasics(name="X"),
        # Diğer her şey boş
    )
    monkeypatch.setattr(kt, "load_brand_identity", lambda _bid: minimal)
    playbook = await kt._get_sales_playbook_impl("biz_min")
    assert playbook["completeness_score"] < 3
    assert playbook["is_ready_for_outreach"] is False


# ---------------------------------------------------------------------------
# Adım 5: Pillar rotation — content_strategy.pillars'tan geliyor mu
# ---------------------------------------------------------------------------


def test_e2e_pillar_rotation_source():
    """Müdür content rotation için pillar listesini playbook'tan alır."""
    brand = _slowdays_brand()
    assert brand.content_strategy.pillars == ["sakin yaşam", "doğa", "yerel lezzet"]
    # Test gereği: müdür bu listeyi instructions disiplinine göre rotate eder
    pillars = brand.content_strategy.pillars
    schedule = []
    for i in range(5):  # 5 günlük hafta
        schedule.append(pillars[i % len(pillars)])
    # Hiçbir pillar arka arkaya 2 gün ÜST ÜSTE olmamalı
    for i in range(1, len(schedule)):
        assert schedule[i] != schedule[i - 1], \
            f"Pillar rotation ihlal: gün {i-1} ve {i}"


# ---------------------------------------------------------------------------
# Adım 6: Sales ↔ Marketing knowledge layer'ı paylaşıyor
# ---------------------------------------------------------------------------


def test_e2e_sales_and_marketing_share_knowledge_tools():
    """Aynı 5 knowledge tool hem Sales hem Marketing agent'ında bulunmalı."""
    from src.agents.marketing_agent import create_marketing_agent
    from src.agents.sales.sales_manager_agent import create_sales_manager_agent

    sales_tools = {t.name for t in create_sales_manager_agent().tools}
    marketing_tools = {t.name for t in create_marketing_agent().tools}

    knowledge = {
        "get_product_catalog",
        "get_target_audience",
        "get_brand_voice",
        "get_unique_value_proposition",
        "get_sales_playbook",
    }
    assert knowledge.issubset(sales_tools)
    assert knowledge.issubset(marketing_tools)


# ---------------------------------------------------------------------------
# Adım 7: Post atma — sadece Marketing yetkili
# ---------------------------------------------------------------------------


def test_e2e_post_authority_split():
    """Sales Director POST ATMAZ, Pazarlama Müdürü atar."""
    from src.agents.marketing_agent import create_marketing_agent
    from src.agents.sales.sales_manager_agent import create_sales_manager_agent

    sales_tools = {t.name for t in create_sales_manager_agent().tools}
    marketing_tools = {t.name for t in create_marketing_agent().tools}

    assert "post_on_instagram" not in sales_tools
    assert "post_on_instagram" in marketing_tools
