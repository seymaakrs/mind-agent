"""Brand Identity — kanonik marka kimligi sema (2026-05-12).

Mevcut ``businesses/{id}.profile`` yapisiz dynamic map idi. Image/Video/
Marketing agentlari farkli field'lar okuyor, schema yoktu, marka uyumu
olculemez idi.

Bu modul **standart Pydantic schema** sunuyor: tum agentlar ayni alanlari
okur, validation type-safe, kullanici netlestiremedikleri alanlari `None`
birakabilir. Tum agent prompt'lari bu kanonik objeyi referans alacak.

Storage:
  Firestore path: ``businesses/{business_id}/brand_identity/v1``
  (subcollection — eski ``profile`` field aynen kalir, geri uyum icin)

Sema versiyonu artiyorsa yeni dokuman: ``brand_identity/v2``. Migration
fonksiyonu eski v'den yeni v'ye gecis yapar (henuz v1 oldugu icin yok).

Kullanim:
    from src.infra.brand_identity import BrandIdentity, load_brand_identity

    bi = load_brand_identity("abc123")
    if bi:
        prompt = f"Brand: {bi.basics.name}. Voice: {bi.voice.tone}..."

Tum field'lar opsiyonel — bos brand_identity legal, ama o zaman content
agentlari "rehbersiz" calisir (fallback olarak businesses doc kullanir).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Schema versiyonu — her kirici degisiklikte +1
BRAND_IDENTITY_SCHEMA_VERSION: int = 1


# ---------------------------------------------------------------------------
# Alt modeller — her bir "boyut" ayri (basics, visual, voice, ...)
# ---------------------------------------------------------------------------


class BrandBasics(BaseModel):
    """Temel marka bilgisi — ilk acilan, en az soyleyebilecegimiz."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, description="Marka ismi")
    tagline: str | None = Field(default=None, description="Kisa slogan / mottu")
    industry: str | None = Field(
        default=None,
        description="Sektor (orn. 'B2B SaaS', 'butik otel', 'guzellik salonu')",
    )
    founded_year: int | None = Field(
        default=None, ge=1900, le=2100, description="Kurulus yili"
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Marka dilleri ISO 639-1 (orn. ['tr', 'en'])",
    )

    @field_validator("languages")
    @classmethod
    def _lowercase_langs(cls, v: list[str]) -> list[str]:
        return [s.lower().strip() for s in v if s]


class BrandVisual(BaseModel):
    """Gorsel kimlik — Image/Video Agent burayi prompt builder'da kullanir."""
    model_config = ConfigDict(extra="forbid")

    primary_colors: list[str] = Field(
        default_factory=list,
        description="Ana marka renkleri (hex). En cok 5.",
        max_length=5,
    )
    secondary_colors: list[str] = Field(
        default_factory=list,
        description="Yardimci renkler (hex). En cok 8.",
        max_length=8,
    )
    logo_url: str | None = Field(
        default=None, description="Cloud Storage URL (gs:// or https://)"
    )
    font_family: str | None = Field(
        default=None, description="Birincil font (orn. 'Inter', 'Playfair')"
    )
    visual_style: str | None = Field(
        default=None,
        description=(
            "Gorsel stil kelime-cumlesi (orn. 'modern, minimal, tech-forward' "
            "veya 'sicak, organik, dogal')"
        ),
    )
    photography_style: str | None = Field(
        default=None,
        description=(
            "Fotograf yonergesi (orn. 'dogal isik, insan odakli' veya "
            "'studyo, urun close-up')"
        ),
    )
    image_dos: list[str] = Field(
        default_factory=list,
        description="YAPILAR (orn. 'yumusak golge', 'insan teması')",
    )
    image_donts: list[str] = Field(
        default_factory=list,
        description="YASAKLAR (orn. 'stock gorunum', 'asiri parlak', 'klise ofis')",
    )

    @field_validator("primary_colors", "secondary_colors")
    @classmethod
    def _validate_hex_colors(cls, v: list[str]) -> list[str]:
        import re
        hex_re = re.compile(r"^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3}([0-9A-Fa-f]{2})?)?$")
        for c in v:
            if not isinstance(c, str) or not hex_re.match(c):
                raise ValueError(f"Color must be hex (#RGB / #RRGGBB / #RRGGBBAA): {c}")
        return [c.upper() for c in v]


CtaStyle = Literal["soft", "hard", "quirky", "informative"]


class BrandVoice(BaseModel):
    """Yazili kimlik — Marketing Agent caption uretirken kullanir."""
    model_config = ConfigDict(extra="forbid")

    tone: str | None = Field(
        default=None,
        description="Tek cumle ton tanimi (orn. 'samimi ama profesyonel')",
    )
    personality: list[str] = Field(
        default_factory=list,
        description="Kisilik etiketleri (orn. ['uzman', 'yardimsever', 'esprili'])",
        max_length=8,
    )
    avoid_words: list[str] = Field(
        default_factory=list,
        description=(
            "Yasak kelime/ifadeler (orn. 'devrim niteliginde', 'muthis'). "
            "LLM post-check ile bunlari uretmesini engeller."
        ),
    )
    preferred_words: list[str] = Field(
        default_factory=list,
        description="Tercih edilen kelimeler (orn. 'guclu', 'verimli')",
    )
    example_captions: list[str] = Field(
        default_factory=list,
        description="2-5 ornek caption (few-shot prompting icin)",
        max_length=10,
    )
    cta_style: CtaStyle | None = Field(
        default=None,
        description=(
            "soft = 'detaylar profilde' | hard = 'simdi kayit ol' | "
            "quirky = creative ironic | informative = ders verir tarzi"
        ),
    )


class BrandAudiencePrimary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(default=None, description="Hedef rol (orn. 'Pazarlama yoneticisi')")
    age_range: str | None = Field(default=None, description="Yas araligi (orn. '28-45')")
    pain_points: list[str] = Field(
        default_factory=list,
        description="Acilari (orn. ['zaman yok', 'ajans pahali'])",
        max_length=10,
    )


class BrandAudience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: BrandAudiencePrimary | None = Field(default=None)
    geo: list[str] = Field(
        default_factory=list,
        description="Cografi hedef (orn. ['TR', 'Istanbul', 'Bodrum'])",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Konusulan diller (ISO 639-1)",
    )

    @field_validator("languages")
    @classmethod
    def _lowercase_langs(cls, v: list[str]) -> list[str]:
        return [s.lower().strip() for s in v if s]


class BrandContentStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pillars: list[str] = Field(
        default_factory=list,
        description="Icerik konu sutunlari (orn. ['egitici', 'sosyal kanit'])",
        max_length=6,
    )
    posting_cadence: str | None = Field(
        default=None,
        description="Yayinlama tempo (orn. 'haftada 3-5 post', 'gunde 1')",
    )
    hashtag_strategy: str | None = Field(
        default=None,
        description=(
            "Hashtag yaklasimi (orn. '5 large + 5 niche + 2 branded' veya "
            "'sadece 3 mikro-niche')"
        ),
    )


class BrandBusinessContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    products: list[str] = Field(
        default_factory=list,
        description="Urun/hizmet listesi",
    )
    usp: str | None = Field(
        default=None,
        description="Unique Selling Proposition (rakipten farkli olan sey)",
    )
    competitors: list[str] = Field(
        default_factory=list,
        description="Rakip markalar (kavramsal)",
    )
    seo_keywords: list[str] = Field(
        default_factory=list,
        description="SEO anahtar kelimeler (Marketing Agent caption'a sikistirir)",
    )


# ---------------------------------------------------------------------------
# Ust seviye Brand Identity dokumani
# ---------------------------------------------------------------------------


class BrandIdentity(BaseModel):
    """Tek kanonik marka kimligi obje. Tum agent'lar bunu okur.

    Tum alt-objeler opsiyonel — bos brand_identity legal. Field'i `None`
    olanlari content agent'lari "rehbersiz" sayar; prompt builder fallback
    yapar (orn. eski ``businesses.profile`` field).
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(
        default=BRAND_IDENTITY_SCHEMA_VERSION,
        description="Sema versiyonu — migration icin",
    )
    business_id: str = Field(..., description="Firestore document id")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Son guncelleme",
    )
    source: Literal["manual", "ai_synthesis", "imported", "draft"] = Field(
        default="manual",
        description=(
            "manual = kullanici eli ile doldurdu; ai_synthesis = Brand "
            "Synthesis Agent draft; imported = eski profile'dan migration; "
            "draft = kullanici onayi bekliyor"
        ),
    )

    basics: BrandBasics = Field(default_factory=BrandBasics)
    visual: BrandVisual = Field(default_factory=BrandVisual)
    voice: BrandVoice = Field(default_factory=BrandVoice)
    audience: BrandAudience = Field(default_factory=BrandAudience)
    content_strategy: BrandContentStrategy = Field(
        default_factory=BrandContentStrategy
    )
    business_context: BrandBusinessContext = Field(
        default_factory=BrandBusinessContext
    )

    # ---- Yardimci metodlar -------------------------------------------------

    def is_substantially_filled(self) -> bool:
        """Brand identity 'kullanilabilir' seviyede dolu mu?

        Minimum kriter: basics.name + (visual.primary_colors VEYA voice.tone).
        Agent'lar bu False ise eski profile fallback'i kullanmali.
        """
        if not self.basics.name:
            return False
        has_visual = bool(self.visual.primary_colors)
        has_voice = bool(self.voice.tone)
        return has_visual or has_voice

    def prompt_summary(self, max_chars: int = 600) -> str:
        """Image/Video/Marketing agent prompt'larina enjekte edilecek
        kompakt brand summary. ``None``/bos alanlari atlar."""
        parts: list[str] = []

        if self.basics.name:
            line = f"Brand: {self.basics.name}"
            if self.basics.industry:
                line += f" ({self.basics.industry})"
            parts.append(line)

        if self.basics.tagline:
            parts.append(f"Tagline: {self.basics.tagline}")

        if self.visual.visual_style:
            parts.append(f"Visual style: {self.visual.visual_style}")

        if self.visual.photography_style:
            parts.append(f"Photography: {self.visual.photography_style}")

        if self.visual.primary_colors:
            parts.append(
                f"Primary colors: {', '.join(self.visual.primary_colors)}"
            )

        if self.visual.image_dos:
            parts.append(f"DO: {', '.join(self.visual.image_dos)}")

        if self.visual.image_donts:
            parts.append(f"DON'T: {', '.join(self.visual.image_donts)}")

        if self.voice.tone:
            parts.append(f"Voice tone: {self.voice.tone}")

        if self.voice.personality:
            parts.append(f"Personality: {', '.join(self.voice.personality)}")

        if self.voice.avoid_words:
            parts.append(
                f"AVOID words: {', '.join(self.voice.avoid_words)}"
            )

        if self.voice.preferred_words:
            parts.append(
                f"Prefer words: {', '.join(self.voice.preferred_words)}"
            )

        if self.audience.primary and self.audience.primary.role:
            aud = f"Audience: {self.audience.primary.role}"
            if self.audience.primary.age_range:
                aud += f" ({self.audience.primary.age_range})"
            parts.append(aud)

        summary = " | ".join(parts)
        if len(summary) > max_chars:
            return summary[: max_chars - 3] + "..."
        return summary


__all__ = [
    "BRAND_IDENTITY_SCHEMA_VERSION",
    "BrandIdentity",
    "BrandBasics",
    "BrandVisual",
    "BrandVoice",
    "BrandAudience",
    "BrandAudiencePrimary",
    "BrandContentStrategy",
    "BrandBusinessContext",
    "CtaStyle",
]
