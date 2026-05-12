"""Fallback templates — used when NocoDB ``message_templates`` is empty/missing.

`olumlu` pool: Seyma's lead_monitor.py'den birebir kopyalandi. Bu uc mesaj
Slowdays'in gercek dilini tasiyor (Bodrum, Marmaris, Fethiye coğrafyasi,
"30 dakikalik kahve", "yuz yuze gorusme"). Bu detaylar onemli — LLM
rephrase'i bu anchor'lari KORUYACAK sekilde calisir; halusine etmesi
yasak (kullanici kararla bu sekilde).

`soru` pool: hafifce uyarlandi; ayni ton, "once gorusme" akisli.
`olumsuz` ve `spam`: bos. LLM bu intent'lerde yanit gondermez (responder.py
should_send kuralina dikkat).
"""
from __future__ import annotations


FALLBACK_TEMPLATES: dict[str, list[str]] = {
    "olumlu": [
        # Seyma'nin lead_monitor.py'sinden birebir; 2026-05-11 hibrit karari:
        # LLM bu mesajlari ANCHOR olarak kullanir, mesaja gore hafifce
        # varyasyonlar ama gerçek detaylari (Bodrum / Marmaris / Fethiye /
        # Booking komisyonu / 30 dakika / yuz yuze) DEGISTIRMEZ.
        "Çok teşekkürler dönüşünüz için 🙂\n\nOtelinize özel hızlı bir plan "
        "çıkaralım — hem Booking komisyonu ödemeden direkt rezervasyon, hem "
        "sosyal medyadan misafir akışı. Bodrumdayım, önümüzdeki günlerde "
        "Marmaris ve Fethiye yoluna çıkıyorum zaten.\n\nUğrayıp yüz yüze 30 "
        "dakika konuşsak hem mekanı görmüş olurum hem size özel net bir plan "
        "çıkarırım. Hangi gün uygun?",
        "Hızlı dönüşünüz için sağolun 🌿\n\nSezon başlamadan otelinize özel "
        "bir doluluk planı çıkarmak isterim. Online reklam ve sosyal medya "
        "tarafı küçük bütçeyle bile çok iş yapıyor.\n\nBu hafta içinde "
        "uğrayabilirim, bir kahve içerken 30 dakika konuşalım. Hem siz beni "
        "tanımış olursunuz hem ben mekanı görürüm. Ne gün size uyar?",
        "Çok güzel, dönüşünüz için teşekkürler 🙂\n\nSizinle yüz yüze 30 "
        "dakikalık bir görüşme yapsak hem otelinize özel hızlı bir plan "
        "çıkarırım hem de tanışmış oluruz. Bodrum tarafından geliyorum, "
        "hafta içi ya da hafta sonu fark etmez.\n\nHangi gün size daha uygun?",
    ],
    "soru": [
        "Sorunuz için teşekkürler 🙂 En doğru cevabı kısa bir görüşmede "
        "verebilirim — Bodrum tarafından geliyorum, uğrayıp 30 dakika "
        "konuşsak hem detayları anlatırım hem mekanı görmüş olurum. Hangi "
        "gün uygun?",
        "Güzel soru — sözlü olarak çok daha net açıklayabilirim. Bu hafta "
        "uğrayabilirim, 30 dakikalık bir kahve görüşmesi yeterli. Ne gün "
        "size uyar?",
    ],
    "itiraz": [
        # Bos — Auto-reply otomatik yanit yollamaz. Bunun yerine n8n
        # Itiraz Agent webhook'una handoff edilir (Gemini siniflandirma +
        # Seyma'ya oneri maili). Insan onayli akis.
    ],
    "olumsuz": [
        # Empty — olumsuz mesajlara yanit verme; otel rahatsiz edilmez.
    ],
    "spam": [
        # Empty — spam'a yanit verme.
    ],
}


def has_active_templates(intent: str) -> bool:
    """True if there is at least one fallback template for this intent."""
    return bool(FALLBACK_TEMPLATES.get(intent))


__all__ = ["FALLBACK_TEMPLATES", "has_active_templates"]
