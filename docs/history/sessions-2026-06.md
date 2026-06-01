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

### Adım 2 — NocoDB şema güncelle (migration) ✅ KOD HAZIR / ⏳ APPLY BEKLİYOR (2026-06-01)

`scripts/migrate_qualifier_schema.py` yazıldı (idempotent, default DRY-RUN, `--apply` ile gerçek).
Eklenenler: Leadler → qualified(Checkbox), source(SingleSelect 8 option:
gmaps/ig/linkedin/meta_lead_ads/mindid_form/itiraz/wa_inbound/manual),
qualification_reason(LongText), qualified_by(SingleLineText), qualified_at(DateTime);
asama enum'una 'Arsiv' option.
Test: `tests/test_migrate_qualifier_schema.py` 15/15 yeşil.
**BLOKAJ:** CLAUDE.md'deki NocoDB token (MNhF4r...) artık 403 Forbidden dönüyor
(rotate edilmiş). Geçerli token + base_url gelince dry-run sonra --apply koşulacak.
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
### Adım 5 — sales_analyst_agent kaldır ⏳
