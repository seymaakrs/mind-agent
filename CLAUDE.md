# Claude Session Notes

> **YENI SESSION BURADAN OKU:**
> 1. Bu bolumdeki **Aktif Durum (Apr 2026)** ve **Sirali Plan** kismini oku
> 2. Kullanici **Beyza** — junior muhendis, ogrenerek ilerliyor (Kural 6'ya bak)
> 3. Asagidaki TEMEL KURALLAR'a uy
> 4. `docs/customer-integration-contract.md` — sozlesme dokumani

## Aktif Durum (Apr 2026)

**Branch:** `claude/integrate-customer-mind-agent-7u9Bn` | **PR:** seymaakrs/mind-agent#2 (draft)

### Ekip
- **Beyza** — Tum uygulama (mind-agent integration, n8n, NocoDB, Cloud Run deploy, customer_agent ekosistemi). Junior muhendis, ogrenerek ilerliyor — kavramlari anlat.
- **Seyma** — Mimar (vizyon, satis kapanis). Kod yazmiyor, gorevleri Beyza yapar.
- **Burak** — Ortakliktan ayrildi (Mart 2026). OpenAI key'i Seyma'ya aktarildi (Apr 26).

### Iki Sistem, Bir Kopru
```
mind-agent (BU REPO — AI brain)        customer_agent (Beyza'nin kurdugu)
  - Image/video/marketing/analysis      - NocoDB CRM (kuruldu, 7 tablo)
  - Customer agent kopru (read-only,    - n8n workflow'lari (Meta baglantisi eksik)
    flag arkasinda, default kapali)     - Zernio Console "akilli agent" (Seyma config)
  - Cloud Run prod: v1.18.0             - 6 sub-agent (LinkedIn/Meta/Clay/DM/Takip/Itiraz)
                                          — henuz yapilmadi, plan: AGENT-MIMARISI-MASTER.md
                                            (customer_agent reposu)
       \         /
        \       /
       NOCODB (single source of truth)
       URL: http://34.26.138.196 (cred .env'de, git'te degil)
```

**Onemli:** mind-agent'taki customer agent koprusu **flag arkasinda** (`settings/app_settings.customerAgent.enabled` default false). Yani biz mind-agent'i deploy edersek mevcut akislar bozulmaz, Beyza customer_agent ekosistemini bitirince flag'i acariz.

### Sirali Plan — Beyza'nin Yapacaklari

| # | Adim | Durum | Detay |
|---|---|---|---|
| 1 | NocoDB cred .env'de | ✅ | Token: `MNhF...` (.env'de, git'te degil) |
| 2 | NocoDB token verify | ✅ | VM'den curl test edildi, lead verisi geldi |
| 3 | Cloud Run env var: yeni OPENAI key | ⏳ | GCP console (`instagram-post-bot-471518`) |
| 4 | Eski OpenAI key revoke | ⏳ | platform.openai.com/api-keys |
| 5 | Faz 4 deploy (Docker v1.19.0 + Cloud Run) | ⏳ | Yol secimi: Cloud Build (kolay) vs Docker Desktop |
| 6 | Beyza dev environment kurulumu | ⏳ | git clone + Python + gcloud (~1 saat) |
| 7 | Customer_agent ekosistemine devam | ⏳ | n8n + 6 agent + Console agent |
| 8 | Customer flag aktivasyonu | ⏳ | Ekosistem hazir olunca Firestore'da `enabled=true` |
| 9 | Git history purge (.env eski commit'lerde) | ⏳ | BFG Repo Cleaner |

### Kritik Notlar (Yeni Claude'a Ipuclari)

1. **Beyza'nin ISP'i port 80'i blokluyor** — `34.26.138.196` (NocoDB) tarayicidan acilmiyor; mobil hotspot/VPN gerekiyor. NocoDB sagliklh, sorun sadece Beyza'nin agi.
2. **Sandbox dis IP'lere erisemiyor** — sandbox'tan curl `34.26.138.196` "Host not in allowlist" doner. Live test ya VM'den ya Cloud Run'dan yapilir.
3. **`.env` git takibinde DEGIL** — `b3f43a8` commit'inde kaldirildi. Ama eski commit'lerde key'ler var (BFG purge bekliyor).
4. **Yeni OpenAI key** `sk-proj-fGrN...` `.env`'de aktif. Eski key (`sk-proj-8j4l...`) hala revoke edilmedi — Cloud Run'da hala eski key.
5. **Cloud Run projesi `instagram-post-bot-471518`** (mindid-lab degil; mindid-lab Seyma'nin baska projesi).
6. **Image agent OpenAI'da kalir** — Gemini gorsel uretimi farkli sistem, swap yapilamaz.
7. **Beyza'nin PC'sinde kod yok** — Burak yazmisti, simdi GitHub'da. Beyza dev environment kurmali (Adim 6).

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

**Mimari:** Image Agent (Gemini) | Video Agent (Veo 3.1) | Marketing Agent (Instagram) | Analysis Agent (SWOT+SEO+Web) | Customer Agent (NocoDB CRM, feature flag) | Orchestrator Agent | Firebase Storage+Firestore | Late API (Instagram/YouTube)

**NOT:** Web Agent kaldirildi. Analysis Agent direkt web tool'larina sahip.

**Customer Agent:** customer_agent ekosistemi (n8n + NocoDB) ile koprudur. Read-only iskelet, feature flag arkasinda (`settings/app_settings.customerAgent`). Sozlesme: `docs/customer-integration-contract.md`.

## Multi-Provider LLM (M1-M5 tamam)

**Path:** `src/infra/llm_providers.py` + `src/infra/agent_model_factory.py` + `src/app/config.py`

3 provider OpenAI-compatible (tek SDK, 3 backend):

| Provider | base_url | env_var |
|---|---|---|
| openai | https://api.openai.com/v1 | `OPENAI_API_KEY` |
| gemini | https://generativelanguage.googleapis.com/v1beta/openai/ | `GOOGLE_AI_API_KEY` |
| deepseek | https://api.deepseek.com/v1 | `DEEPSEEK_API_KEY` |

**Per-agent provider switch** — Firestore'da `settings/app_settings`:
```yaml
agentProviders:
  orchestrator: openai
  marketing:    gemini   # ← bu satiri degistir, agent yeniden basladiginda gecer
  analysis:     gemini
  customer:     openai
```

`make_agent_model(agent_name)`:
- provider=openai → string model adi (default SDK client)
- provider=gemini/deepseek + key SET → `OpenAIChatCompletionsModel(AsyncOpenAI(base_url, api_key))`
- provider=gemini/deepseek + key YOK → string fallback (sistem kirilmaz)
- bilinmeyen provider → openai fallback

**Yeni agent eklerken:** `_AGENT_TO_MODEL_FIELD` dict'ine ekle (`agent_model_factory.py`).

## Customer Agent Capability Flags

`settings/app_settings.customerAgent`:
- `enabled` (master, default false) — false iken orchestrator customer tool'unu HIC enjekte etmez
- `canReadLeads` (default false) — `customer_search_leads`, `customer_get_lead`
- `canReadPipeline` (default false) — `customer_get_pipeline_summary`
- `canAttachReports`, `canTriggerFollowup`, `canPostForLead` — ileri faz, henuz tool yok

Tum bayraklar default false → mevcut akislar etkilenmez (regresyon yok).

## Yapi

```
src/
├── agents/         orchestrator, image, video, marketing, analysis, customer, registry
├── infra/          firebase_client, google_ai_client, kling_client, late_client,
│                   nocodb_client, task_logger, errors
├── tools/          orchestrator_tools, image_tools, video_tools, instagram_tools,
│                   marketing_tools, web_tools, analysis_tools, customer_tools,
│                   agent_wrapper_tools
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
MIND_AGENT_API_KEY        # /task endpoint Bearer token (set => auth ON)
NOCODB_BASE_URL           # NocoDB CRM (customer_agent ekosistemi)
NOCODB_API_TOKEN          # NocoDB xc-token
NOCODB_BASE_ID            # NocoDB project/base ID (p_xxxx)
NOCODB_TABLE_LEADS        # tablo ID — Leadler
NOCODB_TABLE_PIPELINE     # tablo ID — Pipeline
NOCODB_TABLE_ETKILESIMLER # tablo ID — Etkilesimler
N8N_BASE_URL              # n8n webhook base (customer_agent tetikleyici)
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

**Customer (Faz B/iskelet, feature flag arkasinda):**
- `customer_search_leads(asama, limit)` - NocoDB Leadler okuma + asama filtresi
- `customer_get_lead(lead_id)` - tek lead detayi
- `customer_get_pipeline_summary()` - asama sayim + Kazanildi gelir toplami

**Customer Agent Capability Flags** (`settings/app_settings.customerAgent`):
- `enabled` (master) | `canReadLeads` | `canReadPipeline` | `canAttachReports` | `canTriggerFollowup` | `canPostForLead`
- Tum bayraklar default `false`. enabled=False iken orchestrator customer tool'unu HIC enjekte etmez (regresyon yok).

## Kritik Akislar

### Marketing Agent - EXECUTE vs CREATE
- "plana gore paylas" → EXECUTE | "plan olustur" → CREATE

### Business ID Propagation
- Sub-agent brief'lerine `Business ID: {id}` MUTLAKA eklenmeli

### Late API ID'leri
- **Posting:** `instagram_id` (acc_xxxxx) | **Analytics:** `late_profile_id` (raw ObjectId)
- **Metrik Eslistirme:** `platform_post_url` ↔ `permalink` (Late ID degil!)

## Docker Deployment

**Guncel Versiyon:** `v1.18.0`
**GCP Project:** `instagram-post-bot-471518`
**Registry:** Artifact Registry (us-central1)
**Image:** `us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk/agents-sdk-api:v1.18.0`

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

1. **Eski OpenAI key revoke** — Şeyma platform.openai.com'dan yapacak (yeni key `.env`'de aktif: `sk-proj-fGrN...`)
2. **Cloud Run env var guncelle** — `instagram-post-bot-471518` projesinde `OPENAI_API_KEY` swap (Faz 4 deploy ile birlikte)
3. **NocoDB credentials** — Şeyma'dan: `NOCODB_BASE_URL`, `NOCODB_API_TOKEN`, 3 tablo ID
4. **Git history purge** — `.env` git geçmişinde, BFG Repo Cleaner gerekli (eski key'ler hâlâ orada)
5. **Faz 3** — NocoDB live test (cred gelince): `customer_search_leads` end-to-end
6. **Faz 4** — Docker `v1.19.0` build + Cloud Run deploy + flag aktivasyon
7. **Faz 6** — Marketing agent Gemini'ye al (Firestore tek satir), 1 hafta gozlem, kademeli yayilim
8. Firebase Model Ayarlari Guncelleme (settings/app_settings)
9. Video SDK Gecisi (ASKIDA) - google-genai SDK

## Customer Agent Integration — Yapilanlar (Apr 2026)

**Branch:** `claude/integrate-customer-mind-agent-7u9Bn` | **PR:** seymaakrs/mind-agent#2 (draft)

**Faz 1 (skeleton):**
- `docs/customer-integration-contract.md` — sozlesme dokumani
- `src/infra/nocodb_client.py` — NocoDB HTTP client + writable column whitelist
- `src/agents/customer_agent.py`, `src/agents/instructions/customer.py`
- `src/tools/customer_tools.py` — 3 read tool (search_leads, get_lead, pipeline_summary)
- Customer agent feature flags (`enabled`, `canReadLeads`, `canReadPipeline`, ...)
- Orchestrator wrapper tool injection (flag-gated)

**Faz 2 (5 guvenlik fix):**
- CORS `*` → origin whitelist (`get_cors_config()`)
- `/task` Bearer auth (`MIND_AGENT_API_KEY`, `verify_api_key()`)
- Path Traversal: `src/infra/path_safety.py` → `safe_path_segment()`
- SSRF: `src/infra/url_safety.py` → `validate_url_safety()`, `safe_get()` (web_tools)
- IDOR (Firestore): `_validate_firestore_path()`, `ALLOWED_BUSINESS_SUBCOLLECTIONS`
- IDOR (Late): `_check_late_profile_ownership()` (instagram_tools)

**Faz M1-M5 (multi-provider migration):**
- M1: `llm_providers.py` registry
- M2: `config.py` `agent_providers` dict + parser (case-insensitive, fail-safe)
- M3: `agent_model_factory.py` `make_agent_model()` helper
- M5: Gemini live adapter (`OpenAIChatCompletionsModel + AsyncOpenAI`)
- M4 deepseek: yapi hazir, key gelirse otomatik aktif

**Operasyonel:**
- OpenAI key rotation (yeni key `.env`)
- `.env` git takibinden cikarildi (commit `b3f43a8`)

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Firebase Storage path → GCS URI: `gs://bucket/path`
- Story: `is_story=True`, caption bos, 9:16 ratio
- Error reporting: `report_error(business_id, agent, task, error_message, error_type, severity)`
- YouTube: <=3dk = Shorts (thumbnail yok), >3dk = Normal (thumbnail desteklenir)

