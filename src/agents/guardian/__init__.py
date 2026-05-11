"""Guardian Agent (Bekci Robot, Adim 8) — Slowdays kampanyasinin saglik bekcisi.

Her 30 dakikada bir 3 metrigi NocoDB Etkilesimler'den hesaplar:

- **Reply Rate**: 24h Gelen / 24h Outreach Giden  (saglikli %5+, kritik %3 alti)
- **Engagement Rate**: 24h Auto-reply Giden / 24h Gelen  (intent classifier'in
  ne kadar mesaj gondermeye karar verdigi — dusukse cogu inbound olumsuz/spam)
- **Outreach Failure Rate**: 24h FAILED Outreach / toplam Outreach (Adim 9'da
  Outreach FAILED log'u eklenecek; simdilik 0 doner)

Karar:
- GREEN  → hicbir sey yapma, log
- YELLOW → bilgilendir (NocoDB system_settings.last_alert), Outreach calismaya
  devam
- RED    → system_settings.outreach_paused=true. Outreach Robotu bir sonraki
  tick'inde bu bayragi gorur ve durur. Insan onayli yeniden baslatma sart.

Cikti: NocoDB system_settings tablosunda saklanir. Mail bildirimleri n8n
"Bekci Alert" workflow'una webhook ile delege edilir (n8n Gmail node'u var
zaten — kod tekrari yok).
"""
from __future__ import annotations

from .decisions import Decision, DecisionLevel, decide
from .metrics import GuardianMetrics, compute_metrics
from .policy import GuardianConfig


__all__ = [
    "Decision",
    "DecisionLevel",
    "GuardianConfig",
    "GuardianMetrics",
    "compute_metrics",
    "decide",
]
