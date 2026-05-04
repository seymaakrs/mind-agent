# OPERATIONS — Hassas Noktalar & Geri Dönüş

> **Yeni Claude session'ı buraya bakacak. Önce bu dosyayı oku.**
> Bu dosya 4 repo (`mind-id`, `mind-agent`, `customer_agent`, `mindid-nocodb`) için ortak operasyon kılavuzudur.

---

## ✅ Stable Geri Dönüş Noktaları

| Tag | Tarih | Durum | Geri dönüş |
|---|---|---|---|
| `stable-2026-05-04` | 2026-05-04 | Image gen + lead query + Late posting **çalışıyor** | `git checkout stable-2026-05-04` |

**3 repo'da aynı tag adı:** mind-id, mind-agent, customer_agent.

### Cloud Run revision karşılığı
- `agents-sdk-api-00024-qtz` (v1.20.7) → `stable-2026-05-04` ile uyumlu
- Önceki çalışan: `agents-sdk-api-00023-df2`, `agents-sdk-api-00022-vs6`

### Hızlı rollback
```bash
# Repo rollback
git checkout stable-2026-05-04

# Cloud Run rollback (önceki revision'a)
gcloud run services update-traffic agents-sdk-api \
  --region=us-central1 --project=instagram-post-bot-471518 \
  --to-revisions=agents-sdk-api-00024-qtz=100
```

---

## 📋 BEKLEYEN İŞLER (henüz yapılmadı)

Önceliğe göre sıralı:

### 1. Branch protection (KISMEN — sırada)
- [ ] mind-id main: PR + 1 approval gerek
- [ ] mind-agent main: PR + 1 approval gerek
- [ ] customer_agent main: PR + 1 approval gerek

GitHub web UI: `https://github.com/seymaakrs/<repo>/settings/branches` → "Add ruleset" → main → Require PR + Require 1 approval + Do not allow bypassing.

### 2. CLAUDE.md güncellemesi
- [ ] mind-agent CLAUDE.md → `imageGenerationModel: gemini-2.5-flash-image` (yapıldı), `gpt-5 ASLA` notu ekle
- [ ] mind-id CLAUDE.md → "command-center-canvas yeni özellik" notu, branch protection notu

### 3. Güvenlik temizliği (DÜNDEN)
- [ ] `mind-agent/serviceAccount.json` (2376b) git'ten sil + .gitignore
- [ ] `mind-agent/gcp-service-account.json` (2387b) git'ten sil + .gitignore
- [ ] Eski Google AI key (`AIzaSyDGdNaR...kpM`) AI Studio'dan **silindi mi?** Doğrula
- [ ] Yeni Google AI key (`AIzaSyAf...bx08`) chat'e geçti — **rotate edilmeli** (yenisini üret, eskiyi sil)
- [ ] Late/Zernio key (`sk_518334...`) chat'e geçti — rotate öner
- [ ] mind-id PR #6 (`claude/improve-canvas-homepage-VIB8G`) → `netlify.toml` SECRETS_SCAN_OMIT_KEYS bypass içeriyor → **MERGE EDİLMEMELİ**, kapat veya düzelt
- [ ] NocoDB `claude-setup` token revoke
- [ ] n8n `claude-status-2026-05-01` token revoke

### 4. gitleaks (pre-commit secret scanner)
- [ ] 3 repo'ya da kur — credential leak'i baştan engelle

### 5. Firestore Security Rules
- [ ] `settings/app_settings` belgesi sadece super_admin yazabilsin (yanlışlıkla `gpt-5` yazılmasın)

### 6. Şeyma için onay matrisi
- [ ] `CHANGES_REQUIRE_APPROVAL.md` hazırla — hangi değişiklikler onay gerektirir

### 7. mind-id `/satis` sayfası
- [ ] NocoDB Leadler tablosu read-only dashboard

### 8. Anasayfa Canvas (DEVAM EDIYOR)
- [x] command-center-canvas.tsx (4 gün önce merge) ✅
- [ ] Team hierarchy canvas (PR #6, MERGE EDİLMEMELİ — secret bypass içerir)

### 9. Meta Lead Ads webhook
- [ ] Facebook App Review onayı bekleniyor (dış bağımlılık)

### 10. Meta agent → sales_agent rename
- [ ] İsim kafa karıştırıcı (artık tüm CRM'i temsil ediyor)

### 11. Orchestrator model upgrade
- [ ] gpt-4.1-mini routing'de zayıf, lead bypass var ama gelecekte gpt-4o öneri

---

## 🚨 ASLA YAPMA Listesi

Bu hatalar **kanıtlanmış kırılma sebepleri**:

1. ❌ `marketingModel`, `analysisAgent` Firestore'a `gpt-5` yazma → **OpenAI'da gpt-5 YOK**, fake-success döner
2. ❌ `imageGenerationModel`'i `gemini-2.0-flash-image-generation` yapma → Google API'de yok, 404
3. ❌ Repo'ya `serviceAccount.json` / private key commit etme → Google otomatik iptal eder
4. ❌ Netlify secret scan'i bypass etme (`SECRETS_SCAN_OMIT_KEYS`'e private key isimleri ekleme) → güvenlik açığı
5. ❌ Cloud Run revision'a doğrudan deploy etmeden Firestore env'i değiştir → cache uyumsuzluğu
6. ❌ Frontend (mind-id) `serverUrl` Firestore alanını silme → "Bağlantı yok"
7. ❌ Cloud Run servisini `--no-allow-unauthenticated` yapma → mind-id frontend Netlify'dan erişemez
8. ❌ MindID `late_profile_id` Firestore alanını yanlış değer ile değiştir → sync `accounts: []` döner

---

## 🛠️ Hızlı Kurtarma Komutları

### Sistem sağlık testi (5 saniye)
```bash
curl -s https://agents-sdk-api-704233028546.us-central1.run.app/health
# Beklenen: {"status":"ok"}
```

### Lead query backend test
```bash
TOKEN=$(gcloud auth print-identity-token)
curl -s --max-time 60 -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task":"kaç sıcak lead var listele","business_id":"satis_dashboard","task_id":"healthcheck"}' \
  https://agents-sdk-api-704233028546.us-central1.run.app/task | tail -c 500
```

### Image gen backend test
```bash
TOKEN=$(gcloud auth print-identity-token)
curl -s --max-time 60 -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task":"bir kırmızı elma görseli üret","business_id":"vPoHKXpvGqdMQzrjN4i4","task_id":"image-test"}' \
  https://agents-sdk-api-704233028546.us-central1.run.app/task | tail -c 500
```

### Firestore settings doğrulama
```bash
python3 -c "
from google.cloud import firestore
db = firestore.Client(project='mindid-75079')
data = db.collection('settings').document('app_settings').get().to_dict()
print('serverUrl:', data.get('serverUrl'))
print('orchestratorModel:', data.get('orchestratorModel'))
print('marketingModel:', data.get('marketingModel'))
print('analysisAgent:', data.get('analysisAgent'))
print('imageGenerationModel:', data.get('imageGenerationModel'))
"
```

### Beklenen değerler (2026-05-04 itibariyle):
- `serverUrl`: `https://agents-sdk-api-704233028546.us-central1.run.app`
- `orchestratorModel`: `gpt-4.1-mini`
- `marketingModel`: `gpt-4o`
- `analysisAgent`: `gpt-4o`
- `imageGenerationModel`: `gemini-2.5-flash-image`

---

## 📜 Kırılma Geçmişi (kısa)

| Tarih | Sorun | Sebep | Çözüm |
|---|---|---|---|
| 2026-05-01 | UI'dan lead sorguları "yok" diyordu | Firestore `serverUrl` eski Cloud Run URL'sine bakıyordu | URL güncellendi (us-central1) |
| 2026-05-01 | Yeni Cloud Run servisi UI'dan erişilemiyordu | `--no-allow-unauthenticated` mode | `allUsers/run.invoker` eklendi |
| 2026-05-01 | Marketing agent fake-success | Firestore `marketingModel: gpt-5` (yok) | gpt-4o yapıldı |
| 2026-05-02 | Image gen 403 leak | Google AI key public expose, Google iptal etti | Yeni key (...bx08) Cloud Run env |
| 2026-05-02 | Sync butonu sayfayı yeniliyordu | `business-details-tab.tsx:192` reload() | Local state güncelleme (PR #5) |
| 2026-05-02 | MindID Instagram post fail | `late_profile_id` yanlış (boş profile) | Doğru profile ID (`69f4d7e7...`) |
| 2026-05-02 | "Hesap senkronize ama 0 hesap" | Zernio profile'da Instagram bağlı değildi | Zernio dashboard'dan @mindid.ai bağlandı |
| 2026-05-02 | Carousel/image content policy fail | Gerçek tarihi kişi (Frida Kahlo) photorealistic | `_extract_images` fix (net hata mesajı) |
| 2026-05-04 | UI "Bağlantı yok" + Image 123ms fail | Tarayıcı cache, eski thread state | Hard refresh çözdü |

---

## 🔗 Önemli URL/ID'ler

| Servis | Değer |
|---|---|
| Cloud Run URL | `https://agents-sdk-api-704233028546.us-central1.run.app` |
| GCP project | `instagram-post-bot-471518` (Cloud Run) |
| Firebase project | `mindid-75079` (Firestore + Storage) |
| Production frontend | `https://mindid.netlify.app` |
| MindID business_id (Firestore) | `vPoHKXpvGqdMQzrjN4i4` |
| Slowdays business_id | `ytS8ENQfrGNQ2rdHvei9` |
| MindID Zernio profile_id | `69f4d7e77e906597eb4ebf54` |

---

**Son güncelleme:** 2026-05-04
**Bu dosyayı düzenleyen:** Claude (session: 2026-05-04 öğleden sonra)
