# 01 — Sistem Hiyerarşisi

> Bu doküman sistemin **katmanlı mimarisini** ve **bağımlılık kurallarını** tanımlar.
> Yeni özellik eklerken veya refactor yaparken **referans alınacak anayasa** niteliğindedir.

---

## 1. Genel Bakış (Kuş Bakışı)

```
┌──────────────────────────────────────────────────────────────┐
│                    KULLANICI / FRONTEND                       │   L0
│                  (web app, admin panel)                       │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (NDJSON streaming)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  L1 — TRANSPORT KATMANI                       │
│                       src/app/api.py                          │
│  • HTTP endpoint'leri (/task, /capabilities, /health)         │
│  • Request validation (Pydantic)                              │
│  • Streaming response, CORS, hata zarflama                    │
│  • thread_id yönetimi                                         │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  L2 — RUNNER KATMANI                          │
│                src/app/orchestrator_runner.py                 │
│  • Agent yaşam döngüsü (Runner.run)                           │
│  • Context hazırlama (business_id, references, extras)        │
│  • Hooks (CliLoggingHooks, progress queue)                    │
│  • TaskLogger entegrasyonu                                    │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  L3 — AGENT KATMANI                           │
│                       src/agents/                             │
│                                                               │
│   ┌─────────────────────────────────────────┐                │
│   │   ORCHESTRATOR  (gpt-4o-mini)           │  L3a — Üst     │
│   │   • Karar verici                        │                │
│   │   • Alt agent'ları tool olarak çağırır  │                │
│   └────────┬──────────┬──────────┬──────────┘                │
│            ▼          ▼          ▼          ▼                │
│   ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  L3b — Alt  │
│   │ IMAGE  │ │ VIDEO  │ │MARKETNG│ │ ANALYSIS │  (gpt-4o)   │
│   │ AGENT  │ │ AGENT  │ │ AGENT  │ │  AGENT   │             │
│   └────┬───┘ └────┬───┘ └────┬───┘ └────┬─────┘             │
└────────┼──────────┼──────────┼──────────┼────────────────────┘
         ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────┐
│                  L4 — TOOL KATMANI                            │
│                       src/tools/                              │
│  • Domain'e ait business logic                                │
│  • function_tool decorator ile sarılı                         │
│  • Agent'lar bu katmanı tool olarak görür                     │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  L5 — INFRA KATMANI                           │
│                       src/infra/                              │
│  • Dış servis client'ları (Firebase, Late, Gemini, ...)       │
│  • Hata sınıflandırma (errors.py)                             │
│  • Tek sorumluluk: "bağlan, çağır, sonuç döndür"              │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              DIŞ DÜNYA — 3rd Party APIs                       │
│   OpenAI · Gemini · Veo · Kling · HeyGen · fal.ai             │
│   Late · Serper · Firebase · Vertex AI                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Katman Sorumluluk Tablosu

| Katman | Klasör | Sorumlu | Sorumlu Değil |
|--------|--------|---------|---------------|
| **L1 Transport** | `src/app/api.py` | HTTP, streaming, request shape | İş mantığı, agent çağrısı detayları |
| **L2 Runner** | `src/app/orchestrator_runner.py` | Agent yaratma, hook, context | Agent kararları, tool çağrısı |
| **L3a Orchestrator** | `src/agents/orchestrator_agent.py` | Hangi alt agent? Hangi tool? Akış kontrolü | Domain detayı (görsel nasıl yapılır vb.) |
| **L3b Domain Agent** | `src/agents/{image,video,marketing,analysis}_agent.py` | Domain'in nasıl yapılacağı | Diğer domain'in işi, HTTP, DB connection |
| **L4 Tool** | `src/tools/...` | Tek bir iş birimini yapmak | Birden fazla iş birimini koordine etmek |
| **L5 Infra** | `src/infra/...` | Dış servis erişimi | Domain anlamı, iş mantığı |

---

## 3. Bağımlılık Kuralları (Dependency Rules)

> Bu kurallar **import yönünü** kontrol eder. İhlal = mimari kokusu.

### Kural 1 — Yukarıdan Aşağıya Akış
Üst katman alttakini bilebilir; alt katman üsttekini **bilmez**.

```
✅  agents/marketing_agent.py    →  tools/marketing/calendar.py    (OK)
❌  tools/marketing/calendar.py  →  agents/marketing_agent.py      (YASAK)
✅  tools/marketing/calendar.py  →  infra/firebase_client.py       (OK)
❌  infra/firebase_client.py     →  tools/marketing/calendar.py    (YASAK)
```

### Kural 2 — Atlama Yok
Bir katman **sadece bir alttaki** katmanı çağırır; iki katman aşağıyı **doğrudan** çağırmaz.

```
✅  api.py → orchestrator_runner.py → orchestrator_agent.py
❌  api.py → orchestrator_agent.py                            (atlama)
❌  api.py → tools/...                                        (büyük atlama)
```

**İstisna:** L4 (Tool) → L5 (Infra) doğal akış. L1/L2'nin L5'i çağırması yasak.

### Kural 3 — Yatay Çağrı Yasağı (Agent'lar Arası)
Domain agent'lar **birbirini doğrudan çağırmaz** — orchestrator üstünden geçer.

```
❌  marketing_agent  →  image_agent              (doğrudan)
✅  marketing_agent  →  image_agent_wrapper_tool  (tool olarak sarılı)
```

> **Mevcut durumda:** `agent_wrapper_tools.py` bu kuralı zaten uyguluyor. Marketing, Image/Video'yu tool olarak görür — agent olarak değil. ✅

### Kural 4 — Tool'lar Stateless
Tool'lar sınıf değil **fonksiyon** olmalı. State, ya parametre olarak gelir ya Firestore'dan okunur.

```python
# ✅ İYİ
@function_tool
async def save_seo_report(business_id: str, ...) -> dict:
    return await firebase_client.save(...)

# ❌ KÖTÜ
class SeoReporter:
    def __init__(self, business_id):  # state tutma
        self.business_id = business_id
```

### Kural 5 — Infra İzole
Infra modülleri **sadece** dış servisi konuşur. İş mantığı koymak yasaktır.

```python
# ✅ İYİ — late_client.py
async def post_instagram(media_url, caption) -> dict:
    return await self._http.post(...)

# ❌ KÖTÜ — late_client.py içinde
async def post_instagram(media_url, caption):
    if business.industry == "food":      # ← iş mantığı, infra'da olmaz
        caption += " #foodie"
    return await self._http.post(...)
```

---

## 4. Kontrol Akışı vs. Bağımlılık Akışı

İki akış var, ikisini karıştırmamak lazım:

| Akış Tipi | Yön | Örnek |
|-----------|-----|-------|
| **Kontrol akışı** | Yukarıdan aşağıya (çağrı) | api → runner → agent → tool → infra |
| **Bağımlılık akışı** | Yukarıdan aşağıya (import) | api `import` runner; tool `import` infra |
| **Veri akışı** | Çift yönlü | request inerken / response çıkarken |

> 💡 İkisinin de aynı yöne aktığı bir mimariye **layered architecture** denir. Sistemimiz bu pattern'i kullanıyor.

---

## 5. Mevcut Durum vs. İdeal Durum

### ✅ Şu Anda Doğru Olanlar

1. Katman ayrımı belirgin (`app/`, `agents/`, `tools/`, `infra/`).
2. `agent_wrapper_tools.py` ile yatay çağrı yasağı uygulanıyor.
3. `errors.py` ile L5 → L4 hata sınıflandırması typed.
4. Pydantic ile L1 request shape garanti.
5. `function_tool` decorator ile L4 stateless.

### ⚠️ Bilinen İhlaller / Düzeltme Adayları

| Sorun | Dosya | Hangi Kuralı İhlal Ediyor | Çözüm |
|-------|-------|---------------------------|-------|
| Devasa dosya | `src/tools/web_tools.py` (2596 satır) | Tek dosya, çok sorumluluk | `src/tools/web/` paketi (Faz 2) |
| Yanıltıcı isim | `src/tools/analysis_tools.py` (15 satır) | Boş wrapper, kafa karıştırıcı | Sil veya doldur |
| Backward-compat shim | `src/infra/late_client.py` (3 satır) | Geçici köprü kalıcılaştı | `late/` import'larını köke al |
| Capabilities drift | `src/app/capabilities.py` | Gerçek tool listesiyle uyumsuz | Sync testi (Faz 1) |
| Test boşluğu | `src/app/orchestrator_runner.py` | L2 katmanı test edilmemiş | Integration test (Faz 1) |

### 🎯 İdeal Durum (Faz'lar Tamamlanınca)

```
src/
├── app/                          ← L1 + L2
│   ├── api.py
│   ├── orchestrator_runner.py
│   ├── capabilities.py           ← tool envanteri ile sync
│   └── config.py
│
├── agents/                       ← L3
│   ├── orchestrator_agent.py
│   ├── {image,video,marketing,analysis}_agent.py
│   ├── instructions/             ← agent prompt'ları
│   └── registry.py
│
├── tools/                        ← L4 (her agent için bir paket)
│   ├── orchestrator/             (mevcut, OK)
│   ├── marketing/                (mevcut, OK)
│   ├── analysis/                 (mevcut, OK)
│   ├── image/                    (mevcut tek dosya → paket olabilir)
│   ├── video/                    (mevcut tek dosya → paket olabilir)
│   └── web/                      ← YENİ (web_tools.py'den bölünür)
│
├── infra/                        ← L5
│   ├── firebase_client.py
│   ├── google_ai_client.py
│   ├── kling_client.py
│   ├── heygen_client.py
│   ├── late/                     (mevcut paket)
│   ├── serper_client.py          ← YENİ (web_tools'tan ayrılır)
│   ├── errors.py
│   ├── task_logger.py
│   └── thread_manager.py
│
└── models/                       ← Cross-cutting Pydantic modelleri
    ├── prompts.py
    └── tool_io.py
```

---

## 6. Genişleme Kuralları (Yeni Özellik Eklerken)

> Yeni bir özellik gelince **karmaşıklığı artırmadan** eklemenin reçetesi:

| Eklemek istediğin | Yer | Yan etki |
|-------------------|-----|----------|
| Yeni dış servis (örn. Stripe) | `src/infra/stripe_client.py` | Sadece L5 etkilenir |
| Yeni domain tool (örn. SMS gönder) | `src/tools/<agent>/sms.py` | L4 etkilenir, agent instructions'ı güncelle |
| Yeni alt agent | `src/agents/<name>_agent.py` + `instructions/<name>.py` + wrapper | L3 + agent_wrapper_tools |
| Yeni HTTP endpoint | `src/app/api.py` | Sadece L1 |
| Yeni capability (UI'da gözüksün) | `src/app/capabilities.py` | L1 — sync testi düşmesin |

**Kontrol Listesi (her yeni özellik için):**

- [ ] Doğru katmana mı koydum? (`L1` mi `L4` mı `L5` mi?)
- [ ] Yukarı doğru import yaptım mı? (yapmamalıyım)
- [ ] Test ekledim mi? (test-first kuralı)
- [ ] `capabilities.py`'a yansıttım mı? (UI'da gerekiyorsa)
- [ ] İlgili agent instructions güncellendi mi? (CLAUDE.md kural #7)
- [ ] CLAUDE.md ana özeti güncellendi mi?

---

## 7. Veri Yazma Hiyerarşisi

> Her katmanın **hangi Firestore koleksiyonuna yazma yetkisi** var? Bu da bir hiyerarşidir — karmaşıklığı düşürür.

| Koleksiyon | Yazan Katman | Yazmamalı |
|-----------|---------------|-----------|
| `businesses/{bid}` | L4 (orchestrator/business.py) | Agent doğrudan |
| `businesses/{bid}/media/` | L4 (storage.py) | Agent doğrudan |
| `businesses/{bid}/instagram_posts/` | L4 (marketing/media_tracking.py) | L1 |
| `businesses/{bid}/content_calendar/` | L4 (marketing/calendar.py) | Diğer agent'lar |
| `businesses/{bid}/reports/` | L4 (analysis/reports.py) | Marketing agent |
| `businesses/{bid}/seo/*` | L4 (analysis/seo.py) | Marketing agent |
| `businesses/{bid}/agent_memory/{agent}` | L4 (memory.py) | Cross-agent okuma OK, yazma kendi agent'ı |
| `businesses/{bid}/instagram_stats/week-*` | Cloud Function (sistem dışı) | Agent yazmaz, **sadece okur** |
| `active_tasks/`, `errors/`, `logs/` | L2/L4 (task_logger, business.py) | L1 |

**Kural:** Bir koleksiyonun **tek yazarı** olur (genellikle). Birden fazla yer yazıyorsa şema bozulması kaçınılmaz.

---

## 8. Bu Dokümanı Güncelleme Tetikleyicileri

Aşağıdaki olaylardan biri olunca bu doküman **aynı PR içinde** güncellenir:

- Yeni katman eklendi (nadir)
- Yeni agent eklendi → `02-agents.md`
- Yeni dış servis eklendi → `06-external-services.md`
- Bir bağımlılık kuralı bilerek esnetildi → bu dokümanda **istisna olarak** yazılır
- Bilinen ihlal düzeltildi → "Mevcut Durum" bölümünden satır silinir

---

## 9. Hızlı Karar Kılavuzu

> "Bu kodu nereye koyayım?" diye düşünüyorsan:

```
HTTP/streaming işi mi?              →  L1 (app/api.py)
Agent yaşam döngüsü mü?             →  L2 (orchestrator_runner.py)
LLM kararı vermesi gereken mi?      →  L3 (agents/)
Tek bir iş yapan saf fonksiyon mu?  →  L4 (tools/)
Dış API çağrısı mı?                 →  L5 (infra/)
Pydantic model mi?                  →  models/
```

> "Kim çağırsın?" diye düşünüyorsan:

```
Bir LLM kararı gerekiyor mu?        →  Agent'a tool yap
Deterministik akış mı?              →  Orchestrator runner içinde Python ile çağır
Birden fazla LLM kararı mı?         →  Workflow tool olarak compose et (Faz 5)
```
