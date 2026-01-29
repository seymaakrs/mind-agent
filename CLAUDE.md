# Claude Session Notes

Bu dosya Claude Code session'lari arasinda sureklilik saglamak icin olusturuldu.

## TEMEL KURALLAR

1. **HER SESSION'DA BU DOSYAYI GUNCELLE**: Yeni ozellikler, degisiklikler eklendiginde MUTLAKA guncelle.

2. **BILMEDIGIN SEYLERI SOR**: Belirsiz veya eksik bilgi varsa MUTLAKA kullaniciya sor. Varsayim yapma, tahmin etme. Ornegin:
   - API anahtarlari, credential'lar
   - Is mantigi veya is akisi detaylari
   - Kullanicinin tercihleri veya kararlari
   - Proje ile ilgili ozel bilgiler

3. **ONCEKI CALISMALARI OKU**: Bu dosyayi okuyarak onceki session'larda yapilan calismalar hakkinda bilgi edin.

## Proje Ozeti

OpenAI Agents SDK uzerine kurulu multi-agent orchestrator sistemi.

**Mimari:**
- Image Agent: Google AI (Gemini) ile gorsel uretimi
- Video Agent: Google AI (Veo 3.1) ile video uretimi
- Marketing Agent: Instagram analiz, planlama ve paylasim
- Web Agent: Web arama ve website scraping
- Analysis Agent: SWOT analizi ve stratejik raporlar
- Orchestrator Agent: Alt agent'lari yoneten ana agent
- Storage: Firebase Storage + Firestore
- Instagram: Late API (Graph API kaldirildi)

## Yapi

```
src/
├── agents/
│   ├── orchestrator_agent.py  - Ana orchestrator
│   ├── image_agent.py         - Gorsel uretimi
│   ├── video_agent.py         - Video uretimi
│   ├── marketing_agent.py     - Sosyal medya yonetimi
│   ├── web_agent.py           - Web arama/scraping
│   ├── analysis_agent.py      - SWOT analizi
│   └── registry.py            - Agent registry
├── infra/
│   ├── firebase_client.py     - Firebase client
│   ├── google_ai_client.py    - Google AI client
│   ├── late_client.py         - Late API client (Instagram posting)
│   ├── instagram_client.py    - Instagram Graph API (arsiv, kullanilmiyor)
│   └── task_logger.py         - Task logging
├── tools/
│   ├── orchestrator_tools.py  - Firebase + Instagram tools
│   ├── image_tools.py         - generate_image
│   ├── video_tools.py         - generate_video
│   ├── instagram_tools.py     - get_instagram_insights
│   ├── marketing_tools.py     - calendar, memory, posts
│   ├── web_tools.py           - web_search, scrape_website
│   ├── analysis_tools.py      - SWOT report tools
│   └── agent_wrapper_tools.py - Sub-agent wrappers
├── models/
│   └── prompts.py             - ImagePrompt, VideoPrompt
└── app/
    ├── api.py                 - FastAPI REST API
    ├── config.py              - Settings
    └── orchestrator_runner.py - Runner
```

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=...
GCP_PROJECT_ID=...
GCP_LOCATION=us-central1
FIREBASE_CREDENTIALS_FILE=path/to/serviceAccount.json
FIREBASE_STORAGE_BUCKET=bucket.appspot.com
LATE_API_KEY=...              # Late API key (Instagram posting)
DRY_RUN=false                 # true: API cagirmadan prompt logla
```

## Dry-Run Mode

Token kullanimi ve maliyetleri analiz etmek icin dry-run modu.

**Aktiflestime:**
```bash
# .env dosyasinda
DRY_RUN=true

# Docker rebuild gerekli
docker-compose build && docker-compose up -d
```

**Calisma mantigi:**
- Image/Video tool'lari Google API'lerini CAGIRMAZ
- Prompt'lar Firestore'a loglanir: `businesses/{id}/dry_run_logs/`
- Token sayisi tiktoken ile hesaplanir

**Firestore Log Yapisi:**
```json
{
  "type": "image" | "video",
  "prompt_data": { ... },
  "full_prompt": "...",
  "token_count": 340,
  "file_name": "...",
  "aspect_ratio": "1:1",
  "created_at": "2026-01-28T..."
}
```

**Ilgili fonksiyonlar:**
- `save_dry_run_log()` - Log kaydet
- `list_dry_run_logs()` - Loglari listele

## Firebase Model Settings

**Firestore Path:** `settings/app_settings`

```python
from src.app.config import get_model_settings
settings = get_model_settings()
# orchestrator_model, image_agent_model, video_agent_model, etc.
```

**Onerilen Model Ayarlari (Maliyet Optimizasyonu):**
| Alan | Onerilen Model | Notlar |
|------|---------------|--------|
| imageGenerationModel | gemini-2.0-flash-image-generation | gemini-3-pro cok pahali! |
| orchestratorModel | gpt-4o-mini | Hafif gorevler icin yeterli |
| imageAgentModel | gpt-4o | Prompt uretimi icin |
| videoAgentModel | gpt-4o | Prompt uretimi icin |
| marketingModel | gpt-4o | Strateji ve planlama |
| webAgentModel | gpt-4o | Web arama/scraping |
| analysisAgentModel | gpt-4o | SWOT analizi |
| videoGenerationModel | veo-3.1-generate-preview | Video uretimi |

**DIKKAT:** `gemini-3-pro-image-preview` modeli **~%90 daha pahali**. Kullanmayin!

## Ana Tools

### Orchestrator Tools
- `fetch_business(business_id)` - Isletme profili + instagram_id
- `upload_file`, `list_files`, `delete_file` - Firebase Storage
- `get_document`, `save_document`, `query_documents` - Firestore
- `post_on_instagram`, `post_carousel_on_instagram` - Instagram posting (Late API)
- `report_error(...)` - Hata bildirimi (panel'de gosterilir)

### Image/Video Tools
- `generate_image(prompt_data, file_name, business_id, aspect_ratio)`
- `generate_video(prompt_data, file_name, business_id)`

### Marketing Tools
- `create_weekly_plan`, `get_plans`, `get_todays_posts` - Content calendar
- `save_instagram_post(..., permalink)` - Post kaydi (permalink = Late API'den platform_post_url)
- `get_instagram_posts` - Post listele
- `get_marketing_memory`, `update_marketing_memory` - Agent memory
- `get_admin_notes`, `add_admin_note` - Zorunlu kurallar

### Web Tools
- `web_search(query, num_results, search_type)` - DuckDuckGo ile arama
  - search_type: "text" (default) veya "news" (son haberler)
- `scrape_website(url)` - Website analizi
- `save_custom_report(...)` - Esnek block-bazli rapor kaydetme
- `update_business_profile(...)` - Website analizinden profil guncelleme

### Analysis Tools
- `save_swot_report(...)` - SWOT raporu kaydet
- `get_reports(business_id)` - Raporlari listele
- `save_instagram_report(...)` - Instagram metrik raporu

## Firestore Yapisi (Ozet)

```
errors/                      - Agent hata bildirimleri (root level)
├── {error_id}/
│   ├── business_id, agent, task, error_message
│   ├── error_type, severity, context
│   ├── created_at, resolved, resolved_at, resolution_note

businesses/{business_id}/
├── name, colors, logo, profile
├── instagram_id              - Late API hesap ID'si (acc_xxxxx)
├── media/           - Uretilen medyalar
├── instagram_posts/ - Paylasilan postlar (permalink dahil)
├── content_calendar/- Haftalik planlar
├── reports/         - Analiz raporlari
├── agent_memory/    - Agent hafizasi
├── tasks/           - Task tracking
├── logs/            - Task loglari
└── dry_run_logs/    - Token analizi loglari (DRY_RUN=true)
```

## API

```bash
POST /task
{
  "task": "...",
  "business_id": "abc123",
  "task_id": "task-xyz",  # Opsiyonel
  "extras": {}            # Opsiyonel
}
```

## Kritik Akislar

### Marketing Agent - EXECUTE vs CREATE
- "plana gore paylas", "bugunku postu at" → EXECUTE (mevcut plani uygula)
- "plan olustur", "haftalik plan hazirla" → CREATE (yeni plan olustur)
- Orchestrator bu ayrimi acikca belirtmeli!

### Business ID Propagation
- Sub-agent brief'lerine `Business ID: {id}` MUTLAKA eklenmeli
- Bu olmadan media Firestore'a KAYDEDILMEZ

### Instagram Posting (Late API)
1. `fetch_business` → instagram_id al
2. Icerik uret (image/video agent)
3. `post_on_instagram` → Late API (format donusumu Late tarafindan yapiliyor)

## Hizli Komutlar

```bash
pip install -r requirements.txt
uvicorn src.app.api:app --host 0.0.0.0 --port 8000
start-dev.bat  # Docker
```

## Bekleyen Isler

1. **Firebase Model Ayarlari Guncelleme** - `settings/app_settings` dokumaninda:
   - `imageGenerationModel`: gemini-3-pro-image-preview → gemini-2.0-flash-image-generation
   - Agent modelleri: gpt-5/gpt-4.1 → gpt-4o (maliyet optimizasyonu)
2. **Video SDK Gecisi (ASKIDA)** - Veo 3 icin google-genai SDK'ya gecis dusunuluyor

## Late API (Instagram Posting)

Graph API yerine Late API kullaniliyor.

**Endpoint:** `https://getlate.dev/api/v1`
**Auth:** `Authorization: Bearer {LATE_API_KEY}`

**Tool'lar:**
- `post_on_instagram(file_url, caption, content_type, instagram_id, is_story=False)` - Feed post, Reel veya Story
- `post_carousel_on_instagram(media_items, caption, instagram_id)` - Carousel
- `get_instagram_insights(instagram_id, date_from, date_to)` - Analytics

**Story Paylasimi:**
```python
# Story icin is_story=True kullan
post_on_instagram(
    file_url="https://...",
    caption="",  # Story'lerde caption yok, bos gonder
    content_type="image",  # veya "video"
    instagram_id="acc_xxxxx",
    is_story=True
)
```
- Story'ler caption desteklemiyor (metin istiyorsan gorselin uzerine ekle)
- Onerilen aspect ratio: 9:16 (1080x1920)
- 24 saat sonra kaybolur

**Firestore alanlari:**
- `instagram_id` - Late hesap ID'si (acc_xxxxx)

**Notlar:**
- Eski `instagram_account_id` ve `instagram_access_token` alanlari KULLANILMIYOR
- Late API format donusumunu kendi yapiyor

## Error Reporting (Agent Hata Bildirimi)

Agent'lar otonom calisirken hatalari Firebase'e kaydeder, panel'den takip edilir.

**Firestore Path:** `errors/{auto_id}`

**Tool:**
```python
report_error(
    business_id="abc123",
    agent="marketing_agent",      # Hangi agent
    task="Instagram post paylasimi",  # Ne yapiyordu
    error_message="Late API 429 hatasi",
    error_type="rate_limit",      # api_error, validation_error, timeout, rate_limit, not_found, permission, unknown
    severity="high",              # low, medium, high, critical
    context={"file_url": "..."}   # Opsiyonel ek bilgi
)
```

**Schema:**
| Alan | Tip | Aciklama |
|------|-----|----------|
| business_id | string | Hangi isletme |
| agent | string | Hangi agent (image_agent, marketing_agent, etc.) |
| task | string | Ne yapmaya calisiyordu |
| error_message | string | Hata mesaji |
| error_type | string | Hata tipi |
| severity | string | Ciddiyet seviyesi |
| context | object | Ek bilgiler |
| created_at | string | Tarih (ISO) |
| resolved | boolean | Cozuldu mu (panel'den guncellenir) |
| resolved_at | string | Cozulme tarihi |
| resolution_note | string | Nasil cozuldu |

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Firebase Storage path → GCS URI: `gs://bucket/path`
