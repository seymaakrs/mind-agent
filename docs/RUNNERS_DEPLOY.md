# Otonom Lob Cloud Run Job Kurulum Rehberi

Bu doküman **4 otonom lobu** (Bekçi, Avcı, Takipçi, DM Yanıtlayıcı) Cloud Run Job + Cloud Scheduler ile periyodik çalışır hale getirir.

## Mimari

```
Cloud Scheduler (cron)  ──►  Cloud Run Job  ──►  Container start
                                                      ↓
                                              python -m src.agents.X.runner
                                              (RUN_ONCE=true → tick → exit)
                                                      ↓
                                              NocoDB + Zernio yazma/okuma
                                                      ↓
                                              Container exits (kapanır)
```

**Maliyet:** ~$2-5/ay tüm 4 lob için (kullanıma göre).

## Lobların Cadansı

| Lob | Cloud Run Job adı | Scheduler cadansı | Çalışma saati |
|---|---|---|---|
| 🛡️ Bekçi (Guardian) | `guardian-tick` | Her 30 dk | 24/7 |
| 🏹 Avcı (Outreach) | `outreach-tick` | Her 10 dk | İş günleri 09-18 |
| 📞 Takipçi (Followup) | `followup-tick` | Günde 2 kez (10:00, 14:00) | İş günleri |
| 💬 DM Yanıtlayıcı (Auto-reply) | `auto-reply-tick` | Her 5 dk | 24/7 |

## Adım Adım Kurulum

### Adım 1 — Ön koşullar

1. Cloud Run Service `agents-sdk-api` deploy edilmiş olmalı
2. `gcloud` CLI bilgisayarında kurulu olmalı (veya Cloud Shell kullan)
3. Şu hesabı kontrol et: `gcloud auth list` — doğru hesapla giriş yapılmış olmalı
4. Project ID set edilmiş olmalı: `gcloud config set project instagram-post-bot-471518`

### Adım 2 — Service Account oluştur

Cloud Scheduler'in Cloud Run Job'ı tetikleyebilmesi için bir SA gerekiyor.

```bash
gcloud iam service-accounts create cloud-scheduler-runner \
  --display-name="Cloud Scheduler -> Cloud Run Jobs invoker" \
  --project=instagram-post-bot-471518

gcloud projects add-iam-policy-binding instagram-post-bot-471518 \
  --member="serviceAccount:cloud-scheduler-runner@instagram-post-bot-471518.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding instagram-post-bot-471518 \
  --member="serviceAccount:cloud-scheduler-runner@instagram-post-bot-471518.iam.gserviceaccount.com" \
  --role="roles/cloudscheduler.jobRunner"
```

### Adım 3 — Cloud Run Job + Scheduler script'ini çalıştır

```bash
chmod +x scripts/deploy_runners.sh
./scripts/deploy_runners.sh
```

Script:
- Mevcut Cloud Run Service image'ını alır (yeniden build yok)
- 4 Cloud Run Job oluşturur
- 4 Cloud Scheduler kurar
- Her adımda onay sorar

### Adım 4 — Env var'ları her job'a manuel ekle (KRİTİK)

Script env değerlerini kopyalamaz (güvenlik). Her job için Cloud Run UI'den ekle.

Her job için Cloud Run UI:
1. https://console.cloud.google.com/run/jobs?project=instagram-post-bot-471518
2. Job ismine tıkla → "Yeni revizyonu dağıt" / "Edit"
3. "Variables & Secrets" sekmesi
4. Aşağıdaki env var'ları ekle (Service'tekiyle aynı değerler):

#### Tüm joblar için gerekli env var'lar:

```
NOCODB_BASE_URL          (CRM URL)
NOCODB_API_TOKEN         (NocoDB API key)
NOCODB_LEADS_TABLE_ID    (Leadler tablosu)
NOCODB_MESSAGES_TABLE_ID (Etkilesimler tablosu)
NOCODB_SETTINGS_TABLE_ID (system_settings tablosu)  ← Bekçi için KRİTİK
ZERNIO_API_KEY           (Zernio token)
ZERNIO_BASE_URL          (default: https://api.zernio.com/v1)
ZERNIO_WA_ACCOUNT_ID     (WhatsApp account ID)
FIREBASE_CREDENTIALS_FILE  (path; ama Cloud Run'da secret olarak mount)
OPENAI_API_KEY           (auto-reply intent classifier için)
DRY_RUN=false            (production'da kesinlikle false)
```

İpucu: Service'in env var'larını listele ve aynısını her job'a yapıştır:
```bash
gcloud run services describe agents-sdk-api \
  --region=us-central1 \
  --project=instagram-post-bot-471518 \
  --format='value(spec.template.spec.containers[0].env)'
```

### Adım 5 — Manuel tetik ile test et

```bash
# Bekçi'yi test et
gcloud run jobs execute guardian-tick \
  --region=us-central1 \
  --project=instagram-post-bot-471518 \
  --wait

# Logları gör
gcloud run jobs executions list \
  --job=guardian-tick \
  --region=us-central1 \
  --project=instagram-post-bot-471518 \
  --limit=1
```

Beklenen log:
```
guardian starting: window=24h ... max_iter=1
guardian: level=GREEN action=NONE reply=X.X% engagement=Y.Y% ...
```

Diğer 3 lob için de aynısını tekrarla.

### Adım 6 — Scheduler'lar çalışıyor mu doğrula

https://console.cloud.google.com/cloudscheduler?project=instagram-post-bot-471518

4 scheduler görmelisin:
- `guardian-every-30min`
- `outreach-every-10min`
- `followup-3x-daily`
- `auto-reply-every-5min`

Her birinin sağında "Force run" butonu var — manuel tetikleyip log'lardan başarı doğrulayabilirsin.

## Sorun Giderme

### Job tetiklendi ama hata aldı
```bash
gcloud run jobs executions describe <execution-id> \
  --region=us-central1 \
  --project=instagram-post-bot-471518
```

Yaygın sorunlar:
- **NocoDB env var yok** → Adım 4'e geri dön
- **403 forbidden** → Service Account'a IAM rolleri eksik
- **Timeout** → Job task-timeout default 600sn, yetmiyorsa artır

### Scheduler tetiklenmiyor
- Cloud Scheduler Console'da scheduler'ın "Enabled" olduğundan emin ol
- Service Account adresi doğru mu kontrol et
- Cron syntax: `*/30 * * * *` → her 30 dk

### Bekçi GREEN durumda ama outreach çalışmıyor
- Outreach'in `NOCODB_LEADS_TABLE_ID` set edilmiş mi?
- Outreach'in çalışma saatleri ne? (default 09-18 Europe/Istanbul)
- DRY_RUN=true olarak mı kalmış?

## Rollback

Job'ları silmek için:
```bash
gcloud run jobs delete guardian-tick --region=us-central1 --project=instagram-post-bot-471518
gcloud run jobs delete outreach-tick --region=us-central1 --project=instagram-post-bot-471518
gcloud run jobs delete followup-tick --region=us-central1 --project=instagram-post-bot-471518
gcloud run jobs delete auto-reply-tick --region=us-central1 --project=instagram-post-bot-471518

gcloud scheduler jobs delete guardian-every-30min --location=us-central1
gcloud scheduler jobs delete outreach-every-10min --location=us-central1
gcloud scheduler jobs delete followup-3x-daily --location=us-central1
gcloud scheduler jobs delete auto-reply-every-5min --location=us-central1
```

## Sıradaki Adımlar (gelecek seans)

- **Data Collector Jobs**: Instagram insights, YouTube, GA4, GSC için Cloud Run Job + Firestore cache
- **NocoDB webhook → mind-agent event-driven**: Polling yerine real-time
- **Pazarlamacı runner**: 30 günlük plan içeriklerini saati gelince üret + at
