# Claude Session Notes

Bu dosya Claude Code session'lari arasinda sureklilik saglamak icin olusturuldu.
Yeni session'da "CLAUDE.md oku" diyerek kaldigi yerden devam edebilir.

## Proje Ozeti

OpenAI Agents SDK uzerine kurulu multi-agent orchestrator sistemi.

**Mimari:**
- Image Agent: Google AI (Nano Banana / Gemini) ile gorsel uretimi
- Video Agent: Google AI (Veo 3.1) ile video uretimi
- Marketing Agent: Sosyal medya metrikleri, analiz ve planlama
- Orchestrator Agent: Alt agent'lari yoneten ana agent
- Storage: Firebase Storage (gorsel/video depolama)
- Database: Firebase Firestore (dokuman/brand profile)
- Instagram: CloudConvert + Instagram Graph API ile post

## Yapi

```
src/
├── agents/
│   ├── orchestrator_agent.py  - Ana orchestrator
│   ├── image_agent.py         - Gorsel uretimi
│   ├── video_agent.py         - Video uretimi
│   ├── marketing_agent.py     - Sosyal medya analiz/planlama
│   └── registry.py            - Agent registry
├── infra/
│   ├── firebase_client.py     - Firebase Storage + Firestore client
│   ├── google_ai_client.py    - Google AI REST API client (httpx)
│   ├── cloudconvert_client.py - CloudConvert API client (format conversion)
│   ├── instagram_client.py    - Instagram Graph API client
│   └── task_logger.py         - Firebase task logging
├── tools/
│   ├── orchestrator_tools.py  - Firebase storage/firestore/instagram tools
│   ├── image_tools.py         - generate_image, fetch_business
│   ├── video_tools.py         - generate_video
│   ├── instagram_tools.py     - get_instagram_insights
│   ├── marketing_tools.py     - calendar, memory, post tracking
│   └── agent_wrapper_tools.py - Sub-agent wrapper tools (business_id enforcement)
├── models/
│   ├── prompts.py             - ImagePrompt, VideoPrompt modelleri
│   ├── tool_io.py             - Tool input/output modelleri
│   └── base.py                - Temel modeller
└── app/
    ├── api.py                 - FastAPI REST API
    ├── main.py                - CLI entry point
    ├── config.py              - Ayarlar (Settings)
    ├── orchestrator_runner.py - Runner
    └── logging_hooks.py       - Logging hooks
```

## Environment Variables

```bash
# OpenAI (Agents SDK icin)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini          # Fallback model

# Google AI (Nano Banana / Gemini)
GOOGLE_AI_API_KEY=...             # Google AI Studio API key

# GCP / Vertex AI
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1

# Firebase
FIREBASE_CREDENTIALS_FILE=path/to/serviceAccount.json
FIREBASE_STORAGE_BUCKET=your-bucket.appspot.com

# CloudConvert (Instagram media conversion)
CLOUDCONVERT_API_KEY=...    # CloudConvert API key
```

## Firebase Model Settings

Model ayarlari artik .env'den degil Firebase'den okunuyor.

**Firestore Path:** `settings/app_settings`

```javascript
{
  orchestratorModel: "gpt-4o",           // Orchestrator agent LLM
  imageAgentModel: "gpt-4o",             // Image agent LLM
  videoAgentModel: "gpt-4o",             // Video agent LLM
  marketingAgentModel: "gpt-4o",         // Marketing agent LLM
  imageGenerationModel: "gemini-2.5-flash-image",  // Nano Banana
  videoGenerationModel: "veo-3.1-generate-preview", // Veo 3.1
  vertexVideoModel: "veo-2.0-generate-001"  // Vertex AI (image-to-video)
}
```

**Kod kullanimi:**
```python
from src.app.config import get_model_settings

model_settings = get_model_settings()
model_settings.orchestrator_model      # "gpt-4o"
model_settings.image_generation_model  # "gemini-2.5-flash-image"
```

## Tools

### Image Tools (image_tools.py)

**generate_image(prompt_data, file_name, business_id=None, source_file_path=None)**
- `prompt_data`: ImagePrompt (scene, subject, style, colors, mood, composition, lighting, background)
- `file_name`: Kaydedilecek dosya adi
- `business_id`: Opsiyonel business ID (varsa `images/{id}/` altina kaydeder)
- `source_file_path`: Opsiyonel kaynak gorsel (edit/combine icin)
- Returns: {success, message, path, public_url, fileName}
- **Storage Path**: `images/{business_id}/{file_name}` veya `images/{file_name}`

**fetch_business(business_id)**
- Firestore 'businesses' collection'indan isletme profili okur
- Returns: {success, business_id, name, colors, logo, profile, instagram_account_id, instagram_access_token}

### Video Tools (video_tools.py)

**generate_video(prompt_data, file_name, business_id=None, source_file_path=None)**
- `prompt_data`: VideoPrompt (concept, opening_scene, main_action, closing_scene, visual_style, ...)
- `file_name`: Kaydedilecek dosya adi
- `business_id`: Opsiyonel business ID (varsa `videos/{id}/` altina kaydeder)
- `source_file_path`: Opsiyonel kaynak gorsel (image-to-video icin) - TODO
- Returns: {success, message, path, public_url, fileName}
- **Storage Path**: `videos/{business_id}/{file_name}` veya `videos/{file_name}`
- **API**: Veo 3.1 REST API (long-running operation pattern)

### Orchestrator Tools (orchestrator_tools.py)

**Firebase Storage:**
- `upload_file(file_data, destination_path, content_type)` - Dosya yukle
- `list_files(prefix, max_results)` - Dosyalari listele
- `delete_file(file_path)` - Dosya sil

**Firebase Firestore:**
- `get_document(document_id, collection)` - Dokuman oku
- `save_document(document_id, data, collection, merge)` - Dokuman kaydet
- `query_documents(field, operator, value, collection, limit)` - Sorgu

**Media (firebase_client.py):**
- `save_media_record(business_id, media_type, storage_path, public_url, file_name, ...)` - Media kaydet
- `list_media(business_id, media_type=None, limit=100)` - Business medyalarini listele

**Instagram:**
- `post_on_instagram(file_url, caption, content_type, instagram_account_id, instagram_access_token)`
  - `file_url`: Firebase Storage public URL
  - `caption`: Post aciklamasi
  - `content_type`: "image" veya "video"
  - `instagram_account_id`: Business profile'dan
  - `instagram_access_token`: Business profile'dan
  - Otomatik format donusumu yapar (PNG→JPG, video→Instagram MP4)
  - Returns: {success, post_id, creation_id, content_type, message}

- `post_carousel_on_instagram(media_items, caption, instagram_account_id, instagram_access_token)`
  - `media_items`: Medya listesi, her item: `{"url": str, "type": "image" | "video"}`
    - Ornek: `[{"url": "https://...", "type": "image"}, {"url": "https://...", "type": "video"}]`
  - `caption`: Post aciklamasi
  - `instagram_account_id`: Business profile'dan
  - `instagram_access_token`: Business profile'dan
  - En az 2, en fazla 10 medya
  - Otomatik format donusumu yapar (PNG→JPG, video→Instagram MP4)
  - Returns: {success, post_id, creation_id, content_type, item_count, message}

### Instagram Tools (instagram_tools.py) - Marketing Agent

**get_instagram_insights(ig_user_id, access_token, limit=10, ...)**
- Instagram Business Account icin son N icerigin performans metriklerini ceker
- Parameters:
  - `ig_user_id`: Instagram Business Account ID
  - `access_token`: Instagram Graph API access token
  - `limit`: Cekilecek icerik sayisi (default 10, max 50)
  - `since`: ISO date - bu tarihten sonraki icerikler (opsiyonel)
  - `include_reels_watch_time`: Reels icin watch time metrikleri (default True)
  - `include_raw`: Ham API response'lari dahil et (default False)
- Core Metrics (tum media tipleri): reach, views, total_interactions, shares, saved
- Reels Metrics (ek): ig_reels_avg_watch_time, ig_reels_video_view_total_time
- Returns:
  ```json
  {
    "success": true,
    "media_items": [
      {
        "id": "...",
        "media_type": "VIDEO",
        "media_product_type": "REELS",
        "timestamp": "2025-12-18T15:51:22+0000",
        "permalink": "https://...",
        "metrics": {
          "reach": 116,
          "views": 133,
          "total_interactions": 0,
          "shares": 0,
          "saved": 0,
          "ig_reels_avg_watch_time_sec": 1.351,
          "ig_reels_video_view_total_time_sec": 167.582
        }
      }
    ],
    "errors": [],  // fail-soft: basarisiz metric cagrilari
    "summary": {
      "total_media_count": 10,
      "total_reach": 1500,
      "avg_reach": 150,
      "top_by_reach": {"id": "...", "reach": 500, "permalink": "..."},
      "top_by_views": {"id": "...", "views": 800, "permalink": "..."}
    }
  }
  ```
- Fail-soft: Bir metric hatasi digerleri engellemez, hatalar `errors` dizisine eklenir
- Concurrency: 5 paralel istek, rate limit yonetimi

### Marketing Tools (marketing_tools.py)

**Content Calendar (Plan-Based):**
- `create_weekly_plan(business_id, start_date, end_date, posts, notes=None, created_by="agent")` - Haftalik plan olustur
- `get_plans(business_id, status_filter=None, include_past=False, limit=10)` - Planlari listele
- `get_plan(business_id, plan_id)` - Tek plan detayi
- `update_plan_status(business_id, plan_id, status, notes=None)` - Plan durumu guncelle
- `update_post_in_plan(business_id, plan_id, post_id, status, generated_media_path, ...)` - Plan icindeki post guncelle
- `add_post_to_plan(business_id, plan_id, scheduled_date, content_type, topic, brief, ...)` - Plana post ekle
- `remove_post_from_plan(business_id, plan_id, post_id)` - Plandan post cikar
- `get_todays_posts(business_id, status_filter=None)` - Bugunun postlarini getir (aktif planlardan)

**Plan Statusleri:** draft | active | paused | completed | cancelled
**Post Statusleri:** planned | created | posted | skipped

**Instagram Post Tracking:**
- `save_instagram_post(business_id, instagram_media_id, content_type, topic, caption, our_media_path, ...)` - Post kaydet
- `get_instagram_posts(business_id, limit=20, topic_filter=None)` - Postlari listele
- `get_post_by_instagram_id(business_id, instagram_media_id)` - Post detayi

**Agent Memory:**
- `get_marketing_memory(business_id)` - Marketing agent hafizasini oku (admin_notes dahil)
- `update_marketing_memory(business_id, business_understanding, content_insights, new_pattern, new_note)` - Hafiza guncelle

**Admin Notes (Zorunlu Kurallar):**
- `get_admin_notes(business_id)` - Admin notlarini oku (agent bu kurallara UYMAK ZORUNDA)
- `add_admin_note(business_id, note, priority="normal")` - Admin notu ekle (high/normal/low)
- `remove_admin_note(business_id, note_index)` - Admin notu sil (index ile)

**Memory Compaction:**
- `compact_marketing_memory(business_id, keep_patterns=20, keep_notes=30)` - Eski notlari temizle
- `clear_marketing_memory(business_id, keep_admin_notes=True)` - Hafizayi sifirla (admin_notes korunur)

## Prompt Modelleri

### ImagePrompt
```python
scene: str           # Ana sahne (2-3 cumle)
subject: str         # Ana konu
style: str           # Artistik stil
colors: list[str]    # Renkler (#hex veya isim)
mood: str            # Atmosfer
composition: str     # Kompozisyon
lighting: str        # Isiklandirma
background: str      # Arka plan
text_elements: str | None
additional_details: str | None
```

### VideoPrompt
```python
concept: str         # Video konsepti
opening_scene: str   # Acilis sahnesi
main_action: str     # Ana hareket
closing_scene: str   # Kapanis sahnesi
visual_style: str    # Gorsel stil
color_palette: list[str]
mood_atmosphere: str
camera_movement: str
lighting_style: str
pacing: str
transitions: str | None
text_overlays: str | None
audio_suggestion: str | None
additional_effects: str | None
```

## Firestore Yapisi

### businesses Collection
Her doc bir isletmeyi temsil eder:
```
businesses/
└── {business_id}/
    ├── name: string                  # Isletme adi
    ├── colors: array                 # Marka renkleri (hex veya isim)
    ├── logo: string                  # Cloud Storage URL
    ├── instagram_account_id: string  # Instagram Business Account ID
    ├── instagram_access_token: string # Instagram Graph API token
    ├── profile: map                  # Dinamik ek bilgiler (asagidaki alanlar)
    │   ├── slogan: string
    │   ├── industry: string          # cafe, restaurant, retail, beauty, fitness...
    │   ├── sub_category: string
    │   ├── market_position: string   # budget, mid-range, premium, luxury
    │   ├── location_city: string
    │   ├── tone: string              # friendly, professional, playful, luxury...
    │   ├── language: string          # tr, en, tr+en
    │   ├── formality: string         # formal, informal, mixed
    │   ├── emoji_usage: string       # none, minimal, moderate, frequent
    │   ├── caption_style: string     # short_punchy, storytelling, informative...
    │   ├── aesthetic: string         # minimalist, bold, vintage, modern...
    │   ├── photography_style: string # bright, moody, natural, studio...
    │   ├── color_mood: string        # vibrant, muted, pastel, dark, warm, cool
    │   ├── visual_mood: string       # energetic, calm, luxurious, cozy...
    │   ├── target_age_range: string
    │   ├── target_gender: string
    │   ├── target_description: string
    │   ├── target_interests: array
    │   ├── brand_values: array       # quality, sustainability, innovation...
    │   ├── unique_points: array
    │   ├── brand_story_short: string
    │   ├── hashtags_brand: array
    │   ├── hashtags_industry: array
    │   ├── hashtags_location: array
    │   ├── content_pillars: array    # product_showcase, behind_scenes, tips...
    │   ├── avoid_topics: array
    │   ├── seasonal_content: boolean
    │   └── promo_frequency: string   # rare, occasional, regular
    ├── media/                        # Subcollection - uretilen medyalar
    │   └── {media_id}/
    │       ├── type: string              # "image" | "video"
    │       ├── storage_path: string      # Firebase Storage path
    │       ├── public_url: string        # Public URL
    │       ├── file_name: string         # Dosya adi
    │       ├── created_at: string        # ISO timestamp
    │       ├── prompt_summary: string    # Prompt ozeti (ilk 200 karakter)
    │       ├── log_id: string | null     # Hangi task'ta uretildi
    │       └── metadata: map | null      # Ek bilgiler (width, height, duration)
    │
    ├── instagram_posts/              # Subcollection - paylasilan icerikler
    │   └── {instagram_media_id}/     # Instagram'dan donen ID
    │       ├── posted_at: string         # ISO timestamp
    │       ├── content_type: string      # "image" | "reels"
    │       ├── topic: string             # "urun tanitimi", "kampanya"
    │       ├── theme: string | null      # "yilbasi", "sezon sonu"
    │       ├── caption: string           # Paylasilan caption
    │       ├── hashtags: array           # Kullanilan hashtagler
    │       └── our_media_path: string    # Storage path
    │
    ├── content_calendar/             # Subcollection - haftalik icerik planlari
    │   └── {plan_id}/                # "plan-20250106-20250112" (start-end date)
    │       ├── plan_id: string           # Plan ID
    │       ├── start_date: string        # "2025-01-06"
    │       ├── end_date: string          # "2025-01-12"
    │       ├── status: string            # "draft" | "active" | "paused" | "completed" | "cancelled"
    │       ├── created_by: string        # "agent" | "admin"
    │       ├── notes: string | null      # Admin notlari
    │       ├── created_at: string
    │       ├── updated_at: string
    │       └── posts: array              # Plan icindeki postlar
    │           └── [
    │                 {
    │                   id: string,               # "post-1", "post-2", ...
    │                   scheduled_date: string,   # "2025-01-06"
    │                   status: string,           # "planned" | "created" | "posted" | "skipped"
    │                   content_type: string,     # "image" | "reels"
    │                   topic: string,
    │                   brief: string,
    │                   caption_draft: string | null,
    │                   generated_media_path: string | null,
    │                   instagram_post_id: string | null
    │                 },
    │                 ...
    │               ]
    │
    ├── agent_memory/                 # Subcollection - agent hafizasi
    │   └── marketing/                # Marketing agent memory
    │       ├── last_updated: string
    │       ├── business_understanding: map
    │       │   ├── summary: string
    │       │   ├── strengths: array
    │       │   ├── audience: string
    │       │   └── voice_tone: string
    │       ├── content_insights: map
    │       │   ├── best_performing_types: array
    │       │   ├── best_posting_times: array
    │       │   ├── effective_hashtags: array
    │       │   └── caption_styles_that_work: array
    │       ├── learned_patterns: array   # ["Reels 2x daha fazla reach aliyor"]
    │       └── notes: array              # [{note, added_at}]
    │
    └── logs/                         # Subcollection - task run loglari
        └── {log_id}/
            ├── task: string              # Istek metni
            ├── started_at: string        # ISO timestamp
            ├── completed_at: string      # ISO timestamp
            ├── status: string            # "running" | "success" | "error"
            ├── actions: array            # Tool call'lari
            │   └── {tool, input, output, timestamp}
            ├── outputs: array            # Uretilen dosyalar
            │   └── {type, path, public_url}
            └── error: string | null      # Hata varsa

### tasks Subcollection
Her business altinda task'lari tutar (document ID = taskId):
```
businesses/{business_id}/tasks/{task_id}
├── jobId: string | null      # planned/routine icin kaynak job ID
├── type: string              # "immediate" | "planned" | "routine"
├── task: string              # Gorev icerigi
├── status: string            # "pending" | "running" | "completed" | "failed"
├── createdAt: timestamp      # Admin panel tarafindan set edilir
├── startedAt: timestamp      # TaskLogger tarafindan set edilir
├── completedAt: timestamp | null
├── logId: string | null      # businesses/{id}/logs/{log_id} ile baglanti
├── result: string | null     # Basarili sonuc mesaji
└── error: string | null      # Hata mesaji
```

**Not:** `type`, `jobId`, `task`, `createdAt` admin panel tarafindan olusturulur.
TaskLogger sadece `status`, `startedAt`, `completedAt`, `logId`, `result`, `error` gunceller.

## API

### POST /task
```json
{
  "task": "tanitim posteri olustur",
  "business_id": "abc123",  // Opsiyonel - businesses collection doc ID
  "task_id": "task-xyz",    // Opsiyonel - Firebase tasks subcollection'da takip icin
  "extras": {               // Opsiyonel - esnek yapi, her istekte farkli olabilir
    "key1": "value1",
    "nested": { "a": 1 }
  },
  "context": {}             // Opsiyonel - ek context
}
```
Response:
```json
{
  "output": "Poster olusturuldu...",
  "log_path": "logs/run-xxx.log"
}
```

**Not:** `extras` context icine `context.extras` olarak eklenir ve orchestrator'a iletilir.

## Akislar

### Business Profile Flow
1. API'ye `business_id` ile istek gelir
2. `business_id` context'e eklenir
3. Orchestrator `fetch_business` cagirir → isletme profili alir
4. Isletme bilgileri (name, colors, logo, profile) ile image/video agent cagrilir

### Image Generation Flow
1. `fetch_business` → isletme profili (opsiyonel, business_id varsa)
2. `image_agent_tool` → ImagePrompt ile generate_image
3. Gorsel Firebase Storage'a yuklenir
4. path ve public_url doner

### Video Generation Flow
1. `fetch_business` → isletme profili (opsiyonel, business_id varsa)
2. `video_agent_tool` → VideoPrompt ile generate_video
3. Video Firebase Storage'a yuklenir
4. path ve public_url doner

### Instagram Posting Flow
1. `fetch_business` → instagram_account_id ve instagram_access_token al
2. `image_agent_tool` veya `video_agent_tool` → icerik uret
3. `post_on_instagram` cagir:
   - CloudConvert ile format donustur (PNG→JPG veya video→MP4 x264/aac)
   - Instagram Graph API'ye media yukle
   - Video icin: status poll et (FINISHED olana kadar)
   - media_publish ile yayinla
4. post_id doner

### Marketing Agent Flows

**KRITIK - EXECUTE vs CREATE Ayrimi:**
- "plana göre paylaş", "bugünkü postu at" → EXECUTE (mevcut planı uygula)
- "plan oluştur", "haftalık plan hazırla" → CREATE (yeni plan oluştur)
- Orchestrator bu ayrımı marketing agent'a açıkça belirtmeli!

**Execute Plan Flow (Mevcut planı uygula):**
1. `fetch_business` → business profile + credentials
2. `marketing_agent_tool` cagir (mesaj: "Check EXISTING plans, DO NOT create new")
3. Marketing agent:
   - `get_todays_posts(status_filter="planned")` → bugunku plani bul
   - Eger post yoksa → "No posts scheduled" raporla ve DUR
   - `get_marketing_memory` → voice/tone, hashtag'ler
   - `image_agent_tool` veya `video_agent_tool` → icerik uret
     - **KRITIK**: Brief'e `Business ID: {id}` MUTLAKA dahil et!
     - Bu olmadan media Firestore'a KAYDEDILMEZ!
   - Caption yaz (kendi LLM ile)
   - `post_on_instagram` → paylas
   - `save_instagram_post` → post kaydini olustur
   - `update_post_in_plan(status="posted", generated_media_path=...)` → plani guncelle

**Create Plan Flow (Yeni plan oluştur - sadece açıkça istendiğinde):**
1. `fetch_business` → business profile al
2. `marketing_agent_tool` cagir (mesaj: "Create a new weekly content plan")
3. Marketing agent:
   - `get_marketing_memory` → onceki ogrenimleri oku
   - `get_instagram_insights` → mevcut performansi analiz et
   - `get_instagram_posts` → son postlari gor (tekrar onle)
   - `create_weekly_plan(posts=[...])` → haftalik plan olustur (tek seferde)
   - `update_marketing_memory` → yeni ogrenimler kaydet

**Analytics Flow:**
1. `fetch_business` → credentials
2. `marketing_agent_tool` cagir
3. Marketing agent:
   - `get_instagram_insights(limit=20)` → metrikleri cek
   - `get_instagram_posts` → post topic'leriyle eslestir
   - Pattern'leri analiz et
   - `update_marketing_memory` → ogrenimleri kaydet
   - Kullaniciya rapor sun

## Hizli Komutlar

```bash
# Bagimliliklari yukle
pip install -r requirements.txt

# API'yi calistir (lokal)
uvicorn src.app.api:app --host 0.0.0.0 --port 8000

# CLI ile calistir
python -m src.app.main -i "task burada"

# Docker ile calistir (Cloudflare Tunnel + Firebase URL update)
start-dev.bat
# veya manuel:
docker-compose up -d && python scripts/update_tunnel_url.py
```

## Development Server (Cloudflare Tunnel)

Development ortaminda API'yi disariya acmak icin Cloudflare Quick Tunnel kullaniliyor.

**Ozellikler:**
- Ngrok'taki 30s streaming timeout sorunu yok
- Her restart'ta yeni URL (xxx.trycloudflare.com)
- URL otomatik olarak Firebase `settings/app_settings.serverUrl`'e kaydediliyor

**Kullanim:**
```bash
# Tek komutla baslatma (containers + tunnel URL update)
start-dev.bat

# Manuel baslatma
docker-compose up -d
python scripts/update_tunnel_url.py
```

**Dosyalar:**
- `docker-compose.yml` - API + Cloudflare Tunnel containers
- `scripts/update_tunnel_url.py` - Tunnel URL'i alip Firebase'e kaydeder
- `start-dev.bat` - Tek komutla her seyi yapar

## Bekleyen Isler

1. **Video SDK Gecisi (ASKIDA)**
   - Veo 3 icin `google-genai` Python SDK'ya gecis dusunuluyor
   - Text-to-video ve image-to-video tek SDK ile yapilabilir
   - REST API yerine SDK kullanilirsa Vertex AI karmasikligi kalkar
   - Arastirma yapildi, karar bekleniyor
   - Detay: https://ai.google.dev/gemini-api/docs/video

---

## IMAGE-TO-VIDEO IMPLEMENTATION PLANI (TAMAMLANDI)

### Genel Bakis
Vertex AI kullanarak mevcut bir görselden video üretme özelliği.

### API Bilgileri

**Endpoint:**
```
POST https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{MODEL_ID}:predict
```

**Headers:**
```
Authorization: Bearer {GOOGLE_VERTEX_API_KEY}
Content-Type: application/json; charset=utf-8
```

**Request Body:**
```json
{
  "instances": [
    {
      "prompt": "A cinematic drone shot...",
      "image": {
        "gcsUri": "gs://bucket-adi/klasor/resim.png"
      }
    }
  ],
  "parameters": {
    "sampleCount": 1,
    "videoLength": "8s",
    "aspectRatio": "16:9",
    "seed": 12345,
    "personGeneration": "allow_adult"
  }
}
```

**Response:**
```json
{
  "predictions": [
    {
      "video": {
        "gcsUri": "gs://output-bucket/gen-video-123.mp4",
        "mimeType": "video/mp4"
      }
    }
  ]
}
```

### Yeni Environment Variables
```bash
# Vertex AI (Image-to-Video)
GOOGLE_VERTEX_API_KEY=...           # Vertex AI Bearer token
VERTEX_VIDEO_MODEL_ID=veo-2.0-generate-001  # veya veo-3.0
# GCP_PROJECT_ID ve GCP_LOCATION zaten mevcut
```

### Implementation Adimlari

**1. Config Guncellemesi (`src/app/config.py`)**
- `google_vertex_api_key` ekle
- `vertex_video_model_id` ekle

**2. VideoGenerationClient Guncellemesi (`src/infra/google_ai_client.py`)**
```python
async def generate_video_from_image(
    self,
    prompt: str,
    source_image_gcs_uri: str,  # gs://bucket/path/image.png
    video_length: str = "8s",
    aspect_ratio: str = "16:9",
) -> str:  # Returns output video GCS URI
    """
    1. POST to Vertex AI endpoint
    2. Get video GCS URI from response
    3. Return GCS URI (veya download edip bytes dondur)
    """
```

**3. Firebase Storage → GCS URI Donusumu**
Firebase Storage path'i GCS URI'ye cevirmek icin:
- Firebase bucket: `your-bucket.appspot.com`
- Path: `images/abc123/photo.png`
- GCS URI: `gs://your-bucket.appspot.com/images/abc123/photo.png`

**4. video_tools.py Guncellemesi**
`generate_video` fonksiyonunda `source_file_path` varsa:
- Firebase path → GCS URI donustur
- `generate_video_from_image` cagir
- Sonuc video'yu Firebase'e yukle (veya GCS'den indir + yukle)

**5. GCS'den Video Indirme**
Response'daki `gcsUri`'den video indirmek icin:
- Google Cloud Storage client kullan
- veya public URL olustur ve httpx ile indir

### Flow Diagrami
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Firebase Storage'dan source image path al                │
│ 2. Path → GCS URI donustur (gs://bucket/path)              │
│ 3. Vertex AI'a POST (prompt + gcsUri)                       │
│ 4. Response'dan output video gcsUri al                      │
│ 5. GCS'den video indir                                      │
│ 6. Firebase Storage'a yukle                                 │
│ 7. public_url dondur                                        │
└─────────────────────────────────────────────────────────────┘
```

### Notlar
- GCS URI formati: `gs://bucket-name/path/to/file`
- Firebase Storage bucket'i ayni zamanda GCS bucket'i
- Vertex AI sadece GCS URI kabul ediyor (HTTP URL degil)
- Response'daki video da GCS'de, indirmek gerekiyor

---

## Tamamlanan Isler

1. **Storage Path Organizasyonu** - Gorseller `images/{business_id}/`, videolar `videos/{business_id}/` altina kaydediliyor
2. **Firebase Task Logging** - Her task run `businesses/{id}/logs/` subcollection'a loglaniyor
3. **Video Generation (Text-to-Video)** - Veo 3.1 REST API ile implement edildi (long-running operation pattern)
4. **Instagram Posting** - CloudConvert + Instagram Graph API ile implement edildi
   - Image: PNG → JPG donusumu + post
   - Video: MP4 → Instagram uyumlu MP4 (x264/aac) donusumu + Reels olarak post
5. **Image-to-Video** - Vertex AI ile implement edildi
   - Firebase Storage path → GCS URI donusumu
   - Vertex AI predictLongRunning endpoint
   - GCS'den video indirme ve Firebase'e yukleme
6. **Media Collection** - Uretilen medyalar `businesses/{id}/media/` subcollection'a kaydediliyor
   - Her image/video uretiminde otomatik kayit
   - Admin panelinden listelenebilir
   - `list_media(business_id)` ile sorgulama
7. **Firebase Model Settings** - Model ayarlari artik Firebase'den okunuyor
   - `settings/app_settings` dokumanindan
   - `get_model_settings()` ile erisim
   - orchestratorModel, imageAgentModel, videoAgentModel, imageGenerationModel, videoGenerationModel
8. **Marketing Agent + Instagram Insights** - Sosyal medya analiz ve planlama agenti
   - `marketing_agent.py` olusturuldu
   - Orchestrator'a `marketing_agent_tool` olarak eklendi
   - `instagram_tools.py` eklendi: `get_instagram_insights` tool
   - Instagram Graph API uzerinden media metrikleri: reach, views, interactions, shares, saved
   - Reels icin ek metrikler: avg_watch_time, video_view_total_time
   - Fail-soft pattern: bir metric hatasi digerleri etkilemez
   - Summary hesaplama: total, average, top performers
   - Marketing agent `post_on_instagram` ve `post_carousel_on_instagram` tool'larina sahip
   - Orchestrator "paylas" dediginde marketing agent tum sureci yonetir
9. **API Extras Alani** - Task endpoint'ine esnek `extras` alani eklendi
   - Her istekte farkli yapi olabilir
   - `context.extras` olarak agent'a iletiliyor
10. **Marketing Agent Tam Yonetim** - Marketing agent artik tam sosyal medya yoneticisi
    - `marketing_tools.py` eklendi: calendar, memory, post tracking
    - Marketing agent image/video agent'lari cagirabiliyor
    - Icerik takvimi olusturma ve yonetme
    - Post kayitlari ve topic tracking
    - Agent memory: isletme bazli ogrenme ve hafiza
    - Orchestrator'dan bagimsiz icerik uretme ve paylasma
11. **Plan-Based Content Calendar** - Haftalik plan yapisi eklendi
    - Her hafta 1 dokuman, icinde posts array
    - Plan statusleri: draft, active, paused, completed, cancelled
    - Post statusleri: planned, created, posted, skipped
    - `create_weekly_plan`, `get_plans`, `get_todays_posts` tools
12. **EXECUTE vs CREATE Ayrimi** - Marketing agent workflow'u duzeltildi
    - "plana gore paylas" = mevcut plani uygula (yeni plan OLUSTURMA!)
    - "plan olustur" = yeni plan olustur
    - Orchestrator bu ayrimi marketing agent'a acikca belirtiyor
    - Marketing agent soru sormadan otonom calisiyor
13. **Business ID Propagation Fix** - Media kayitlari duzeltildi
    - Marketing agent artik image/video brief'lerine `Business ID: {id}` ekliyor
    - Image/video agent'lar business_id'yi extract edip generate fonksiyonlarina geciyor
    - Uretilen medyalar `businesses/{id}/media/` subcollection'a kaydediliyor
14. **Business ID Wrapper Tools** - Orchestrator'un uydurma ID kullanmasi engellendi
    - `agent_wrapper_tools.py` eklendi - sub-agent'lar icin wrapper tools
    - `image_agent_tool`, `video_agent_tool`, `marketing_agent_tool` artik wrapper olarak calisir
    - `business_id` zorunlu parametre olarak alinir, LLM uydurma ID gecemez
    - Wrapper'lar input'a `[Business ID: xxx]` prefix'i ekler
    - Sub-agent'lar bu prefix'ten business_id'yi extract eder
15. **Admin Notes + Memory Compaction** - Agent icin zorunlu kurallar ve hafiza yonetimi
    - `admin_notes` array eklendi - agent'in UYMAK ZORUNDA oldugu kurallar
    - `add_admin_note(business_id, note, priority)` - Kural ekle (high/normal/low oncelik)
    - `remove_admin_note(business_id, note_index)` - Kural sil
    - `compact_marketing_memory(business_id)` - Eski notlari temizle, son 20 pattern + 30 not tut
    - `clear_marketing_memory(business_id)` - Hafizayi sifirla (admin_notes korunur)
    - Marketing agent her calistiginda admin_notes'u okuyup kurallara uyar
16. **Instagram Carousel Posting** - Coklu medya paylasimi
    - `post_carousel_on_instagram` tool eklendi
    - 2-10 arasi image/video destegi
    - Her medya icin ayri item container olusturma
    - Video item'lar icin status polling
    - CloudConvert ile otomatik format donusumu
    - Instagram Graph API v24.0 kullaniliyor
17. **TaskId Entegrasyonu** - Task tracking sistem
    - API task_id parametresi alir (`POST /task`)
    - TaskLogger: `businesses/{id}/tasks/{task_id}` subcollection'a yazar
    - `start()`: status="running", logId, startedAt
    - `complete()`: status="completed"/"failed", completedAt, result/error
    - Log'lara da task_id yaziliyor (`businesses/{id}/logs/{log_id}.task_id`)

## Test

```bash
# Image API test (dogrudan REST API testi)
python test_image_api.py
```

## Google AI REST API (Nano Banana)

Image generation icin Gemini API REST endpoint kullaniliyor.

**Endpoint:**
```
POST https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent
```

**Headers:**
```
x-goog-api-key: {GOOGLE_AI_API_KEY}
Content-Type: application/json
```

**Request (text-to-image):**
```json
{
  "contents": [{
    "parts": [{"text": "prompt here"}]
  }]
}
```

**Request (image editing):**
```json
{
  "contents": [{
    "parts": [
      {"text": "edit prompt"},
      {"inlineData": {"mimeType": "image/png", "data": "<BASE64>"}}
    ]
  }]
}
```

**Response:**
```json
{
  "candidates": [{
    "content": {
      "parts": [
        {"text": "description"},
        {"inlineData": {"mimeType": "image/png", "data": "<BASE64>"}}
      ]
    }
  }]
}
```

**ONEMLI:** API response'lari camelCase kullanir (inlineData, mimeType).

## Veo 3.1 REST API (Video Generation)

Video generation icin Veo 3.1 long-running operation pattern kullaniliyor.

**Endpoint (Start):**
```
POST https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning
```

**Request:**
```json
{
  "instances": [{
    "prompt": "video description here"
  }]
}
```

**Response (operation started):**
```json
{
  "name": "operations/xxx-yyy-zzz"
}
```

**Poll Endpoint:**
```
GET https://generativelanguage.googleapis.com/v1beta/{operation_name}
```

**Poll Response (completed):**
```json
{
  "done": true,
  "response": {
    "generateVideoResponse": {
      "generatedSamples": [{
        "video": {
          "uri": "https://..."
        }
      }]
    }
  }
}
```

**Flow:**
1. POST ile operation baslat → operation name al
2. GET ile poll et (10 saniye aralikla)
3. `done: true` olunca video URI'yi al
4. Video URI'den videoyu indir (API key ile)
5. Firebase Storage'a yukle

## CloudConvert API

Media format donusumu icin CloudConvert kullaniliyor.

**Image Conversion (PNG → JPG):**
```json
{
  "tasks": {
    "import-file": { "operation": "import/url", "url": "<firebase_url>" },
    "convert-to-jpg": { "operation": "convert", "input": ["import-file"], "output_format": "jpg", "quality": 90 },
    "export-file": { "operation": "export/url", "input": ["convert-to-jpg"] }
  }
}
```

**Video Conversion (Instagram uyumlu MP4):**
```json
{
  "tasks": {
    "import-file": { "operation": "import/url", "url": "<firebase_url>" },
    "convert-for-instagram": {
      "operation": "convert",
      "input": "import-file",
      "output_format": "mp4",
      "video_codec": "x264",
      "audio_codec": "aac",
      "preset": "fast",
      "faststart": true,
      "engine": "ffmpeg"
    },
    "export-file": { "operation": "export/url", "input": "convert-for-instagram" }
  }
}
```

## Instagram Graph API

Instagram posting icin Facebook Graph API kullaniliyor.

**Image Post Flow:**
1. `POST /{account_id}/media` (image_url, caption) → creation_id
2. Wait 5 seconds
3. `POST /{account_id}/media_publish` (creation_id) → post_id

**Video/Reels Post Flow:**
1. `POST /{account_id}/media` (video_url, caption, media_type=REELS) → creation_id
2. Poll: `GET /{creation_id}?fields=status_code` until FINISHED
3. `POST /{account_id}/media_publish` (creation_id) → post_id

**Carousel Post Flow:**
1. Her medya icin item container olustur:
   - Image: `POST /{account_id}/media` (image_url, is_carousel_item=true) → item_id
   - Video: `POST /{account_id}/media` (video_url, media_type=VIDEO, is_carousel_item=true) → item_id
2. Video item'lar icin poll: `GET /{item_id}?fields=status_code` until FINISHED
3. Carousel container olustur: `POST /{account_id}/media` (media_type=CAROUSEL, children=id1,id2,id3, caption) → creation_id
4. `POST /{account_id}/media_publish` (creation_id) → post_id

## Instagram Insights API (Marketing Agent)

Marketing agent'in `get_instagram_insights` tool'u icin kullanilan API.

**Media List:**
```
GET /{ig_user_id}/media?fields=id,media_type,media_product_type,timestamp,permalink&limit={limit}
```

**Media Insights (tek metric):**
```
GET /{media_id}/insights?metric={metric_name}
```

**Core Metrics (tum media tipleri):**
- `reach` - Unique hesap sayisi
- `views` - Goruntuleme sayisi
- `total_interactions` - Toplam etkilesim
- `shares` - Paylasim sayisi
- `saved` - Kaydedilme sayisi

**Reels Ek Metrikleri:**
- `ig_reels_avg_watch_time` - Ortalama izleme suresi (ms)
- `ig_reels_video_view_total_time` - Toplam izleme suresi (ms)

**Response Format:**
```json
{
  "data": [{
    "name": "reach",
    "period": "lifetime",
    "values": [{"value": 116}],
    "title": "Reach",
    "description": "...",
    "id": "..."
  }]
}
```

**Notlar:**
- Her metric icin ayri API cagrisi gerekiyor (batch desteklenmiyor)
- `period=lifetime` doner - gunluk delta icin agent hafiza kullanacak
- Rate limit: ~200 call/hour, concurrency 5 ile yonetiliyor

## Notlar

- N8N tamamen kaldirildi
- Google Drive yerine Firebase Storage kullaniliyor
- Google Docs yerine Firebase Firestore kullaniliyor
- Image generation: google-genai SDK yerine REST API (httpx) kullaniliyor
- API response key'leri camelCase: `inlineData`, `mimeType` (snake_case degil!)
- Instagram posting: CloudConvert ile format donusumu + Graph API ile post
