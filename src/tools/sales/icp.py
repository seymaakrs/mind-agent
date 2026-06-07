"""ICP (Ideal Customer Profile) fit — saf/deterministik puanlama.

Qualifier Agent'ın LLM kararına referans olan çekirdek mantık. LLM'siz,
test edilebilir. Mind ID / Vibe ID hedef profili:
- **Sektör:** otelcilik, yeme-içme, turizm, spa-wellness ağırlıklı.
- **Konum:** Bodrum / Muğla bölgesi.

score_icp_fit() bir sözlük döner: {fit, fit_score, reasons}. `fit` bool eşik
kararı; nihai `qualified` flag'ini yine de LLM verir (ek sinyalleri tartarak).
"""
from __future__ import annotations

from typing import Any

# Hedef sektörler (NocoDB 'sektor' SingleSelect option'larıyla hizalı).
TARGET_SEKTORLER = [
    "Otelcilik",
    "Yeme-Icme",
    "Restoran",
    "Kafe",
    "Turizm",
    "Spa-Wellness",
    "Tekne-Yat",
]

# İkincil (kabul edilebilir ama düşük öncelikli) sektörler.
SECONDARY_SEKTORLER = [
    "Perakende",
    "E-ticaret",
    "Emlak",
    "Butik-Moda",
]

# Hedef konumlar — serbest metin konum içinde substring olarak aranır.
TARGET_KONUMLAR = [
    "Bodrum",
    "Mugla",
    "Muğla",
    "Marmaris",
    "Fethiye",
    "Datca",
    "Datça",
    "Gocek",
    "Göcek",
    "Yalikavak",
    "Yalıkavak",
    "Turgutreis",
]

# fit eşiği: bu puanın üstü ICP'ye uyuyor kabul edilir.
FIT_THRESHOLD = 60


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def score_icp_fit(
    sektor: str | None = None,
    konum: str | None = None,
    lead_skoru: int | None = None,
) -> dict[str, Any]:
    """ICP uyum puanı hesaplar (0-100) + insan-okunur gerekçeler.

    Puanlama (additive, 100'de cap'lenir):
    - Hedef sektör: +50, ikincil sektör: +25
    - Hedef konum: +35
    - Mevcut lead_skoru sinyali: +10 (>= 60 ise)
    """
    reasons: list[str] = []
    score = 0

    s = _norm(sektor)
    target_s = {x.lower() for x in TARGET_SEKTORLER}
    secondary_s = {x.lower() for x in SECONDARY_SEKTORLER}
    if s and s in target_s:
        score += 50
        reasons.append(f"Hedef sektör: {sektor}")
    elif s and s in secondary_s:
        score += 25
        reasons.append(f"İkincil sektör: {sektor}")
    elif s:
        reasons.append(f"Sektör ICP dışı: {sektor}")

    k = _norm(konum)
    if k and any(_norm(t) in k for t in TARGET_KONUMLAR):
        score += 35
        reasons.append(f"Hedef konum: {konum}")
    elif k:
        reasons.append(f"Konum ICP dışı: {konum}")

    if lead_skoru is not None and lead_skoru >= 60:
        score += 10
        reasons.append(f"Yüksek lead skoru sinyali: {lead_skoru}")

    score = min(score, 100)
    return {
        "fit": score >= FIT_THRESHOLD,
        "fit_score": score,
        "reasons": reasons,
    }


__all__ = [
    "score_icp_fit",
    "TARGET_SEKTORLER",
    "SECONDARY_SEKTORLER",
    "TARGET_KONUMLAR",
    "FIT_THRESHOLD",
]
