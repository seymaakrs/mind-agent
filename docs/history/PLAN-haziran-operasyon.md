# Slowdays AI — Haziran Operasyon Planı (Hedef: 250.000 TL ciro)

> Tarih: 2026-06-01 · Branch: claude/relaxed-clarke-tUchS · PR #39
> Bu doküman "büyük vizyon" plandır. Kod değil, yol haritası.

## 0) Tek cümle
Defteri (NocoDB) temizleyip, Satış Müdürü'nü ürün/fiyat bilgisiyle donatıp,
"TL ciro" hedefini sisteme ekleyip, sonra gerçek lead toplamayı (Qualifier +
Google Maps) açacağız. Her şey TEK veri kapısından (NocoDB) akacak.

## 1) Satış Müdürü denetimi — şu an hazır mı?

Müdür ajanın 42 aracı var. Durum:

| Yetenek | Durum | Not |
|---|---|---|
| Lead okuma/raporlama (10 araç) | ✅ Var | NocoDB'den okuyor |
| Lead yönetimi/atama (7 araç) | ✅ Var | — |
| Aylık hedef takibi (goals) | ⚠️ Yarım | metrikler: sicak_lead/yeni_lead/kazanildi/total_outreach. **TL ciro YOK** |
| Ürün/fiyat bilgisi (knowledge, 5 araç) | 🔴 Eksik | Marka Kimliği defterinden okuyor; defter boşsa "bilgi yok" der |
| Hedef kitle/ton | ⚠️ Aynı kaynağa bağlı | Marka Kimliği dolu değilse boş |
| Sıcak lead triyajı (2 araç) | ✅ Var | — |

**Sonuç:** Altyapı sağlam ama "kasa" boş. Müdür şu an fiyatlara hâkim DEĞİL
(Marka Kimliği business_context doldurulmamış) ve ciroyu (TL) takip edemiyor.

## 2) Mail atanlar nereden veri çekiyor?

Hepsi tek defterden: **NocoDB** (Leadler + Etkilesimler + Firsatlar).

| Mail atan | Kaynak | Durum |
|---|---|---|
| Lead Toplama Agent | Webhook → NocoDB | 🔴 Kapatıldı (Adım 1) |
| Takip Agent (eski) | NocoDB Leadler | 🔴 Kapatıldı (Adım 1) |
| Meta Lead Ads Agent | FB reklam formu → NocoDB | ✅ Aktif (karar) |
| Upsell / Referans | NocoDB Firsatlar | ✅ Aktif |
| Haftalık/Günlük Rapor | NocoDB Leadler | ✅ Aktif |
| Bekçi Alert | Guardian (deploy değil) | tetik var |

→ Tek veri kapısı NocoDB. Temizlik (Adım 3) herkesi etkiler — temiz veri = doğru mail.

## 3) Maliyet stratejisi (token/API)
- Orchestrator + Müdür zaten gpt-4o-mini (en ucuz akıllı model).
- Zernio MCP 80 araç context'i şişiriyor → Müdür'e araç filtresi (~15 araç).
- Prompt caching (sabit talimatlar) → tekrar token ~%90 ucuzlar.
- n8n cron'ları seyrek + HARD_CAP → boşa LLM/mail yok.
- Google Maps: Places API batch + cache → minimum çağrı.

## 4) Sıralı yol haritası

### Faz A — NocoDB defterini temizle (token gelince, EN SONA bırakıldı)
- Adım 2-apply: yeni kolonlar gerçek uygulanır (`scripts/migrate_qualifier_schema.py --apply`)
- Adım 3: `scripts/cleanup_fake_leads.py` yazılır → dry-run say → onayla sil

### Faz B — Müdür'ü donanımlı yap
- Portal "Marka Kimliği"ne ürün/hizmet + FİYAT LİSTESİ + USP girilir (business_context.enabled=true)
- Müdür talimatlarına KATI KURALLAR: "1–30 Haziran 250k TL; fiyat uydurma, sadece
  defterden oku; her sıcak lead'e X saatte dön; eksik bilgi varsa Şeyma'ya sor"

### Faz C — "Ciro (TL)" hedefini ekle (şu an eksik)
- goals metriğine `ciro_tl` + NocoDB Firsatlar'a `tutar` alanı
- Müdür: "250k'nın %kaçındayız, günlük ne lazım" raporu

### Faz D — Gerçek lead toplama (sonraki oturum, ŞİMDİ YAZMA)
- Qualifier Agent (LLM + ICP fit → qualified=true)
- Google Maps Prospecting (gerçek işletme verisi)
- Tek yazma kapısından NocoDB'ye → Müdür gerçek veriyle çalışır

## 5) NEREDE KALDIK (2026-06-01 sonu)
- ✅ Adım 1 (mail durdu), Adım 4 (legacy taşındı), Adım 5 (sales_analyst kaldırıldı)
- ✅ Adım 2 kod+test hazır → APPLY token bekliyor (NocoDB en sona)
- ⏳ Adım 3 script henüz yazılmadı (token gelince)
- 🔴 BLOKAJ: NocoDB token 403 (rotate edilmiş). Şeyma güncel token verecek.
- 📌 Pre-existing kırık test: test_director_total_tool_count (30→42), kapsam dışı.

## 6) SONRAKİ OTURUMDA İLK İŞ
1. Güncel NocoDB token'ı al → Adım 2-apply + Adım 3 (Faz A bitir)
2. Faz B: Marka Kimliği'ne fiyat gir + Müdür katı kurallar
3. Faz C: ciro_tl metriği
