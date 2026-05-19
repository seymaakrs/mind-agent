#!/usr/bin/env bash
# v1.21.0 Cloud Run deploy — Sales Analyst (PR #9)
#
# Cloud Shell'de calistir:
#   bash scripts/deploy_v1_21_0.sh
#
# Onceki revision'a rollback gerekirse en alttaki yorumdaki komut.

set -euo pipefail

PROJECT_ID="instagram-post-bot-471518"
REGION="us-central1"
SERVICE="agents-sdk-api"
REGISTRY="us-central1-docker.pkg.dev/${PROJECT_ID}/agents-sdk"
VERSION="v1.21.0"
IMAGE="${REGISTRY}/${SERVICE}:${VERSION}"
BRANCH="claude/add-hot-leads-count-LJNi7"

echo "==> [1/5] Branch ${BRANCH} guncel mi"
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull origin "${BRANCH}"

echo "==> [2/5] Cloud Build ile image"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE}" \
  --timeout=20m \
  .

echo "==> [3/5] Cloud Run deploy"
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --allow-unauthenticated

echo "==> [4/5] Yeni revision URL'i"
gcloud run services describe "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)"

echo "==> [5/5] Smoke test (sales_analyst)"
URL=$(gcloud run services describe "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")
echo "Test eden istek:"
echo "curl -sS -X POST ${URL}/task -H 'Content-Type: application/json' -d '{\"task\":\"kac sicak lead var\",\"business_id\":\"YOUR_BUSINESS_ID\",\"task_id\":\"smoke-v1210\"}'"

echo ""
echo "OK. Eger smoke test yanlissa rollback:"
echo "  gcloud run services update-traffic ${SERVICE} --project=${PROJECT_ID} --region=${REGION} --to-revisions=agents-sdk-api-00009-667=100"
