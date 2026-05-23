"""Brand-aware image prompt builder.

2026-05-22 (Şeyma isteği): Defne (image_agent) Pazarlama Müdürü'nden gelen
brief'i ve BrandIdentity'i alıp deterministik şekilde ImagePrompt-uyumlu
yapıya çevirir. Pure Python — LLM çağrısı YOK.

Neden deterministik?
- Maliyet: Defne tek LLM round'unda hem brand_identity okuyor hem
  ImagePrompt üretiyor. Bu helper LLM yükünü azaltır.
- Tutarlılık: Aynı brand + brief = aynı temel iskelet. LLM sadece sahne/
  konu yaratıcılığını yapar.
- Test edilebilir: deterministik fonksiyon = unit test'le sıkı garanti.

Kullanım:
    from src.tools.image import build_brand_aware_image_prompt
    from src.tools.brand import load_brand_identity

    bi = load_brand_identity("biz_x")
    prompt = build_brand_aware_image_prompt(
        brand=bi,
        topic="Bodrum'da sakin bir sabah",
        content_pillar="sakin yaşam",
        scene_hint="erken sabah, sis kalkmış, durgun deniz",
    )
    # prompt -> ImagePrompt-uyumlu dict
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.infra.brand_identity import BrandIdentity


# Brand identity yoksa veya alan boşsa kullanılacak güvenli generic varsayılanlar.
# Bunlar "marka kimliği yok" durumunda en az zararlı seçim — generic foto stil.
_FALLBACK_STYLE = "modern, clean, professional photography"
_FALLBACK_MOOD = "calm, inviting, premium feel"
_FALLBACK_LIGHTING = "natural soft light, warm tones"
_FALLBACK_BACKGROUND = "clean minimal backdrop, subtle gradient"
_FALLBACK_COLORS = ["#FFFFFF", "#000000"]


@dataclass
class BrandAwareImagePromptBuilder:
    """ImagePrompt yapısına dönüşecek konfigürasyon.

    Test edilebilir, immutable yapı. `to_dict()` ile ImagePrompt-uyumlu
    dict döner — generate_image bu dict'i Pydantic ile validate eder.
    """
    scene: str
    subject: str
    style: str
    colors: list[str]
    mood: str
    composition: str
    lighting: str
    background: str
    text_elements: str | None
    additional_details: str | None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "scene": self.scene,
            "subject": self.subject,
            "style": self.style,
            "colors": list(self.colors),
            "mood": self.mood,
            "composition": self.composition,
            "lighting": self.lighting,
            "background": self.background,
        }
        if self.text_elements:
            d["text_elements"] = self.text_elements
        if self.additional_details:
            d["additional_details"] = self.additional_details
        return d


def _safe_join(items: list[str], sep: str = ", ", limit: int = 5) -> str:
    """En fazla `limit` adet, virgülle ayrılmış."""
    return sep.join(items[:limit])


def _resolve_style(brand: BrandIdentity | None) -> str:
    if brand and brand.visual.visual_style:
        return brand.visual.visual_style
    return _FALLBACK_STYLE


def _resolve_lighting(brand: BrandIdentity | None) -> str:
    """photography_style varsa onu lighting ipucu olarak kullan."""
    if brand and brand.visual.photography_style:
        return brand.visual.photography_style
    return _FALLBACK_LIGHTING


def _resolve_colors(brand: BrandIdentity | None) -> list[str]:
    if not brand:
        return list(_FALLBACK_COLORS)
    palette: list[str] = list(brand.visual.primary_colors)
    palette.extend(brand.visual.secondary_colors)
    if not palette:
        return list(_FALLBACK_COLORS)
    # En fazla 6 renk — ImagePrompt'taki tipik palette boyutu.
    return palette[:6]


def _resolve_additional_details(
    brand: BrandIdentity | None,
    user_extras: str | None,
    content_pillar: str | None,
) -> str | None:
    """DOs + DONTs + pillar etiketi + kullanıcı extras."""
    parts: list[str] = []
    if content_pillar:
        parts.append(f"Content pillar: {content_pillar}")
    if brand:
        if brand.visual.image_dos:
            parts.append("DO: " + _safe_join(brand.visual.image_dos, limit=6))
        if brand.visual.image_donts:
            parts.append("AVOID (DO NOT): " + _safe_join(brand.visual.image_donts, limit=6))
    if user_extras:
        parts.append(user_extras)
    return " | ".join(parts) if parts else None


def _resolve_subject(
    brand: BrandIdentity | None,
    topic: str,
    scene_hint: str | None,
) -> str:
    """subject = ana özne tanımı. Topic + (varsa) brand isim/sektör."""
    bits: list[str] = []
    if brand and brand.basics.name:
        bits.append(f"For brand '{brand.basics.name}'")
        if brand.basics.industry:
            bits[-1] += f" ({brand.basics.industry})"
    bits.append(topic.strip())
    if scene_hint:
        bits.append(scene_hint.strip())
    return ". ".join(bits)


def _resolve_mood(brand: BrandIdentity | None) -> str:
    """voice.personality'den mood çıkar; yoksa fallback."""
    if brand and brand.voice.personality:
        # personality kelimelerini mood'a çevir
        return _safe_join(brand.voice.personality, limit=4) + " feel"
    return _FALLBACK_MOOD


def build_brand_aware_image_prompt(
    brand: BrandIdentity | None,
    topic: str,
    *,
    content_pillar: str | None = None,
    scene_hint: str | None = None,
    composition_hint: str | None = None,
    text_elements: str | None = None,
    extra_details: str | None = None,
) -> BrandAwareImagePromptBuilder:
    """Brand + brief -> ImagePrompt-uyumlu builder.

    Args:
        brand: BrandIdentity (None ise fallback generic stil).
        topic: Postun konusu (zorunlu, boş olamaz).
        content_pillar: İçerik sütunu (örn. "sakin yaşam").
        scene_hint: Sahne tasviri (örn. "erken sabah, sis kalkmış").
        composition_hint: Kompozisyon ipucu (örn. "rule of thirds, leading lines").
        text_elements: Görsele yerleştirilecek metin (örn. "Yeni sezon" headline).
        extra_details: Ekstra detaylar.

    Returns:
        BrandAwareImagePromptBuilder

    Raises:
        ValueError: topic boş ise.
    """
    if not topic or not topic.strip():
        raise ValueError("topic is required (non-empty)")

    style = _resolve_style(brand)
    lighting = _resolve_lighting(brand)
    colors = _resolve_colors(brand)
    mood = _resolve_mood(brand)
    additional = _resolve_additional_details(brand, extra_details, content_pillar)
    subject = _resolve_subject(brand, topic, scene_hint)

    scene = (
        scene_hint.strip()
        if scene_hint
        else f"A scene depicting: {topic.strip()}"
    )

    composition = (
        composition_hint.strip()
        if composition_hint
        else "Balanced composition with clear focal point, rule of thirds placement"
    )

    background = _FALLBACK_BACKGROUND
    # Brand'in visual_style'ı "outdoor" / "studio" gibi bir ipucu içerirse
    # background fallback yerine onu kullanmak istersek -> ileri faz. Şimdilik
    # background = studio fallback. Brand image_dos zaten additional_details'a
    # giriyor; LLM nihai sahne kararını orada görüyor.

    return BrandAwareImagePromptBuilder(
        scene=scene,
        subject=subject,
        style=style,
        colors=colors,
        mood=mood,
        composition=composition,
        lighting=lighting,
        background=background,
        text_elements=text_elements,
        additional_details=additional,
    )


__all__ = [
    "build_brand_aware_image_prompt",
    "BrandAwareImagePromptBuilder",
]
