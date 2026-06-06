# Geçmiş Session Notları (Mayıs 2026)

> Bu dosya CLAUDE.md'den taşınan eski session-devir bloklarıdır.
> Veri kaybı olmasın diye saklandı; aktif çalışma için CLAUDE.md'ye bakın.

---

## 2026-05-09 — Slowdays kampanyası, mimari harita, plan

### Mimari haritası (3 ev)
| Ev | Repo | Rol | Teknoloji |
|---|---|---|---|
| Vitrin | `mind-id` | Portal (MindBot, dashboard) | Next.js, Vercel |
| Beyin | `mind-agent` | Agent orchestrator | Python + OpenAI Agents SDK, Cloud Run |
| Defter | `mindid-nocodb` | Lead CRM | NocoDB |
| n8n akışları | `customer_agent` | Webhook/cron orkestrasyon | n8n.cloud |

### Slowdays canlı sistemi (Şeyma'nın Windows PC'sinde çalışıyordu)
- Google Places ile 331 otel çekildi → Zernio (WhatsApp Cloud API wrapper)
- `otel_gonderim.py`: 25-90sn random delay, 240/24h limit, template `ege_otel_yaz_sezon_v1`
- `lead_monitor.py`: 60sn polling, yanıt verene 30-60sn sonra 3 random varyant
- WA_ACCOUNT_ID = `69ecc2273a63baf2053dfc21`

### Plan (Slowdays deploy sırası)
| # | Adım | Durum |
|---|---|---|
| 1 | Portal ↔ Beyin köprüsü | DONE (PR #10) |
| 2 | Zernio client + 4 tool | DONE (`25f75eb`) |
| 3 | n8n Lead Toplama payload fix | DONE |
| 4 | Outreach Agent | DONE (`1bb86af`) |
| 5 | Zernio webhook listener | DONE (`ce37bf5`) |
| 6 | Auto-reply Agent | DONE (`a76cc21`) |
| 7 | Şeyma scripti parity fix | DONE (`6cd9adb`) |
| 8 | Bekçi Robot (Guardian) | DONE (`0fe8397`) |
| 8.5 | Bekçi Alert n8n workflow + 13 inaktif arşiv | DONE (`1573c41`) |
| 8.6 | system_settings auto-create migration | DONE (`9ed27d6`) |
| C | MindBot 3 status tool | DONE (`dc74375`) |
| 9 | n8n bridge tool | DONE (`4e8772e`) |

---

## 2026-05-11 — n8n sales agent haritası

| Agent | Workflow ID | Tetik | Domain |
|---|---|---|---|
| İtiraz Agent | `9nTdKNPLCjo8DKfE` | Webhook `/itiraz-gelen` | Gemini sınıflandırma, Şeyma'ya öneri maili |
| Takip Agent | `nWNMQYHJzsMvMUGP` | Schedule 6sa | Leadler tarama, mail |
| Upsell Agent | `kVXXr4e6O5F3lGiD` | Schedule 10:00 | Fırsatlar Kazanıldı + 28-32 gün |
| Referans Agent | `28hnN6OrH5TF9NX2` | Schedule 11:00 | 58-62 gün referans maili |
| Meta Lead Ads Agent | `xblguxS49CJ4r4OF` | FB Lead Ads webhook | Lead → NocoDB + mail |
| Lead Toplama Agent | `l31p16NRZeyk4eEm` | Webhook | Lead skor + NocoDB + mail |

### Migration: Guardian schema (Cloud Shell, 2026-05-11)
`scripts/migrate_guardian_schema.py` — system_settings tablosu, 7 kolon, initial row.
- `NOCODB_SETTINGS_TABLE_ID=mzpphfqirl8njoe`

---

## 2026-05-12 — Faz 1 Deploy + Brand Identity

### Cloud Run v1.22.6 (revision `agents-sdk-api-00034-vgb`) canlıya alındı
Rollback noktası: `agents-sdk-api-00025-rnw` (v1.21.0 orijinal).

### Brand Identity Faz A altyapısı (commit `2c76c8e`)
- `src/infra/brand_identity.py` — Pydantic BrandIdentity şeması
- `src/tools/brand/__init__.py` — Firestore load/save/fetch/update
- 40 yeni test
- Firestore yolu: `businesses/{id}/brand_identity/v1`
- `BRAND_IDENTITY_SCHEMA_VERSION = 1`

### Brand Identity şeması özet
```
basics: name, tagline, industry, founded_year, languages
visual: primary_colors, secondary_colors, logo_url, font_family, ...
voice:  tone, personality, avoid_words, preferred_words, cta_style
audience: primary, geo, languages
content_strategy: pillars, posting_cadence, hashtag_strategy
business_context: products, usp, competitors, seo_keywords
```

Helper: `BrandIdentity.prompt_summary()` agent prompt'larına enjekte.

### Atomic switch planı (deploy edilmedi)
- 3 Cloud Run job: `slowdays-outreach`, `slowdays-auto-reply`, `slowdays-guardian`
- Hepsi ilk `DRY_RUN=true`, atomic pencerede `false`
- Zernio panel webhook URL → Cloud Run endpoint
- n8n Takip Agent filter güncelle

---

## Migrations koşulanlar (geçmiş kayıt)
- 2026-05-10: `migrate_auto_reply_schema.py` — Etkileşimler.auto_reply_processed, Leadler.asama 'Takipte', Leadler.son_temas
- 2026-05-11: `migrate_guardian_schema.py` — system_settings tablosu

---

## Bekleyen iş listesi (snapshot, 2026-05-12)
1. Lead Onboarding workflow publish (`nz8tNAR737yjrQRS`)
2. İtiraz aşama option migration
3. Takip Agent v3 vs Hot Lead Reminder kararı
4. Slowdays atomic switch (deploy edilmedi)
5. Güvenlik P1 (NocoDB token rotate, Secret Manager, Caddy reverse proxy)
6. Tier 2.2-2.3 + Tier 3-4 n8n workflow'ları
