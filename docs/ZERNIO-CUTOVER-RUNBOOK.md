# Zernio Cutover Runbook

Üretim Late → Zernio geçişinin **deterministik, geri-alınabilir** yapılma kılavuzu. PR #34 (Faz 0–6) bu runbook'la birlikte deploy edilir.

> PR #34 Faz 6 ile Late paketini sildi. Bu nedenle "shadow mode" sadece **Faz 3 commit'inde** (`312d684`) çalıştırılır; Faz 6 (HEAD) merge edilmeden önce parity log toplanır.

---

## Önkoşullar

| Kontrol | Komut | Beklenen |
|---|---|---|
| Cloud Run service mevcut | `gcloud run services describe agents-sdk-api --region=us-central1 --format='value(status.url)'` | https URL döner |
| Zernio API key Secret Manager'da | `gcloud secrets versions access latest --secret=zernio-api-key \| wc -c` | > 20 |
| Mind-agent main branch'inde Faz 3 commit erişilebilir | `git log --oneline 312d684 -1` | "feat(publisher): shadow mode + migrate Instagram tool (Faz 3)" |

---

## Aşama 1 — Shadow Mode (Faz 3 commit'inde, 1–3 gün)

**Hedef:** Late ve Zernio aynı request'i paralel post'lar, dönüşler diff'lenir. Faz 6 merge edilmeden önce divergence yokluğunu kanıtlamak.

```bash
# 1) Faz 3 HEAD'inde build edilmiş image'ı deploy et
git checkout 312d684
docker build -t gcr.io/$PROJECT/agents-sdk-api:shadow .
docker push gcr.io/$PROJECT/agents-sdk-api:shadow

gcloud run deploy agents-sdk-api \
  --region=us-central1 \
  --image=gcr.io/$PROJECT/agents-sdk-api:shadow \
  --update-env-vars="PUBLISHER_BACKEND=late,PUBLISHER_SHADOW=true" \
  --update-secrets="LATE_API_KEY=late-api-key:latest,ZERNIO_API_KEY=zernio-api-key:latest" \
  --no-traffic \
  --tag=shadow

# 2) Trafiğin tamamını shadow revision'a yönlendirme — sadece smoke test:
gcloud run services update-traffic agents-sdk-api \
  --region=us-central1 --to-tags=shadow=10  # %10 shadow trafik
```

**Gözlem (1–3 gün):**
```bash
# Log analizini otomatize et
python3 scripts/parity_check.py --since=24h
```

Çıktı 0 divergence olmalı. Mismatch varsa Aşama 2'yi YAPMA — PR yazarına bildir.

---

## Aşama 2 — Production Cutover (PR #34 merge sonrası)

**Hedef:** Bu PR'ın HEAD revision'ını Cloud Run'a deploy et, trafiği %100'e yönlendir.

```bash
# 1) main'e merge sonrası image build
git checkout main
docker build -t gcr.io/$PROJECT/agents-sdk-api:v1.24.0 .
docker push gcr.io/$PROJECT/agents-sdk-api:v1.24.0

# 2) Yeni env: shadow & Late tamamen kapalı
gcloud run deploy agents-sdk-api \
  --region=us-central1 \
  --image=gcr.io/$PROJECT/agents-sdk-api:v1.24.0 \
  --remove-env-vars=PUBLISHER_BACKEND,PUBLISHER_SHADOW,LATE_API_KEY \
  --update-secrets="ZERNIO_API_KEY=zernio-api-key:latest" \
  --no-traffic \
  --tag=v1240

# 3) Canary: %10 → %50 → %100, her aşamada 30 dk gözlem
gcloud run services update-traffic agents-sdk-api --region=us-central1 --to-tags=v1240=10
sleep 1800 && python3 scripts/parity_check.py --since=30m --mode=zernio-only

gcloud run services update-traffic agents-sdk-api --region=us-central1 --to-tags=v1240=50
sleep 1800

gcloud run services update-traffic agents-sdk-api --region=us-central1 --to-tags=v1240=100

# 4) Eski revision'ı garbage collect (24 saat sonra)
gcloud run revisions list --service=agents-sdk-api --region=us-central1
# eski revision'ları manuel temizle
```

---

## Smoke Checklist (her aşama sonrası)

- [ ] `/durum` endpoint 200 döner: `curl -s "$URL/durum" | jq .status` → `"healthy"`
- [ ] Instagram smoke post: `python3 scripts/smoke_publish.py --platform=instagram`
- [ ] LinkedIn smoke post: `python3 scripts/smoke_publish.py --platform=linkedin`
- [ ] TikTok video smoke: `python3 scripts/smoke_publish.py --platform=tiktok`
- [ ] YouTube smoke: `python3 scripts/smoke_publish.py --platform=youtube`
- [ ] Firestore `published_at` field doluyor mu — son 5 post'a bak

---

## Rollback

Herhangi bir aşamada smoke kırmızı olursa:

```bash
# Trafiği derhal önceki stable revision'a kaydır
gcloud run services update-traffic agents-sdk-api \
  --region=us-central1 --to-revisions=agents-sdk-api-00012-gln=100

# Faz 3 shadow ise: PUBLISHER_BACKEND=late env'i geri set et
gcloud run services update agents-sdk-api \
  --region=us-central1 \
  --update-env-vars=PUBLISHER_BACKEND=late,LATE_API_KEY=... \
  --remove-env-vars=PUBLISHER_SHADOW
```

**Rollback sonrası:** PR #34'ü hold'a al, divergence root cause'unu bul, fix commit'le.

---

## Bilinen Riskler & Karşı-önlemler

| Risk | Tespit | Önlem |
|---|---|---|
| Zernio rate-limit Late'ten farklı | `parity_check.py` 429 sayısı | Backoff config'i Zernio'ya kalibre et |
| Carousel media validation farkı | smoke `--platform=instagram-carousel` 4xx | İlgili tool'da pre-validation, Zernio response'a güvenmeden |
| `published_at` format drift | Firestore `published_at` parse hatası | `tests/test_publisher_contract.py` snapshot test bunu yakalar |
| Tool layer downstream consumer kırılır | `tests/test_publisher_contract.py` C-2 testi | Shape değişirse PR CI kırılır, intentional change isteklilik PR |

---

## İlgili PR & dosyalar

- PR #34 — Faz 0–6 merge
- `tests/test_publisher_contract.py` — to_dict + tool layer shape contract
- `scripts/parity_check.py` — shadow log analiz aracı
- `src/infra/publisher/` — Late silindi, Zernio default
