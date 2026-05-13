"""Izole image A/B + debug runner.

Sadece image_agent calistirir (marketing agent yok → token limiti
saglikli). Brand kimligi var/yok iki versiyonu uretir. Detayli log
acabilirsin (--debug).

Kullanim:
    python scripts/image_brand_ab.py <business_id>
    python scripts/image_brand_ab.py <business_id> "ozel gorev metni"
    python scripts/image_brand_ab.py <business_id> --debug
    python scripts/image_brand_ab.py <business_id> --only after
    python scripts/image_brand_ab.py <business_id> --retries 3

Cikti:
    ab_outputs/image_ab_<business_id>_<timestamp>/
      before.txt   - marka kimliksiz image_agent ciktisi
      after.txt    - marka kimligi enjekte image_agent ciktisi
      debug.log    - tam tool cagri + hata izi (sadece --debug ile)
      README.md    - URL'ler + ozet

Notlar:
- 'before' versiyonu icin image_agent factory'i marka tool'u olmadan +
  BRAND ALIGNMENT promot'u silinmis olarak yeniden olusturulur.
- 'after' versiyonu mevcut Faz C kodu.
- Retry mantigi: 429 / 503 / 'hata' iceren cevaplarda baska prompt
  varyantiyla yeniden dener (max --retries kadar).
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
# 'Before' simulasyon factory'i (sadece image_agent)
# ---------------------------------------------------------------------------

def _strip_brand_section(text: str) -> str:
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


# ---------------------------------------------------------------------------
# Calistirma
# ---------------------------------------------------------------------------

def _failure_signals(text: str) -> bool:
    """Agent ciktisinda 'gorsel uretilemedi' tipi bir sinyali yakala."""
    if not text:
        return True
    low = text.lower()
    bad = [
        "hata oluştu", "olusturulamadi", "olusturulamadı",
        "yetki yok", "yetkim yok", "yetkim bulunmuyor",
        "üretilemedi", "uretilemedi",
        "rate limit", "rate_limit", "429",
        "lütfen tekrar", "lutfen tekrar",
    ]
    return any(b in low for b in bad)


def _extract_url(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"https?://[^\s)>\]]+\.(?:png|jpg|jpeg|webp)", text, re.IGNORECASE)
    return m.group(0) if m else None


async def _run_once(agent, business_id: str, task: str, debug_buf: list[str] | None) -> str:
    from agents import Runner

    prompt = f"[Business ID: {business_id}]\n\n{task}"
    try:
        result = await Runner.run(agent, prompt)
    except Exception as exc:
        if debug_buf is not None:
            debug_buf.append(f"[exception] {type(exc).__name__}: {exc}")
        return f"[runner exception] {type(exc).__name__}: {exc}"

    if debug_buf is not None:
        debug_buf.append(f"\n=== {agent.name} items ===")
        for i, item in enumerate(result.new_items):
            debug_buf.append(f"--- item {i}: {type(item).__name__} ---")
            debug_buf.append(repr(item)[:1500])

    return str(result.final_output or "")


async def _run_with_retries(
    agent, business_id: str, prompts: list[str],
    retries: int, debug_buf: list[str] | None, label: str,
) -> str:
    last = ""
    attempts = min(len(prompts), retries)
    for i in range(attempts):
        if debug_buf is not None:
            debug_buf.append(f"\n>>> {label} attempt {i+1}/{attempts}: {prompts[i][:100]}")
        out = await _run_once(agent, business_id, prompts[i], debug_buf)
        last = out
        if not _failure_signals(out):
            return out
        print(f"  ! {label} attempt {i+1} failed signal, trying next variant...")
        # 30s pause to avoid TPM
        await asyncio.sleep(30)
    return last


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_VARIANTS = [
    "Bodrum'da bir butik otelin onunde gun batiminda cekilmis premium bir Instagram gorseli olustur. Sezon basi atmosferi.",
    "Bir butik otelin terasinda kahve ve manzara — premium, sade, minimal kompozisyon.",
    "Slowdays AI markasi icin Bodrum'da bir butik otele dair ozet gorsel.",
]


async def main_async(args: argparse.Namespace) -> int:
    business_id = args.business_id

    # Verify business + brand_identity
    from src.infra.firebase_client import get_document_client
    biz = get_document_client("businesses").get_document(business_id)
    if not biz:
        print(f"! businesses/{business_id} yok.")
        return 2

    from src.tools.brand import load_brand_identity
    bi = load_brand_identity(business_id)
    if bi is None or not bi.is_substantially_filled():
        print(f"! brand_identity bos veya yetersiz. Once fill_brand_identity.py calistir.")
        if not args.force:
            return 3
    else:
        print(f"✓ brand_identity dolu (source={bi.source})")
        print(f"  summary: {bi.prompt_summary(max_chars=300)}")

    if args.task:
        prompts = [args.task]
    else:
        prompts = DEFAULT_VARIANTS

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "ab_outputs" / f"image_ab_{business_id}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCikti: {out_dir}")

    debug_buf: list[str] | None = [] if args.debug else None
    before_out = after_out = None

    if args.only in (None, "before"):
        print("\n[1/2] BEFORE — marka kimliksiz image_agent...")
        agent = _build_before_image_agent()
        before_out = await _run_with_retries(
            agent, business_id, prompts, args.retries, debug_buf, "before"
        )
        (out_dir / "before.txt").write_text(before_out, encoding="utf-8")
        print(f"  ✓ before.txt")

    if args.only in (None, "after"):
        print("\n[2/2] AFTER — marka kimligi enjekte image_agent...")
        from src.agents.registry import create_image
        agent = create_image()
        after_out = await _run_with_retries(
            agent, business_id, prompts, args.retries, debug_buf, "after"
        )
        (out_dir / "after.txt").write_text(after_out, encoding="utf-8")
        print(f"  ✓ after.txt")

    if debug_buf is not None:
        (out_dir / "debug.log").write_text("\n".join(debug_buf), encoding="utf-8")
        print(f"  ✓ debug.log")

    # README
    before_url = _extract_url(before_out or "")
    after_url = _extract_url(after_out or "")
    md = [f"# Image A/B — {business_id}", "",
          f"**Zaman:** {datetime.now().isoformat(timespec='seconds')}", ""]
    if before_out is not None:
        md.append("## BEFORE — marka kimliksiz")
        md.append(f"- URL: {before_url or '(uretilemedi)'}\n")
        md.append("```")
        md.append(before_out[:1500])
        md.append("```\n")
    if after_out is not None:
        md.append("## AFTER — marka kimligi enjekte")
        md.append(f"- URL: {after_url or '(uretilemedi)'}\n")
        md.append("```")
        md.append(after_out[:1500])
        md.append("```\n")
    (out_dir / "README.md").write_text("\n".join(md), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Karsilastirma URL'leri:")
    print(f"  BEFORE: {before_url or '(yok)'}")
    print(f"  AFTER : {after_url or '(yok)'}")
    print(f"\nIndir:")
    print(f"  cd {out_dir}")
    print(f"  cloudshell download README.md before.txt after.txt", end="")
    if debug_buf is not None:
        print(" debug.log")
    else:
        print("")
    print("=" * 60)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Isolated image agent A/B + debug")
    ap.add_argument("business_id")
    ap.add_argument("task", nargs="?", default=None,
                    help="Tek bir gorev metni (verilirse retry varyantlari kullanilmaz)")
    ap.add_argument("--only", choices=["before", "after"], default=None,
                    help="Sadece bir tarafi calistir")
    ap.add_argument("--retries", type=int, default=3,
                    help="Basarisiz olursa farkli varyantla deneme sayisi (max 3)")
    ap.add_argument("--debug", action="store_true",
                    help="Tool cagri ve hata izi debug.log'a yaz")
    ap.add_argument("--force", action="store_true",
                    help="brand_identity bos olsa da calistir")
    args = ap.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        # Suppress noisy http loggers
        for name in ["httpx", "httpcore", "urllib3", "google"]:
            logging.getLogger(name).setLevel(logging.WARNING)

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
