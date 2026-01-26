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
- Instagram: CloudConvert + Instagram Graph API

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
│   ├── cloudconvert_client.py - Format donusumu
│   ├── instagram_client.py    - Instagram API
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
CLOUDCONVERT_API_KEY=...
```

## Firebase Model Settings

**Firestore Path:** `settings/app_settings`

```python
from src.app.config import get_model_settings
settings = get_model_settings()
# orchestrator_model, image_agent_model, video_agent_model, etc.
```

## Ana Tools

### Orchestrator Tools
- `fetch_business(business_id)` - Isletme profili + Instagram credentials
- `upload_file`, `list_files`, `delete_file` - Firebase Storage
- `get_document`, `save_document`, `query_documents` - Firestore
- `post_on_instagram`, `post_carousel_on_instagram` - Instagram posting

### Image/Video Tools
- `generate_image(prompt_data, file_name, business_id, aspect_ratio)`
- `generate_video(prompt_data, file_name, business_id)`

### Marketing Tools
- `create_weekly_plan`, `get_plans`, `get_todays_posts` - Content calendar
- `save_instagram_post`, `get_instagram_posts` - Post tracking
- `get_marketing_memory`, `update_marketing_memory` - Agent memory
- `get_admin_notes`, `add_admin_note` - Zorunlu kurallar

### Web Tools
- `web_search(query)` - Google arama
- `scrape_website(url)` - Website analizi

### Analysis Tools
- `save_swot_report(...)` - SWOT raporu kaydet
- `get_reports(business_id)` - Raporlari listele
- `save_instagram_report(...)` - Instagram metrik raporu

## Firestore Yapisi (Ozet)

```
businesses/{business_id}/
├── name, colors, logo, profile
├── instagram_account_id, instagram_access_token
├── media/           - Uretilen medyalar
├── instagram_posts/ - Paylasilan postlar
├── content_calendar/- Haftalik planlar
├── reports/         - Analiz raporlari
├── agent_memory/    - Agent hafizasi
├── tasks/           - Task tracking
└── logs/            - Task loglari
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

### Instagram Posting
1. `fetch_business` → credentials al
2. Icerik uret (image/video agent)
3. `post_on_instagram` → CloudConvert + Graph API

## Hizli Komutlar

```bash
pip install -r requirements.txt
uvicorn src.app.api:app --host 0.0.0.0 --port 8000
start-dev.bat  # Docker
```

## Bekleyen Isler

1. **Video SDK Gecisi (ASKIDA)** - Veo 3 icin google-genai SDK'ya gecis dusunuluyor

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Instagram posting: PNG→JPG, video→MP4 x264/aac donusumu otomatik
- Firebase Storage path → GCS URI: `gs://bucket/path`
