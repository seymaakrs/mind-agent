# Claude Session Notes

## 🎯 STRATEJIK ÖNCELIK (2026-05-20)

**Sales + Marketing = şirketin para kazanma motoru.** Yatırım/zaman/token
bütçesi öncelik sırası:

1. **Sales Manager (Satış Müdürü)** + alt birimleri (Outreach/Auto-reply/Follow-up)
2. **Marketing Agent** + alt birimleri (Image/Video, brand-aware üretim)
3. Diğer her şey (infra, observability, dev experience) sonra gelir.

Yeni özellik / refactor önerisinde önce şu soru: *"Bu Sales veya Marketing'in
para kazandırma gücünü artırır mı?"* Hayırsa, sıraya en altta gider.

## ⚡ YENI SESSION? ÖNCE BURAYI OKU — DURUM (2026-05-12)

**Branch (3 repo):** `claude/add-hot-leads-count-LJNi7`

### 🎯 GÜNCEL HEDEF (2026-05-12 sonrası değişti)

**Eski odak:** Slowdays kampanyası deploy → Şeyma'nın PC scriptleri Cloud Run'a
**Yeni odak:** **İçerik üretim kalitesi + marka kimliği %100 uyum**

Slowdays atomic switch, güvenlik P1, Tier 2-4 n8n workflow'lar → **EN SONA bırakıldı**.

### 🛡️ ROLLBACK NOKTALARI

| Kaynak | İşaret | Anlam |
|---|---|---|
| **Canlı Cloud Run revision** | `agents-sdk-api-00034-vgb` (v1.22.6) | Slowdays MCP entegre, NocoDB filter fix |
| **Sağlam git commit (Faz A öncesi)** | `a8b895b` | Lead Onboarding draft sonrası |
| **Son commit (Faz A sonrası)** | `2c76c8e` | Brand identity schema (deploy edilmedi) |

Acil rollback: `gcloud run services update-traffic agents-sdk-api --region=us-central1 --to-revisions=agents-sdk-api-00034-vgb=100`

### 📊 BUGÜNE KADAR YAPILANLAR (2026-05-12 oturumu)

| Adım | Commit | Açıklama |
|---|---|---|
| Faz 1: Zernio MCP entegrasyonu | `6f9c2d8` | 280 tool → 80 filtered, MCP server lifecycle |
| Lifespan fix | `7de7714` → `f4a8c2e` | MCP server connect/cleanup FastAPI lifespan |
| Tool filter signature fix | `3b0187b` | SDK 0.6.2 `(context, tool)` imzası |
| NocoDB datetime fix | `e949745` | exactDate/daysAgo operator (4 deneme sonunda) |
| Faz 1 deploy v1.22.x | revision `00026` → `00034-vgb` (canlı) | 9 deploy, hepsi rollback noktalı |
| Tier 1.1 Takip Agent v2 | n8n workflow update | mail bombardımanı önleme (son_temas + Slowdays exclude + HARD_CAP) |
| Tier 1.2 Auto-reply itiraz handoff | `533606d` | 5. intent + n8n İtiraz Agent POST handoff |
| Tier 2.1 Lead Onboarding workflow | n8n yarat + `a8b895b` | draft, 3 aşamalı welcome dizisi (publish bekliyor) |
| Mimari review (bağımsız Plan agent) | — | 8 kategori risk haritası, 5 kritik madde |
| **Faz A Brand Identity altyapı** | `2c76c8e` | Pydantic schema + Firestore tools + 40 test |

### 🎨 YENI YOL HARITASI (4 Faz)

| Faz | İçerik | Durum | Süre |
|---|---|---|---|
| **A** Brand Identity schema + tools | Pydantic + load/save/fetch/update + 40 test | ✅ TAMAM (`2c76c8e`) | — |
| **B1** Brand Synthesis Agent | website + IG scrape → AI brand_identity draft | ⏳ Sırada | ~3 saat |
| **B2** Portal "İşletme Ekle" wizard | mind-id Vercel — 5 adım UI | ⏳ Kullanıcı kararı bekliyor (repo erişimi?) | ~3 saat |
| **C** Agent entegrasyon | Image/Video/Marketing brand_identity okusun | ⏳ | ~3 saat |
| **D** Brand-fit scorer + drift | LLM judge (gpt-4o-mini), auto-retry, drift report | ⏳ | ~2 saat |
| **Z** Tek atomik deploy (v1.23.0) | A+B1+C+D birikim → canlıya | ⏳ Son adım | 1 deploy |

### 🔑 KRITIK KISIMLAR

- **Faz A tamamen additive**: Mevcut hiçbir agent şu an brand_identity okumuyor. Sadece altyapı kuruldu. Cloud Run'da etkisi yok.
- **fetch_business aynen kalır** (geri uyum garantisi).
- **businesses/{id}.profile field aynen kalır** (Firestore'da). brand_identity ayrı subcollection `businesses/{id}/brand_identity/v1`.
- **Schema versioning**: `BRAND_IDENTITY_SCHEMA_VERSION = 1`. Kırıcı değişiklikte +1.

### 🎯 BRAND IDENTITY ŞEMASI (tek satır özet)

```
basics: name, tagline, industry, founded_year, languages
visual: primary_colors, secondary_colors, logo_url, font_family,
        visual_style, photography_style, image_dos, image_donts
voice:  tone, personality, avoid_words, preferred_words,
        example_captions, cta_style (soft/hard/quirky/informative)
audience: primary {role, age_range, pain_points}, geo, languages
content_strategy: pillars, posting_cadence, hashtag_strategy
business_context: products, usp, competitors, seo_keywords
```

Helper: `BrandIdentity.prompt_summary()` → compact metin agent prompt'larına enjekte edilir.

### ⏳ ASKIDA OLAN İŞLER (HATIRLAT — yeni session bunları unutma!)

1. **Lead Onboarding workflow publish** (`nz8tNAR737yjrQRS`)
   - Migration `scripts/migrate_onboarding_schema.py` koşulmadı (2 yeni kolon)
   - Mail içerikleri Beyza/Şeyma onayı bekliyor
   - n8n UI'dan publish bekliyor

2. **İtiraz asama option migration** (`scripts/migrate_itiraz_asama_option.py`)
   - Cloud Shell'den koşulmalı (Auto-reply deploy öncesi şart)
   - Şu an Auto-reply Worker deploy değil, acil değil

3. **Takip Agent v3 vs Hot Lead Reminder kararı**
   - Sıcak/Teklif/Takipte stage'leri de izlesin mi?
   - Tier 4 sonu civarı karar

4. **Slowdays atomic switch** (Outreach + Auto-reply + Bekçi deploy)
   - EN SON — Beyza/Şeyma kararıyla
   - Kod %100 hazır, deploy edilmedi

5. **Güvenlik P1 (mimari review'da çıkan 5 madde)**
   - EN SON (portala sadece Beyza/Şeyma erişiyor)
   - NOCODB_API_TOKEN rotate, Secret Manager, ZERNIO_WEBHOOK_SECRET zorunlu vs.

6. **Tier 2.2-2.3 + Tier 3-4 n8n workflows**
   - NoShow Follow-up, Deal Kayıp Analiz, LinkedIn/Clay/IG DM, Meta CTR, Rapor genişletme
   - Faz A-D sonrası

### 📂 ÖNEMLI DOSYALAR (yeni session bunlara bakacak)

| Dosya | Ne yapar |
|---|---|
| `src/infra/brand_identity.py` | Pydantic BrandIdentity schema + alt modeller |
| `src/tools/brand/__init__.py` | Firestore load/save + fetch/update tool'lar |
| `src/infra/zernio/mcp_server.py` | Zernio MCP lifecycle (lifespan'de connect) |
| `src/tools/n8n_registry.py` | 11 n8n workflow registry (lead_onboarding dahil) |
| `src/agents/outreach/runner.py` | Outreach (deploy değil) |
| `src/agents/auto_reply/runner.py` | Auto-reply + itiraz handoff (deploy değil) |
| `src/agents/guardian/runner.py` | Bekçi Robot (deploy değil) |
| `src/app/api.py` | FastAPI lifespan + /task + /zernio/webhook |
| `tests/test_brand_identity.py` + `tests/test_brand_tools.py` | 40 yeni test |

### 🎬 YENI SESSION'DA İLK 5 DAKİKADA YAPACAĞIN

1. Bu bölümü oku (5 dk)
2. Sırada **Faz B1: Brand Synthesis Agent** var
3. `git log --oneline -5` ile son commit'leri gör
4. Sandbox'ta git pull yap, branch kontrol et
5. Kullanıcıya "B1 başlayalım mı?" diye sor + mind-id repo erişimi var mı netleştir

### 💰 MEVCUT MALİYET (Slowdays canlı değil)

| Kalem | $/ay |
|---|---|
| Cloud Run | $0-2 (free tier) |
| Artifact Registry | $0.10 |
| OpenAI (orchestrator + sales analyst) | $10-25 |
| **Toplam** | **~$15-30/ay** |

Slowdays canlıya geçince +$1 (WhatsApp Meta zaten Şeyma'nın aboneliği).

### ❓ KULLANICI BEKLENTİSİ

- "Yeni session'a geç" dedi → fresh başla
- "Devir notunu yaz" dedi → bu bölüm = full devir
- "Anlatmak zorunda kalmayayım" → CLAUDE.md başında her şey

## ⚡ YENI SESSION? ÖNCE BURAYI OKU — SLOWDAYS DEPLOY DURUMU (2026-05-11)

**Branch (3 repo):** `claude/add-hot-leads-count-LJNi7`

### Tek cumlede ne yapiyoruz
Mindid kendi B2B CRM omurgasini koruyarak, Slowdays kampanyasi (331 otel Whatsapp outreach) icin 4 robot (Outreach + Postaci/webhook + Cevap + Bekci) ve MindBot icin 3 status tool + n8n koprusu kurduk. Tum kod hazir, **deploy edilmedi**. Seyma'nin Windows PC'sindeki `otel_gonderim.py` ve `lead_monitor.py` HALA gercek mesaj atan sistem.

### Bitenler (sirasiyla, hepsi GitHub'da)
| Adim | Ne | Commit | Test |
|---|---|---|---|
| 1 | Portal-Beyin koprusu (mind-id chat → mind-agent /task) | onceki session | ✅ Canli |
| 2 | Zernio client (`src/infra/zernio/`) + 4 tool | `25f75eb` | 19 |
| 3 | n8n Lead Toplama payload bug fix | smoke OK | — |
| 4 | Outreach Robotu (`src/agents/outreach/`) | `1bb86af` | 35 |
| 5 | Postaci (`/zernio/webhook` endpoint) | `ce37bf5` | 27 |
| 6 | Cevap Robotu / Auto-reply (`src/agents/auto_reply/`) | `a76cc21` | 24 |
| 6.5 | NocoDB migration (auto_reply_processed, Takipte, son_temas) | Cloud Shell'de kosuldu, OK | 10 |
| 7 | Seyma scripti parity fix paketi (4 fix: daily limit persistence, retry, contact tagging, hibrit templates) | `6cd9adb` | +11 |
| 8 | Bekci Robot / Guardian (`src/agents/guardian/`) | `0fe8397` | 21 |
| 8.5 | Bekci Alert n8n workflow yaratildi + 13 inaktif workflow arsivlendi | `1573c41` | — |
| 8.6 | `system_settings` NocoDB tablosu auto-create migration | `9ed27d6`, Cloud Shell'de kosuldu, OK | 8 |
| C | MindBot 3 status tool (outreach_status, auto_reply_status, outreach_health) | `dc74375` | +9 |
| 9 | n8n bridge tool (`src/tools/n8n_bridge_tools.py`) — MindBot 10 workflow'u tanir | `4e8772e` | 16 |

**Toplam test: 182/182 yesil**, regression yok.

### KRITIK BILGILER (yeni session bunlari ezbere bilmeli)

**GCP:**
- Project: `instagram-post-bot-471518`
- Cloud Run service: `agents-sdk-api` (us-central1)
- Mevcut image: `v1.21.0` (eski, yeni kod YOK)
- **ROLLBACK noktasi:** `agents-sdk-api-00025-rnw` (v1.21.0, 2026-05-09)
- Region: `us-central1`
- Active project ayri olabilir; once `gcloud config set project instagram-post-bot-471518` yapilmali

**NocoDB (`http://34.26.138.196`):**
- API token: `MNhF4r4rHzFwBZXn96Xpjl-EdffKmifC7-eLK7Kn` (3 kez ekranda gozuktu — kullanici BILEREK rotate'i ertelemis, deploy sonrasi yapacak)
- base_id: `ps9dj2fqrh823av`
- Leadler table: `m5lcgc5ifeqh38h`
- Etkilesimler table: `mx3kbw2vhwimxjf`
- **system_settings table: `mzpphfqirl8njoe`** (Bekci'nin paused flag'i burada)

**Zernio (WhatsApp wrapper):**
- API key: `sk_bbd6...` (Seyma'nin scriptinde plain)
- WA account ID: `69ecc2273a63baf2053dfc21`
- Webhook URL'i SU AN nereye gidiyor BILINMIYOR (Beyza/Seyma kontrol edecek)

**n8n (`https://mindidai.app.n8n.cloud`):**
- 25 aktif workflow (38'den 13'u arsivlendi 2026-05-11)
- **Bekci Alert workflow:** `JQrjJcDRuYKTpMkC` (`/webhook/bekci-alert`, Gmail node Seyma'ya)
- Itiraz Agent: `9nTdKNPLCjo8DKfE` (webhook /itiraz-gelen, Gemini siniflandirma)
- Takip Agent: `nWNMQYHJzsMvMUGP` (schedule 6sa, deploy gunu filter guncellenecek)
- Lead Toplama: `l31p16NRZeyk4eEm`
- Upsell: `kVXXr4e6O5F3lGiD`, Referans: `28hnN6OrH5TF9NX2`
- Meta Lead Ads: `xblguxS49CJ4r4OF`

### DEPLOY ICIN GEREKLI Cloud Run env'leri (HENUZ EKLENMEMIS)

`agents-sdk-api` servisine eklenecekler:
```
ZERNIO_API_KEY=sk_bbd6...
ZERNIO_WA_ACCOUNT_ID=69ecc2273a63baf2053dfc21
ZERNIO_WEBHOOK_SECRET=<openssl rand -hex 32>
NOCODB_SETTINGS_TABLE_ID=mzpphfqirl8njoe
N8N_BASE_URL=https://mindidai.app.n8n.cloud
GUARDIAN_ALERT_WEBHOOK_URL=https://mindidai.app.n8n.cloud/webhook/bekci-alert
```

**3 yeni Cloud Run JOB** kurulacak (ayni image, farkli command):
- `slowdays-outreach`: `python -m src.agents.outreach.runner`
- `slowdays-auto-reply`: `python -m src.agents.auto_reply.runner`
- `slowdays-guardian`: `python -m src.agents.guardian.runner`

Hepsi ilk DRY_RUN=true ile baslat, paralel izle, atomic switch'te DRY_RUN=false.

### SIRADAKI ADIM — DEPLOY EVRELERI

1. **Zernio panel kontrolu (2 dk):** Inbox / Conversations → son 1 saat outbound mesaj var mi? Bu Seyma'nin PC'sindeki scripti calisiyor mu kontrol icin.
   - **A:** 0 mesaj → PC kapali, direkt deploy
   - **C:** 5+ mesaj → PC acik, Seyma'ya "scriptleri kapat" mesaji
2. **Docker build v1.22.0** (Cloud Shell, gcloud builds submit)
3. **Cloud Run service update** (yeni image)
4. **3 Cloud Run job yarat** (DRY_RUN=true)
5. **30 dk shadow run** — loglarda Outreach/Auto-reply Cloud kararlari logla, PC kararlariyla karsilastir
6. **Atomic switch (5 dk):**
   - Zernio panel webhook URL → `https://.../zernio/webhook`
   - Seyma PC scripts: Ctrl+C (Beyza/Seyma uzaktan veya Seyma manuel)
   - Cloud Run job env: DRY_RUN=false
   - n8n Takip Agent filter update (mind-agent SDK ile, ben yaparim)
7. **24 saat izleme**

### MALIYET (aylik tahmini)
- Cloud Run jobs (3 worker): $0-2 (free tier'da)
- Artifact Registry: ~$0.10
- OpenAI gpt-4o-mini (auto-reply): ~$0.10
- Diger (NocoDB/n8n/Zernio/Meta WhatsApp): Seyma'nin zaten odedigi
- **Slowdays icin ek aylik maliyet: ~$1**

### KULLANICI ERISIM DURUMU
- Beyza + Seyma'nin TUM hesaplarina erisim var (GCP/NocoDB/Zernio/n8n/GitHub)
- **Seyma'nin Windows PC'si yanimda DEGIL** — uzaktan ulasilamiyor
- Cloud Shell + browser yeterli, deploy yapilabilir

### GUVENLIK BACKLOG (deploy sonrasi)
- `NOCODB_API_TOKEN` ekran kaydina dustu — rotate edilecek (kullanici bilerek erteliyor)
- Cloud Run env'inde tum API key'ler plain text — Secret Manager'a tasinacak

### TASARIM KARARLARI (DEGISTIRME)
- Outreach long-running worker (cron degil) — jitter + batch break Meta spam filtresine karsi
- Auto-reply intent classifier + LLM rephrase HIBRIT — Seyma'nin 3 gercek mesaji ANCHOR olarak templates.py'da, LLM bunu KORUMAKLA yukumlu (Bodrum/Marmaris/Fethiye, "30 dakikalik kahve", "Booking komisyonu")
- Bekci Robot otomatik yeniden baslatma YAPMAZ — RED kararla pause, insan onayli resume
- n8n workflow'lari (Itiraz/Upsell/Referans/Lead Toplama) AYNEN KALIR, mind-agent'a porte EDILMEZ — koprü tool ile MindBot bunlari tetikler
- Slowdays leadleri vs Mindid B2B leadleri ayni NocoDB Leadler tablosunda, ayirt edici field `source_workflow_id` (Slowdays = `outreach_agent_v1`)

### YAPILMAYAN — SONRAYA
- Adim 7 (Guardrail) ZATEN Adim 8 olarak yapildi — yok artik
- Adim 8B: Auto-reply'a `itiraz` intent ekle + n8n Itiraz Agent webhook handoff (gercek itiraz ornekleri gordukten sonra)
- Adim 10: Reporting dashboard mind-id portal sekmesi
- LinkedIn / Clay / IG DM agentlari (`AGENT-MIMARISI-MASTER.md`)
- Cloud Run secrets sertlestirme (P1 backlog #6)

---

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
| 8 | Bekci Robot (Guardian) — kotu metric'lerde Outreach pause | 6 | 4 saat | **DONE 2026-05-11** — `src/agents/guardian/{policy,metrics,decisions,runner}.py`. Her 30dk Etkilesimler'den 24h reply rate / engagement rate / failure rate hesapla. GREEN/YELLOW/RED state machine. RED ise system_settings.outreach_paused=true. Outreach runner her tick basinda bu bayragi okur, durur. Insan onayli yeniden baslatma. n8n alert webhook (env GUARDIAN_ALERT_WEBHOOK_URL) — Sema'ya mail icin n8n Gmail node'u tetiklenir (kod tekrari yok). Migration: `scripts/migrate_guardian_schema.py` (system_settings tablosuna kolon + initial row). 21 yeni test, 158/158 yesil. |
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

### MIGRATIONS DONE (Cloud Shell, 2026-05-10)

NocoDB schema migration calistirildi (`python scripts/migrate_auto_reply_schema.py`):
- ✅ Etkilesimler.auto_reply_processed (Checkbox, default false)
- ✅ Leadler.asama option 'Takipte' eklendi
- ✅ Leadler.son_temas (DateTime)

Bu Adim 6 Auto-reply Agent'in NocoDB tarafindaki onkosulu — artik Beyza tarafinda UI ile elle ekleme kalmadi.

### n8n SALES AGENT HARITASI (2026-05-11 MCP ile dogrulandi)

`mindidai.app.n8n.cloud`'da 38 workflow var. Sales ile alakali olanlar:

| Agent | Workflow ID | Tetik | Domain | Python ile cakisma? |
|---|---|---|---|---|
| **Itiraz Agent** | `9nTdKNPLCjo8DKfE` | Webhook `/itiraz-gelen` | Mindid B2B (form/email itiraz) → Gemini → NocoDB Itirazlar → Seyma'ya oneri maili (insan onayli, otomatik mesaj YOLLAMAZ) | ❌ Yok. Auto-reply'a `itiraz` intent eklenip handoff yapilabilir (POST `/itiraz-gelen`). |
| **Takip Agent** | `nWNMQYHJzsMvMUGP` | Schedule 6 saatte bir | Slowdays Leadler tablosunu tarar, `asama=Yeni OR Soguk` → Seyma'ya mail | ⚠️ **EVET, RISK.** Outreach canliya gecince gunde 240 Soguk olusur → Takip Agent 4×240=960 mail atar. Filter'a `son_temas null OR <now-7gun` ekle. **Atomic switch ile birlikte yap.** |
| **Upsell Agent** | `kVXXr4e6O5F3lGiD` | Schedule gunde 10:00 | NocoDB Firsatlar (`mnf5nyu2mx5xtej`, asama=Kazanildi) → 28-32 gun once kapanmis → upsell maili | ❌ Yok |
| **Referans Agent** | `28hnN6OrH5TF9NX2` | Schedule gunde 11:00 | Aynı Firsatlar → 58-62 gun → referans maili | ❌ Yok |
| **Meta Lead Ads Agent** | `xblguxS49CJ4r4OF` | Facebook Lead Ads webhook | Lead → NocoDB + Seyma'ya mail | ❌ Yok (Adim 3 ile fix'lendi) |
| **Lead Toplama Agent** | `l31p16NRZeyk4eEm` | Webhook | Lead skor + NocoDB + mail | ❌ Yok |

### ATOMIC SWITCH PLANI (Outreach + Auto-reply canliya gecis)

Seyma'nin local script'leri (`otel_gonderim.py`, `lead_monitor.py`) hala Windows PC'sinde calisiyor. Python sistemler GitHub'da hazir ama deploy edilmedi. Cakisma SADECE deploy + Seyma scripti acik kalirsa olur.

Sirali plan (10 dakika):
1. Cloud Run image v1.22.0 build & push (yeni `/zernio/webhook` route + iki yeni job)
2. Outreach + Auto-reply Cloud Run job'larini `DRY_RUN=true` ile baslat (gerçek mesaj atmaz, shadow loglar)
3. 30 dk Seyma scripti ile paralel log kiyaslamasi (NocoDB Etkilesimler tablosuna farkli "agent" field'i)
4. ATOMIC pencere (5 dk):
   - Seyma PC: `otel_gonderim.py` ve `lead_monitor.py` process'lerini kill
   - Zernio panel: webhook URL → `https://...run.app/zernio/webhook` + secret set
   - Cloud Run job env: `DRY_RUN=false` update
   - n8n Takip Agent: filter'a `(son_temas,is_empty)~or(son_temas,before,now-7d)` ekle (Adim A)
5. 1 saat gozlem: bir otele 2 mesaj geliyor mu? — gelmiyorsa OK
6. 24 saat sonra Seyma scripti dosyalarini sil (PC'den)

### MIGRATIONS DONE (Cloud Shell, 2026-05-11) — Guardian schema

`python scripts/migrate_guardian_schema.py` (auto-create modu):
- ✅ system_settings tablosu yaratildi (base_id=ps9dj2fqrh823av)
- ✅ **NOCODB_SETTINGS_TABLE_ID=mzpphfqirl8njoe** (Cloud Run env'ine eklenecek)
- ✅ 7 kolon: outreach_paused (Checkbox), pause_reason (LongText),
  paused_at (DateTime), last_health_check (DateTime),
  last_decision_level (SingleLineText), last_decision_reason (LongText),
  last_metrics_json (LongText)
- ✅ Initial row (Id=1) insert edildi (outreach_paused=false)

Bekci Robot artik bu tabloya tick yazabilir. Outreach Robotu her tick basinda
outreach_paused okur; True ise mesaj atmaz.

### FAZ 1 DEPLOY DONE (2026-05-12) — Zernio MCP canli

Cloud Run v1.22.6 (revision agents-sdk-api-00034-vgb) canli %100 trafik.
Rollback noktasi: 00025-rnw (v1.21.0 orijinal).

Test sonuclari (portal + curl):
- ✅ "Sicak lead sayisi?" → 68 (count_leads NocoDB)
- ✅ "Zernio'da hangi sosyal medya hesaplari?" → 9 hesap, Zernio MCP (accounts_list)
- ✅ "Slowdays reklamlarimi listele" → Zernio MCP (list_ad_campaigns)
- ✅ "n8n'de hangi workflow'lar var?" → 10 workflow (köprü)
- ✅ "Bekci Alert yapilandirildi mi?" → configured: true
- ✅ "Bugun outreach kac mesaj?" → 0/240 (NocoDB exactDate filter)

8 deploy yaptik, hicbiri canliyi bozmadi (Cloud Run revision/health check
fail-safe). Bug'lar production'da gozlemlendi, fix'lendi:
1. MCP otomatik connect etmiyor → FastAPI lifespan
2. agents.mcp.manager modulu yok → inline minimal manager
3. tool_filter signature (context, tool) → fix
4. NocoDB v2 datetime ISO format reddediyor → exactDate/daysAgo operator

Bilinen sinir: gpt-4o TPM 30K, Zernio MCP 80 tool context'i ~28K token.
Hizli ardisik sorularda 429 rate limit. Faz 2-3-4 boyunca takilmaz; demo
oncesi tool filter darat + gpt-4o-mini orchestrator kombosu uygulanir.

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
6. **Cloud Run secrets sertlestirme (P1, 2026-05-10 tespit edildi)** — `agents-sdk-api` servisinde OPENAI_API_KEY / GOOGLE_AI_API_KEY / LATE_API_KEY / FAL_KEY / SERPER_API_KEY / KLING_*  / **NOCODB_API_TOKEN** hepsi **plain text env var** olarak duruyor (yalnizca FIREBASE_CREDENTIALS_FILE Secret Manager'da). Risk: `gcloud run services describe` cikti loglara, terminal scrollback'ine, ekran kayitlarina dusuyor. **Cozum:** Her birini `gcloud secrets create <name> --data-file=-` ile Secret Manager'a tasi, `gcloud run services update --update-secrets KEY=secret:latest` ile bagla. Beyza musait olunca yapilacak.
7. **Zernio env'leri eksik (2026-05-10 tespit edildi)** — `agents-sdk-api` Cloud Run servisinde ZERNIO_API_KEY ve ZERNIO_WEBHOOK_SECRET YOK. Adim 2-5 deploy oncesi Secret Manager + `--update-secrets` ile eklenmeli, yoksa `/zernio/webhook` ve auto_reply/outreach worker fail eder.

## Notlar

- API response'lar camelCase: `inlineData`, `mimeType`
- Firebase Storage path → GCS URI: `gs://bucket/path`
- Story: `is_story=True`, caption bos, 9:16 ratio
- Error reporting: `report_error(business_id, agent, task, error_message, error_type, severity)`
- YouTube: <=3dk = Shorts (thumbnail yok), >3dk = Normal (thumbnail desteklenir)



---

## 🧹 Açık İş Bırakma Kuralı (Kalıcı — 2026-05-24)

**Kural:** Yeni bir göreve başlamadan ÖNCE Claude tüm repolarda (`mind-id`, `mind-agent`, `customer_agent`) açık PR ve unutulmuş branch olup olmadığını **mutlaka kontrol eder**. Açık iş varsa önce onları temizler (merge / kapat / arşivle), sonra yeni göreve başlar.

**Sebep:** Açık PR + yarım branch birikince Claude'un kafası karışıyor — hangi kod aktif, hangi değişiklik nerede belirsizleşiyor. Temiz başlangıç = doğru karar.

**Session başında zorunlu kontrol:**
1. Her 3 repoda açık PR listesi (MCP `list_pull_requests` veya `gh pr list --state open`)
2. Her 3 repoda PR'sız stale branch listesi
3. Açık iş varsa kullanıcıya rapor et + temizlik planı sun
4. Temizlik bitmeden yeni iş başlatma

Bu kural CLAUDE.md'lerin sonuna her 3 repoda da yazıldı; biri silinirse diğerlerinden geri yüklenir.
