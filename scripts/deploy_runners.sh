#!/bin/bash
# scripts/deploy_runners.sh — 5 otonom lobu Cloud Run Job + Scheduler olarak kurar.
#
# Loblar: Bekci, Avci, Takipci, DM Yanitlayici, Pazarlamaci Dispatcher.
#
# ÖN KOŞUL:
# - Cloud Run servisi (agents-sdk-api) zaten deploy edilmiş olmalı
# - Aynı container image kullanılır (yeniden build yok)
# - gcloud CLI kurulu + yetkili olmalı
#
# KULLANIM:
#   chmod +x scripts/deploy_runners.sh
#   ./scripts/deploy_runners.sh
#
# Komut interactive — her adım için onay sorar. İlk çalıştırma 5-10 dk sürer.

set -euo pipefail

PROJECT_ID="instagram-post-bot-471518"
REGION="us-central1"
SERVICE_NAME="agents-sdk-api"

echo "═══════════════════════════════════════════════════════════════"
echo "  MIND-AGENT — Otonom Lob Cloud Run Jobs Kurulumu"
echo "═══════════════════════════════════════════════════════════════"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo ""

# Servis image'ını al
echo "→ Mevcut servis image'ı tespit ediliyor..."
IMAGE=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(spec.template.spec.containers[0].image)')

if [[ -z "$IMAGE" ]]; then
  echo "✗ HATA: $SERVICE_NAME servisinin image'ı bulunamadı."
  echo "  Önce Cloud Run servisini deploy et."
  exit 1
fi
echo "  ✓ Image: $IMAGE"
echo ""

# Cloud Run servisinin env var'larını al — job'larda aynısını kullanacağız
echo "→ Servisin env var'ları çekiliyor..."
ENV_VARS=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(spec.template.spec.containers[0].env[].name)' | tr '\n' ',' | sed 's/,$//')
echo "  ✓ Env var sayısı: $(echo "$ENV_VARS" | tr ',' '\n' | wc -l)"
echo ""
echo "⚠️  Bu script env değerlerini KOPYALAMAZ (güvenlik). Job'lar create edildikten sonra"
echo "    Cloud Run UI'den her job'a env var'ları manuel ekleyeceksin. Bkz. docs/RUNNERS_DEPLOY.md"
echo ""

read -p "Devam etmek için ENTER (iptal için Ctrl+C)..." _

# ─────────────────────────────────────────────────────────────────
# 1. CLOUD RUN JOBS — 5 lob için
# ─────────────────────────────────────────────────────────────────

create_job() {
  local job_name=$1
  local module=$2
  local description=$3
  local timeout=${4:-600}

  echo "→ Job oluşturuluyor: $job_name ($description)"

  if gcloud run jobs describe "$job_name" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ⚠ Job zaten var, güncelleniyor..."
    gcloud run jobs update "$job_name" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --image="$IMAGE" \
      --command="python" \
      --args="-m,$module" \
      --set-env-vars="RUN_ONCE=true" \
      --max-retries=1 \
      --task-timeout="$timeout" \
      --memory=512Mi \
      --cpu=1
  else
    gcloud run jobs create "$job_name" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --image="$IMAGE" \
      --command="python" \
      --args="-m,$module" \
      --set-env-vars="RUN_ONCE=true" \
      --max-retries=1 \
      --task-timeout="$timeout" \
      --memory=512Mi \
      --cpu=1
  fi
  echo "  ✓ $job_name hazır"
}

create_job "guardian-tick" "src.agents.guardian.runner" "Bekçi — kampanya sağlık monitörü" 600
create_job "outreach-tick" "src.agents.outreach.runner" "Avcı — soğuk outreach" 600
create_job "followup-tick" "src.agents.followup.runner" "Takipçi — geç kalmış lead'lere takip" 600
create_job "auto-reply-tick" "src.agents.auto_reply.runner" "DM Yanıtlayıcı — gelen mesajlara cevap" 600
# Pazarlamaci dispatcher: orchestrator + LLM + image/video gen alabilir,
# daha uzun timeout gerekli (3000sn = 50dk).
create_job "marketing-tick" "src.agents.marketing.runner" "Pazarlamacı — planlanan postları tetikler" 3000

echo ""
echo "✓ 5 Cloud Run Job oluşturuldu/güncellendi."
echo ""

# ─────────────────────────────────────────────────────────────────
# 2. CLOUD SCHEDULER — Her job için cron tetik
# ─────────────────────────────────────────────────────────────────

# Service account — Cloud Scheduler Cloud Run Job'ı invoke etmek için gerekli
SCHEDULER_SA="cloud-scheduler-runner@${PROJECT_ID}.iam.gserviceaccount.com"

echo "→ Service Account: $SCHEDULER_SA"
echo "  Eğer yoksa oluştur ve gerekli IAM rolünü ver:"
echo ""
cat <<EOF
  gcloud iam service-accounts create cloud-scheduler-runner \\
    --display-name="Cloud Scheduler -> Cloud Run Jobs invoker" \\
    --project=$PROJECT_ID

  gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member="serviceAccount:$SCHEDULER_SA" \\
    --role="roles/run.invoker"

  gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member="serviceAccount:$SCHEDULER_SA" \\
    --role="roles/cloudscheduler.jobRunner"
EOF
echo ""
read -p "Service Account hazır mı? (devam için ENTER)..." _

create_scheduler() {
  local schedule_name=$1
  local job_name=$2
  local cron=$3
  local description=$4

  local job_uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${job_name}:run"

  echo "→ Scheduler oluşturuluyor: $schedule_name ($description) — cron: $cron"

  if gcloud scheduler jobs describe "$schedule_name" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ⚠ Scheduler zaten var, güncelleniyor..."
    gcloud scheduler jobs update http "$schedule_name" \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --schedule="$cron" \
      --uri="$job_uri" \
      --http-method=POST \
      --oauth-service-account-email="$SCHEDULER_SA" \
      --time-zone="Europe/Istanbul"
  else
    gcloud scheduler jobs create http "$schedule_name" \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --schedule="$cron" \
      --uri="$job_uri" \
      --http-method=POST \
      --oauth-service-account-email="$SCHEDULER_SA" \
      --time-zone="Europe/Istanbul"
  fi
  echo "  ✓ $schedule_name hazır"
}

# Bekçi: her 30 dakikada sağlık check
create_scheduler "guardian-every-30min" "guardian-tick" "*/30 * * * *" "Bekçi her 30 dk"

# Outreach: çalışma saatleri 09:00-18:00, her 10 dk
create_scheduler "outreach-every-10min" "outreach-tick" "*/10 9-18 * * 1-5" "Avcı iş günleri 09-18 arası 10 dk'da bir"

# Followup: günde 2 kez (10:00, 14:00)
create_scheduler "followup-2x-daily" "followup-tick" "0 10,14 * * 1-5" "Takipçi günde 2 kez iş günleri"

# Auto-reply: her 5 dk (24/7, çünkü müşteri her saat yazabilir)
create_scheduler "auto-reply-every-5min" "auto-reply-tick" "*/5 * * * *" "DM Yanıtlayıcı her 5 dk"

# Marketing dispatcher: sabah 08:00 (Europe/Istanbul) — gunluk plan tetikleyici
create_scheduler "marketing-daily-8am" "marketing-tick" "0 8 * * *" "Pazarlamacı dispatcher her sabah 08:00"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ TAMAM — 5 Job + 5 Scheduler kuruldu"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "SONRAKİ ADIMLAR:"
echo "  1. Her job için env var'ları Cloud Run UI'den ekle"
echo "     (NOCODB_API_TOKEN, ZERNIO_API_KEY, FIREBASE_*, OPENAI_API_KEY, vs.)"
echo "     Detay: docs/RUNNERS_DEPLOY.md"
echo ""
echo "  2. Manuel tetik ile test et:"
echo "     gcloud run jobs execute guardian-tick --region=$REGION --project=$PROJECT_ID --wait"
echo ""
echo "  3. Logları kontrol et:"
echo "     gcloud run jobs executions list --job=guardian-tick --region=$REGION --project=$PROJECT_ID"
echo ""
echo "Sched listesi: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo "Jobs listesi:  https://console.cloud.google.com/run/jobs?project=$PROJECT_ID"
