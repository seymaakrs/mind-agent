# Zernio Migration — Durum Raporu

**Tarih:** 2026-05-22
**Branch:** `claude/vibrant-brahmagupta-m8eqI` (3 repo)
**PR:** mind-agent #34 (draft)

## TL;DR

| Repo | Durum | Açıklama |
|---|---|---|
| `mind-agent` | ✅ TAMAM | Late → Zernio geçişi 6 fazda tamamlandı, 39/39 test yeşil, audit fix'leri push edildi. |
| `mind-id` | ⚠️ EKSİK | Hâlâ Late API'ye canlı bağımlı (sync-accounts route + Cloud Functions). Ayrı migration ticket gerek. |
| `customer_agent` | ✅ N/A | Sadece doküman/script var, kod yok. Migration kapsamı dışında. |

---

## mind-agent — Yapılanlar (Faz 0 – Faz 6)

### Faz 0 — Env Scaffolding
- `.env`, `.env.sales.example`, `src/app/config.py`'a şu env'ler eklendi:
  - `ZERNIO_API_KEY`, `ZERNIO_BASE_URL`, `ZERNIO_WA_ACCOUNT_ID`, `ZERNIO_WEBHOOK_SECRET`
- `TODO.md`'ye credentials görevi eklendi.

### Faz 1 — Zernio Client SDK
`src/infra/zernio/` paketi (mixin composition):
- `base.py` — `_ZernioBase` (httpx AsyncClient + `_post`, `_get`, `_patch`, `_post_multipart`)
- `whatsapp.py`, `inbox.py` — mevcut (Slowdays için kurulmuştu)
- `posts.py` — **YENİ:** `create_post`, `get_post`, `list_posts`, `retry_post`, `unpublish_post`
- `media.py` — **YENİ:** `presign_media` (≤5 GB), `upload_media_direct` (≤25 MB)
- `analytics.py` — **YENİ:** `get_analytics`, `get_post_analytics`, `get_accounts`
- `__init__.py` — `ZernioClient` = WhatsApp + Inbox + Posts + Media + Analytics + Base
- Test: `tests/test_zernio_posts.py` (16 test)

### Faz 2 — Publisher Abstraction
`src/infra/publisher/`:
- `base.py` — `PublishResult` dataclass + `PublisherClient` runtime_checkable Protocol
- `zernio_publisher.py` — `ZernioPublisher`: `instagram_post/_carousel`, `linkedin_post/_carousel`, `tiktok_video/_carousel`, `youtube_video`, `get_analytics`
- `to_dict()` Late'in tarihsel response shape'ini birebir korur → downstream consumer'lar etkilenmez.
- Test: `tests/test_publisher.py` (23 test)

### Faz 3 — Orchestrator Tools (IG)
- `src/tools/orchestrator/instagram.py` artık `late_client` yerine `publisher` kullanıyor.

### Faz 4 — Orchestrator Tools (LinkedIn, TikTok, YouTube)
- `src/tools/orchestrator/{linkedin,tiktok,youtube}.py` aynı migrasyon.

### Faz 5 — Analytics
- `src/tools/instagram_tools.py` → `publisher.get_analytics()` kullanıyor.
- `ZernioPublisher.get_analytics()` Zernio'nun `_id` → `postId` shape farkını normalize ediyor.

### Faz 6 — Late Temizliği
**Silinen:**
- `src/infra/late/` (5 dosya: __init__, base, instagram, linkedin, tiktok, youtube)
- `src/infra/late_client.py`
- `src/infra/publisher/late_publisher.py`
- `src/infra/publisher/shadow.py`
- 4 test dosyası (linkedin_post, tiktok_carousel, tiktok_video, publisher_shadow)
**Değişen:**
- `src/app/config.py`: `LATE_API_KEY` field kaldırıldı
- `.env`: `LATE_API_KEY` kaldırıldı
- `src/infra/publisher/__init__.py`: default backend `"zernio"`, `PUBLISHER_BACKEND=late` artık helpful error fırlatır
- `test_publisher.py` yeniden yazıldı, sadece ZernioPublisher

### Audit Fix (post-Faz-6, commit `1d7a93a`)
- `docker-compose.yml`: `LATE_API_KEY` env injection → `ZERNIO_*` (4 env)
- `src/infra/publisher/base.py`: docstring artık silinmiş `late_publisher.py`'a referans vermiyor
- `src/infra/late/` artık dizini tamamen silindi (audit'te `__pycache__` kalıntısı bulundu, temizlendi)

### Tests
**39 / 39 yeşil** (test_zernio_posts + test_publisher).

---

## mind-agent — Bilinçli Bırakılan (kozmetik, runtime'ı etkilemez)

| Yer | Sebep |
|---|---|
| `late_profile_id`, `late_post_id`, `latePostId` field adları | Wire shape — Zernio'nun döndürdüğü payload'ın tarihsel ismi. Tüm Firestore dokümanları + agent instruction'ları bu isimleri biliyor. |
| `classify_late_response()` fonksiyon adı | `service` parametresi alıyor, hem "late" hem "zernio" değerleriyle çalışıyor. Yeniden adlandırma > 50 callsite dokunur, risk/değer oranı düşük. |
| Orchestrator/marketing instruction docstring'lerindeki "via Late API" ifadeleri | Agent prompt'larında "Late ID" → "Zernio profile ID" cilası bir sonraki cilada yapılabilir, davranışı etkilemiyor. |

---

## mind-id — Yapılması Gerekenler

### Mevcut Durum
- **Zernio entegrasyonu yok** (sıfır referans).
- Hâlâ canlı Late API'ye konuşan dosyalar:
  - `app/api/sync-accounts/route.ts` — Late API'den IG/YT/TT/LI hesap senkronu
  - `functions/src/index.ts` (sat. 469-642+) — `getLateApiKey`, post listesi, IG stats Cloud Functions
  - `types/firebase.ts`, `lib/firebase/firestore.ts`, `hooks/useBusinesses.ts`, `hooks/useBusinessForm.ts` — `late_profile_id` Business field'i
  - UI: `business-detail.tsx`, `BasicInfoSection.tsx`, `business-details-tab.tsx`, `SyncAccountsButton.tsx`, `add-business.tsx`, `village-canvas.tsx`

### Eksikler / Yapılacaklar (öncelik sırasına göre)
1. **`app/api/sync-accounts/route.ts`** → Zernio `/v1/accounts` endpoint'ine port et.
2. **Cloud Functions (`functions/src/index.ts`)** → Late post fetch + IG stats fonksiyonlarını Zernio'ya port et. **Bu en kritik**: Late hesabı kapanırsa IG stats sıfırlanır.
3. **Business schema** → `zernio_profile_id` alanı ekle (paralel tut, Late ID'yi göç sonrası kaldır).
4. **Connections UI** → portal'a "Zernio Bağlantısı" akışı (API key, account ID, test connection butonu).
5. **`village-canvas.tsx`** marketing copy'sinde "Late API" → "Zernio" güncellemesi.

### Tahmini Süre
~1-2 gün (ayrı PR / ticket olarak ele alınmalı).

---

## customer_agent — Durum

- Yalnızca dokümantasyon ve script var (`AGENT-MIMARISI-MASTER.md`, `OPERATIONS.md`, `n8n/`, `scripts/`, `docs/`).
- Çalışan Python/TS kodu **yok**. Zernio referansı yok.
- `OPERATIONS.md`'deki 3 "Late" geçişi tarihsel referans — değişiklik gerekmiyor.

---

## Production Deploy Sırası (KRİTİK)

mind-agent PR #34'ü merge etmeden **önce**:

1. Cloud Run `agents-sdk-api` servisine env ekle:
   - `ZERNIO_API_KEY` (Secret Manager'dan)
   - `ZERNIO_WEBHOOK_SECRET`
   - `PUBLISHER_BACKEND=zernio` (opsiyonel — zaten default)
2. Yeni image'ı **kanarya** olarak deploy et (eski revision %100 traffic'te kalsın).
3. Sentetik bir IG post smoke test'i çalıştır.
4. Yeşil → `--to-revisions=new=100` ile cutover.
5. PR #34'ü merge et (Late kodu repo'dan silinir).

**Aksi takdirde** PR merge → eski revision'da `from src.infra.late import …` import fail → service down.

---

## Özet Komut Çıktısı

```
mind-agent tests:        39/39 ✅
mind-agent Late import:  0    ✅
mind-id Zernio refs:     0    ⚠️  (migration bekliyor)
customer_agent kodu:     n/a  —
```
