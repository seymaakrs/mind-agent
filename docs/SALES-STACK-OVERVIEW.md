# Sales Stack — Mimari Özet (Cross-Repo)

Bu doküman ADIM 3'te tamamlanan üç PR'ın birleşik mimari haritasıdır. Sales motoru `customer_agent` (n8n) tarafından beslenir, `mind-agent` (Python/FastAPI) tarafından yönetilir, `mind-id` (Next.js/Vercel) tarafından gözlemlenir.

> **Bağımlı PR'lar:**
> * mind-agent **PR #24** — Sales Manager QA + 5 yeni tool kategorisi + REST API (`/sales/*`)
> * mind-agent **PR #27** — Faz 2 birim katmanı (Avcılık / CX / Kalite, 9 yazma tool)
> * mind-id **PR #13** — Portal Sales sekmesi + canlı agent durumları + business preview card
> * mind-agent **PR #34** — Late→Zernio publisher cutover (Sales'ten bağımsız ama paralel ilerliyor)

---

## Topoloji

```
                    ┌─────────────────────────────────────┐
                    │   mind-id (Next.js, Vercel)         │
                    │   Portal — Sales sekmesi (PR #13)   │
                    │   • 4 metrik kart                   │
                    │   • Funnel bar chart                │
                    │   • Outreach pause badge            │
                    │   • Canlı agent canvas              │
                    └──────────────┬──────────────────────┘
                                   │ HTTPS (Bearer auth)
                                   │ SALES_API_TOKEN env
                                   ▼
                    ┌─────────────────────────────────────┐
                    │   /api/sales/[...path]/route.ts     │
                    │   Server-side proxy (token tutucu)  │
                    └──────────────┬──────────────────────┘
                                   │ Authorization: Bearer ${SALES_API_TOKEN}
                                   ▼
       ┌───────────────────────────────────────────────────────────┐
       │   mind-agent (Python/FastAPI, Cloud Run agents-sdk-api)   │
       │                                                           │
       │  ┌─────────────────────────────────────────────────────┐  │
       │  │  /sales/* REST router (PR #24 sales_api.py)         │  │
       │  │  • leads/count      → _count_leads_impl             │  │
       │  │  • leads/funnel     → _lead_funnel_impl             │  │
       │  │  • outreach/status  → _outreach_status_impl         │  │
       │  │  • outreach/health  → _outreach_health_impl         │  │
       │  └─────────────────────────────────────────────────────┘  │
       │                                                           │
       │  ┌─────────────────────────────────────────────────────┐  │
       │  │  Sales Director Agent (LLM, gpt-4o)                 │  │
       │  │  • get_management_tools() = union of:               │  │
       │  │      - get_outreach_unit_tools()    (PR #27)        │  │
       │  │      - get_cx_unit_tools()          (PR #27)        │  │
       │  │      - get_quality_unit_tools()     (PR #27)        │  │
       │  │      - get_lead_management_tools()  (PR #24)        │  │
       │  │  • Memory: sales_memory subcollection (PR #24)      │  │
       │  └─────────────────────────────────────────────────────┘  │
       └──────────────┬──────────────────┬─────────────────────────┘
                      │                  │
                      ▼                  ▼
       ┌──────────────────────┐  ┌──────────────────────────┐
       │  NocoDB Leadler +    │  │  Firestore               │
       │  Etkilesimler +      │  │  businesses/{id}/        │
       │  system_settings     │  │  └── sales_memory/       │
       │  (mindid-nocodb VM)  │  │      ├── decisions/      │
       │                      │  │      ├── preferences/    │
       │                      │  │      ├── learnings/      │
       │                      │  │      └── contacts/       │
       └──────────────────────┘  └──────────────────────────┘
                      ▲
                      │ webhook + n8n write
                      │
       ┌──────────────────────────────────────────┐
       │  customer_agent (n8n workflows)          │
       │  • Lead Toplama (webhook)                │
       │  • Outreach Agent (Cloud Run job)        │
       │  • Auto-reply Agent (Cloud Run job)      │
       │  • Guardian (Bekçi, Cloud Run job)       │
       │  • Takip/İtiraz/Upsell/Referans          │
       └──────────────────────────────────────────┘
```

---

## Endpoint contract matrix

Backend `_*_impl` dönüşleri ile portal `sales-tab.tsx` tip tanımları cross-verify edildi (ADIM 3 hardening). Aşağıdaki shape'ler **donduruldu**:

| Endpoint | Required keys | Optional | Snapshot |
|---|---|---|---|
| `GET /sales/leads/count` | `success`, `count` | `summary_tr` | `tests/test_sales_api_contract.py` |
| `GET /sales/leads/funnel` | `success`, `data[].asama`, `data[].count` | `total`, `type`, `schema`, `summary_tr` | aynı |
| `GET /sales/outreach/status` | `success`, `sent_today`, `daily_limit`, `remaining` | `percent_used`, `sent_last_hour`, `summary_tr` | aynı |
| `GET /sales/outreach/health` | `success`, `paused`, `active` | `configured`, `reason`, `paused_at`, `summary_tr` | aynı |

**Drift kuralı:** İsim değişikliği yapılacaksa **mind-agent + mind-id aynı anda merge.** Tek taraflı rename = silent UI bozulması.

---

## Auth zinciri

```
SALES_API_TOKEN (32-byte hex secret)
├── Secret Manager: gcloud secrets create sales-api-token
├── mind-agent Cloud Run env binding: --update-secrets=SALES_API_TOKEN=sales-api-token:latest
└── mind-id Vercel env: vercel env add SALES_API_TOKEN (production + preview + development)
```

Rotation prosedürü: `docs/SALES-API-DEPLOY-RUNBOOK.md` (mind-agent).

---

## Merge sırası ve kabul kriterleri

| # | PR | Önkoşul | Kabul kriteri |
|---|---|---|---|
| 1 | mind-agent **#24** | yok | CI yeşil + `test_sales_api_contract.py` 4 endpoint snapshot |
| 2 | mind-agent **#27** | #24 main'de | `./scripts/rebase_pr27_onto_pr24.sh` ile rebase + CI yeşil |
| 3 | mind-agent Cloud Run deploy | #24 + #27 main'de | `SALES_API_TOKEN` Secret Manager + env binding aktif, smoke checklist (`SALES-API-DEPLOY-RUNBOOK.md`) yeşil |
| 4 | mind-id **#13** | mind-agent canlı | `PORTAL-SALES-E2E.md` Adım 1-7 yeşil, browser DevTools token leak yok |
| 5 | mind-agent **#34** | bağımsız (paralel ilerleyebilir) | `parity_check.py --since=24h` 0 divergence |

### Genel rollback
1. mind-id: Vercel previous deployment'a geç (1 dakika)
2. mind-agent: `gcloud run services update-traffic agents-sdk-api --region=us-central1 --to-revisions=<previous>=100` (30 saniye)
3. Hata sebebini araştır, fix-forward commit

---

## Hardening katmanları (ADIM 3 özeti)

| # | Katman | Test/Doc | Repo |
|---|---|---|---|
| H-1 | REST API response shape snapshot | `tests/test_sales_api_contract.py` | mind-agent |
| H-2 | Manager action input validation | `tests/test_manager_actions_validation.py` | mind-agent |
| H-3 | Sales memory idempotency | `tests/test_memory_tools_idempotency.py` | mind-agent |
| H-4 | Deploy + rotation runbook | `docs/SALES-API-DEPLOY-RUNBOOK.md` | mind-agent |
| H-5 | Unit tools input validation | `tests/test_unit_tools_input_validation.py` | mind-agent |
| H-6 | Factory backward-compat | `tests/test_factory_backward_compat.py` | mind-agent |
| H-7 | Rebase helper | `scripts/rebase_pr27_onto_pr24.sh` | mind-agent |
| H-8 | Token leak audit (statik) | `docs/PORTAL-SALES-E2E.md` §H-8 | mind-id |
| H-9 | UI shape audit (statik) | `docs/PORTAL-SALES-E2E.md` §H-9 | mind-id |
| H-10 | Manuel E2E smoke checklist | `docs/PORTAL-SALES-E2E.md` §H-10 | mind-id |
| H-11 | Cross-stack mimari özet | `docs/SALES-STACK-OVERVIEW.md` | mind-agent (bu doküman) |

---

## Bilinen sınırlar ve gelecek iş

* **mind-id'de unit test framework yok.** H-8/H-9 statik audit; H-10 manuel. Vitest setup önerisi `PORTAL-SALES-E2E.md` "Future work" bölümünde — ayrı PR olarak girebilir.
* **DB-level idempotency.** Memory `set_document(merge=True)` Firestore garantisi; ek SQL constraint yok (Firestore = NoSQL).
* **Trace_id propagation eksik.** mind-id → mind-agent → NocoDB hattında end-to-end correlation yok. ADIM 4 kapsamı.
* **Observability.** Cloud Monitoring SLO + alert (Cloud Run latency p95, `/sales/*` error rate) ADIM 4'te eklenecek.
* **Prompt versioning.** `instructions/sales/manager.py` versiyon sabiti yok; A/B fallback yok. Sales Director prompt iteration sıklaşınca eklenir.

---

## İlgili dokümanlar

* `docs/SALES-API-DEPLOY-RUNBOOK.md` — token üretimi + Secret Manager + Cloud Run + Vercel + rotation (mind-agent)
* `docs/ZERNIO-CUTOVER-RUNBOOK.md` — PR #34 Late→Zernio cutover (mind-agent, paralel)
* mind-id `docs/PORTAL-SALES-E2E.md` — portal E2E runbook + statik audit
* `customer_agent/AGENT-MIMARISI-MASTER.md` — 6 sales agent master mimari (gelecek genişleme)
