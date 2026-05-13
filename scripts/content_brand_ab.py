"""TAM AKIS Brand A/B — gercek uretim koşullarinda karsilastirma.

Senin agent portal'dan "Slowdays icin yarinki post'u uret" dedigin
zamanki cagri yolunu birebir taklit eder: marketing_agent ana giris
noktasi, kendi icinde image_agent_tool'u cagirir, caption + gorsel
birlikte uretir.

Iki versiyon:
  BEFORE: marketing_agent + image_agent + BRAND ALIGNMENT promptlari
          ve fetch_brand_identity tool'u STRIPPED. Marka kimligini hic
          okumaz. ("2 gun once" simulasyonu)
  AFTER : Mevcut Faz A+A2+C kodu. Marketing okur, image agent okur,
          caption + gorsel marka kimligine uyumlu uretir.

Cikti:
  ab_outputs/content_ab_<business_id>_<timestamp>/
    before.txt   - marketing'in tam ciktisi (caption + image URL)
    after.txt    - aynisi marka enjekteli
    README.md    - URL'leri + caption'lar yan yana

Kullanim:
  python scripts/content_brand_ab.py <business_id>
  python scripts/content_brand_ab.py <business_id> "ozel gorev"

Notlar:
  - Marketing agent uzun prompt'tur; TPM sinirina dikkat. Run'lar arasi
    30s bekleme var.
  - Sadece ICERIK UYUMU karsilastirir. Posting yapilmaz (caption icinde
    "paylas" yazmamak onemli).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import re
import sys
from datetime import datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Brand kismi sokulmus 'before' factory'leri
# ---------------------------------------------------------------------------

def _strip_brand_section(text: str) -> str:
    """Marketing ve Image promptlarindan BRAND ALIGNMENT bolumunu kaldir."""
    text = re.sub(
        r"## ABSOLUTE RULE #1\.5: BRAND ALIGNMENT.*?(?=## ABSOLUTE RULE #2)",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"## BRAND ALIGNMENT.*?(?=## [A-Z])",
        "",
        text,
        flags=re.DOTALL,
    )
    return text


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
        tools=get_image_tools(config),
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model_settings.image_agent_model or settings.openai_model,
    )


def _build_before_image_wrapper_tool():
    """Marketing agent'in cagiracagi image_agent_tool — fakat icinde
    BRAND-LESS image agent calistirir."""
    from agents import Runner, function_tool

    @function_tool(
        name_override="image_agent_tool",
        description_override=(
            "Generate images using the image agent. REQUIRED: business_id, prompt."
        ),
        strict_mode=False,
    )
    async def _wrapper(business_id: str, prompt: str) -> str:
        agent = _build_before_image_agent()
        result = await Runner.run(
            starting_agent=agent,
            input=f"[Business ID: {business_id}]\n\n{prompt}",
            max_turns=3,
        )
        return result.final_output

    return _wrapper


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

    # No fetch_brand_identity, with brand-less image wrapper
    image_tool = _build_before_image_wrapper_tool()

    tools = [
        *get_instagram_tools(),
        *get_marketing_tools(),
        *get_report_tools(),
        post_on_instagram,
        post_carousel_on_instagram,
        get_document,
        save_document,
        query_documents,
        image_tool,
    ]
    instructions = _strip_brand_section(MARKETING_AGENT_INSTRUCTIONS)

    return Agent(
        name="marketing_before",
        handoff_description="Marketing agent (marka kimliksiz simulasyon).",
        instructions=instructions,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model_settings.marketing_agent_model or settings.openai_model,
    )


def _build_after_marketing_agent():
    """Mevcut Faz C versiyonu — marka kimliği tam aktif."""
    from src.agents.marketing_agent import create_marketing_agent
    from src.tools.agent_wrapper_tools import create_image_agent_wrapper_tool

    image_tool = create_image_agent_wrapper_tool()
    return create_marketing_agent(image_agent_tool=image_tool)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_url(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"https?://[^\s)>\]]+\.(?:png|jpg|jpeg|webp)", text, re.IGNORECASE)
    return m.group(0) if m else None


async def _run(agent, business_id: str, task: str) -> str:
    from agents import Runner
    prompt = f"[Business ID: {business_id}]\n\n{task}"
    result = await Runner.run(starting_agent=agent, input=prompt, max_turns=10)
    return str(result.final_output or "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_TASK = (
    "Slowdays AI icin yarin paylasilacak bir Instagram post'u uret. "
    "Bodrum'daki kucuk otel sahiplerine yaz sezonu doluluk hatirlatmasi. "
    "Caption + uygun gorsel uret. Paylasma — sadece taslagi don."
)


async def main_async(args: argparse.Namespace) -> int:
    business_id = args.business_id
    task = args.task or DEFAULT_TASK

    from src.infra.firebase_client import get_document_client
    biz = get_document_client("businesses").get_document(business_id)
    if not biz:
        print(f"! businesses/{business_id} yok.")
        return 2

    from src.tools.brand import load_brand_identity
    bi = load_brand_identity(business_id)
    if bi is None or not bi.is_substantially_filled():
        print(f"! brand_identity bos/yetersiz. Once fill_brand_identity.py.")
        if not args.force:
            return 3
    else:
        print(f"✓ brand_identity dolu (source={bi.source})")
        print(f"  {bi.prompt_summary(max_chars=200)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "ab_outputs" / f"content_ab_{business_id}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCikti: {out_dir}")
    print(f"\nGorev: {task}\n")

    print("[1/2] BEFORE — marka kimliksiz tam akis (marketing → image)...")
    print("       Marketing brief yazar → image_agent_tool ile gorsel ister")
    before_agent = _build_before_marketing_agent()
    before_out = await _run(before_agent, business_id, task)
    (out_dir / "before.txt").write_text(before_out, encoding="utf-8")
    print(f"  ✓ before.txt ({len(before_out)} chars)")

    print("\n  ... 30 saniye bekleme (TPM koruma) ...\n")
    await asyncio.sleep(30)

    print("[2/2] AFTER — marka kimligi enjekte tam akis...")
    print("       Marketing brand_identity okur + image_agent brand_identity okur")
    after_agent = _build_after_marketing_agent()
    after_out = await _run(after_agent, business_id, task)
    (out_dir / "after.txt").write_text(after_out, encoding="utf-8")
    print(f"  ✓ after.txt ({len(after_out)} chars)")

    before_url = _extract_url(before_out)
    after_url = _extract_url(after_out)

    md = [
        f"# Tam Akis Brand A/B — {business_id}",
        "",
        f"**Zaman:** {datetime.now().isoformat(timespec='seconds')}",
        f"**Gorev:** {task}",
        "",
        "Marketing agent giris noktasi olarak calisti. Kendi icinde",
        "image_agent_tool'u cagirip gorseli de uretti. **Gercek uretim",
        "kosulunun aynisi.**",
        "",
        "---",
        "",
        "## BEFORE — marka kimliksiz (\"2 gun once\" simulasyonu)",
        "",
        f"- Gorsel: {before_url or '(uretilemedi)'}",
        "",
        "```",
        before_out[:3000],
        "```",
        "",
        "---",
        "",
        "## AFTER — marka kimligi enjekte (Faz A+A2+C)",
        "",
        f"- Gorsel: {after_url or '(uretilemedi)'}",
        "",
        "```",
        after_out[:3000],
        "```",
        "",
        "---",
        "",
        "## Ne karsilastirilacak?",
        "- Caption tonu, hitap (siz/sen), emoji yogunlugu, hook",
        "- Yasak kelime / yasak konu yoklugu (after'da)",
        "- Tercih edilen kelimelerin gorunmesi",
        "- CTA: 'after'da gercek CTA kalibi (DM at / profile bak / link) kullanilmis mi",
        "- Zorunlu hashtag (#SlowdaysAI) after'da var mi",
        "- Gorsel: marka renkleri, mimari minimalizm, premium butik vs turistik klise",
    ]
    (out_dir / "README.md").write_text("\n".join(md), encoding="utf-8")

    print("\n" + "=" * 60)
    print("URL'ler:")
    print(f"  BEFORE: {before_url or '(yok)'}")
    print(f"  AFTER : {after_url or '(yok)'}")
    print("\nIndir:")
    print(f"  cd {out_dir}")
    print(f"  cloudshell download README.md before.txt after.txt")
    print("=" * 60)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Full pipeline content A/B")
    ap.add_argument("business_id")
    ap.add_argument("task", nargs="?", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    for name in ["httpx", "httpcore", "urllib3", "google"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
