# GERİ DÖNÜŞ NOKTALARI (ROLLBACK)

> Bu dosya **her zaman güncel** tutulmalı. Her deploy / Firestore
> değişikliği öncesinde "şu an çalışan duruma nasıl dönerim" sorusunun
> cevabı burada olmalı.

**Son güncelleme:** 2026-05-14 (Faz A-D çalışmaları, henüz canlıya
alınmadı)

---

## 1. ŞU AN CANLI OLAN DURUM (TOUCH NOTHING)

### mind-agent (Cloud Run)
| Alan | Değer |
|---|---|
| Service | `agents-sdk-api` |
| Region | `us-central1` |
| GCP Project | `instagram-post-bot-471518` |
| **AKTİF Revision** | **`agents-sdk-api-00012-gln`** |
| **AKTİF Image** | **`agents-sdk-api:v1.21.2`** |
| URL | https://agents-sdk-api-704233028546.us-central1.run.app |
| Deploy tarihi | 2026-05-01 |
| Açıklama | Brand identity çalışmaları YOK. Beyza canlı NocoDB
şemasına hizalı. Production stabil. |

**Bu revision'a TRAFİK 100%** — değişmeyene kadar `00012-gln` çalışıyor.

### mind-id (Vercel) — 2026-05-15 GÜNCELLENDİ
| Alan | Değer |
|---|---|
| Site | `mind-id.vercel.app` (CANLI — Vercel migrasyonu/C1 TAMAM) |
| C1 durumu | ✅ Kullanıcı panel adımlarını (Faz 0-4) tamamladı, Vercel canlı çalışıyor (kullanıcı teyidi 2026-05-15) |
| C1 kodu | `claude/vercel-migration-aKUyl` branch (netlify.toml silindi, Node 20 pin, VillageCanvas aktif) |
| Eski Netlify | `mindid.netlify.app` — yedek olarak duruyor (Faz 6: ~1 hafta sonra sil/dondur) |
| Geri dönüş | Vercel'de problem olursa Netlify'da "Resume builds" + eski publish — yedek ayakta |

**`main`'e push edersek site bozulmaz** (build dondu). Ama Netlify'ı
yeniden aktif edersek prod kırılır — DOKUNMA.

### Firestore (`instagram-post-bot-471518`)
- `settings/app_settings.imageGenerationModel` → **şu an `gpt-image-1`**
  (Faz D testi için biz değiştirdik; canlıda olmasını istemiyorsak geri al)
  - **Önceki değer:** `gemini-2.5-flash-image`
- `businesses/slowdays_ai_test` → bizim test kaydımız (canlıda
  görünmüyor çünkü mind-id paneli farklı businesses listeliyor)
- `businesses/slowdays_ai_test/brand_identity/v1` → bizim manual marka
  kimliği test verisi

### Git
| Alan | Değer |
|---|---|
| Production branch | `main` |
| Son main commit | `f583020` (Beyza schema fix, 2026-05-01) |
| Çalışma branch | `claude/greeting-implementation-Up3H3` |
| PR | seymaakrs/mind-agent#10 (DRAFT) |

---

## 2. GERİ DÖNÜŞ KOMUTLARI

### A. Sadece Firestore'daki image model'ini geri al
**Ne zaman:** OpenAI image deneyimi sonrası Gemini'ye geri dönmek
istersek (maliyet, kalite, vb.).

```bash
python -c "
from src.infra.firebase_client import get_document_client
c = get_document_client('settings')
c.set_document('app_settings',
    {'imageGenerationModel': 'gemini-2.5-flash-image'},
    merge=True)
print('Image model: gemini-2.5-flash-image')
"
```

Doğrula:
```bash
python -c "
from src.infra.firebase_client import get_document_client
print(get_document_client('settings').get_document('app_settings').get('imageGenerationModel'))
"
```

### B. Cloud Run'ı (deploy ETTİYSEK) eski revision'a döndür
**Ne zaman:** Faz Z deploy sonrası prod kırılırsa.

```bash
gcloud run services update-traffic agents-sdk-api \
  --region=us-central1 \
  --project=instagram-post-bot-471518 \
  --to-revisions=agents-sdk-api-00012-gln=100
```

Doğrula (URL test):
```bash
TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task":"test","business_id":"slowdays_ai_test","task_id":"rollback_check"}' \
  https://agents-sdk-api-704233028546.us-central1.run.app/task
```

### C. Test verilerini Firestore'dan sil
**Ne zaman:** Test kayıtlarından (slowdays_ai_test) kurtulmak.

```bash
python -c "
from src.infra.firebase_client import get_document_client
# Brand identity'i sil
get_document_client('businesses/slowdays_ai_test/brand_identity').delete_document('v1')
# İşletme kaydını sil
get_document_client('businesses').delete_document('slowdays_ai_test')
print('Test data deleted')
"
```

### D. PR #10'u kapat / branch'i sil
**Ne zaman:** Brand identity çalışmasından tamamen vazgeçersek.

```bash
# Önce PR'ı kapat (GitHub UI'dan veya gh CLI ile)
# Sonra branch'i sil
cd ~/mind-agent
git checkout main
git branch -D claude/greeting-implementation-Up3H3   # lokal
git push origin --delete claude/greeting-implementation-Up3H3  # uzak
```

### E. Belirli bir commit'i geri al (revert)
**Ne zaman:** Bir faz çalıştı diğeri çalışmadı — sadece sorunlu olanı
kaldır.

```bash
# Faz D'yi (OpenAI image migration) geri al
git revert 43601db
git push

# Faz C'yi (agent enjeksiyon) geri al
git revert 2668c44
git push
```

Faz'lar pure additive — birini geri almak diğerlerini kırmaz.

---

## 3. ÇALIŞMA SIRAMIZIN COMMIT GEÇMİŞİ

Sırayla geri alınabilir (her biri additive):

| Sırası | Commit | İçerik | Etkisi |
|---|---|---|---|
| 1 | `612779c` | **Faz A** — BrandIdentity schema + tools | Yeni Pydantic schema + Firestore yardımcı tools |
| 2 | `942724f` | **Faz B1** — Brand Synthesis Agent | Yeni agent (registry'e eklendi) |
| 3 | `2668c44` | **Faz C** — Marketing/Image/Video enjeksiyon | 3 agent'a fetch_brand_identity eklendi |
| 4 | `532f640` | scripts — interaktif fill/show CLI | Cloud Shell araçları (kod davranışı etkilemez) |
| 5 | `b555815` | scripts — brand_ab_compare runner | Test aracı |
| 6 | `5ebc0e5` | scripts — debug_image_brand runner | Tanı aracı |
| 7 | `f951176` | scripts — content_brand_ab runner | Test aracı |
| 8 | `870a859` | **Faz A2** — 10 yeni schema alanı + script + prompt | BrandIdentity'e Seyma listesinden 10 alan |
| 9 | `3b2d860` | **fix(image)** — tool-level retry | Transient Gemini hatalarına otomatik retry |
| 10 | `24d990f` | **fix(image/video)** — REFINES değil REPLACES | Prompt felsefesi düzeltmesi |
| 11 | `2a64c11` | **fix(image/marketing)** — YAZI/POSTER yasak | Text overlay + split-screen önleme |
| 12 | `0cd5358` | **Plan B** — prompt_summary'i image/caption böl | Constraint overload çözümü |
| 13 | `43601db` | **Faz D** — OpenAI image client + factory | Gemini → OpenAI toggle |

**Rollback noktası:** `f583020` (main'in son safe commit'i; bizim
hiçbir commit'imiz öncesi).

---

## 4. CANLIYA ALMA (FAZ Z) ÖNCESİ ÖN HAZIRLIK

Deploy yapılacağı zaman bu dosyaya **yeni bir bölüm eklenecek**:
- Yeni image tag (örn. `v1.22.0`)
- Yeni revision adı (Cloud Run otomatik atar)
- Yeni Firestore alan değerleri
- Deploy öncesi tam snapshot

**Şu an Faz Z henüz yapılmadı.** Yukarıdaki "AKTİF" bilgiler hâlâ
geçerli.

---

## 4.5. CANLI n8n DEĞİŞİKLİĞİ — Zernio fix (2026-05-14)

**YAPILDI — canlı production'a uygulandı (kod değil, n8n workflow).**

| Alan | Değer |
|---|---|
| Workflow | `Lead Toplama Agent` (id `l31p16NRZeyk4eEm`) |
| n8n | https://mindidai.app.n8n.cloud |
| Değişen | Sadece `Calculate Lead Score` code node `jsCode` |
| Eski kod | 3174 char (Zernio formatını parse etmiyordu — boş kayıt) |
| Yeni kod | 2894 char (Zernio message/comment + generic + boş-kayıt koruması) |
| Test | Id 196 "Test Otel Sahibi" dolu düştü → kanıtlandı, sonra silindi |
| Workflow durumu | ACTIVE kaldı (değişmedi) |

**Geri dönüş (eski koda dön):**
Yedek: `/tmp/lead-toplama-BACKUP.json` (Cloud Shell — kalıcı değil, /tmp
temizlenebilir!). Repo'da eski kod git history'de: commit `0de44b9`
öncesi `n8n/workflows/lead-toplama-agent.json`.

```bash
# Eski koda dönmek için (customer_agent repo'da):
git show 0de44b9~1:n8n/workflows/lead-toplama-agent.json > /tmp/lead-OLD.json
# /tmp/lead-OLD.json içindeki eski jsCode'u alıp aynı PUT script'iyle
# n8n'e geri yaz (Bölüm 2'deki Zernio uygulama script'inin tersi).
```

Kalıcı yedek için `/tmp/lead-toplama-BACKUP.json`'ı repo dışı güvenli
bir yere kopyalamak iyi olur (henüz yapılmadı — /tmp geçici).

---

## 5. KURAL

1. **Her büyük değişiklik öncesi** bu dosyaya bak. Bir önceki güvenli
   duruma dönüş komutu burada olmalı.
2. **Her değişiklik sonrası** bu dosyayı güncelle. Yeni durumu yaz,
   eski durumu "önceki" olarak kaydet.
3. **Production'a (Cloud Run main revision veya Netlify published
   deploy) dokunma** — `claude/...` branch'i her şeyi yapsın, main'e
   merge ve deploy ayrı bir adım.
4. Şüphedeysen **önce burayı oku, sonra dokun**.
