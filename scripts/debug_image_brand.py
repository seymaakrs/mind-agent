"""TANI: brand-aware image prompt ile dogrudan Gemini'ye 5 farkli call.
Agent layer'i atla — gercek hata mesajini ham olarak gor.

Amac: 'AFTER' modunda image generation neden basariz oluyor?
Sebep aday listesi:
  1. Hex kodlar (#001338) Gemini'yi rahatsiz ediyor
  2. Turkce karakterler (image_dos/donts) corrupt oluyor
  3. Prompt cok uzun (tum brand alanlar)
  4. Belirli kelime kombinasyonu content policy tetikliyor
  5. API quota / model versiyon

Calistirma:
  python scripts/debug_image_brand.py slowdays_ai_test
"""
from __future__ import annotations

import asyncio
import sys
import pathlib
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def _try(label: str, prompt: str, aspect: str = "4:5"):
    from src.infra.google_ai_client import get_image_generation_client
    print(f"\n{'='*70}")
    print(f"[{label}]  prompt len: {len(prompt)} chars")
    print(f"{prompt[:300]}{'...' if len(prompt) > 300 else ''}")
    print(f"{'-'*70}")
    client = get_image_generation_client()
    try:
        images = await client.generate_image(prompt=prompt, aspect_ratio=aspect)
        if images:
            print(f"  ✓ SUCCESS — {len(images)} image(s), {len(images[0])} bytes")
        else:
            print(f"  ✗ EMPTY response (no images, no exception)")
    except Exception as exc:
        print(f"  ✗ EXCEPTION  type={type(exc).__name__}")
        print(f"     str: {str(exc)[:500]}")
        # Look for status code attrs
        for attr in ("status_code", "code", "response"):
            if hasattr(exc, attr):
                print(f"     {attr} = {getattr(exc, attr)!r}"[:200])
        # Trim traceback
        tb = traceback.format_exc().splitlines()
        print("     traceback (last 10 lines):")
        for line in tb[-10:]:
            print(f"     | {line}")


async def main(business_id: str):
    from src.tools.brand import load_brand_identity
    bi = load_brand_identity(business_id)
    if bi is None:
        print(f"! brand_identity yok: {business_id}")
        return 1
    summary = bi.prompt_summary(max_chars=2000)
    print(f"brand_identity prompt_summary ({len(summary)} chars):")
    print(summary)

    # 1. Plain prompt — kontrol grubu
    await _try(
        "1. PLAIN (kontrol)",
        "A modern boutique hotel terrace at sunset, premium minimal style.",
    )

    # 2. Just hex colors
    await _try(
        "2. HEX COLORS",
        "A modern boutique hotel terrace. Color palette strictly: #001338 (deep navy) and #F5E6D3 (cream).",
    )

    # 3. Brand summary plain ASCII
    await _try(
        "3. BRAND SUMMARY (full)",
        f"Generate an Instagram image for: {summary}",
    )

    # 4. Brand summary + Turkish DOs/DONTs
    dos = ", ".join(bi.visual.image_dos)
    donts = ", ".join(bi.visual.image_donts)
    await _try(
        "4. TURKISH DOS/DONTS",
        f"A boutique hotel image. DO: {dos}. DON'T: {donts}.",
    )

    # 5. Combined long prompt (typical agent output)
    long_prompt = (
        f"Scene: A premium boutique hotel entrance in Bodrum, soft morning light. "
        f"Subject: Architectural minimalism, clean shadows. "
        f"Style: {bi.visual.visual_style}. "
        f"Colors: {', '.join(bi.visual.primary_colors)}. "
        f"Mood: calm, premium, professional. "
        f"Composition: centered, rule of thirds, generous negative space. "
        f"Lighting: soft natural daylight. "
        f"Background: minimal architectural details. "
        f"Photography style: {bi.visual.photography_style}. "
        f"DO: {dos}. DONT: {donts}."
    )
    await _try("5. FULL AGENT-LIKE PROMPT", long_prompt)

    print(f"\n{'='*70}")
    print("Tani sonu. Hangi adimda hata olduguna gore kok sebep tespit edilebilir.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_image_brand.py <business_id>")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
