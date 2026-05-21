# OPERATIONS — Hassas Noktalar & Geri Dönüş

> **Yeni Claude session'ı buraya bakacak. Önce bu dosyayı oku.**
> Bu dosya 3 repo (`mind-id`, `mind-agent`, `customer_agent`) için ortak operasyon kılavuzudur.

---

## ✅ Stable Geri Dönüş Noktaları

| Tag | Tarih | Durum | Geri dönüş |
|---|---|---|---|
| `stable-2026-05-04` | 2026-05-04 | Image gen + lead query + Late posting **çalışıyor** | `git checkout stable-2026-05-04` |

### Cloud Run revision karşılığı
- `agents-sdk-api-00034-vgb` (v1.22.6) — Zernio MCP canlı (son istikrarlı)
- `agents-sdk-api-00024-qtz` (v1.20.7) — `stable-2026-05-04` ile uyumlu
- Önceki çalışan: `agents-sdk-api-00023-df2`, `agents-sdk-api-00022-vs6`

### Hızlı rollback
```bash
gcloud run services update-traffic agents-sdk-api \
  --region=us-central1 --project=instagram-post-bot-471518 \
  --to-revisions=agents-sdk-api-00034-vgb=100
```

---

## 📋 BEKLEYEN İŞLER

### 1. Branch protection ✅
- [x] mind-id main: PR + 1 approval (2026-05-21)
- [x] mind-agent main: PR + 1 approval (2026-05-21)
- [x] customer_agent main: PR + 1 approval (2026-05-21)

### 2. Güvenlik temizliği
- [x] `mind-agent/serviceAccount.json` git'ten silindi (2026-05-21)
- [x] `mind-agent/gcp-service-account.json` git'ten silindi (2026-05-21)
- [ ] Eski Google AI key (`AIzaSyDGdNaR...kpM`) AI Studio'dan silindi mi? Doğrula
- [ ] Yeni Google AI key (`AIzaSyAf...bx08`) rotate edilmeli
- [ ] Late/Zernio key (`sk_518334...`) rotate öner
- [ ] NocoDB `claude-setup` token revoke
- [ ] n8n `claude-status-2026-05-01` token revoke
- [ ] NOCODB_API_TOKEN (Cloud Run env, plain text) → Secret Manager'a taşı
- [ ] OPENAI/GOOGLE/LATE/SERPER/KLING anahtarları → Secret Manager

### 3. gitleaks pre-commit ✅
- [x] 3 repoya kuruldu (2026-05-21)

### 4. Firestore Security Rules
- [ ] `settings/app_settings` belgesi sadece super_admin yazabilsin

### 5. Cloud Run Jobs deploy (PR #23 ile gelen)
- [ ] `scripts/deploy_runners.sh` çalıştırılacak
- [ ] 4 job için Cloud Run env var'ları eklenecek
- [ ] `gcloud run jobs execute guardian-tick --wait` test

### 6. Meta Lead Ads webhook
- [ ] Facebook App Review onayı bekleniyor

### 7. Sales Manager Faz 2
- [ ] PR #24 main'e rebase + conflict resolution + merge (8 commit, REST API + müdür v2 25 tool + peer wiring)

### 8. Orchestrator model upgrade
- [ ] gpt-4.1-mini routing'de zayıf, gelecekte gpt-4o öneri

---

## 🚨 ASLA YAPMA Listesi

Bu hatalar **kanıtlanmış kırılma sebepleri**:

1. ❌ `marketingModel`, `analysisAgent` Firestore'a `gpt-5` yazma → **OpenAI'da gpt-5 YOK**, fake-success döner
2. ❌ `imageGenerationModel`'i `gemini-2.0-flash-image-generation` yapma → Google API'de yok, 404
3. ❌ Repo'ya `serviceAccount.json` / private key commit etme → Google otomatik iptal eder
4. ❌ Cloud Run revision'a doğrudan deploy etmeden Firestore env'i değiştir → cache uyumsuzluğu
5. ❌ Frontend (mind-id) `serverUrl` Firestore alanını silme → "Bağlantı yok"
6. ❌ Cloud Run servisini `--no-allow-unauthenticated` yapma → mind-id frontend (Vercel) erişemez
7. ❌ MindID `late_profile_id` Firestore alanını yanlış değer ile değiştir → sync `accounts: []` döner
8. ❌ `git push --force` main'e (branch protection blokluyor, deneme bile)

---

## 🛠️ Hızlı Kurtarma Komutları

### Sistem sağlık testi
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

### Beklenen değerler (2026-05-04):
- `serverUrl`: `https://agents-sdk-api-704233028546.us-central1.run.app`
- `orchestratorModel`: `gpt-4.1-mini`
- `marketingModel`: `gpt-4o`
- `analysisAgent`: `gpt-4o`
- `imageGenerationModel`: `gemini-2.5-flash-image`

---

## 🔗 Önemli URL/ID'ler

| Servis | Değer |
|---|---|
| Cloud Run URL | `https://agents-sdk-api-704233028546.us-central1.run.app` |
| GCP project | `instagram-post-bot-471518` (Cloud Run) |
| Firebase project | `mindid-75079` (Firestore + Storage) |
| Production frontend | Vercel — `mind-id-gray.vercel.app` |
| MindID business_id | `vPoHKXpvGqdMQzrjN4i4` |
| Slowdays business_id | `ytS8ENQfrGNQ2rdHvei9` |
| MindID Zernio profile_id | `69f4d7e77e906597eb4ebf54` |
| NocoDB Leadler table | `m5lcgc5ifeqh38h` |
| NocoDB Etkilesimler table | `mx3kbw2vhwimxjf` |
| NocoDB system_settings table | `mzpphfqirl8njoe` |

---

**Son güncelleme:** 2026-05-21
