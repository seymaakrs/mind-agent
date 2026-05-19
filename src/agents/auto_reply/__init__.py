"""Auto-reply Agent (Adim 6) — hot lead inbound mesajlarina LLM ile yanit verir.

Seyma'nin ``lead_monitor.py`` muadili. Akis:

1. Adim 5 webhook inbound mesaji Etkilesimler'e ``auto_reply_processed=false``
   ile yazar.
2. Bu paketteki runner 60sn polling ile bu satirlari bulur.
3. ``responder.decide_reply`` LLM ile intent siniflandirir (olumlu/olumsuz/
   soru/spam) + Slowdays tonunda dogal bir yanit yazar.
4. Olumlu/soru ise Zernio ``send_message`` (free-form, 24h CS window icinde
   guvenli — inbound mesaj az once geldi) ile yanit gonderir.
5. Etkilesimler'e Giden satir log eder, gelen satiri ``auto_reply_processed=
   true`` yapar, lead.asama ``Sicak`` -> ``Takipte`` gecisi.

NocoDB schema gereksinimleri (Beyza tek seferlik):
- Etkilesimler tablosuna ``auto_reply_processed`` (Checkbox, default false)
- (Opsiyonel) ``message_templates`` tablosu: intent SingleSelect, variant_no
  Number, template_text LongText, aktif Checkbox. Yoksa ``templates.py``
  fallback'i kullanilir.
"""
from __future__ import annotations

from .policy import AutoReplyConfig
from .responder import AutoReplyDecision, decide_reply
from .targeting import find_pending_inbounds
from .templates import FALLBACK_TEMPLATES


__all__ = [
    "AutoReplyConfig",
    "AutoReplyDecision",
    "decide_reply",
    "find_pending_inbounds",
    "FALLBACK_TEMPLATES",
]
