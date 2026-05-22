#!/usr/bin/env bash
# mind-agent Cloud Run deploy — canlı test (2026-05-22)
# Tüm env'ler .env dosyasından okunur ve env-vars-file olarak Cloud Run'a gönderilir.
# Credentials (firebase, gcp) Secret Manager'dan mount edilir.
#
# Kullanım (Cloud Shell, mind-agent dizininde):
#   bash scripts/deploy_v1_23_0.sh
#
# Önkoşul: .env'de şunlar olmalı (yoksa script ekleyebilir):
#   NOCODB_*, ZERNIO_*, OPENAI_API_KEY, vb.

set -euo pipefail

PROJECT_ID="instagram-post-bot-471518"
REGION="us-central1"
SERVICE="agents-sdk-api"
REGISTRY="us-central1-docker.pkg.dev/${PROJECT_ID}/agents-sdk"
VERSION="v1.23.0-$(date +%Y%m%d-%H%M)"
IMAGE="${REGISTRY}/${SERVICE}:${VERSION}"
ENV_FILE="/tmp/agents-sdk-env-${VERSION}.yaml"

if [ ! -f .env ]; then
  echo "HATA: .env yok. mind-agent dizininde çalıştır." >&2
  exit 1
fi

# Cloud Run'da kullanılmaması gereken local-only env'ler
SKIP_VARS="FIREBASE_CREDENTIALS_FILE GOOGLE_APPLICATION_CREDENTIALS GOOGLE_SERVICE_ACCOUNT_FILE NGROK_AUTHTOKEN DRY_RUN"

echo "==> [1/6] .env -> ${ENV_FILE} (YAML)"
python3 <<PYEOF
import os, re, yaml
skip = set("${SKIP_VARS}".split())
out = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k in skip or not k:
            continue
        out[k] = v
# Credential paths (secret mount'tan):
out["FIREBASE_CREDENTIALS_FILE"] = "/secrets/firebase/key.json"
out["GOOGLE_APPLICATION_CREDENTIALS"] = "/secrets/gcp/key.json"
out["GOOGLE_SERVICE_ACCOUNT_FILE"] = "/secrets/gcp/key.json"
out["DRY_RUN"] = "false"
with open("${ENV_FILE}", "w") as f:
    yaml.safe_dump(out, f, default_style='"')
print(f"  {len(out)} env yazıldı")
PYEOF

echo "==> [2/6] Cloud Build (image: ${IMAGE})"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE}" \
  --timeout=20m \
  .

echo "==> [3/6] Cloud Run deploy"
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --allow-unauthenticated \
  --env-vars-file="${ENV_FILE}" \
  --update-secrets="/secrets/firebase/key.json=firebase-credentials:latest,/secrets/gcp/key.json=gcp-credentials:latest" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --max-instances=10

echo "==> [4/6] Servis URL"
URL=$(gcloud run services describe "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")
echo "URL: ${URL}"

echo "==> [5/6] /health"
curl -sS "${URL}/health" | python3 -m json.tool || echo "health fail"

echo "==> [6/6] /capabilities (kısa)"
curl -sS "${URL}/capabilities" | python3 -m json.tool | head -40

echo ""
echo "✅ Deploy tamam. URL: ${URL}"
echo ""
echo "Sonraki adımlar:"
echo "  1. Zernio panel webhook URL'i set: ${URL}/zernio/webhook"
echo "     Secret (HMAC): f9904ec1afc8cdd8f87b2c288df5761b50819714ea5895ba279128f11ed34a44"
echo "  2. mind-id Firestore settings/app_settings.serverUrl = ${URL}"
