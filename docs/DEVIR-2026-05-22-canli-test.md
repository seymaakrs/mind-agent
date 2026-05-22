# DEVİR NOTU — 2026-05-22 — Canlı Test Setup Sprint

## 🎯 Sprint Hedefi
Tüm eksik API anahtarlarını toplayıp mind-id → mind-agent → NocoDB/Zernio/Firebase zincirini canlıya almak.

## ✅ Sonuç
**%95 tamamlandı.** Tek blocker: OpenAI API key geçersiz, kullanıcıdan yeni key bekleniyor.

---

## 📍 Mevcut Durum (Bir Sonraki Session İçin)

### Canlı Servisler
- **mind-agent Cloud Run:** `https://agents-sdk-api-704233028546.us-central1.run.app`
  - Revision: `agents-sdk-api-00003-r99` (v1.23.0)
  - `/health` → 200 OK
  - `/capabilities` → çalışıyor
  - `/task` → çalışıyor ama OpenAI 401 alıyor (key sorunu)
- **mind-id Vercel preview:** `https://mind-wscdmowoc-seymaakrs-slowdays-web.vercel.app`
  - Login + işletme seçim + chat UI çalışıyor
  - Orkestratör'e ulaşıyor ("Bağlı", "Düşünüyor" çıkıyor)
  - OpenAI 401'de takılıyor
- **NocoDB:** `http://34.26.138.196` (3 tablo live)
- **Firestore rules:** authenticated tam yetkili (gevşetilmiş)
- **Firestore settings/app_settings:** `serverUrl` + `testServerUrl` Cloud Run URL'inde

### Repo Durumu (mind-agent, mind-id)
- Branch: `claude/vibrant-brown-qENng` (3 repo için)
- mind-agent son commit: `2c95d95` fix(deploy): port 8000
- mind-id son commit: `25b6850` fix(firestore-rules)
- mind-id Vercel build çıkışı: ✓ Ready

---

## 🔴 BLOCKER (Açılır açılmaz yap)

### OpenAI API Key Yenileme
Mevcut key (`sk-proj-...CkUA`, length=164) Cloud Run'a doğru iletildi ama OpenAI 401 dönüyor. Sebep: revoke/rotate veya project silimi.

**Aksiyon:**
1. Kullanıcıdan yeni OpenAI key al
2. `gcloud run services update agents-sdk-api --project=instagram-post-bot-471518 --region=us-central1 --update-env-vars=OPENAI_API_KEY=<YENI>`
3. mind-agent `.env`'i de güncelle (commit'le, repo tracked)
4. Smoke test: Vercel preview URL'de "kac sicak lead var" yaz

---

## 📋 Kalan İşler (öncelik sırası)

### Hemen (blocker sonrası)
1. **E2E akış testi**
   - "kac sicak lead var" → NocoDB'den dönen sayı
   - "son 3 lead listele" → gerçek data
   - "modern banner görseli oluştur" → Gemini image
   - "30 saniyelik tanıtım videosu" → Veo 3.1
2. **Zernio panel webhook URL set**
   - URL: `https://agents-sdk-api-704233028546.us-central1.run.app/zernio/webhook`
   - Secret: `f9904ec1afc8cdd8f87b2c288df5761b50819714ea5895ba279128f11ed34a44`
3. **mind-id production deploy:** `vercel --prod` (smoke test bitince)

### Güvenlik Borçları (canlı test sonrası, atomik bir PR)
4. NocoDB `claude-setup` token revoke
5. NOCODB_API_TOKEN → GCP Secret Manager
6. ZERNIO_API_KEY → Secret Manager + Zernio panel'den rotate (chat'te yapışmış)
7. OpenAI yeni key → Secret Manager + rotate
8. NocoDB HTTPS (Cloud LB veya Caddy reverse proxy) + firewall 0.0.0.0/0 → VPC connector
9. Firestore rules sertleştirme: `match /{document=**}` write açık → admin SDK proxy veya per-collection ownership

### Bekleyen
10. customer_agent (n8n) entegrasyonu — ayrı sprint
11. mind-id production URL Firestore `serverUrl`'e bağlama (`mind-id-gray.vercel.app`)

---

## 🔑 Değer Sözlüğü

```
mind-agent Cloud Run:  https://agents-sdk-api-704233028546.us-central1.run.app
mind-id Vercel prev:   https://mind-wscdmowoc-seymaakrs-slowdays-web.vercel.app
mind-id Vercel prod:   https://mind-id-gray.vercel.app
NocoDB:                http://34.26.138.196

GCP deploy project:    instagram-post-bot-471518   (Cloud Run, Vertex)
Firebase project:      mindid-75079                (Auth, Firestore, Storage)
Artifact Registry:     us-central1-docker.pkg.dev/instagram-post-bot-471518/agents-sdk
Compute SA:            704233028546-compute@developer.gserviceaccount.com
Firebase admin SA:     firebase-adminsdk-fbsvc@mindid-75079.iam.gserviceaccount.com

NocoDB tables:
  Leadler         m5lcgc5ifeqh38h
  Etkilesimler    mx3kbw2vhwimxjf  (notifications da buraya, tur='bildirim')
  system_settings mzpphfqirl8njoe
  workspace       wgh5kblj
  base            ps9dj2fqrh823av

Zernio:
  WA_ACCOUNT_ID:    69ecc2273a63baf2053dfc21
  WEBHOOK_SECRET:   f9904ec1afc8cdd8f87b2c288df5761b50819714ea5895ba279128f11ed34a44
  Base URL:         https://api.zernio.com/v1

Branch (3 repo):  claude/vibrant-brown-qENng
```

---

## 🛠 Bu Sprint'te Üretilen Dosyalar

| Dosya | Repo | Amaç |
|---|---|---|
| `scripts/deploy_v1_23_0.sh` | mind-agent | `.env` → YAML otomatik, Cloud Run deploy + Secret Manager mount |
| `.env` (Zernio + NocoDB) | mind-agent | Live env'ler |
| `firestore.rules` (gevşetildi) | mind-id | Authenticated user için write açıldı |
| `.env.local` | mind-id | Firebase client + admin config |

## 🚧 Bu Sprint'te Karşılaşılan Tuzaklar (gelecekte tekrar etmemek için)

1. **Cloud Run aynı dizine birden fazla secret mount edemiyor**
   - `/secrets/firebase.json` + `/secrets/gcp.json` ❌
   - `/secrets/firebase/key.json` + `/secrets/gcp/key.json` ✅
2. **Cloud Run default port 8080, uvicorn 8000** — `--port=8000` zorunlu, yoksa container "ready" görünür ama health check fail
3. **Service account `secretAccessor` rolü** — yeni servis için secret mount öncesi vermek gerekiyor
4. **Cloud Shell preview proxy POST + NDJSON streaming'i koparıyor** — yerel test için Vercel preview deploy gerekli
5. **mind-id dev mode `testServerUrl` öncelikli** — sadece `serverUrl` yetmez, ikisini de set et
6. **firestore.rules `write: false` global** — UI 30+ client-side write yapıyor, rules ile uyumsuzdu, gevşetildi (borç olarak sertleştirme planlandı)
7. **OpenAI key length 164 char** — `.env`'den YAML'a transit'te bozulma yok, key OpenAI tarafında geçersiz

---

## 📞 Kullanıcı (Seyma) Notları

- Kurucu, kod bilmiyor, sade dil tercih ediyor
- Karar sorularında A/B seçenek sunulmalı
- Bu sprint'te yapıştırılan secret'lar (NOCODB token, ZERNIO key, OpenAI key) **screen recording'e düşmüş** — rotate borç olarak işaretli
- "Ultra mühendislik" + "step by step" tercihi vardı
- Cloud Shell'i aktif kullanıyor (`seymaakrs@cs-491899653936-default`)

---

**Devir alacak Claude'a:** Önce OpenAI key gelir, `gcloud run services update` ile push'la, Vercel preview URL'de "kac sicak lead var" test et. Yanıt gelirse zafer. Sonra güvenlik borçlarına geç.
