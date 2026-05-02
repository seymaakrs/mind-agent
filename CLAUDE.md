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

## Kritik Akislar

### Marketing Agent - EXECUTE vs CREATE
- "plana gore paylas" → EXECUTE | "plan olustur" → CREATE

### Business ID Propagation
- Sub-agent brief'lerine `Business ID: {id}` MUTLAKA eklenmeli

### Late API ID'leri
- **Posting:** `instagram_id` (acc_xxxxx) | **Analytics:** `late_profile_id` (raw ObjectId)
- **Metrik Eslistirme:** `platform_post_url` ↔ `permalink` (Late ID degil!)

## Docker Deployment

**Guncel Versiyon:** `v1.20.0` (2026-05-01 — production)
**Cloud Run Revision:** `agents-sdk-api-00009-667`
**Cloud Run URL:** `https://agents-sdk-api-704233028546.us-central1.run.app`
**GCP Project:** `instagram-post-bot-471518`
**Registry:** Artifact Registry (us-central1)
**Image:** `us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.20.0`

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
| imageGenerationModel | gemini-2.5-flash-image |
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

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Firebase Storage path → GCS URI: `gs://bucket/path`
- Story: `is_story=True`, caption bos, 9:16 ratio
- Error reporting: `report_error(business_id, agent, task, error_message, error_type, severity)`
- YouTube: <=3dk = Shorts (thumbnail yok), >3dk = Normal (thumbnail desteklenir)

