"""A/B karsilastirma: marka kimligi var/yok ayni gorev.

Ayni business + ayni task + ayni model. Tek degisken: agent'in
brand_identity'i okuyup okumamasi.

Cikti:
    ab_outputs/<business_id>_<timestamp>/
      caption_before.txt   - marketing agent (eski davranis simulasyonu)
      caption_after.txt    - marketing agent (Faz C: marka enjekte)
      image_before.txt     - image agent URL (marka renk/stil yok)
      image_after.txt      - image agent URL (marka renk/stil dahil)
      README.md            - karsilastirma ozeti

Kullanim:
    python scripts/brand_ab_compare.py <business_id> "<gorev metni>"
    python scripts/brand_ab_compare.py <business_id> "<gorev metni>" --skip-image

Notlar:
- 'Before' simulasyonu: ilgili agent factory'leri marka tool'u olmadan
  + instruction prompt'undan BRAND ALIGNMENT bolumu silinmis halde
  yeniden olusturuyoruz. Geri kalan her sey (model, diger tool'lar,
  baska kurallar) AYNI.
- 'After': mevcut Faz C kodu oldugu gibi.
- Iki gorsel uretilir → Firebase Storage'a yazilir. Maliyet ~$0.05-0.10.
- Sonuc dosyalarini 'cloudshell download <dosya>' ile indirebilirsin.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import re
import sys
from datetime import datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# "Before" simulasyon factory'leri
# ---------------------------------------------------------------------------

def _strip_brand_section(text: str) -> str:
    """Instruction prompt'undan BRAND ALIGNMENT bolumunu kaldir.

    Marketing prompt'unda: '## ABSOLUTE RULE #1.5: BRAND ALIGNMENT' ile
    '## ABSOLUTE RULE #2' arasi.
    Image/Video prompt'unda: '## BRAND ALIGNMENT' ile bir sonraki '## '
    baligi arasi.
    """
    # Marketing kalibi
    text = re.sub(
        r"## ABSOLUTE RULE #1\.5: BRAND ALIGNMENT.*?(?=## ABSOLUTE RULE #2)",
        "",
        text,
        flags=re.DOTALL,
    )
    # Image/Video kalibi: '## BRAND ALIGNMENT' ile sonraki '## ' arasi
    text = re.sub(
        r"## BRAND ALIGNMENT.*?(?=## [A-Z])",
        "",
        text,
        flags=re.DOTALL,
    )
    return text


def _build_before_marketing_agent():
    from agents import Agent

    from src.app.config import get_settings, get_model_settings
    from src.tools.instagram_tools import get_instagram_tools
    from src.tools.marketing_tools import get_marketing_tools
    from src.tools.analysis_tools import get_report_tools
    from src.tools.orchestrator_tools import (
        post_on_instagram,
        post_carousel_on_instagram,
        get_document,
        save_document,
        query_documents,
    )
    from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS

    settings = get_settings()
    model_settings = get_model_settings()

    # Marka tool'u YOK
    tools = [
        *get_instagram_tools(),
        *get_marketing_tools(),
        *get_report_tools(),
        post_on_instagram,
        post_carousel_on_instagram,
        get_document,
        save_document,
        query_documents,
    ]
    instructions = _strip_brand_section(MARKETING_AGENT_INSTRUCTIONS)

    return Agent(
        name="marketing_before",
        handoff_description="Marketing agent (marka kimliksiz simulasyon).",
        instructions=instructions,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=(
            model_settings.marketing_agent_model or settings.openai_model
        ),
    )


def _build_before_image_agent():
    from agents import Agent

    from src.app.config import get_settings, get_model_settings, get_agent_instructions
    from src.tools.image_tools import get_image_tools
    from src.agents.instructions import (
        IMAGE_AGENT_CORE_INSTRUCTIONS,
        DEFAULT_IMAGE_PERSONA,
    )

    settings = get_settings()
    model_settings = get_model_settings()
    config = get_agent_instructions("image_agent")

    persona = config.persona or DEFAULT_IMAGE_PERSONA
    instructions = IMAGE_AGENT_CORE_INSTRUCTIONS.replace("{persona}", persona)
    instructions = _strip_brand_section(instructions)

    return Agent(
        name="image_before",
        handoff_description="Image agent (marka kimliksiz simulasyon).",
        instructions=instructions,
        tools=get_image_tools(config),  # fetch_brand_identity yok
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model_settings.image_agent_model or settings.openai_model,
    )


# ---------------------------------------------------------------------------
# Calistirma
# ---------------------------------------------------------------------------

async def _run(agent, business_id: str, task: str) -> str:
    from agents import Runner

    prompt = f"[Business ID: {business_id}]\n\n{task}"
    result = await Runner.run(agent, prompt)
    return str(result.final_output)


def _write(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ {path}")


def _readme(out_dir: pathlib.Path, business_id: str, task: str,
            caption_before: str, caption_after: str,
            image_before: str | None, image_after: str | None) -> None:
    md = f"""# Brand A/B Karsilastirma — {business_id}

**Zaman:** {datetime.now().isoformat(timespec="seconds")}
**Gorev:** {task}

Ayni model, ayni gorev, ayni isletme. Tek degisken: marka kimligi
enjeksiyonu.

---

## 1. Caption — ONCESI (marka bilgisi YOK)

{caption_before}

## 2. Caption — SONRASI (marka kimligi DOLU, agent okuyup uyguladi)

{caption_after}

---
"""
    if image_before or image_after:
        md += "## 3. Gorsel\n\n"
        if image_before:
            md += f"**Oncesi:** {image_before}\n\n"
        if image_after:
            md += f"**Sonrasi:** {image_after}\n\n"
    md += """---

## Ne karsilastirilacak?
- Caption tonu, kelime secimi, yasak kelimelerin yoklugu, hashtag/CTA tutarliligi
- Gorsel: marka renkleri (lacivert/krem?), stil (modern/minimal mi?), DOs/DONTs uygulanmis mi
"""
    _write(out_dir / "README.md", md)


async def main_async(args: argparse.Namespace) -> int:
    business_id = args.business_id
    task = args.task

    # 1) business var mi?
    from src.infra.firebase_client import get_document_client
    biz = get_document_client("businesses").get_document(business_id)
    if not biz:
        print(f"! businesses/{business_id} bulunamadi. Onceden olustur veya farkli id ver.")
        return 2

    # 2) brand_identity durumu
    from src.tools.brand import load_brand_identity
    bi = load_brand_identity(business_id)
    if bi is None or not bi.is_substantially_filled():
        print("! Bu business icin brand_identity yok veya cok bos.")
        print("  Once: python scripts/fill_brand_identity.py", business_id)
        print("  (Marka kimligi olmadan 'sonrasi' farkli olmaz — anlamli A/B icin gerekli)")
        if not args.force:
            return 3
    else:
        print(f"✓ brand_identity dolu (source={bi.source})")
        print(f"  prompt_summary: {bi.prompt_summary(max_chars=200)}")

    # 3) cikti klasoru
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "ab_outputs" / f"{business_id}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCiktilar: {out_dir}")

    # 4) caption — before
    print("\n[1/4] Caption — ONCESI (marka kimliksiz)...")
    before_marketing = _build_before_marketing_agent()
    cap_before = await _run(before_marketing, business_id, task)
    _write(out_dir / "caption_before.txt", cap_before)

    # 5) caption — after
    print("\n[2/4] Caption — SONRASI (marka enjekte)...")
    from src.agents.registry import create_marketing
    after_marketing = create_marketing()
    cap_after = await _run(after_marketing, business_id, task)
    _write(out_dir / "caption_after.txt", cap_after)

    img_before_text = None
    img_after_text = None

    if not args.skip_image:
        # 6) image — before
        print("\n[3/4] Gorsel — ONCESI (marka renk/stil yok)...")
        before_image = _build_before_image_agent()
        img_task = task + "\n\nBuna uygun bir Instagram gorseli uret."
        img_before_text = await _run(before_image, business_id, img_task)
        _write(out_dir / "image_before.txt", img_before_text)

        # 7) image — after
        print("\n[4/4] Gorsel — SONRASI (marka renk/stil dahil)...")
        from src.agents.registry import create_image
        after_image = create_image()
        img_after_text = await _run(after_image, business_id, img_task)
        _write(out_dir / "image_after.txt", img_after_text)
    else:
        print("\n[image atlandi: --skip-image]")

    # 8) README
    _readme(out_dir, business_id, task, cap_before, cap_after,
            img_before_text, img_after_text)

    print("\n" + "=" * 60)
    print("Hazir. Indirmek icin Cloud Shell'de:")
    print(f"  cd {out_dir}")
    print("  cloudshell download README.md caption_before.txt caption_after.txt", end="")
    if not args.skip_image:
        print(" image_before.txt image_after.txt")
    else:
        print("")
    print("=" * 60)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Brand A/B comparison runner")
    ap.add_argument("business_id")
    ap.add_argument("task", help="Gorev metni — agent'a verilecek")
    ap.add_argument("--skip-image", action="store_true",
                    help="Sadece caption uret, gorsel atlama")
    ap.add_argument("--force", action="store_true",
                    help="brand_identity bos olsa da calistir")
    args = ap.parse_args()

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
