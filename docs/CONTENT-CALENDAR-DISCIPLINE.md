# İçerik Takvimi Disiplini (Pazarlama Müdürü)

> **Hedef:** Pazarlama Müdürü içerik takvimini doldurken hangi sırada,
> hangi kontrolleri yaparak ilerleyeceğini bilsin. Vibe coding +
> ADHD-dostu işleyiş için tek sayfa.

## Yer

İçerik takvimi **Firestore**'da:
```
businesses/{business_id}/content_calendar/{plan_id}
```

NocoDB'de YOK — ADR-001 sınırına göre (NocoDB = CRM/Sales, Firestore =
medya/ops). Sales Manager bu takvime ERIŞMEZ; sadece Pazarlama Müdürü
yazar.

## Mevcut tool seti (zaten kurulu)

| Tool | Ne yapar |
|---|---|
| `create_weekly_plan(business_id, start_date, end_date, posts, notes)` | Haftalık plan yarat |
| `get_plans(business_id, status?)` | Planları listele |
| `get_plan(business_id, plan_id)` | Tek plan detayı |
| `update_plan_status(business_id, plan_id, status)` | draft/active/archived |
| `add_post_to_plan(business_id, plan_id, post)` | Plana post ekle |
| `update_post_in_plan(business_id, plan_id, post_id, fields)` | Post güncelle |
| `remove_post_from_plan(business_id, plan_id, post_id)` | Post sil |
| `get_todays_posts(business_id, date?)` | Bugünün postları |

## Plan dokümanı şeması (mevcut)

```json
{
  "plan_id": "plan-20260518-20260524",
  "business_id": "biz_x",
  "start_date": "2026-05-18",
  "end_date": "2026-05-24",
  "status": "active",
  "created_by": "agent",
  "posts": [
    {
      "post_id": "post-1",
      "scheduled_date": "2026-05-22",
      "scheduled_time": "10:00",
      "content_type": "image",
      "content_pillar": "sakin yaşam",
      "topic": "Bodrum'un kalabalıksız koylarında bir sabah",
      "brief": "Erken sabah, sis kalkmış, deniz durgun, kahve fincanı...",
      "caption_draft": "Sade kal, yavaş yaşa. Yeni günün ilk ışığında...",
      "voice_check": "tone=sıcam ama profesyonel, avoid=müthiş kullanılmadı",
      "status": "draft"
    }
  ],
  "notes": "Haftalık 3 post: 2 görsel + 1 carousel"
}
```

> `content_pillar` ve `voice_check` alanları 2026-05-22'de **Pazarlama
> Müdürü disiplini** için tanıtıldı. Zorunlu değil ama Müdür bu iki
> alanı boş bırakmamalı — content rotation ve marka tonu denetimi
> için kullanılacak.

## Mecburi akış (Pazarlama Müdürü'nün kendi içinde)

```
1. Şef/Şeyma "X marka için haftalık takvim yap" der
   ↓
2. get_sales_playbook(business_id)
   ↓ completeness >= 3?
   ↓ HAYIR → "Brand identity eksik, doldurman gerek" diye dur
   ↓ EVET ↓
3. content_pillars listesini al → pillar rotation kuralı uygula
   (her pillar haftada en az 1 kez, hiçbir pillar arka arkaya 2 gün değil)
   ↓
4. Her post için:
   - scheduled_date + time
   - content_pillar (PLAYBOOK'taki listeden, uydurma değil)
   - topic + brief (Defne/Toprak için brand-aware brief)
   - caption_draft (voice.tone + voice.preferred_words kullan,
                    voice.avoid_words YASAK)
   - voice_check (kısa not: "tone uyumlu, avoid_words yok")
   ↓
5. create_weekly_plan(...) → plan_id döner
   ↓
6. Şef/Şeyma'ya "X plan oluşturuldu, N post içeriyor, ilk post: ..." diye raporla
```

## Pillar rotation kuralları

Müdür `content_strategy.pillars` listesini Brand Identity'den okur. Örnek:
`["sakin yaşam", "doğa", "yerel lezzet"]` (3 pillar).

Haftalık 5 post için pillar dağılımı:
- Pazartesi: sakin yaşam
- Salı: doğa
- Çarşamba: yerel lezzet
- Perşembe: sakin yaşam (tekrar)
- Cuma: doğa

Asla aynı pillar iki gün üst üste değil — algoritma seviyesinde basit.

## Brief yazma kuralları (Defne için)

Defne (`image_agent`) bir brief alır. Bu brief'in içermesi gereken:

1. **Brand kontekst** — visual.visual_style + visual.image_dos
2. **Konu** — content_pillar + post topic
3. **Yasak** — visual.image_donts + voice.avoid_words (caption yasakları
   ile karıştırma — bu görsel yasak)
4. **Çıktı formatı** — boyut (1:1 IG single, 4:5 IG portrait, 9:16 story),
   format (JPG, max 5MB)

Örnek brief:
```
[İşletme: Slowdays | Stil: organik, sıcak, doğal | Renkler: #E8D5B7, #2B4A3E]
Konu: Sakin yaşam pillar — Bodrum'un kalabalıksız koylarında sabah
Görsel YAPILAR: dogal ısık, insan teması, yumuşak gölge
Görsel YASAKLAR: stock görünüm, parlak studio, kalabalık plaj
Boyut: 1080x1080 (IG single, 1:1), JPG, max 5MB
```

## Hata durumları (Müdür DURMALI)

| Durum | Aksiyon |
|---|---|
| Brand identity yok | "Şeyma BrandIdentity doldurmalı, üretim duruyor" raporu |
| completeness < 3 | "Marka bilgisi eksik (X/5), tamamlanmadan üretim YOK" raporu |
| content_strategy.pillars boş | "İçerik sütunları tanımsız, hangi konuda üretelim?" |
| voice.tone boş | "Marka sesi tanımsız, generic ton kullanmaktan kaçınıyorum" |
| Aynı pillar art arda 2 gün | "Rotation ihlal — düzeltiyorum" + planı yeniden hesapla |

## Maliyet / not

- Plan oluşturma 1 LLM round'u (yaklaşık 5K-10K token).
- Defne brief'i otomatik üretme: Pazarlama Müdürü kendi LLM round'unda yapar.
- Her post için ayrı Defne çağrısı → ayrı Gemini Images call → ayrı maliyet.
- 5 postluk hafta: ~5×$0.005 = $0.025 (Gemini 2.0 Flash Image)
- LLM planning: ~$0.05 (gpt-4o-mini)
- **Toplam haftalık: ~$0.10**

## İlerideki TODO

- [ ] `content_pillar` ve `voice_check` alanları için schema validator
      (Marketing tool seviyesinde reddet)
- [ ] Late API entegrasyonu — plan üzerinden zamanlanmış post (Şeyma tarafı)
- [ ] Drift detection — yayınlanan post'un brand voice'a uyumu (PR sonrası faz)
