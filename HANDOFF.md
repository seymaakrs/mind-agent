# MindID Multi-Agent — Session Devir Notu

**Tarih:** 2026-05-21
**Branch (3 repo):** `claude/marketing-runner-deployment-0wpKw`
**Son commit (mind-agent):** `b5bcabc` — "feat(sales-manager): A2 + B1 + C1 entegrasyonu — Müdür v2 (25 tool)"
**Test durumu:** 70/70 green

---

## 1. TAMAMLANAN — Sales Manager v2 (Batch 1)

Sales Analyst → **Sales Manager** dönüşümü tamamlandı. 25 tool, 5 yetenek grubu:

| Grup | Tool sayısı | Dosya |
|---|---|---|
| Okuma (raporlama) | 10 | `src/tools/sales/reporting_tools.py` |
| Yazma (CRM kontrol) — **TODO A** | 6 | `src/tools/sales/manager_actions.py` |
| Hafıza — **A2** | 3 | `src/tools/sales/memory_tools.py` |
| Aylık hedef + KPI — **B1** | 3 | `src/tools/sales/goals_tools.py` |
| Triage (sıcak lead) — **C1** | 2 | `src/tools/sales/triage_tools.py` |
| Marka | 1 | `fetch_brand_identity` |
| **TOPLAM** | **25** | |

### Anahtar dosyalar
- `src/agents/sales/sales_manager_agent.py` (80 satır) — factory, 25 tool wiring, `gpt-4o-mini`
- `src/agents/instructions/sales/manager.py` (213 satır) — SALES_MANAGER_INSTRUCTIONS, 7 karar prensibi, peer-via-Şef pattern, yazma aksiyonu kuralları
- `src/agents/instructions/__init__.py` — top-level `SALES_MANAGER_INSTRUCTIONS` export
- `src/agents/instructions/orchestrator.py` — `sales_analyst_tool` → `sales_manager_tool`
- `tests/test_sales_manager_wiring.py` (220 satır) — `test_total_tool_count_is_25` dahil
- `tests/test_manager_actions.py` (210 satır, 22 test)
- `tests/test_memory_tools.py` (13), `tests/test_goals_tools.py` (13), `tests/test_triage_tools.py` (8)

### Yazma tool'ları (audit log'lu, reason ≥5 char)
- `outreach_pause`, `outreach_resume`
- `lead_reassign`, `lead_priority_set`
- `auto_reply_template_update`
- `outreach_daily_limit_set`
- Audit log tablosu: `NOCODB_MANAGER_ACTIONS_TABLE_ID`

### Frontend (mind-id, PR #13 draft)
- `app/api/sales/[...path]/route.ts` — proxy, SALES_API_TOKEN server-side
- `components/businesses/tabs/sales-tab.tsx`
- `hooks/useBusinessSummary.ts`, `hooks/useOutreachHealth.ts`
- `components/mind-id-canvas/useLiveAgentStates.ts` — Firestore `active_tasks` listener (mock kaldırıldı)

---

## 2. AÇIK PR'lar (draft)
- **mind-agent PR #24** — sales manager v2
- **mind-id PR #13** — sales tab + canvas live states

---

## 3. SIRADAKİ İŞLER (öncelik sırasıyla)

### Batch 2 — paralel yapılabilir (farklı dosyalar)
- **B2: Otonom cycle** (~3h) — Cloud Run scheduler 09:00/13:00/18:00, runner script
- **B3: Kriz refleksi** (~2h) — Bekçi RED → webhook → Müdür pause, FastAPI endpoint

### Batch 3
- **D1: Upsell/Cross-sell agent** (~4h)
- **D2: Churn management** (~3h)
- **F1: Sales team performance tracking** (~4h)

### Uzun vade
- **E1: Meta Ads API write** (1 hafta + Meta onayı)
- **C2: Vector DB memory** (structured yetersiz kalırsa)

### Deploy / altyapı
- Faz 2 deploy: Vercel + Cloud Run env (`SALES_API_TOKEN`)
- NocoDB `business_id` migration (multi-tenant)
- Slowdays atomic switch (kullanıcı onayı bekleniyor)
- Langfuse v2 + LiteLLM entegrasyonu

---

## 4. MİMARİ KARARLAR (sabit)

- **NocoDB = tek SoT** (LLM uydurmaz)
- **Peer-via-Şef pattern**: Sales Manager → Reklam Uzmanı handoff'u orchestrator üzerinden (direkt çağrı yok)
- **BRAND_AWARE_PREFIX** her agent instructions başına eklenir, `fetch_brand_identity` zorunlu ilk adım
- **Audit log** her yazma için (kim/ne/ne zaman/neden), `reason ≥5 char` zorunlu
- **SALES_API_TOKEN** sadece server-side (Next.js proxy route), tarayıcıya gitmez
- **Orchestrator post tool taşımaz** — marketing/video agent'a delege
- **Branch:** her zaman `claude/marketing-runner-deployment-0wpKw` (3 repo'da da aynı)
- **Repo allowlist:** seymaakrs/{mind-id, mind-agent, customer_agent}
- **Git kuralları:** `--no-verify` YOK, amend YOK (yeni commit), main'e force-push YOK

---

## 5. YENİ SESSION'A BAŞLARKEN
1. `git status` + `git log -5` — son durumu doğrula
2. `pytest tests/ -q` — 70/70 green olduğunu teyit et
3. PR #24 ve #13 review durumunu kontrol et
4. Kullanıcıya: "Batch 2 (B2+B3 paralel) ile devam edelim mi?" diye sor — **onaysız başlama**

---

Son kullanıcı talebi: "yaptın mı" → YES, Batch 1 (A2+B1+C1) tamamen entegre + push edildi.
