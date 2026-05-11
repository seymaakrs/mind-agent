# Claude Session Notes

## TEMEL KURALLAR

1. **TEST-FIRST DEVELOPMENT**: Her kod yazmadan ONCE testi yaz. Sonra kodu yaz. Sonra testi calistir. Test gecene kadar kodu duzelt.
2. **SELF-REVIEW**: Kodu yazdiktan sonra kendi kodunu review et. Hatalari, edge case'leri ve iyilestirmeleri kontrol et.
3. **HER SESSION'DA BU DOSYAYI GUNCELLE**: Yeni ozellikler, degisiklikler eklendiginde MUTLAKA guncelle.
4. **BILMEDIGIN SEYLERI SOR**: Belirsiz veya eksik bilgi varsa MUTLAKA kullaniciya sor. Varsayim yapma.
5. **ONCEKI CALISMALARI OKU**: Bu dosyayi okuyarak onceki session'larda yapilan calismalar hakkinda bilgi edin.
6. **KULLANICI BIR YAZILIM MUHENDİSİ**: Kullanıcı bir yeni mezun olacak bir yazılım mühendisi. Kodları sana yazdırıyor çünkü sen daha iyi yazıyorsun. Fakat kendisi de yazılımdan geri kalmak istemiyor kendini geliştirmek istiyor. Bu yüzden onu da süreçlere dahil ederek onunda kendini gelistirmesini sagla. Fakat yazilim mühendisliğinde bulunan genel kavramları öğrenmesini sağla. Özellikle kod yazarken kullanilan kavramlari anlat.
7. **YENİ EKLEME = BAĞLI YERLERİ DE GÜNCELLE**: Yeni bir tool, agent veya özellik eklendiğinde MUTLAKA şu yerleri kontrol et ve güncelle:
   - `src/agents/instructions/video.py` → `## YOUR TOOLS` listesi (tool sayısı ve açıklaması)
   - `src/agents/instructions/video.py` → `## TOOL SELECTION` bölümü (ne zaman kullanılacağı)
   - `src/agents/instructions/orchestrator.py` → ilgili keyword listesi ve NOTE satırları
   - `src/tools/video_tools.py` → `get_video_tools()` return listesi
   - Bu CLAUDE.md → Ana Tools özeti ve ilgili bölümler
   **Kural:** Bir tool'u sadece kod olarak eklemek yetmez. Agent o tool'u ancak instruction'larında görürse kullanır.

## Proje Ozeti

OpenAI Agents SDK uzerine kurulu multi-agent orchestrator sistemi.

**Mimari:** Image Agent (Gemini) | Video Agent (Veo 3.1) | Marketing Agent (Instagram) | Analysis Agent (SWOT+SEO+Web) | **Meta Agent (Sales/Lead Ads)** | Orchestrator Agent | Firebase Storage+Firestore | Late API (Instagram/YouTube) | NocoDB CRM

**NOT:** Web Agent kaldirildi. Analysis Agent direkt web tool'larina sahip.

**SALES AGENTS (yeni):** `src/agents/sales/` altinda - Meta Agent ile basladi. Diger sales agentlari (LinkedIn, Clay, IG DM, Takip, Itiraz) `customer_agent/AGENT-MIMARISI-MASTER.md`'de planli, asama asama eklenecek.

## Yapi

```
src/
├── agents/         orchestrator, image, video, marketing, analysis, registry
│   ├── sales/      meta_agent (LinkedIn/Clay/IG DM/Takip/Itiraz planli)
│   └── instructions/  ... + sales/meta.py
├── infra/          firebase_client, google_ai_client, kling_client, late_client,
│                   task_logger, errors, nocodb_client
├── tools/          orchestrator_tools, image_tools, video_tools, instagram_tools,
│                   marketing_tools, web_tools, analysis_tools, agent_wrapper_tools
│   └── sales/      nocodb_tools (create_lead, update_lead, query_leads, ...)
├── models/         prompts.py (ImagePrompt, VideoPrompt)
└── app/            api.py, config.py, orchestrator_runner.py
```

## Environment Variables

```bash
OPENAI_API_KEY, GOOGLE_AI_API_KEY, GCP_PROJECT_ID, GCP_LOCATION=us-central1
FIREBASE_CREDENTIALS_FILE, FIREBASE_STORAGE_BUCKET
LATE_API_KEY              # Late API (Instagram/YouTube posting)
FAL_KEY                   # fal.ai MMAudio ses ekleme
SERPER_API_KEY            # Serper.dev Google SERP arama
KLING_ACCESS_KEY          # Kling AI Access Key (app.klingai.com)
KLING_SECRET_KEY          # Kling AI Secret Key
HEYGEN_API_KEY            # HeyGen AI API Key (app.heygen.com/settings)
NOCODB_BASE_URL           # NocoDB instance URL (e.g. https://noco.example.com)
NOCODB_API_TOKEN          # NocoDB xc-token
NOCODB_LEADS_TABLE_ID     # leads tablosu id
NOCODB_MESSAGES_TABLE_ID  # lead_messages tablosu id
NOCODB_NOTIFICATIONS_TABLE_ID  # seyma_notifications tablosu id
ZERNIO_API_KEY            # Zernio (WhatsApp Business + Inbox + Social) API key
ZERNIO_BASE_URL           # default: https://api.zernio.com/v1
ZERNIO_WA_ACCOUNT_ID      # default: 69ecc2273a63baf2053dfc21 (Slowdays WA hatti)
ZERNIO_WEBHOOK_SECRET     # /zernio/webhook HMAC dogrulama secret'i. Bos ise dogrulama atlanir (dev mode).
DRY_RUN=false             # true: API cagirmadan prompt logla
```

## Ana Tools (Ozet)

**Orchestrator:** `fetch_business`, `upload_file`, `list_files`, `delete_file`, `get_document`, `save_document`, `query_documents`, `post_on_instagram`, `post_carousel_on_instagram`, `post_on_youtube`, `post_on_tiktok`, `post_carousel_on_tiktok`, `post_on_linkedin`, `post_carousel_on_linkedin`, `report_error`

**Image/Video:** `generate_image`, `generate_video` (Veo 3.1), `generate_video_kling` (Kling 3.0), `generate_video_heygen` (HeyGen Video Agent), `add_audio_to_video` (fal.ai MMAudio V2)

**Marketing:** `create_weekly_plan`, `get_plans`, `get_todays_posts`, `save_instagram_post`, `get_instagram_posts`, `save_youtube_video`, `get_youtube_videos`, `get_marketing_memory`, `update_marketing_memory`, `get_admin_notes`

**Web (Analysis Agent):**
- `web_search(query, num_results, search_type)` - Serper.dev API (text/news)
- `scrape_for_seo(url)` - SEO v2 (6 kategori, 100p) + GEO analizi (4 kategori, 100p)
- `scrape_competitors(urls)` - Toplu rakip scraping (max 15 URL)
- `check_serp_position(domain, keywords)` - SERP gorunurlugu (max 10 keyword)

**Analysis:** `save_swot_report`, `save_seo_report` (v2+GEO), `save_seo_keywords`, `save_seo_summary` (v2+GEO), `get_seo_keywords`, `get_reports`, `save_instagram_report`

**Sales/Meta (NocoDB CRM):** `upsert_lead` (idempotent, ana tool), `update_lead`, `get_lead`, `query_leads`, `log_lead_message`, `notify_seyma`
- `create_lead` DEPRECATED (kod tabanında duruyor ama agent listesinde yok — webhook retry'lerinde duplicate üretiyordu)
- Wrapper: `meta_agent_tool` (orchestrator routing)
- Trigger: n8n Facebook Lead Ads -> POST /task with extras.lead_data
- Akis: lead parse -> skor hesapla -> **upsert_lead (external_id ile idempotent)** -> log_lead_message -> sicaksa notify_seyma
- Live idempotency kanıtlandı (2026-05-01): aynı external_id ile 2 task → NocoDB'de 1 kayıt

**Sales/Zernio (WhatsApp + Inbox):** `list_contacts`, `find_conversation`, `send_message`, `send_whatsapp_template`, `tag_contact`
- Client: `src/infra/zernio/` (mixin pattern: WhatsApp + Inbox; Late paterni)
- Tools: `src/tools/sales/zernio_tools.py` (henuz hicbir agent'a bagli degil — Adim 4/5'te Outreach + Webhook agent'larina baglanacak)
- `send_message` SADECE free-form (24h CS window). Cold outreach template'i `/whatsapp/bulk` Adim 4'te eklenecek.
- Error mapping: `src/infra/errors.py` `_ZERNIO_MAP` (HTTP status -> ErrorCode)

**Zernio Inbox Webhook (Adim 5):** `POST /zernio/webhook` (FastAPI route)
- Modul: `src/app/zernio_webhook.py` — `verify_signature` (HMAC-SHA256, soft mode), `map_to_lead_fields`, `map_to_message_fields`, `derive_external_id` (BSUID > phone > sender.id), `handle`
- Akis: Zernio `message.received` -> imza dogrula -> map -> `upsert_record(Leadler, external_id, ...)` -> `upsert_record(Etkilesimler, external_message_id, ...)`
- Idempotency: ayni kullanici 2 mesaj atarsa 1 lead (external_id ayni); ayni mesaj 2 kez gelirse 1 Etkilesimler satiri (platformMessageId ayni)
- Sicaklik: `direction=incoming` -> `Sicak`, `outgoing` -> `Yeni`. Diger event'ler 200 ack ile no-op.

## Kritik Akislar

### Marketing Agent - EXECUTE vs CREATE
- "plana gore paylas" → EXECUTE | "plan olustur" → CREATE

### Business ID Propagation
- Sub-agent brief'lerine `Business ID: {id}` MUTLAKA eklenmeli

### Late API ID'leri
- **Posting:** `instagram_id` (acc_xxxxx) | **Analytics:** `late_profile_id` (raw ObjectId)
- **Metrik Eslistirme:** `platform_post_url` ↔ `permalink` (Late ID degil!)

## SESSION DEVIR — 2026-05-09 (Beyza, Slowdays kampanyasi)

> **Yeni session: ONCE BU BOLUMU OKU.** Beyza kod bilmez, sade dil + tablo + emoji. Asagidaki "Plan" tablosu yapilacaklar listesidir, sirayla gidilir.

### Mevcut durum (snapshot)
- **Portal sorunu (CRM erisilemiyor):** mind-id chat route'lari mind-agent /task'e ZATEN baglandi — **PR #10** (mind-id, branch `claude/add-hot-leads-count-LJNi7`). Netlify CI'i bekliyor; Vercel'de `CHAT_API_URL=https://agents-sdk-api-704233028546.us-central1.run.app` set edilmesi gerek (set edilmese de hardcoded default ayni).
- **Persistent thread/mesaj history yok** (Firestore-backed store ayri PR'a birakildi).

### Mimari haritasi (3 ev)
| Ev | Repo | Rol | Teknoloji |
|---|---|---|---|
| Vitrin | `mind-id` | Portal (MindBot, dashboard) | Next.js, Vercel (Netlify backup, ~3 gun sonra kaldirilacak) |
| Beyin | `mind-agent` | Agent orchestrator | Python + OpenAI Agents SDK, Cloud Run |
| Defter | `mindid-nocodb` | Lead CRM | NocoDB |
| n8n akislari | `customer_agent` | Webhook/cron orkestrasyon | n8n.cloud |

### Seyma'nin canli sistemi (Slowdays kampanyasi)
- Google Places ile 331 otel cekildi -> Zernio (WhatsApp Cloud API wrapper, `https://api.zernio.com/v1`).
- `otel_gonderim.py`: 25-90sn random delay, 240/24h limit, onayli template `ege_otel_yaz_sezon_v1`.
- `lead_monitor.py`: 60sn polling, yanit verene 30-60sn sonra 3 random varyanttan biri (samimi, yuz yuze gorusme onerili).
- Scriptler **Seyma'nin Windows PC'sinde** arka planda — kapaninca durur. **Cloud Run'a tasinmali.**
- Tum dosyalar: `docs/from-seyma/HANDOFF.md`, `lead_monitor.py`, `otel_gonderim.py`, `zernio-api-openapi.yaml` (19000 satir tam OpenAPI).
- `WA_ACCOUNT_ID = 69ecc2273a63baf2053dfc21`, `ZERNIO_API_KEY = sk_bbd6...` (Secret Manager'a alinacak).

### Zernio (= Late) ne ise yariyor?
- **Sosyal medya posting** (zaten `src/infra/late/` paketinde aktif: IG/FB/LinkedIn/TikTok/YouTube)
- **WhatsApp Business + Inbox** (yeni keşif, `docs/from-seyma/HANDOFF.md`'de listelenmis 7 endpoint — henuz mind-agent'a entegre degil)
- **Comment-to-DM otomasyonu** (Instagram yorumdan DM'e — entegre degil)
- **Yapamadigi:** WhatsApp disinda outbound DM yok zaten (IG DM Zernio uzerinden var)

### Plan (sirali)
| # | Adim | Onkosul | Sure | Durum |
|---|---|---|---|---|
| 1 | Portal <-> Beyin koprusu (mind-id chat -> mind-agent /task) | — | done | **PR #10 acik, CI bekleniyor** |
| 2 | Zernio client paketi (`src/infra/zernio/`) + 4 tool (list_contacts/find_conversation/send_message/tag_contact) | 1 | 3-4 saat | **DONE 2026-05-09** — `src/infra/zernio/` (base + whatsapp + inbox mixins), `src/tools/sales/zernio_tools.py`, 19 test gecti, `_ZERNIO_MAP` errors.py'a eklendi. Agent'a henüz bağlı değil (Adım 4/5). |
| 3 | n8n "Lead Toplama Agent" payload bug fix (Calculate Lead Score code node Zernio payload mapping) | — | 1 saat | n8n API token gerekir |
| 4 | Outreach Agent (Cloud Run'da 7/24, otel_gonderim.py muadili, NocoDB'den hedef listesi) | 2 | 1 gun | **DONE 2026-05-09** — `src/agents/outreach/{policy,targeting,runner}.py`, `send_whatsapp_template` tool eklendi (Zernio /whatsapp/bulk). Cloud Run job entry: `python -m src.agents.outreach.runner`. NocoDB filter: `source_workflow_id=outreach_agent_v1 AND asama=Yeni AND telefon!=''`. DRY_RUN env'i ile guvenli test. 24 yeni test gecti. **Eksik:** Cloud Run job spec deploy + Beyza'nin 331 otel'inin NocoDB'ye `source_workflow_id=outreach_agent_v1` ile import edilmesi (Adim 9). |
| 5 | Zernio webhook listener (`/zernio/webhook` endpoint, 60sn polling biter) | 2 | 4 saat | **DONE 2026-05-09** — `src/app/zernio_webhook.py` (HMAC verify soft mode + payload mapping + idempotent upsert + Etkilesimler log), `POST /zernio/webhook` route eklendi, 27 test gecti. n8n by-pass kod tarafi hazir; Zernio panel'inden webhook URL switch manuel is. |
| 6 | Auto-reply Agent (NocoDB `message_templates` tablosu, UTF-8 dogru, intent siniflandirici opsiyonel) | 5 | 1 gun | **DONE 2026-05-10** — `src/agents/auto_reply/{policy,templates,responder,targeting,runner}.py`. LLM (OpenAI Agents SDK, Pydantic structured output) intent classify (olumlu/olumsuz/soru/spam) + Slowdays tonunda rephrase tek cagri. Polling 60sn, jitter 30-60sn, max age 60dk. Olumsuz/spam ya da conf<0.5 -> gondermez. Cloud Run job entry: `python -m src.agents.auto_reply.runner`. Adim 5 webhook'a `auto_reply_processed=false` field eklendi (Etkilesimler tablosuna Checkbox column gerek). 22 yeni test gecti, regression yok (51/51). |
| 7 | Guardrail (reply rate <%5 -> pause, quality YELLOW -> pause) + Seyma bildirim | 6 | 4 saat | bekliyor |
| 8 | Reporting dashboard (mind-id sekmesi, gonderim/reply/quality/CPL) | 7 | 1 gun | bekliyor |
| 9 | Seyma'nin local scriptlerini emekliye ayir + 331 oteli NocoDB'ye tasi | 4-7 | 2 saat | bekliyor |
| 10 | NocoDB test verisi temizligi (is_test=true flag, dev/prod ayrim) | 9 | 2 saat | bekliyor |

### Bekleyen kullanici aksiyonlari
- **Vercel'de** `CHAT_API_URL` env'ini Cloud Run URL'ine set et (PR #10 merge sonrasi)
- **Cloud Run Secret Manager'a** `ZERNIO_API_KEY` ekle (Adim 2 deploy oncesi)
- **n8n API token** uret (Adim 3 icin)
- **Whatsapp Business hangi araç?** sorusu artik gereksiz — Zernio kullaniliyor (Seyma'nin handoff'undan netlesti)

---

### YARIN DEVAM (2026-05-10) — kaldigimiz yer

**Bugun bitenler (2026-05-09):**
- Adim 1: mind-id PR #10 (portal-beyin koprusu) — onceki session
- Adim 2: Zernio client + 4 tool — commit `25f75eb`
- Adim 3: n8n payload mapping fix + smoke test (NocoDB Id=66 verified, sonra silindi)
- Adim 4: Outreach Agent — commit `1bb86af` (24 test gecti)
- Adim 5: Zernio webhook listener — commit `ce37bf5` (27 test gecti)

**Su an aktif branch (3 repo):** `claude/add-hot-leads-count-LJNi7`

**SIRADA (oncelik sirasi):**
1. **Deploy + import** (kullanicinin manuel isleri — kod tarafi hazir):
   - Cloud Run image rebuild (v1.22.0): API'da `/zernio/webhook` route, ayrica yeni Cloud Run **job** (entry `python -m src.agents.outreach.runner`)
   - Cloud Run job env: `NOCODB_*`, `ZERNIO_API_KEY`, `OUTREACH_*` overrides, **ilk start `DRY_RUN=true`**
   - Zernio panel webhook URL'i n8n yerine `https://...run.app/zernio/webhook` + secret set
   - 331 otel NocoDB'ye import: `source_workflow_id=outreach_agent_v1`, `asama=Yeni`, `kaynak=Manuel`, `telefon` E.164 (Adim 9 ile birlesir)
2. **Adim 6 — Auto-reply Agent** (`lead_monitor.py` muadili). Adim 5 webhook'u inbound mesaji `Sicak`'a flag'liyor; Adim 6 LLM ile rephrase'lenmis takip atar. NocoDB `message_templates` tablosu okur (UTF-8). Onkosul: Adim 5 (HAZIR).
3. **Adim 7** — Guardrail (reply rate <%5 / quality YELLOW pause + Seyma bildirim)
4. **Adim 8** — Reporting dashboard (mind-id sekmesi)

**Aciklik gerektiren karar (yarin Beyza'ya sor):**
- Adim 6'da intent siniflandirici (LLM ile "olumlu/olumsuz/soru") koyalim mi, yoksa basit keyword mu? Seyma'nin scriptindeki 3 random varyant yaklasimi yeterli mi?

**Tasarim kararlari hatirlatma (degistirmemek icin not):**
- Adim 4'te `kaynak` degil `source_workflow_id='outreach_agent_v1'` ile filter — kaynak "lead nereden geldi" anlamini korur, workflow_id "hangi agent sahip"
- Adim 5 webhook HMAC: `ZERNIO_WEBHOOK_SECRET` set degilse soft mode (log warning, accept) — Zernio panel switch'i sirasinda kullanici break olmasin diye
- Adim 4 long-running worker (cron yerine) — jitter + batch break Meta spam filtresine karsi


### Karar verilmis seyler (degismez)
- Vercel canonical (Netlify ~3 gun backup)
- mind-agent Python + OpenAI Agents SDK
- Branch (her 3 repo): `claude/add-hot-leads-count-LJNi7`
- Yol A (mimari dogru, thread API ileride Firestore-backed) tercih edildi — Yol B (hizli stateless) elendi
- Beyza kod bilmez: sade dil, tablo, emoji renk; teknik soru yok; A/B sec sor

### Ilgili PR'lar
- mind-id #10 (chat bridge, draft, CI bekliyor)

---

## Docker Deployment

**Guncel Versiyon:** `v1.21.0` (2026-05-09 — production, Sales Analyst eklendi)
**Cloud Run Revision:** `agents-sdk-api-00025-rnw`
**Cloud Run URL:** `https://agents-sdk-api-704233028546.us-central1.run.app`
**Portal URL (mind-id, Vercel):** `https://mind-id-gray.vercel.app`
**GCP Project:** `instagram-post-bot-471518`
**Registry:** Artifact Registry (us-central1)
**Image:** `us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.21.0`
**Onceki revision (rollback):** `agents-sdk-api-00009-667` (v1.20.0)

**v1.21.0 Yenilikler (Sales Analyst):**
- `src/tools/sales/reporting_tools.py` — 7 read-only tool (count/list/funnel/channel/stale/timeline/digest)
- `src/agents/sales/sales_analyst_agent.py` — yeni agent (read-only NocoDB CRM raporu)
- Orchestrator -> `sales_analyst_tool` routing (kac/listele/funnel/dagilim/takili/timeline/gunluk rapor)
- Akilli tarih yorumu ([TODAY: ISO] marker'i + LLM "bu hafta" -> ISO date_from/date_to)
- TR cevap, default limit 10, max 500
- `meta_agent_tool` (yazma) vs `sales_analyst_tool` (okuma) net ayrimi

**v1.20.0 Yenilikler:**
- Sales Agent (Meta) + NocoDB CRM tools entegre
- `upsert_lead` idempotent tool (external_id key)
- `nocodb_client` array body fix (NocoDB v2 records API requirement)
- Firebase Secret Manager üzerinden okunuyor (env var değil)

**Secrets (Cloud Run env'de değil, Secret Manager'da):**
- `FIREBASE_CREDENTIALS_FILE` → secret `firebase-credentials:latest` (key id 52b2405d, mindid-75079 SA)

```bash
docker build -t agents-sdk-api:v1.16.1 .
docker tag agents-sdk-api:v1.16.1 us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.16.1
docker push us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.16.1
```

Versioning: `vMAJOR.MINOR.PATCH` (MAJOR=breaking, MINOR=feature, PATCH=bugfix)

## SEO Workflow (8 adim)

1. `fetch_business` → website URL
2. `scrape_for_seo` → v2 skor (6 kategori) + GEO analizi (4 kategori)
3. `web_search` → rakipleri bul
4. `scrape_competitors` → toplu scrape
5. `check_serp_position` → SERP dogrulama
6. `save_seo_keywords` → keywords kaydet
7. `save_seo_report` → rapor kaydet (v2+GEO)
8. `save_seo_summary` → ozet + agent memory + SERP + GEO

**SEO Skoru (100p):** Technical(25) + OnPage(25) + Content(20) + Mobile(15) + Schema(10) + Authority(5)
**GEO Skoru (100p):** AI Crawler(25) + Content Structure(25) + Citation(25) + AI Discovery(25)
**NOT:** v2 skorlari dusuk (tipik site: 50-65). GEO ve SEO AYRI skorlar.

## Firestore Yapisi

```
active_tasks/{id}           - Task monitoring (TTL 24h)
errors/{id}                 - Agent hata bildirimleri
businesses/{bid}/
├── media/, instagram_posts/, youtube_videos/, content_calendar/
├── reports/                - SWOT, SEO, Instagram raporlari
├── seo/summary             - SEO ozeti (overwrite)
├── seo/keywords            - Anahtar kelimeler (overwrite)
├── agent_memory/           - Agent hafizasi
├── instagram_stats/        - Haftalik metrikler (week-YYYY-WW)
├── tasks/, logs/, dry_run_logs/
```

## Instagram Haftalik Analiz

**Path:** `instagram_stats/week-{YYYY}-{WW}`
- Cloud Function → metrics yaz → Agent gorev at
- Marketing Agent → doc oku → onceki haftalarla karsilastir → Turkce summary yaz (`merge=True`)

**Summary Alan Adlari (STRICT):** `insights`, `recommendations`, `week_over_week`, `analyzed_at` (ISO), `analyzed_by` ("marketing_agent")
- Alan adlari INGILIZCE, icerikler TURKCE

## Video Audio (fal.ai MMAudio V2)

`add_audio_to_video(video_url, prompt, business_id, file_name, ...)` - fal.ai CDN gecici, Firebase'e kaydet!
Akis: `generate_video` → `add_audio_to_video` → `post_on_instagram/youtube`

## Model Ayarlari

**Path:** `settings/app_settings` | `from src.app.config import get_model_settings`
**DIKKAT:** `gemini-3-pro-image-preview` ~%90 daha pahali!

| Alan | Model |
|------|-------|
| imageGenerationModel | gemini-2.0-flash-image-generation |
| orchestratorModel | gpt-4o-mini |
| image/video/marketing/analysisModel | gpt-4o |
| videoGenerationModel | veo-3.1-generate-preview |
| klingVideoModel | kling-v3 |

## API

```bash
POST /task { "task": "...", "business_id": "abc123", "task_id": "task-xyz", "extras": {} }
```

## Structured Error Handling (v1.15.0)

**Modul:** `src/infra/errors.py` — `ServiceError`, `ErrorCode`, `classify_error()`, `classify_late_response()`

**Tool'lar structured error dict doner:**
```python
{"success": False, "error": "...", "error_code": "RATE_LIMIT", "service": "google_ai",
 "retryable": True, "retry_after_seconds": 60, "user_message_tr": "Servis su an yogun..."}
```

**Error Codes:** RATE_LIMIT, SERVER_ERROR, TIMEOUT, CONTENT_POLICY, AUTH_ERROR, INVALID_INPUT, INSUFFICIENT_BALANCE, NOT_FOUND, PERMISSION_DENIED, NETWORK_ERROR, UNKNOWN

**Agent Davranisi:**
- `retryable=True` → Agent max 1 kez retry yapar (retry_after_seconds bekler)
- `retryable=False` → Agent user_message_tr ile kullaniciya bildirir + report_error cagir
- `error_code=CONTENT_POLICY` → Prompt'u rephrase edip tekrar dene
- `error_code=RATE_LIMIT` (marketing) → schedule_retry_job ile ertelenmis retry

## Hizli Komutlar

```bash
pip install -r requirements.txt
uvicorn src.app.api:app --host 0.0.0.0 --port 8000
start-dev.bat  # Docker
```

## Bekleyen Isler

1. Firebase Model Ayarlari Guncelleme (settings/app_settings)
2. Video SDK Gecisi (ASKIDA) - google-genai SDK
3. **Sales Agent Genisletme:** customer_agent/AGENT-MIMARISI-MASTER.md'deki diger 5 agent (LinkedIn, Clay, IG DM, Takip, Itiraz). Her biri `src/agents/sales/` altinda Meta agent ornegini takip edecek.
4. **Meta Agent Genisletme:** Facebook Ads Manager API (CTR/CPC/CPL izleme, A/B test, gunluk rapor) - su anki tools sadece NocoDB CRUD.
5. **NocoDB sertlestirme (P1, 2026-05-09 tespit edildi)** — 3 sorun ust uste yasandi:
   - Bazi ISP/kurumsal aglar port 80'i blokluyor (Beyza pc'sinden erisemedi, telefon hotspot'undan ya da Cloud Shell'den OK)
   - External IP ephemeral; restart sonrasi degisme riski
   - Bot saldirilari (/cgi-bin/.../sh path'leri) NocoDB SQLite pool'unu doldurdu -> OOM crash, kontainer restart'a girdi
   **Cozum:** Static IP + subdomain (orn. `crm.slowdaysai.com`) + Caddy reverse proxy (auto Let's Encrypt 443) + NocoDB'yi `127.0.0.1:8080`'e bagla (dis dunyaya hic acik olmasin) + Caddy'de junk path filter (/cgi-bin /.env /.git /wp-admin -> 444). 1-2 saatlik tek seferlik is. Beyza musait olunca yapilacak.

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Firebase Storage path → GCS URI: `gs://bucket/path`
- Story: `is_story=True`, caption bos, 9:16 ratio
- Error reporting: `report_error(business_id, agent, task, error_message, error_type, severity)`
- YouTube: <=3dk = Shorts (thumbnail yok), >3dk = Normal (thumbnail desteklenir)

