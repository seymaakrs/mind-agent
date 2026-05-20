"""Fallback templates — used when NocoDB ``message_templates`` is empty/missing.

`olumlu` pool: Seyma's lead_monitor.py'den birebir kopyalandi. Bu uc mesaj
Slowdays'in gercek dilini tasiyor (Bodrum, Marmaris, Fethiye coğrafyasi,
"30 dakikalik kahve", "yuz yuze gorusme"). Bu detaylar onemli — LLM
rephrase'i bu anchor'lari KORUYACAK sekilde calisir; halusine etmesi
yasak (kullanici kararla bu sekilde).

`soru` pool: hafifce uyarlandi; ayni ton, "once gorusme" akisli.
`olumsuz` ve `spam`: bos. LLM bu intent'lerde yanit gondermez (responder.py
should_send kuralina dikkat).

``ITIRAZ_PLAYBOOK``: Faz 1 — itiraz cevap taslagi icin anchor havuzu.
objection_type basina Seyma'nin gercek satis dilinde 2 ikna ornegi. LLM
bunlari ANCHOR alir; musteriye OTOMATIK gitmez — Seyma onayina dusen
oneri taslagi uretmek icin kullanilir (runner.py native itiraz akisi).
Link/fiyat/garanti yok; tek hedef yuz yuze 30 dk gorusme.
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
        # Bos — Auto-reply otomatik yanit yollamaz. Itiraz cevap taslagi
        # ITIRAZ_PLAYBOOK'tan anchor alir (Faz 1: Seyma onayli oneri).
    ],
    "olumsuz": [
        # Empty — olumsuz mesajlara yanit verme; otel rahatsiz edilmez.
    ],
    "spam": [
        # Empty — spam'a yanit verme.
    ],
}


# objection_type -> ikna anchor havuzu. Seyma'nin sahadaki dili: empati +
# tek somut bir sonraki adim (yuz yuze 30 dk). Fiyat/garanti/link YOK.
ITIRAZ_PLAYBOOK: dict[str, list[str]] = {
    "fiyat": [
        "Bütçe tarafını çok iyi anlıyorum 🙂 Zaten amacım size ek maliyet "
        "değil — Booking komisyonu ödemeden gelen direkt rezervasyon, kendini "
        "fazlasıyla çıkarıyor. Bodrumdayım, uğrayıp 30 dakika otelinize özel "
        "net rakamlarla konuşsak çok daha somut olur. Hangi gün uygun?",
        "Maliyet endişenizi anlıyorum, haklısınız da. Bunu telefonda değil, "
        "yüz yüze otelinize özel bir planla konuşmak isterim — küçük bütçeyle "
        "nereden başlanır, net göstereyim. Marmaris–Fethiye yoluna "
        "çıkıyorum zaten, 30 dakika ayırabilir misiniz?",
    ],
    "rekabet": [
        "Başka ekiplerle de görüşmeniz çok normal 🙂 Ben farkı yüz yüze "
        "anlatmayı tercih ederim — otelinize özel ne yapacağımı somut "
        "göstereyim, kıyaslama sizde kalsın. Bodrum tarafından geliyorum, "
        "30 dakikalık bir görüşme yeterli. Hangi gün size uyar?",
        "Anlıyorum, seçenekleri değerlendiriyorsunuz. Karşılaştırmanın en "
        "sağlıklı yolu mekanı görüp size özel bir plan çıkarmam. Uğrayıp "
        "30 dakika konuşalım, kararı rahat verirsiniz. Ne gün uygun?",
    ],
    "erteleme": [
        "Tabii, yoğun döneminizi anlıyorum 🙂 Tam da bu yüzden sezon "
        "başlamadan kısa bir görüşme iş yükünüzü artırmaz, aksine "
        "rahatlatır. Bodrumdayım, size uygun herhangi bir gün 30 dakika "
        "uğrayabilirim. Hafta içi mi hafta sonu mu daha rahatsınız?",
        "Şu an müsait olmamanız çok normal. Acele etmenize gerek yok — "
        "sadece takvimde 30 dakika bırakalım, gerisini ben otelinize "
        "gelince hallederim. Önümüzdeki günlerde Marmaris–Fethiye "
        "yolundayım, hangi gün denk getirebiliriz?",
    ],
    "olcek": [
        "Küçük/butik bir işletme olmanız aslında en güçlü tarafınız 🙂 "
        "Doğru anlatımla küçük yerler sosyal medyada çok hızlı doluyor. "
        "Otelinize özel ne yapılabilir, uğrayıp 30 dakika somut "
        "konuşalım. Bodrum tarafından geliyorum, hangi gün uygun?",
        "Ölçeğiniz benim için sorun değil, tam tersine sade ve hızlı plan "
        "çıkar. Mekanı görüp size özel bir yol haritası çizmek isterim — "
        "30 dakikalık bir görüşme yeter. Ne gün size uyar?",
    ],
    "teknoloji": [
        "Teknik tarafı sizin düşünmenize hiç gerek yok 🙂 Tüm kurulum ve "
        "takip bende; sizden tek istediğim otelinizi tanımam. Uğrayıp "
        "30 dakika konuşsak nasıl işlediğini sade anlatırım. Bodrumdayım, "
        "hangi gün uygun?",
        "Sistemlerle uğraşmak zorunda kalmayacaksınız, o kısmı tamamen ben "
        "yönetiyorum. En kolayı yüz yüze görüp göstermem — 30 dakika "
        "ayırabilir misiniz? Marmaris–Fethiye yoluna çıkıyorum zaten.",
    ],
    "kanit": [
        "Sonuç görmek istemeniz çok yerinde 🙂 Genel örnek yerine "
        "otelinize özel neyin işe yarayacağını yüz yüze göstermek "
        "isterim — somut olur. Bodrum tarafından geliyorum, 30 dakikalık "
        "bir görüşme yeterli. Hangi gün size uyar?",
        "Referans ve örnekleri telefonda değil, otelinize özel bir planla "
        "birlikte anlatmak daha ikna edici oluyor. Uğrayıp 30 dakika "
        "konuşalım, kararı kendiniz verin. Ne gün denk getirebiliriz?",
    ],
}


def has_active_templates(intent: str) -> bool:
    """True if there is at least one fallback template for this intent."""
    return bool(FALLBACK_TEMPLATES.get(intent))


def has_objection_playbook(objection_type: str) -> bool:
    """True if there is at least one rebuttal anchor for this objection."""
    return bool(ITIRAZ_PLAYBOOK.get(objection_type))


__all__ = [
    "FALLBACK_TEMPLATES",
    "ITIRAZ_PLAYBOOK",
    "has_active_templates",
    "has_objection_playbook",
]
