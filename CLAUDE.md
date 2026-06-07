# Claude Session Notes

> Geçmiş session detayları → `docs/history/sessions-2026-05.md`, `docs/history/sessions-2026-06.md`
>
> 📌 **2026-06-06:** Temizlik oturumu bitti, **PR #39 main'e merge edildi.** Mail
> bombardımanı durduruldu, webhook FAZ 0, NocoDB qualifier şeması uygulandı,
> 28 sahte lead temizlendi (538→510), legacy kod + sales_analyst ayıklandı.
> Sıradaki: Qualifier Agent + Google Maps prospecting + 250k TL Satış Müdürü.

## 🎯 Stratejik Öncelik

**Sales + Marketing = para kazanma motoru.** Öncelik:
1. **Gerçek lead toplama** (proaktif prospecting — pasif inbox değil)
2. Marketing Agent + brand-aware üretim
3. Diğer her şey (infra, observability, dev experience)

Soru: *"Bu Sales/Marketing'in para kazandırma gücünü artırır mı?"* Hayırsa altta.

---

## 🚦 Aktif Faz: Gerçek Lead Sistemi (2026-06-01 başladı)

### Temel kural
- **Gerçek lead = bizim bulduğumuz, ICP'ye uyan işletme.** Mesaj atan herkes değil.
- **Şeyma'ya mail yalnız şu üçü birden olunca gider:**
  1. `qualified = true`
  2. `source ∈ {gmaps, ig, linkedin, meta_lead_ads, mindid_form, itiraz}`
  3. `asama ∈ {Sicak, Teklif, Takipte}`

### Faz tablosu
| Faz | İçerik | Durum |
|---|---|---|
| **0** Kanama durdur (webhook Sıcak yazmasın, HMAC zorunlu) | ✅ DONE (PR #39, branch `claude/relaxed-clarke-tUchS`) |
| **1** Arşivleme + sade CLAUDE.md | ✅ DONE (bu commit) |
| **2** NocoDB şema güncelle (`qualified`, `source`, `Arsiv`) | ✅ DONE (applied 2026-06-02) |
| **3** n8n duplicate mail kaynakları (Lead Toplama + eski Takip Agent) kapat | ✅ DONE (deactivate) |
| **4** Sahte/test leadler temizlendi (tek seferlik, 538→510); bundan sonra `asama=Arsiv` | ✅ DONE (2026-06-02) |
| **5** Qualifier Agent (LLM + ICP fit) | ✅ DONE (branch `claude/confident-bardeen-cnKT8`) |
| **6** Google Maps Prospecting Agent | ⏳ |
| **7** Instagram Prospecting Agent | ⏳ |
| **8** LinkedIn Prospecting Agent | ⏳ |

### Bütçe kararı
- **Clay/Apollo YOK** (pahalı). Google Places API + IG public scrape + LinkedIn manuel/yumuşak.
- Google Places API key: zaten aktif (GCP `instagram-post-bot-471518`).

---

## 📂 Proje Yapısı

```
src/
├── agents/         orchestrator, image, video, marketing, analysis
│   ├── sales/      reklam_uzmani (meta alias), sales_manager  [sales_analyst KALDIRILDI]
│   ├── _legacy_slowdays/   outreach + auto_reply + guardian (eski Slowdays, deploy değil)
│   └── instructions/
├── infra/          firebase, google_ai, nocodb_client, zernio/, brand_identity
├── tools/          orchestrator, image, video, marketing, web, analysis
│   ├── sales/      nocodb (upsert_lead, query_leads, notify_seyma), reporting_tools
│   └── brand/      brand_identity load/save
├── models/         prompts
└── app/            api (FastAPI + /zernio/webhook), config
```

---

## 🔧 Kritik Bilgiler

### Cloud Run
- Service: `agents-sdk-api` (us-central1)
- Canlı revision: `agents-sdk-api-00034-vgb` (v1.22.6)
- Rollback: `agents-sdk-api-00025-rnw`
- URL: `https://agents-sdk-api-704233028546.us-central1.run.app`
- GCP Project: `instagram-post-bot-471518`

### NocoDB
- URL: `https://db.mindidai.com.tr` (Caddy reverse proxy) — eski direkt IP: `http://34.26.138.196`
- ⚠️ Caddy panel UI'yı (`/`, `/dashboard`) 403 kapatıyor; `/api/v2/*` açık. Token
  panelden alınamıyorsa `scripts/nocodb_make_token.sh` (email+şifre → API token).
- base_id: `ps9dj2fqrh823av`
- Leadler: `m5lcgc5ifeqh38h`
- Etkileşimler: `mx3kbw2vhwimxjf`
- system_settings: `mzpphfqirl8njoe`

### n8n (`https://mindidai.app.n8n.cloud`)
- Lead Toplama Agent (`l31p16NRZeyk4eEm`): ✅ DEACTIVATE edildi (duplicate mail kaynağı)
- Takip Agent eski (`nWNMQYHJzsMvMUGP`): ✅ DEACTIVATE edildi
- "Send Hot Lead Alert" ayrı workflow değil — Lead Toplama içindeki Gmail node'u
- İtiraz/Upsell/Referans/Meta Lead Ads/Bekci Alert/Raporlar: aynen kalır (aktif)

### Zernio
- WA account: `69ecc2273a63baf2053dfc21`
- Webhook: `/zernio/webhook` (artık sadece Etkileşimler log; `ZERNIO_WEBHOOK_CREATE_LEAD=true` ile opt-in lead)
- HMAC zorunlu: `ZERNIO_WEBHOOK_SECRET` set değilse 401

---

## ⚙️ Environment Variables

```bash
OPENAI_API_KEY, GOOGLE_AI_API_KEY, GCP_PROJECT_ID, GCP_LOCATION=us-central1
FIREBASE_CREDENTIALS_FILE, FIREBASE_STORAGE_BUCKET
LATE_API_KEY, FAL_KEY, SERPER_API_KEY, KLING_*, HEYGEN_API_KEY
NOCODB_BASE_URL, NOCODB_API_TOKEN
NOCODB_LEADS_TABLE_ID, NOCODB_MESSAGES_TABLE_ID, NOCODB_NOTIFICATIONS_TABLE_ID
NOCODB_SETTINGS_TABLE_ID=mzpphfqirl8njoe
ZERNIO_API_KEY, ZERNIO_BASE_URL, ZERNIO_WA_ACCOUNT_ID
ZERNIO_WEBHOOK_SECRET           # ZORUNLU
ZERNIO_WEBHOOK_CREATE_LEAD      # default false (lead yazımı qualifier'a kalsın)
N8N_BASE_URL, GUARDIAN_ALERT_WEBHOOK_URL
DRY_RUN=false
```

---

## 🧰 Ana Tools (Özet)

**Orchestrator:** `fetch_business`, dosya/firestore, posting (IG/YT/TikTok/LinkedIn), `report_error`

**Image/Video:** `generate_image` (Gemini), `generate_video` (Veo 3.1), Kling, HeyGen, fal.ai MMAudio

**Marketing:** `create_weekly_plan`, marketing memory, admin notes

**Web (Analysis):** `web_search` (Serper), `scrape_for_seo` (SEO+GEO), `scrape_competitors`, `check_serp_position`

**Analysis:** SWOT/SEO/Instagram raporları

**Sales (NocoDB CRM):** `upsert_lead` (external_id idempotent), `update_lead`, `query_leads`, `mark_lead_qualified` (Faz 5 — qualified/source/reason yazar), `log_lead_message`, `notify_seyma`

**Qualifier (Faz 5):** `qualifier` agent (registry) — lead'leri ICP fit'e (`src/tools/sales/icp.py`) göre niteler, `qualified=true/false` flag'ler. Mail kapısı: qualified + source ∈ {gmaps,ig,linkedin,meta_lead_ads,mindid_form,itiraz} + asama ∈ {Sicak,Teklif,Takipte}.

**Zernio:** `list_contacts`, `find_conversation`, `send_message`, `send_whatsapp_template`, `tag_contact`

**Brand:** `fetch_brand_identity`, `save_brand_identity`

---

## 🧭 Kritik Akışlar

### Lead Yaşam Döngüsü (yeni)
```
Prospect → Enriched → Outreach Queued → Contacted → Engaged → Qualified → Opportunity → Customer
```
Prospecting agent'ları (gmaps/ig/linkedin) `Prospect/Enriched` yazar. Qualifier `qualified=true` flag'ler. Outreach/Auto-reply ilerletir. Mail yalnız qualified + uygun aşamada.

### Webhook → Lead ayrımı
- Inbound mesaj (WA/IG) → **Etkileşimler log only**, lead değil.
- Lead promotion: Qualifier Agent (LLM + ICP) → `qualified=true` → mail.

### Business ID Propagation
Sub-agent brief'lerine `Business ID: {id}` mutlaka eklenmeli.

---

## 🔐 Güvenlik Backlog (P1 — Faz 8 sonrası)
1. NocoDB Caddy + static IP + subdomain
2. Cloud Run secrets → Secret Manager (OPENAI, GOOGLE_AI, NOCODB_API_TOKEN, ZERNIO_*)
3. NOCODB_API_TOKEN rotate

---

## 🧹 Açık İş Bırakma Kuralı (Kalıcı)

Yeni göreve başlamadan önce 3 repoda (`mind-id`, `mind-agent`, `customer_agent`) açık PR + stale branch kontrol. Açık iş varsa önce temizle, sonra başla.

---

## 📋 Temel Kurallar

1. **Test-first**: Kodu yazmadan önce test yaz.
2. **Self-review**: Yazdıktan sonra kendi kodunu review et.
3. **CLAUDE.md güncel tut**: Yeni özellik/karar → buraya yaz.
4. **Bilmediğini sor**: Varsayım yapma.
5. **Veri silme, arşivle**: Eski kayıtlar `docs/history/`, eski data `asama=Arsiv` flag.
6. **Kullanıcı yeni mezun yazılım mühendisi**: Anlatırken yazılım kavramlarını da öğret.

---

## 🚀 Docker/Deploy

```bash
docker build -t agents-sdk-api:v1.X.X .
docker tag ... us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.X.X
docker push ...
```
Versioning: `vMAJOR.MINOR.PATCH`

## API

```bash
POST /task { "task": "...", "business_id": "abc123", "task_id": "task-xyz", "extras": {} }
POST /zernio/webhook   # HMAC zorunlu, default Etkileşimler-only
```

---

## 📊 Mevcut Maliyet (~$15-30/ay)
- Cloud Run: $0-2 | Artifact Registry: $0.10 | OpenAI: $10-25
