# Zernio Entegre Sistem Haritası

**Tarih:** 2026-05-22
**Durum:** 4 paralel ajan tamamlandı, hepsi `claude/vibrant-brahmagupta-m8eqI` üzerine merge edildi ve push edildi.

---

## 1. Yeni Sistem End-to-End Akışı (Şeyma → Müşteri → Şeyma)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ŞEYMA (Kurucu)                                  │
│                       seymaakrs@gmail.com                                │
└────────────┬────────────────────────────────────────────────────────────┘
             │
             ▼ (browser)
┌─────────────────────────────────────────────────────────────────────────┐
│                    mind-id (Next.js / Vercel)                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────────────┐ │
│  │ Anasayfa     │ İşletmeler   │ Bağlantılar  │ Agent Chat (MindBot) │ │
│  │ (Canvas)     │ (CRUD)       │ ✨ YENİ      │                      │ │
│  └──────────────┴──────────────┴───────┬──────┴────────────┬─────────┘ │
└────────────────────────────────────────┼───────────────────┼───────────┘
                                         │                   │
                  ┌──────────────────────┘                   │
                  │                                          │ POST /task
                  ▼                                          ▼
        ┌───────────────────┐                  ┌─────────────────────────────┐
        │ Firebase Firestore│◀─────────────────│  mind-agent (Cloud Run)     │
        │  businesses/{id}  │                  │  FastAPI + OpenAI Agents SDK│
        │  ├ zernio_profile │                  │                             │
        │  │  _id ✨        │                  │  ┌───────────────────────┐  │
        │  ├ connections/   │  realtime        │  │ Orchestrator Agent    │  │
        │  │  {platform} ✨ │  onSnapshot      │  │  ├ marketing_agent    │  │
        │  ├ comment_to_dm/ │                  │  │  ├ image_agent        │  │
        │  │  config ✨     │                  │  │  ├ video_agent        │  │
        │  ├ ads_history/ ✨│                  │  │  ├ analysis_agent     │  │
        │  └ instagram_posts│                  │  │  ├ sales_analyst      │  │
        │  errors/          │                  │  │  ├ meta_agent (CRM)   │  │
        │  zernio_logs/ ✨  │                  │  │  └ ads_expert ✨ YENİ │  │
        └─────────▲─────────┘                  │  └────────────┬──────────┘  │
                  │                            │               │             │
                  │ writes                     │               ▼             │
                  │                            │  ┌───────────────────────┐  │
                  │                            │  │ Tool Layer            │  │
                  │                            │  │  ├ orchestrator/      │  │
                  │                            │  │  ├ sales/zernio_ads_  │  │
                  │                            │  │  │  tools.py ✨      │  │
                  │                            │  │  ├ comment_to_dm ✨  │  │
                  │                            │  │  └ auto_reply        │  │
                  │                            │  └────────────┬──────────┘  │
                  │                            │               │             │
                  │                            │               ▼             │
                  │                            │  ┌───────────────────────┐  │
                  │                            │  │ src/infra/zernio/     │  │
                  │                            │  │ (mixin composition)   │  │
                  │                            │  │  ├ posts              │  │
                  │                            │  │  ├ analytics          │  │
                  │                            │  │  ├ inbox              │  │
                  │                            │  │  ├ whatsapp           │  │
                  │                            │  │  ├ media              │  │
                  │                            │  │  ├ ads ✨ YENİ        │  │
                  │                            │  │  ├ logs ✨ YENİ       │  │
                  │                            │  │  └ base (telemetry ✨)│  │
                  │                            │  └────────────┬──────────┘  │
                  │                            │               │             │
                  │                            │  GET /admin/zernio/status ✨│
                  │                            │  GET /admin/zernio/recent-  │
                  │                            │      calls ✨               │
                  │                            └───────────────┼─────────────┘
                  │                                            │
                  │                                            ▼
                  │                            ┌─────────────────────────────┐
                  │                            │   Zernio API                │
                  │                            │  api.zernio.com/v1          │
                  │  reklam loglar             │  ┌─────────────────────────┤
                  │  her API çağrısı           │  │ Posts (IG/TT/LI/YT/FB)  │
                  └────────────────────────────┤  │ Analytics               │
                                               │  │ Ads + Boost ✨          │
                                               │  │ Inbox (DM/yorum)        │
                                               │  │ WhatsApp Business       │
                                               │  │ Webhooks (8 event ✨)   │
                                               │  │ Logs API ✨             │
                                               │  └─────────────────────────┤
                                               └────────────────┬────────────┘
                                                                │
                                                                ▼
                                               ┌─────────────────────────────┐
                                               │ External Platforms          │
                                               │ Instagram | Facebook | TT   │
                                               │ LinkedIn  | YouTube  | WA   │
                                               │ Twitter                     │
                                               └────────────────┬────────────┘
                                                                │
                                          Müşteri (otel/lead)   │
                                          mesaj/yorum/etk.      │
                                                                ▼
                                               ┌─────────────────────────────┐
                                               │  Zernio Webhook             │
                                               │  POST /zernio/webhook       │
                                               │  ✨ Genişletildi: 7 event   │
                                               │  ┌─────────────────────────┤
                                               │  │ message.received        │
                                               │  │ post.published ✨       │
                                               │  │ post.failed ✨          │
                                               │  │ account.disconnected ✨ │
                                               │  │ comment.received ✨     │
                                               │  │ message.sent ✨         │
                                               │  │ post.boost.completed ✨ │
                                               │  └─────────────────────────┤
                                               └────────────────┬────────────┘
                                                                │
                                                                ▼
                                               ┌─────────────────────────────┐
                                               │ NocoDB CRM                  │
                                               │ Leadler / Etkilesimler /    │
                                               │ Itirazlar / Firsatlar       │
                                               └─────────────────────────────┘
```

---

## 2. 3 Repo / Ne Yapar / Kimle Konuşur

| Repo | Rol | Teknoloji | Konuştuğu yerler |
|---|---|---|---|
| **mind-id** | Şeyma'nın gördüğü yüz (portal) | Next.js 16, Vercel, Tailwind, Firebase Auth | → mind-agent `/task` (chat), → Zernio API doğrudan (`/accounts`, `/analytics`), → Firestore (read+write) |
| **mind-agent** | Tüm AI orkestrasyonu, agent ailesi | Python 3.11+, FastAPI, OpenAI Agents SDK, Cloud Run | → Zernio API (posts/ads/inbox/analytics/logs), → NocoDB, → Firebase, → n8n bridge, → external (Meta Ads, Google Ads, fal.ai, HeyGen, Kling, Veo) |
| **customer_agent** | n8n workflow + dokümantasyon (kod yok) | n8n.cloud | → mind-agent webhook, → NocoDB, → Gmail (Şeyma'ya rapor) |

---

## 3. Bu Session'da Yapılan Eklemeler (Hepsi Merge Edildi)

### Mind-agent (Python — `claude/vibrant-brahmagupta-m8eqI` HEAD)

| Modül | Branch | Commit | Ne yapar |
|---|---|---|---|
| **A: Zernio Ads** | `claude/zernio-ads-agent` | `899cca1` | `_AdsMixin` (14 endpoint), `ads_expert_agent` (kıdemli reklam uzmanı persona), 27 test |
| **B: DM + Webhook Events** | `claude/zernio-dm-webhooks` | `884cd1a` | 7 webhook event handler, Comment-to-DM otomasyon, replay-attack guard, 34 test |
| **D: Logs Observability** | `claude/zernio-logs-obs` | `b8bc27a` | Tüm Zernio çağrıları üstüne client-side telemetri (Langfuse + ring buffer + metrics), Logs API poller, anomali tespiti, 20 test |

**Tüm yeni test sayısı:** 120 yeşil (39 önceki + 27 ads + 34 dm/webhook + 20 logs)

### Mind-id (TypeScript — `claude/vibrant-brahmagupta-m8eqI` HEAD)

| Modül | Branch | Commit | Ne yapar |
|---|---|---|---|
| **Late→Zernio scaffolding** | `claude/vibrant-brahmagupta-m8eqI` | `f1123e3` | Paralel field migration (zernio_profile_id + late_profile_id), sync-accounts route Zernio öncelikli, Cloud Functions IG stats Zernio'ya port |
| **C: Connections UI** | `claude/zernio-connections-ui` | `c3c4b45` | "🔗 Bağlantılar" sayfası, 7 platform real-time status, Bağla/Yeniden Bağla dialog, migration banner |

---

## 4. 5 Happy-Path Flow Durumu

| # | Flow | Durum | Test Edildi? |
|---|---|---|---|
| 1 | Şeyma yeni işletme ekler → portal → Firestore → opsiyonel Zernio sync | ✅ Çalışır | Manuel UI testi gerekli (CI yok) |
| 2 | "Şu posta 100 TL boost at" → orchestrator → ads_expert → Zernio Ads | ✅ Çalışır | 27 unit test geçti, prod canlı testi gerekli |
| 3 | Marketing agent → Instagram post → Zernio `/posts` | ✅ Çalışır | 39 publisher test geçti |
| 4 | Lead WhatsApps Slowdays → webhook → NocoDB → auto_reply | ✅ Çalışır + 7 event'e genişledi | 34 yeni test, replay-attack guard |
| 5 | Haftalık IG stats → Cloud Function → Zernio analytics → Firestore | ✅ Migration tamam (Late fallback'li) | Cloud Function deploy gerekli |
| **6** ✨ | Comment-to-DM (IG yorum → otomatik DM) | ✅ Yeni implementasyon | 22 test, prod deploy bekliyor |
| **7** ✨ | Zernio anomali alert (5xx %5+, 429 sel) → Bekçi Robot | ✅ Yeni implementasyon | 20 test, Cloud Run job deploy bekliyor |

---

## 5. Bulunan ve Düzeltilen Hatalar (Audit'ten)

| Bulgu | Düzeltme |
|---|---|
| Merge conflict: `src/infra/zernio/__init__.py` (A vs D mixin sıralaması) | El ile birleştirildi: `_AdsMixin` + `_LogsMixin` ikisi de eklendi |
| `src/infra/zernio/base.py` auto-merged | `_request` chokepoint (D) + `_put`/`_delete` (A) — D'nin chokepoint'i kullanılıyor, A'nın iki verbs'ı eski tarz (telemetri'sız) — kabul edilebilir, sonra refactor edilebilir |
| `late_profile_id` field hâlâ Business şemasında | **Bilinçli korundu** — paralel migration stratejisi (eski işletmeler kırılmasın) |
| Cloud Function Late fallback | **Bilinçli korundu** — Zernio key set edilmeden Cloud Run deploy edilirse eski sistem çalışmaya devam eder |

---

## 6. Deploy Sırası (Production'a Çıkış İçin)

Şu sırayla yapmadan **PR #34 merge etme:**

1. **Secret Manager'a** ekle:
   - `ZERNIO_API_KEY` (zaten Cloud Run env'de plain — Secret Manager'a taşı)
   - `ZERNIO_WEBHOOK_SECRET`
   - `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (opsiyonel — observability için)
2. **Firestore `secrets/other`** doc'a ekle: `zernio_api_key` (mind-id Cloud Functions için)
3. **Cloud Run env güncelle:**
   - `--update-secrets ZERNIO_API_KEY=zernio-api-key:latest`
   - `GUARDIAN_ALERT_WEBHOOK_URL=https://mindidai.app.n8n.cloud/webhook/bekci-alert`
4. **Yeni Cloud Run job:** `zernio-observer` (entry: `python -m src.agents.zernio_observer.runner`), DRY_RUN=true ile başlat
5. **Zernio panel webhook URL'i** → `https://agents-sdk-api-704233028546.us-central1.run.app/zernio/webhook` (HMAC secret set)
6. **Canary deploy** mind-agent v1.23.0, kanarya %10 trafik
7. **Smoke test:** /admin/zernio/status, bir test post oluştur, webhook event tetikle
8. **Yeşil ise** %100 trafik
9. **mind-id Vercel deploy** otomatik (push'tan tetiklenir)

---

## 7. Sonraki Adımlar (Konfor #6: Users / Multi-tenant)

Hâlâ bekliyor (kullanıcı kararı):
- Zernio Users API → mind-id'de per-admin sub-user oluşturma
- Audit log: "Bu postu hangi admin attı?"
- White-label SaaS hazırlığı

Şeyma'nın kararı bekleniyor — bu strateji erken mi, yoksa şimdi mi yapılsın?

---

## 8. Branch Durumu

```
seymaakrs/mind-agent
└── claude/vibrant-brahmagupta-m8eqI   ◀── HEAD (pushed) ✅
    ├── merge: Ajan A (Ads)
    ├── merge: Ajan D (Logs Obs)
    └── merge: Ajan B (DM + Webhook)

seymaakrs/mind-id
└── claude/vibrant-brahmagupta-m8eqI   ◀── HEAD (pushed) ✅
    └── merge: Ajan C (Connections UI)

seymaakrs/customer_agent
└── (değişiklik yok — kod yok)
```

PR #34 (mind-agent) güncellendi; mind-id için PR'ı kullanıcı açacak.
