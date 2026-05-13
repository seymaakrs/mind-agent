"""Interaktif CLI: brand_identity'i elle doldur ve Firestore'a yaz.

Kullanim:
    python scripts/fill_brand_identity.py <business_id>
    python scripts/fill_brand_identity.py             # business_id'yi sorar

Cloud Shell'de Firebase credentials zaten ortamda (FIREBASE_CREDENTIALS_FILE
veya gcloud auth) olmali. Firestore'a `source='manual'` kaynagiyla yazar
— Synthesis Agent bu alanlarin uzerine yazmaz.

Tasarim notu:
  - Her alan icin Enter = bos/None gecerli (zorunlu alan yok).
  - Listeler virgulle ayrilarak girilir.
  - Hex renk regex ile dogrulanir, geversiz hata kullaniciya gosterilir.
  - Literal (cta_style) icin numaralı menu.
  - Final ozet + onay; onay vermezsen Firestore'a yazilmaz.
"""
from __future__ import annotations

import re
import sys
from typing import Any, Callable


# Repo kokunden import edilebilsin diye sys.path ayari
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.infra.brand_identity import (  # noqa: E402
    BRAND_IDENTITY_SCHEMA_VERSION,
    BrandIdentity,
    BrandBasics,
    BrandVisual,
    BrandVoice,
    BrandAudience,
    BrandAudiencePrimary,
    BrandContentStrategy,
    BrandBusinessContext,
)
from src.tools.brand import (  # noqa: E402
    load_brand_identity,
    save_brand_identity,
)


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3}([0-9A-Fa-f]{2})?)?$")
CTA_CHOICES = ["soft", "hard", "quirky", "informative"]
ADDRESS_CHOICES = ["siz", "sen"]
EMOJI_CHOICES = ["bol", "az", "yok", "secili"]
PRICE_CHOICES = ["ekonomik", "orta", "premium", "luks"]


def _ask(prompt: str, default: str | None = None) -> str | None:
    """Tek deger sorar. Bos input → None."""
    suffix = f" [{default}]" if default else " (Enter=atla)"
    raw = input(f"  {prompt}{suffix}: ").strip()
    if not raw:
        return default
    return raw


def _ask_list(prompt: str, default: list[str] | None = None) -> list[str]:
    """Virgulle ayrilmis liste. Bos → mevcut/default."""
    shown = ", ".join(default) if default else ""
    suffix = f" [{shown}]" if shown else " (virgulle ayir, Enter=bos)"
    raw = input(f"  {prompt}{suffix}: ").strip()
    if not raw:
        return list(default or [])
    return [s.strip() for s in raw.split(",") if s.strip()]


def _ask_hex_list(prompt: str, default: list[str] | None = None) -> list[str]:
    """Hex renk listesi. Gecersiz renk varsa tekrar sorar."""
    while True:
        values = _ask_list(prompt, default)
        invalid = [c for c in values if not HEX_RE.match(c)]
        if invalid:
            print(f"  ! Hex degil: {invalid}. Format: #RGB / #RRGGBB / #RRGGBBAA. Tekrar dene.")
            continue
        return [c.upper() for c in values]


def _ask_int(prompt: str, default: int | None = None, lo: int = 1900, hi: int = 2100) -> int | None:
    raw = _ask(prompt, str(default) if default else None)
    if not raw:
        return None
    try:
        v = int(raw)
        if v < lo or v > hi:
            print(f"  ! {lo}-{hi} arasi olmali. Atladim.")
            return None
        return v
    except ValueError:
        print(f"  ! Sayi degil: {raw!r}. Atladim.")
        return None


def _ask_literal(prompt: str, choices: list[str], default: str | None = None) -> str | None:
    print(f"  {prompt}:")
    for i, c in enumerate(choices, 1):
        marker = " (default)" if c == default else ""
        print(f"    {i}) {c}{marker}")
    print("    0) atla")
    raw = input("    secim: ").strip()
    if not raw or raw == "0":
        return default
    try:
        idx = int(raw)
        if 1 <= idx <= len(choices):
            return choices[idx - 1]
    except ValueError:
        pass
    print(f"  ! Gecersiz secim, atladim.")
    return default


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def _fill_basics(existing: BrandBasics) -> BrandBasics:
    _section("BASICS — temel marka bilgisi")
    return BrandBasics(
        name=_ask("Marka adi", existing.name),
        tagline=_ask("Slogan/mottu", existing.tagline),
        industry=_ask("Sektor (orn. 'butik otel', 'B2B SaaS')", existing.industry),
        founded_year=_ask_int("Kurulus yili", existing.founded_year),
        languages=_ask_list("Diller (ISO 639-1, orn. tr, en)", existing.languages),
        keywords=_ask_list("Markayi tanimlayan 5 anahtar kelime", existing.keywords),
    )


def _fill_visual(existing: BrandVisual) -> BrandVisual:
    _section("VISUAL — gorsel kimlik (Image/Video Agent burayi kullanir)")
    return BrandVisual(
        primary_colors=_ask_hex_list("Ana renkler (hex)", existing.primary_colors),
        secondary_colors=_ask_hex_list("Yardimci renkler (hex)", existing.secondary_colors),
        logo_url=_ask("Logo URL (gs:// veya https://)", existing.logo_url),
        font_family=_ask("Birincil font (orn. 'Inter', 'Playfair')", existing.font_family),
        visual_style=_ask("Gorsel stil (orn. 'modern, minimal, premium')", existing.visual_style),
        photography_style=_ask("Fotograf yonergesi (orn. 'dogal isik, insan odakli')", existing.photography_style),
        image_dos=_ask_list("Image DOs (orn. yumusak golge, insan teması)", existing.image_dos),
        image_donts=_ask_list("Image DON'Ts (orn. stock gorunum, klise ofis)", existing.image_donts),
    )


def _fill_voice(existing: BrandVoice) -> BrandVoice:
    _section("VOICE — yazili kimlik (Marketing Agent caption icin)")
    return BrandVoice(
        agent_role=_ask("Agent rolu (orn. 'Kidemli Copywriter')", existing.agent_role),
        tone=_ask("Ton (tek cumle, orn. 'samimi ama profesyonel')", existing.tone),
        personality=_ask_list("Kisilik etiketleri (orn. uzman, yardimsever, esprili)", existing.personality),
        address_form=_ask_literal("Hitap sekli", ADDRESS_CHOICES, existing.address_form),
        emoji_usage=_ask_literal("Emoji kullanim tarzi", EMOJI_CHOICES, existing.emoji_usage),
        hook_style=_ask("Hook stili (orn. 'kisa soru', 'iddiali aciklama')", existing.hook_style),
        avoid_words=_ask_list("Yasak kelimeler (orn. devrim niteliginde, muthis)", existing.avoid_words),
        avoid_topics=_ask_list("Yasakli konular (orn. siyaset, rakip X)", existing.avoid_topics),
        preferred_words=_ask_list("Tercih edilen kelimeler", existing.preferred_words),
        cta_templates=_ask_list("Gercek CTA kaliplari (orn. 'Profildeki linke tikla')", existing.cta_templates),
        example_captions=_ask_list("Ornek caption'lar (virgulle ayir)", existing.example_captions),
        cta_style=_ask_literal("CTA stili (genel)", CTA_CHOICES, existing.cta_style),
    )


def _fill_audience(existing: BrandAudience) -> BrandAudience:
    _section("AUDIENCE — hedef kitle")
    prim = existing.primary or BrandAudiencePrimary()
    primary = BrandAudiencePrimary(
        role=_ask("Birincil hedef rol (orn. 'Pazarlama yoneticisi')", prim.role),
        age_range=_ask("Yas araligi (orn. '28-45')", prim.age_range),
        gender=_ask("Cinsiyet (kadin/erkek/karma)", prim.gender),
        ses=_ask("SES (A/B/C1/orta-ust)", prim.ses),
        pain_points=_ask_list("Aci noktalari", prim.pain_points),
        motivations=_ask_list("Motivasyonlar (orn. statu, zaman tasarrufu)", prim.motivations),
    )
    # primary'i sadece icinde bir sey varsa kaydet
    if not any([
        primary.role, primary.age_range, primary.gender, primary.ses,
        primary.pain_points, primary.motivations,
    ]):
        primary_final = None
    else:
        primary_final = primary
    return BrandAudience(
        primary=primary_final,
        geo=_ask_list("Cografi hedef (orn. TR, Istanbul, Bodrum)", existing.geo),
        languages=_ask_list("Konusulan diller (ISO 639-1)", existing.languages),
    )


def _fill_content_strategy(existing: BrandContentStrategy) -> BrandContentStrategy:
    _section("CONTENT STRATEGY — icerik stratejisi")
    return BrandContentStrategy(
        pillars=_ask_list("Icerik sutunlari (orn. egitici, sosyal kanit)", existing.pillars),
        posting_cadence=_ask("Yayinlama tempo (orn. 'haftada 3-5 post')", existing.posting_cadence),
        hashtag_strategy=_ask("Hashtag stratejisi", existing.hashtag_strategy),
        required_hashtags=_ask_list("Zorunlu hashtagler (orn. #SlowdaysAI)", existing.required_hashtags),
    )


def _fill_business_context(existing: BrandBusinessContext) -> BrandBusinessContext:
    _section("BUSINESS CONTEXT — ticari baglam")
    return BrandBusinessContext(
        products=_ask_list("Urun/hizmet listesi", existing.products),
        usp=_ask("USP (rakipten farkli olan sey)", existing.usp),
        price_segment=_ask_literal("Fiyat segmenti", PRICE_CHOICES, existing.price_segment),
        competitors=_ask_list("Rakip markalar", existing.competitors),
        seo_keywords=_ask_list("SEO anahtar kelimeler", existing.seo_keywords),
    )


def _summary(bi: BrandIdentity) -> None:
    print("\n========= OZET =========")
    print(bi.model_dump_json(indent=2, exclude_none=False))
    print("========================")
    print(f"\nprompt_summary (agent prompt'una giren kompakt metin):")
    print(f"  {bi.prompt_summary()!r}")


def main() -> int:
    args = sys.argv[1:]
    if args:
        business_id = args[0]
    else:
        business_id = input("business_id: ").strip()
    if not business_id:
        print("business_id zorunlu.")
        return 2

    print(f"\nbusiness_id = {business_id}")
    existing = load_brand_identity(business_id)
    if existing is None:
        print("Mevcut brand_identity yok — sifirdan dolduruyoruz.")
        existing = BrandIdentity(business_id=business_id)
    else:
        print(f"Mevcut brand_identity bulundu (source={existing.source}).")
        print("Enter = mevcut degeri koru. Yeni deger = uzerine yaz.")

    print("\nNot: Tum alanlar opsiyonel. Bilmediginiz alani Enter ile gecin.")
    print("     Bos birakilan alanlari Synthesis Agent sonradan doldurabilir.")

    bi = BrandIdentity(
        business_id=business_id,
        schema_version=BRAND_IDENTITY_SCHEMA_VERSION,
        source="manual",  # Synthesis bu kaynaga dokunmaz
        basics=_fill_basics(existing.basics),
        visual=_fill_visual(existing.visual),
        voice=_fill_voice(existing.voice),
        audience=_fill_audience(existing.audience),
        content_strategy=_fill_content_strategy(existing.content_strategy),
        business_context=_fill_business_context(existing.business_context),
    )

    _summary(bi)
    confirm = input("\nFirestore'a kaydet? [E/h]: ").strip().lower()
    if confirm not in ("", "e", "evet", "y", "yes"):
        print("Iptal edildi. Firestore'a yazilmadi.")
        return 1

    result = save_brand_identity(bi)
    if result.get("success"):
        print(f"\n✓ Kaydedildi: businesses/{business_id}/brand_identity/v1")
        print(f"  updated_at: {result.get('updated_at')}")
        print(f"  source: manual (Synthesis Agent bu alanlara dokunamaz)")
        return 0
    else:
        print(f"\n✗ Kayit hatasi: {result.get('error')}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
