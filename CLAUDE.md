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
- Analysis Agent: SWOT + SEO analizi + Web arama/scraping (direkt erisim)
- Orchestrator Agent: Alt agent'lari yoneten ana agent
- Storage: Firebase Storage + Firestore
- Instagram: Late API (Graph API kaldirildi)

**NOT:** Web Agent kaldirildi. Analysis Agent artik web_search, scrape_for_seo ve scrape_competitors tool'larina direkt erisime sahip.

## Yapi

```
src/
├── agents/
│   ├── orchestrator_agent.py  - Ana orchestrator
│   ├── image_agent.py         - Gorsel uretimi
│   ├── video_agent.py         - Video uretimi
│   ├── marketing_agent.py     - Sosyal medya yonetimi
│   ├── analysis_agent.py      - SWOT + SEO + Web (direkt tool erisimi)
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
│   ├── video_tools.py         - generate_video, add_audio_to_video
│   ├── instagram_tools.py     - get_instagram_insights, get_post_analytics
│   ├── marketing_tools.py     - calendar, memory, posts
│   ├── web_tools.py           - web_search, scrape_website, scrape_for_seo
│   ├── analysis_tools.py      - SWOT + SEO report tools
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
FAL_KEY=...                   # fal.ai API key (MMAudio ses ekleme)
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
| analysisAgentModel | gpt-4o | SWOT + SEO analizi |
| videoGenerationModel | veo-3.1-generate-preview | Video uretimi |

**DIKKAT:** `gemini-3-pro-image-preview` modeli **~%90 daha pahali**. Kullanmayin!

## Ana Tools

### Orchestrator Tools
- `fetch_business(business_id)` - Isletme profili + website + instagram_id + late_profile_id + youtube_id
- `upload_file`, `list_files`, `delete_file` - Firebase Storage
- `get_document`, `save_document`, `query_documents` - Firestore
- `post_on_instagram`, `post_carousel_on_instagram` - Instagram posting (Late API)
- `post_on_youtube` - YouTube video posting (Late API)
- `report_error(...)` - Hata bildirimi (panel'de gosterilir)

### Image/Video Tools
- `generate_image(prompt_data, file_name, business_id, aspect_ratio)`
- `generate_video(prompt_data, file_name, business_id)`
- `add_audio_to_video(video_url, prompt, business_id, file_name, ...)` - fal.ai MMAudio V2

### Marketing Tools
- `create_weekly_plan`, `get_plans`, `get_todays_posts` - Content calendar
- `save_instagram_post(..., permalink)` - Post kaydi (permalink = Late API'den platform_post_url)
- `get_instagram_posts` - Post listele
- `save_youtube_video`, `get_youtube_videos`, `get_youtube_video_by_id` - YouTube video kayitlari
- `get_marketing_memory`, `update_marketing_memory` - Agent memory
- `get_admin_notes`, `add_admin_note` - Zorunlu kurallar

### Web Tools (Analysis Agent icin)
- `web_search(query, num_results, search_type)` - DuckDuckGo ile arama
  - search_type: "text" (default) veya "news" (son haberler)
- `scrape_website(url)` - Website analizi (genel kullanim)
- `scrape_for_seo(url, include_subpages, max_subpages)` - Detayli SEO analizi (v2)
  - Meta tags, headings (H1-H6), images (alt text), links, schema markup
  - **v2:** Technical SEO (robots.txt, sitemap, SSL, redirect, TTFB, security headers)
  - **v2:** Mobile-friendliness (viewport, responsive, media queries, touch icon)
  - **v2:** Content quality (readability, keyword placement, stuffing detection)
  - **v2:** 6-kategorili SEO skoru (0-100, daha gercekci)
  - Alt sayfa analizi destegi
- `scrape_competitors(urls, max_concurrent)` - Toplu rakip scraping
  - Birden fazla URL'i tek seferde paralel scrape eder
  - common_keywords, avg_seo_score, schema_types_used dondurur
  - **v2:** mobile_viewport, content_depth (thin/normal/comprehensive)
  - max 15 URL, max 10 concurrent
- `check_serp_position(domain, keywords, num_results)` - **YENİ** Gercek arama gorununurlugu
  - DuckDuckGo'da her keyword icin arar, domain'in sonuclarda olup olmadigini kontrol eder
  - visibility_score (0-100), pozisyon (1-10 veya bulunamadi)
  - Max 10 keyword, aramalar arasi 1sn bekleme

### Analysis Tools
- `save_swot_report(...)` - SWOT raporu kaydet (reports/ altina)
- `save_seo_report(...)` - SEO analiz raporu kaydet (reports/ altina, versiyonlu)
  - **v2:** score_breakdown, technical_seo, mobile_analysis, content_quality, serp_positions, serp_visibility_score
- `save_seo_keywords(...)` - SEO anahtar kelimeleri kaydet (seo/keywords, tek doc, overwrite)
- `save_seo_summary(...)` - SEO ozeti + agent memory guncelle (seo/summary, overwrite)
  - **v2:** serp_visibility_score, score_breakdown
- `get_seo_keywords(...)` - Kayitli anahtar kelimeleri getir
- `get_reports(business_id)` - Raporlari listele
- `save_instagram_report(...)` - Instagram metrik raporu

## Firestore Yapisi (Ozet)

```
active_tasks/                - Aktif task monitoring (root level, TTL 24h)
├── {auto_id}/
│   ├── business_id, task, task_id, log_id
│   ├── status (running/success/failed)
│   ├── started_at, completed_at, duration_ms
│   ├── current_step, last_activity_at  (fire-and-forget, her tool call'da guncellenir)
│   ├── error, expires_at (Firestore TTL - completed_at + 24h)

errors/                      - Agent hata bildirimleri (root level)
├── {error_id}/
│   ├── business_id, agent, task, error_message
│   ├── error_type, severity, context
│   ├── created_at, resolved, resolved_at, resolution_note

businesses/{business_id}/
├── name, colors, logo, profile
├── website                   - Isletme website URL'i (SEO analizi icin)
├── instagram_id              - Late API Instagram hesap ID'si (acc_xxxxx) - POSTING icin
├── late_profile_id           - Late profile ID (raw ObjectId) - ANALYTICS icin
├── youtube_id                - Late API YouTube hesap ID'si (acc_xxxxx)
├── media/           - Uretilen medyalar
├── instagram_posts/ - Paylasilan Instagram postlari (permalink dahil)
├── youtube_videos/  - Paylasilan YouTube videolari
├── content_calendar/- Haftalik planlar
├── reports/         - Analiz raporlari (SWOT, SEO, Instagram, custom)
├── seo/             - SEO verileri (tek versiyon, her analizde guncellenir)
│   ├── summary      - SEO ozeti (hizli erisim, rapor referansi)
│   └── keywords     - Anahtar kelimeler (array olarak tek doc)
├── agent_memory/    - Agent hafizasi (seo bilgileri dahil)
├── instagram_stats/ - Haftalik Instagram metrikleri + agent summary
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

## Docker Deployment (Cloud Run)

**Guncel Versiyon:** `v1.7.1`

**GCP Project ID:** `instagram-post-bot-471518`

**Image URL (Cloud Run icin):**
```
gcr.io/instagram-post-bot-471518/agents-sdk-api:v1.7.2
```

### GCR'ye Push (Kullanici "gcr ye pushla" dediginde)

```bash
# 1. Build (proje root'unda)
docker build -t agents-sdk-api:v1.7.2 .

# 2. Tag (GCR icin)
docker tag agents-sdk-api:v1.7.2 gcr.io/instagram-post-bot-471518/agents-sdk-api:v1.7.2

# 3. Push
docker push gcr.io/instagram-post-bot-471518/agents-sdk-api:v1.7.2
```

### Versiyon Yukseltme

Yeni versiyon cikarirken:
1. Bu dokumandaki "Guncel Versiyon" alanini guncelle
2. Semantic versioning kullan: `vMAJOR.MINOR.PATCH`
   - MAJOR: Breaking change
   - MINOR: Yeni ozellik (backward compatible)
   - PATCH: Bug fix
3. Tag'de nokta hatasi yapma! `v1.2.0` ✓ / `v.1.2.0` ✗

### Notlar

- Docker Hub yerine GCR kullan (Cloud Run ile ayni altyapi, daha hizli)
- `mirror.gcr.io` cache gecikmeleri sorun cikarabilir, GCR direkt erisim saglar
- Cloud Run deploy icin: Console'dan veya `gcloud run deploy` ile

## Bekleyen Isler

1. **Firebase Model Ayarlari Guncelleme** - `settings/app_settings` dokumaninda:
   - `imageGenerationModel`: gemini-3-pro-image-preview → gemini-2.0-flash-image-generation
   - Agent modelleri: gpt-5/gpt-4.1 → gpt-4o (maliyet optimizasyonu)
2. **Video SDK Gecisi (ASKIDA)** - Veo 3 icin google-genai SDK'ya gecis dusunuluyor

## Video Audio Generation (fal.ai MMAudio V2)

Video'lara AI ile ses/muzik ekleme. fal-client kutuphanesi kullanilarak.

**API:** `fal-ai/mmaudio-v2` (fal.ai)
**Auth:** `FAL_KEY` env var (fal-client otomatik okur, config'den direkt okunur)
**Kutuphane:** `fal-client>=0.13`

**Tool:**
```python
add_audio_to_video(
    video_url="https://...",      # Public video URL (ZORUNLU)
    prompt="gentle piano music",   # Ses aciklamasi (ZORUNLU)
    business_id="abc123",          # Firebase kaydi icin
    file_name="video_audio.mp4",   # Firebase dosya adi
    negative_prompt="no speech",   # Istenmeyen sesler
    num_steps=25,                  # Kalite (4-50, default 25)
    duration=8,                    # Ses suresi saniye (1-30, default 8)
    cfg_strength=4.5               # Prompt sadakati (0-20, default 4.5)
)
```

**Tipik Akis:**
1. `generate_video` → video olustur, public_url al
2. `add_audio_to_video` → public_url ile ses ekle, Firebase'e kaydet
3. `post_on_instagram` veya `post_on_youtube` → sesli videoyu paylas

**Notlar:**
- `duration` video suresi ile eslestirilmeli
- `cfg_strength` yuksek = prompt'a sadik, dusuk = video icerigine sadik
- fal.ai CDN URL'leri gecici → business_id + file_name ile Firebase'e kaydet!
- DRY_RUN modunda fal.ai API cagirilmaz

## Late API (Instagram Posting)

Graph API yerine Late API kullaniliyor.

**Endpoint:** `https://getlate.dev/api/v1`
**Auth:** `Authorization: Bearer {LATE_API_KEY}`

**Tool'lar:**
- `post_on_instagram(file_url, caption, content_type, instagram_id, is_story=False)` - Feed post, Reel veya Story
- `post_carousel_on_instagram(media_items, caption, instagram_id)` - Carousel
- `get_instagram_insights(instagram_id, date_from, date_to, limit, page, sort_by, order)` - Analytics (pagination + sorting)
- `get_post_analytics(instagram_id, post_id)` - Tekil post analitigi

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
- `instagram_id` - Late hesap ID'si (acc_xxxxx) - **POSTING icin**
- `late_profile_id` - Late profile ID (raw ObjectId) - **ANALYTICS icin**

**Notlar:**
- Eski `instagram_account_id` ve `instagram_access_token` alanlari KULLANILMIYOR
- Late API format donusumunu kendi yapiyor
- Posting ve Analytics farkli ID'ler kullaniyor!

## Instagram Metrik Eslistirme

**ONEMLI:** Late Analytics'ten gelen `id` (postId) Late'in internal ID'sidir, Instagram'in native ID'si DEGILDIR!

| Kaynak | ID Alani | Icerik |
|--------|----------|--------|
| Late Analytics | `id` | Late Internal ID (MongoDB ObjectId) |
| Late Analytics | `late_post_id` | Late Scheduled Post ID (opsiyonel) |
| Late Analytics | `platform_post_url` | Instagram post URL'i ✓ |
| Firestore `instagram_posts` | doc ID | Instagram Native ID |
| Firestore `instagram_posts` | `permalink` | Instagram post URL'i ✓ |

**Eslistirme icin `platform_post_url` ve `permalink` kullanin:**

```python
# Analytics'ten gelen insight'i Firestore post'una eslestir
for insight in insights:
    url = insight.get("platform_post_url")
    matching_post = next(
        (p for p in saved_posts if p.get("permalink") == url),
        None
    )
    if matching_post:
        # Artik insight'in metriklerini matching_post'un topic/theme'i ile iliskilendirebilirsin
        topic = matching_post.get("topic")
        reach = insight.get("metrics", {}).get("reach")
```

**Dikkat Edilecekler:**
- Eski kayitlarda `permalink` bos olabilir (Late gecisinden once)
- `is_external: true` postlar Firestore'da kayitli olmayabilir
- URL karsilastirmasi yaparken trailing slash farki olabilir

## Instagram Analytics Tools

**ONEMLI:** Analytics ve Posting farkli ID'ler kullaniyor!
- **Posting:** `instagram_id` (acc_xxxxx formati)
- **Analytics:** `late_profile_id` (raw ObjectId formati: `6977991f7e7ed569a4f15eca`)

**Liste Analitigi:**
```python
get_instagram_insights(
    late_profile_id,        # Late profile ID (raw ObjectId, business.late_profile_id)
    date_from=None,         # YYYY-MM-DD format
    date_to=None,           # YYYY-MM-DD format
    limit=20,               # Posts per page (max 100)
    page=1,                 # Page number
    sort_by="date",         # "date" or "engagement"
    order="desc"            # "asc" or "desc"
)
```
- Returns: `media_items[]`, `pagination{}`, `summary{}`
- Metrikler: impressions, reach, likes, comments, shares, saves, clicks, views, engagement_rate
- **NOT:** Analytics verisi Late API tarafindan en fazla 60 dakikada bir guncellenir (cache)

**Tekil Post Analitigi:**
```python
get_post_analytics(
    late_profile_id,        # Late profile ID (raw ObjectId, business.late_profile_id)
    post_id                 # Late ID veya External ID (otomatik resolve)
)
```
- Returns: Detayli post objesi + `platform_analytics[]`
- Metrikler: impressions, reach, likes, comments, shares, saves, clicks, views, engagement_rate, last_updated

**Ornek Kullanim:**
```python
# Son 1 haftanin en iyi performans gosterenleri
insights = await get_instagram_insights(
    late_profile_id="6977991f7e7ed569a4f15eca",
    date_from="2026-01-25",
    date_to="2026-01-31",
    limit=10,
    sort_by="engagement",
    order="desc"
)

# Tekil post detayi
post = await get_post_analytics(
    late_profile_id="6977991f7e7ed569a4f15eca",
    post_id="65f1c0a9e2b5af..."
)
```

**Pagination Response:**
```json
{
  "pagination": {
    "total": 47,
    "page": 1,
    "limit": 20,
    "total_pages": 3
  }
}
```

## YouTube Posting (Late API)

YouTube'a video yukleme icin Late API kullaniliyor. **Otomatik Firestore kaydı yapar.**

**Tool'lar:**
- `post_on_youtube(video_url, youtube_id, business_id, ...)` - Video yukle + otomatik Firestore kaydi
- `get_youtube_videos(business_id)` - Videolari listele
- `get_youtube_video_by_id(business_id, youtube_video_id)` - Tek video kaydi

**Firestore alanlari:**
- `youtube_id` - Late hesap ID'si (acc_xxxxx)

**Firestore Path:** `businesses/{business_id}/youtube_videos/{video_id}`

**Zorunlu parametreler:**
- `video_url` - Video dosyasinin public URL'i
- `youtube_id` - Late hesap ID'si
- `business_id` - Firestore kaydi icin business ID

**Opsiyonel parametreler:**
- `title` - Video basligi (max 100 karakter)
- `description` - Video aciklamasi (max 5000 karakter)
- `visibility` - public, unlisted, private (default: public)
- `made_for_kids` - COPPA uyumlulugu (default: false)
- `tags` - Etiketler (toplam 500 karakter limiti)
- `thumbnail_url` - Ozel kapak gorseli (sadece >3dk videolar)
- `first_comment` - Sabitlenecek ilk yorum (max 10000 karakter)
- `scheduled_for` - Zamanlanmis yayin (ISO datetime)
- `our_media_path` - Kaynak video Firebase Storage path'i (tracking icin)

**Video Tipleri:**
| Sure | Tip | Thumbnail |
|------|-----|-----------|
| <= 3 dakika | YouTube Shorts | Desteklenmiyor |
| > 3 dakika | Normal Video | Destekleniyor |

**Ornek Kullanim:**
```python
# 1. Business'tan youtube_id al
business = await fetch_business(business_id)
youtube_id = business["youtube_id"]

# 2. Video yukle (otomatik Firestore'a kaydeder)
result = await post_on_youtube(
    video_url="https://storage.googleapis.com/.../video.mp4",
    youtube_id=youtube_id,
    business_id=business_id,
    title="Video Basligi",
    description="Video aciklamasi...",
    tags=["tag1", "tag2"],
    our_media_path="videos/business123/video.mp4"
)
# Firestore'a otomatik kaydedildi: businesses/{business_id}/youtube_videos/{video_id}
```

## SEO Analysis v2 (Anahtar Kelime, Rakip ve SERP Analizi)

Analysis agent DIREKT web tool'larina sahip. Baska agent cagirmaz.

**Veri Yapisi:**
- `seo/` collection: Guncel SEO durumu (tek versiyon, her analizde overwrite)
- `reports/seo-xxx`: SEO raporlari (versiyonlu, tarihce icin)

**SEO Workflow (8 adim):**
1. `fetch_business` → website URL al
2. `scrape_for_seo` → isletme sitesini analiz et (v2: technical SEO, mobile, content quality, 6-kategorili skor)
3. `web_search` → rakipleri bul
4. `scrape_competitors` → TUM rakipleri tek seferde scrape et
5. `check_serp_position` → **YENİ** top 5-7 keyword ile gercek arama gorununurlugunu dogrula
6. `save_seo_keywords` → anahtar kelimeleri kaydet (seo/keywords overwrite)
7. `save_seo_report` → raporu kaydet (reports/ altina, versiyonlu, v2 alanlari dahil)
8. `save_seo_summary` → ozet guncelle (seo/summary overwrite) + agent memory + SERP visibility

**v2 SEO Skor Algoritmasi (6 Kategori, 100 Puan):**
| Kategori | Maks Puan | Kontrol Edilen |
|----------|-----------|----------------|
| Teknik SEO | 25 | robots.txt, sitemap, SSL+guvenlik, redirect, TTFB, canonical |
| On-Page SEO | 25 | title, meta desc, H1, heading hierarchy, image alt, URL |
| Icerik Kalitesi | 20 | kelime sayisi, okunabilirlik, keyword title'da, keyword H1'de, stuffing yok |
| Mobil & Performans | 15 | viewport, responsive, touch icon, mobil TTFB |
| Schema & Yapisal Veri | 10 | JSON-LD, schema tipleri, OG tags |
| Otorite Sinyalleri | 5 | dis linkler, ic linkler, sosyal linkler |

**Cezalar:** Title yok (-15), H1 yok (-10), HTTPS degil (-10), Birden fazla H1 (-5), Keyword stuffing (-5), Sitemap yok (-3), SSL 30 gun icinde bitiyor (-3), 3+ redirect (-2)

**ONEMLI:** v2 skorlari v1'den DAHA DUSUK olacak. Tipik kucuk isletme sitesi 50-65 arasi skor alir. 75+ sadece iyi optimize edilmis siteler icin.

**Keyword Kategorileri:**
| Kategori | Aciklama |
|----------|----------|
| primary | Yuksek hacim, cogu rakipte var |
| secondary | Orta hacim, bazi rakiplerde |
| long_tail | Spesifik, 3+ kelime, dusuk rekabet |
| local | Lokasyon bazli (sehir, ilce) |

**Search Intent:**
- `informational` - Bilgi arayan (nasil, nedir, rehber)
- `transactional` - Satin alma niyetli (satin al, fiyat, siparis)
- `navigational` - Belirli siteye ulasma

---

### SEO Firestore Semalari

**Path:** `businesses/{business_id}/seo/summary`
```json
{
  "overall_score": 55,
  "business_seo_score": 55,
  "top_keywords": ["dijital ajans", "web tasarim", "istanbul"],
  "main_issues": ["No sitemap.xml", "SERP visibility 0%", "Missing H1"],
  "competitor_count": 10,
  "competitor_avg_score": 48,
  "last_report_id": "seo-20260205-abc123",
  "last_analysis_date": "2026-02-05T10:30:00Z",
  "updated_at": "2026-02-05T10:30:00Z",
  "serp_visibility_score": 25,
  "score_breakdown": {
    "technical_seo": {"score": 18, "max": 25},
    "on_page_seo": {"score": 15, "max": 25},
    "content_quality": {"score": 10, "max": 20},
    "mobile_performance": {"score": 8, "max": 15},
    "schema_structured_data": {"score": 2, "max": 10},
    "authority_signals": {"score": 2, "max": 5}
  }
}
```
| Alan | Tip | Aciklama |
|------|-----|----------|
| overall_score | number | Genel SEO skoru (0-100, v2) |
| business_seo_score | number | Isletme sitesinin SEO skoru |
| top_keywords | string[] | En onemli 10 anahtar kelime |
| main_issues | string[] | Duzeltilmesi gereken sorunlar (max 5) |
| competitor_count | number | Analiz edilen rakip sayisi |
| competitor_avg_score | number | Rakiplerin ortalama SEO skoru |
| last_report_id | string | Son raporun ID'si (reports/ referansi) |
| last_analysis_date | string | Son analiz tarihi (ISO) |
| updated_at | string | Guncelleme tarihi (ISO) |
| serp_visibility_score | number\|null | **v2** Gercek arama gorununurlugu (0-100) |
| score_breakdown | object\|null | **v2** 6-kategorili skor detayi |

---

**Path:** `businesses/{business_id}/seo/keywords`
```json
{
  "items": [
    {
      "keyword": "dijital ajans",
      "category": "primary",
      "search_intent": "transactional",
      "priority": "high",
      "competitor_usage": 8,
      "notes": "8/10 rakip kullaniyor"
    },
    {
      "keyword": "istanbul web tasarim",
      "category": "local",
      "search_intent": "transactional",
      "priority": "high",
      "competitor_usage": 6,
      "notes": ""
    }
  ],
  "total_count": 25,
  "source": "seo_analysis",
  "report_id": "seo-20260131-abc123",
  "updated_at": "2026-01-31T10:30:00Z"
}
```
| Alan | Tip | Aciklama |
|------|-----|----------|
| items | array | Anahtar kelime listesi |
| items[].keyword | string | Anahtar kelime |
| items[].category | string | primary, secondary, long_tail, local |
| items[].search_intent | string | informational, transactional, navigational |
| items[].priority | string | high, medium, low |
| items[].competitor_usage | number | Kac rakip kullaniyor |
| items[].notes | string | Ek notlar |
| total_count | number | Toplam kelime sayisi |
| source | string | Kaynak (seo_analysis) |
| report_id | string | Iliskili rapor ID'si |
| updated_at | string | Guncelleme tarihi (ISO) |

---

**Path:** `businesses/{business_id}/reports/seo-{date}-{hex}`
```json
{
  "id": "seo-20260205-abc123",
  "type": "seo",
  "created_at": "2026-02-05T10:30:00Z",
  "created_by": "agent",
  "overall_score": 55,
  "summary": "SEO skoru 55/100. Teknik altyapi orta (robots.txt yok, sitemap eksik). SERP gorununurlugu dusuk...",
  "business_website_analysis": {
    "url": "https://example.com",
    "meta_tags": { "title": "...", "title_length": 55, "description": "...", "description_length": 150 },
    "headings": { "h1": ["..."], "h1_count": 1, "has_single_h1": true },
    "images": { "total_images": 15, "images_with_alt": 12, "images_without_alt": 3 },
    "seo_score": 55
  },
  "competitors": [
    { "domain": "rakip1.com", "seo_score": 62, "title": "...", "description": "...", "mobile_viewport": true, "content_depth": "comprehensive" }
  ],
  "competitor_urls": ["https://rakip1.com", "https://rakip2.com"],
  "keyword_recommendations": [
    { "keyword": "dijital ajans", "category": "primary", "search_intent": "transactional", "priority": "high", "competitor_usage": 8, "notes": "..." }
  ],
  "technical_issues": [
    { "type": "warning", "issue": "No sitemap.xml", "recommendation": "Create sitemap.xml with all page URLs" },
    { "type": "error", "issue": "SERP visibility 0%", "recommendation": "Submit sitemap to Google Search Console" }
  ],
  "content_recommendations": ["Ana sayfa metnini 800 kelimeye cikarin", "Her hizmet icin ayri sayfa olusturun"],
  "data_sources": { "business_website": true, "competitors": true, "web_search": true },
  "score_breakdown": {
    "total_score": 55, "raw_score": 58, "penalty_total": -3,
    "breakdown": {
      "technical_seo": {"score": 18, "max": 25},
      "on_page_seo": {"score": 15, "max": 25},
      "content_quality": {"score": 10, "max": 20},
      "mobile_performance": {"score": 8, "max": 15},
      "schema_structured_data": {"score": 5, "max": 10},
      "authority_signals": {"score": 2, "max": 5}
    }
  },
  "technical_seo": {
    "robots_txt": {"has_robots_txt": false, "allows_crawling": true},
    "sitemap": {"has_sitemap": false},
    "ssl": {"ssl_valid": true, "cert_expiry_days": 180},
    "ttfb_ms": 850, "redirect_count": 1
  },
  "mobile_analysis": {"has_viewport": true, "has_responsive_meta": true, "has_media_queries": true, "score": 11},
  "content_quality": {"word_count": 520, "content_depth": "normal", "readability_score": 8.2, "keyword_stuffing": false},
  "serp_positions": [
    {"keyword": "dijital ajans istanbul", "position": null, "found": false},
    {"keyword": "web tasarim", "position": 7, "found": true}
  ],
  "serp_visibility_score": 25
}
```

## Instagram Haftalık Analiz Sistemi

Cloud Function tarafından tetiklenen otomatik haftalık Instagram analiz sistemi.

**Akış:**
```
1. Cloud Function (Pazar 23:00)
   └─> Late API'den son 7 günlük veriyi çek
   └─> Firestore'a metrics yaz (instagram_stats/week-YYYY-WW)
   └─> Backend /task endpoint'ine agent görevi at

2. Marketing Agent
   └─> Doc'u oku (get_document)
   └─> Önceki haftaları listele (query_documents)
   └─> Karşılaştırmalı analiz yap
   └─> Summary üret (Türkçe)
   └─> Aynı doc'a yaz (save_document, merge=True)
```

**Firestore Path:** `businesses/{business_id}/instagram_stats/week-{YYYY}-{WW}`

**Week ID Format:** `week-2026-05` (yılın 5. haftası, ISO week number)

### Schema

```json
{
  "week_id": "week-2026-05",
  "week_number": 5,
  "year": 2026,
  "date_range": {
    "start": "2026-01-27",
    "end": "2026-02-02"
  },

  "metrics": {
    "total_posts": 8,
    "total_reach": 12400,
    "total_impressions": 18600,
    "total_likes": 892,
    "total_comments": 67,
    "total_saves": 156,
    "total_shares": 43,
    "avg_engagement_rate": 4.2,
    "by_content_type": {
      "reels": { "count": 4, "reach": 8900, "likes": 620 },
      "image": { "count": 3, "reach": 2800, "likes": 210 },
      "carousel": { "count": 1, "reach": 700, "likes": 62 }
    },
    "top_posts": [
      { "url": "https://instagram.com/p/xxx", "type": "reels", "reach": 4200 }
    ]
  },

  "created_at": "2026-02-02T23:00:00Z",
  "created_by": "cloud_function",

  "summary": {
    "insights": [
      "Bu hafta Reels içerikler toplam erişimin %72'sini sağladı",
      "Geçen haftaya göre erişim %18 arttı"
    ],
    "recommendations": [
      "Reels paylaşım sıklığını koruyun",
      "Carousel içerikleri artırmayı deneyin"
    ],
    "week_over_week": {
      "reach_change": "+18%",
      "engagement_change": "+5%",
      "trend": "positive"
    }
  },
  "analyzed_at": "2026-02-02T23:05:00Z",
  "analyzed_by": "marketing_agent"
}
```

| Alan | Tip | Aciklama |
|------|-----|----------|
| week_id | string | Hafta ID'si (week-YYYY-WW) |
| week_number | number | Yılın kaçıncı haftası (ISO) |
| year | number | Yıl |
| date_range | object | Hafta başlangıç/bitiş tarihleri |
| metrics | object | Cloud Function tarafından yazılan metrikler |
| metrics.by_content_type | object | Reels/Image/Carousel breakdown |
| summary | object | Marketing Agent tarafından yazılan analiz |
| summary.insights | string[] | Türkçe bulgular (3-5 madde) |
| summary.recommendations | string[] | Türkçe öneriler (2-3 madde) |
| summary.week_over_week | object\|null | Önceki haftayla karşılaştırma (ilk hafta null) |
| analyzed_at | string | Agent analiz tarihi (ISO 8601) |
| analyzed_by | string | Sabit değer: "marketing_agent" |

### ⚠️ STRICT SCHEMA - Alan Adları Sabit

Agent'ın summary yazarken SADECE şu alan adlarını kullanması ZORUNLU:

| Doğru Alan Adı | Yasak Alternatifler |
|----------------|---------------------|
| `insights` | ~~genel_bakis~~, ~~bulgular~~, ~~ozet~~ |
| `recommendations` | ~~oneriler~~, ~~tavsiyeler~~ |
| `week_over_week` | ~~hafta_karsilastirmasi~~, ~~karsilastirma~~ |
| `analyzed_at` | ~~analiz_tarihi~~, ~~tarih~~ |
| `analyzed_by` | ~~analist~~, ~~agent~~ |

- Alan adları **İngilizce** ama içerikler **Türkçe** olmalı
- `analyzed_at` ISO 8601 formatında: `"2026-02-03T10:00:00Z"`
- `analyzed_by` her zaman `"marketing_agent"` string değeri
- İlk hafta analizi ise `week_over_week` değeri `null` olabilir

### Agent Görevi Örneği

Cloud Function'ın `/task` endpoint'ine atacağı payload:

```json
{
  "task": "Bu işletmenin Instagram haftalık metriklerini analiz et. Metriklerin yolu: businesses/abc123/instagram_stats/week-2026-05. Önceki haftalarla karşılaştır ve Türkçe bir özet hazırla. Özeti aynı dokümanın summary alanına kaydet.",
  "business_id": "abc123"
}
```

### Notlar

- **Summary MUTLAKA Türkçe** olmalı
- Agent `merge=True` kullanmalı (metrics silinmesin)
- İlk hafta için `week_over_week` null olabilir
- Panelde `summary` null ise "henüz analiz edilmedi" gösterilmeli

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
