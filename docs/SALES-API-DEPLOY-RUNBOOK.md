# Sales REST API Deploy Runbook

PR #24 ile birlikte gelen `/sales/*` endpoint'leri portal (mind-id) tarafından LLM çağırmadan deterministik metric çekmek için kullanılır. Bu runbook deploy + token yönetimi + rotation prosedürlerini sabitler.

> İlgili kod:
> * Backend: `src/app/sales_api.py` (router) + `src/tools/sales/reporting_tools.py` (impl)
> * Frontend: `mind-id` PR #13 `app/api/sales/[...path]/route.ts` (token-tutucu proxy)
> * Auth: `SALES_API_TOKEN` env var (mind-agent ile mind-id paylaşımlı)

---

## Tek-seferlik kurulum

### 1) Token üret
```bash
SALES_API_TOKEN=$(openssl rand -hex 32)
echo "SALES_API_TOKEN=$SALES_API_TOKEN"
```

### 2) Secret Manager'a yaz (mind-agent tarafı)
```bash
echo -n "$SALES_API_TOKEN" | gcloud secrets create sales-api-token \
  --replication-policy=automatic --data-file=-

# Cloud Run servisine bağla
gcloud run services update agents-sdk-api \
  --region=us-central1 \
  --update-secrets=SALES_API_TOKEN=sales-api-token:latest
```

### 3) Vercel'e gir (mind-id tarafı)
```bash
# mind-id projesi root'unda
vercel env add SALES_API_TOKEN production
# (prompt'a aynı $SALES_API_TOKEN değerini yapıştır)
vercel env add SALES_API_TOKEN preview
vercel env add SALES_API_TOKEN development
```

mind-id `app/api/sales/[...path]/route.ts` bu env'i okur ve `Authorization: Bearer ...` header'ı olarak yukarı geçirir.

### 4) Doğrulama (deploy sonrası)
```bash
# Hayat sinyali — endpoint açık olmalı
curl -sf -H "Authorization: Bearer $SALES_API_TOKEN" \
  "$AGENT_URL/sales/leads/count" | jq .

# Yetkisiz çağrı 401 dönmeli
curl -s -o /dev/null -w '%{http_code}\n' "$AGENT_URL/sales/leads/count"
# Beklenen: 401

# Portal proxy üzerinden
curl -sf "$PORTAL_URL/api/sales/leads/count" | jq .
# Beklenen: 200 + {success, count, ...}
```

---

## Rotation (90 günde bir, veya sızıntı şüphesinde)

```bash
# 1) Yeni token üret
NEW=$(openssl rand -hex 32)

# 2) Secret Manager'a yeni version ekle
echo -n "$NEW" | gcloud secrets versions add sales-api-token --data-file=-

# 3) Cloud Run otomatik :latest okur — yeni revision deploy etmeden update
gcloud run services update agents-sdk-api \
  --region=us-central1 \
  --update-secrets=SALES_API_TOKEN=sales-api-token:latest

# 4) Vercel env güncelle
vercel env rm SALES_API_TOKEN production --yes
vercel env add SALES_API_TOKEN production
# (yeni değeri yapıştır)
vercel --prod  # yeni deployment ile env aktive olur

# 5) Eski version'ı 24 saat sonra disable et (rollback penceresi)
gcloud secrets versions disable 1 --secret=sales-api-token
```

**Rotation sırasında oluşan kısa pencere** (Cloud Run yeni token'ı okudu ama Vercel deployment henüz tamamlanmadı): portal `/api/sales/*` 401 alır, UI Sales sekmesinde "Veri yüklenemedi" gösterir. 1-2 dakikalık downtime kabul edilebilir; iş saatleri dışında yap.

---

## Endpoint contract referansı

| Endpoint | Required keys | İlgili portal komponenti |
|---|---|---|
| `GET /sales/leads/count` | `success`, `count` | `components/businesses/tabs/sales-tab.tsx` Sıcak Lead kartı |
| `GET /sales/leads/funnel` | `success`, `stages[].asama`, `stages[].count` | Funnel bar chart |
| `GET /sales/outreach/status` | `success`, `sent_today`, `remaining_capacity` | Outreach status kartı |
| `GET /sales/outreach/health` | `success`, `paused` | Pause badge (yeşil/kırmızı) |

Shape değişikliği = `tests/test_sales_api_contract.py` kırılır = mind-id PR #13 ile koordine deploy gerekir. Hiçbir endpoint shape'i tek tarafta değiştirilmez.

---

## Hata kodları

| HTTP | Anlam | Aksiyon |
|---|---|---|
| 200 | OK + `{success: true, ...}` | — |
| 401 | Token eksik / yanlış | Authorization header kontrol et |
| 502 | NocoDB/Firestore okuma hatası | `gcloud logging read` ile detayı çek, retry |
| 503 | `SALES_API_TOKEN` env yok | Cloud Run env binding'i kontrol et (`gcloud run services describe`) |

---

## Smoke checklist (her deploy sonrası)

- [ ] `curl /sales/leads/count` 200 döner ve `count` int
- [ ] `curl /sales/leads/funnel` 200 döner ve `stages` boş değil
- [ ] `curl /sales/outreach/health` 200, `paused` bool
- [ ] Token'sız çağrı 401
- [ ] Portal Sales sekmesi → 4 metrik kart dolu, console'da hata yok
- [ ] Vercel function log'unda `Authorization: Bearer` header geçtiği teyit (token değeri loglanmamalı — sadece header varlığı)

---

## İlgili dosyalar

* `src/app/sales_api.py` — router (Bearer auth + 4 endpoint)
* `src/app/api.py` — main FastAPI'a router'ı dahil eden satır
* `src/tools/sales/reporting_tools.py` — `_*_impl()` fonksiyonları
* `tests/test_sales_api_contract.py` — H-1 shape snapshot
* `mind-id` PR #13 → `app/api/sales/[...path]/route.ts`
