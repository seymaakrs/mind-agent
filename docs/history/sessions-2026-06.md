# Session Notes — 2026-06

## Temizlik Oturumu (2026-06-01) — branch: claude/relaxed-clarke-tUchS, PR #39

Amaç: Yeni robot YAZMADAN mevcut mimariyi temizle. Mail bombardımanını durdur,
NocoDB defterini temizle, kullanılmayan Slowdays artıklarını ayır.

### Adım 1 — Mail bombardımanını DURDUR ✅ DONE (2026-06-01)

n8n'de 2 workflow DEACTIVATE edildi (silinmedi, kapatıldı — geri açılabilir):
- **Lead Toplama Agent** (`l31p16NRZeyk4eEm`) → active=false
  - Not: "Send Hot Lead Alert" ayrı workflow DEĞİL; bu workflow'un içindeki bir
    Gmail node'u. Workflow kapanınca o da ateşlenmiyor.
- **Takip Agent** eski (`nWNMQYHJzsMvMUGP`) → active=false

Karar (Beyza onayı): **Meta Lead Ads Agent** (`xblguxS49CJ4r4OF`) AKTİF bırakıldı —
gerçek Facebook reklam leadleri için. (Şu an reklam yoksa mail gelmez.)

Kalan otomatik mail kaynakları (bilinçli aktif): Meta Lead Ads, Haftalik Rapor,
Gunluk Rapor, Upsell, Referans, İtiraz, Bekci Alert.

### Adım 2 — NocoDB şema güncelle (migration) ✅ DONE (2026-06-02 APPLY edildi)

`scripts/migrate_qualifier_schema.py` yazıldı (idempotent, default DRY-RUN, `--apply` ile gerçek).
Eklenenler: Leadler → qualified(Checkbox), source(SingleSelect 8 option:
gmaps/ig/linkedin/meta_lead_ads/mindid_form/itiraz/wa_inbound/manual),
qualification_reason(LongText), qualified_by(SingleLineText), qualified_at(DateTime);
asama enum'una 'Arsiv' option.
Test: `tests/test_migrate_qualifier_schema.py` 15/15 yeşil.
APPLY edildi (2026-06-02, Cloud Shell): qualified/source/qualification_reason/
qualified_by/qualified_at eklendi; asama 'Arsiv' zaten vardı. Veri kaybı yok.
ERİŞİM NOTU: base_url artık https://db.mindidai.com.tr (Caddy reverse proxy).
Caddy panel UI'yı (/ ve /dashboard) 403 ile kapatıyor AMA /api/v2/meta/* açık.
Token panelden alınamadığı için scripts/nocodb_make_token.sh ile email+şifre →
/api/v2/auth/user/signin → /api/v1/tokens üzerinden üretildi. Migration Cloud
Shell'den koşuldu (Claude bulut oturumu host_not_allowed ile dışarı çıkamıyor).
### Adım 3 — NocoDB temizlik (tek seferlik hard-delete) ⏳
### Adım 4 — mind-agent legacy kod taşı (_legacy_slowdays/) ✅ DONE (2026-06-01)

Taşınanlar (git mv, import yolları güncellendi):
- src/agents/outreach → src/agents/_legacy_slowdays/outreach
- src/agents/auto_reply → src/agents/_legacy_slowdays/auto_reply
- src/agents/guardian → src/agents/_legacy_slowdays/guardian
- 10 test → tests/_legacy_slowdays/
- scripts/deploy_runners.sh entrypoint yolları da güncellendi.
Aktif kod bu paketleri import ETMİYOR (grep ile doğrulandı). Collection temiz
(1019 test toplandı, import hatası yok), taşınan testlerde 144 geçti; 6 'loop'
testi sandbox ağ kısıtı (NocoDB host allowlist) yüzünden düştü, taşımayla
ilgisiz.
### Adım 5 — sales_analyst_agent kaldır ✅ DONE (2026-06-01)

Karar: sales_analyst YOK; sales_manager + reklam_uzmani (+ meta alias) kaldi.
Hicbir aktif kod sales_analyst'i CAGIRMIYORDU (sadece deprecated tanim/alias).
Taşınanlar (_legacy):
- src/agents/sales/sales_analyst_agent.py → src/agents/sales/_legacy/
- src/agents/instructions/sales/analyst.py → src/agents/instructions/sales/_legacy/
- tests/test_sales_analyst_agent.py → tests/_legacy/
Temizlenen aktif referanslar: registry.py (import+factory+alias+__all__),
sales/__init__.py, instructions/sales/__init__.py, agent_wrapper_tools.py
(deprecated create_sales_analyst_wrapper_tool kaldirildi), orchestrator yorumu.
ÖNEMLİ: **reporting_tools.py TAŞINMADI** — artik aktif sales_manager'in okuma
katmani (get_reporting_tools) + sales_api/goals/triage/management/manager_actions
kullaniyor. Tasinsaydi Mudur cokerdi. Beyza onayiyla yerinde birakildi.
test_sales_manager_wiring: backcompat testi guncellendi (artik 'sales_analyst
registry'de YOK' assert'i).


### NocoDB erişim teşhisi (2026-06-02)
- Bu Claude bulut oturumunun ağ politikası KAPALI: github/example dahil tüm dış
  host'lar 403 'host_not_allowed' veriyor. Yani migration buradan koşulamaz;
  ya oturum network policy'sine db.mindidai.com.tr eklenir ya da Şeyma kendi
  Cloud Shell'inden koşar.
- Kullanıcı tarayıcıda https://db.mindidai.com.tr Forbidden alıyor (ayrı sorun,
  muhtemelen Caddy reverse proxy Host/IP allowlist).
- `scripts/diagnose_nocodb.sh` yazıldı: Cloud Shell'den domain+IP'yi yoklayıp
  Forbidden'ın kaynağını (proxy mi, token mı, IP allowlist mi) tespit eder.
  Read-only. Çıktıya göre sonraki adım belirlenecek.
