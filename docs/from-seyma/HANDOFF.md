# SLOWDAYS AI — OTEL & KONAKLAMA KAMPANYASI HANDOFF
**Tarih:** 2026-05-09 | **Durum:** Aktif gönderim devam ediyor

---

## 1. PROJE ÖZÜ

**Marka:** Slowdays AI (Bodrum, AI destekli reklam & yazılım ajansı)
**Amaç:** Bodrum/Marmaris/Fethiye/Göcek bölgesinde küçük/orta otel sahiplerine dijital hizmet paketi satmak (B2B).
**Strateji açısı:** "Büyük zincirler kapalı / sınırlı — küçük otelin yılı bu sezon. Dijitalde görün, sezonu kazan."
**Timing:** Mayıs 2026, Kurban Bayramı yaklaşıyor.

**3 paralel kanal:**
- WhatsApp toplu cold outreach (template bazlı, 331 otel) — **AKTİF**
- Meta Ads marka bilinirliği (Reels, 200 TL/gün) — **PAUSED, görsel ve pixel bekliyor**
- Meta Ads conversion (statik + Lead Form/CTW, 400 TL/gün) — **PAUSED, görsel ve pixel bekliyor**

---

## 2. AKTİF SİSTEMLER (DOKUNMA)

### 2.1 WhatsApp Gönderim
- **Script:** `otel_gonderim.py`
- **Task ID:** `bnklv9qm9` (background, devam ediyor)
- **Endpoint:** `POST https://api.zernio.com/v1/whatsapp/bulk`
- **Template:** `ege_otel_yaz_sezon_v1` (APPROVED, MARKETING, dil: tr)
- **Variables:** `{{1}}` = otel adı
- **Davranış:** 25-90sn random delay, 20'şer batch sonrası 4-7 dk mola, 09:00-21:00 mesai
- **Limit:** 240/24h (TIER_250 buffer)
- **Master liste:** `otel_master.csv` (331 otel)
- **Log:** `gonderim_log.csv` (canlı, append)
- **Resume:** Script restart ettiğinde log'dan SENT olanları atlar

### 2.2 Lead Monitor + Auto-Reply
- **Script:** `lead_monitor.py`
- **Task ID:** `be2pfuvdx` (background, devam ediyor)
- **Polling:** 60 saniye
- **Tetiklendiğinde:**
  1. Yeni inbound yakalar
  2. Zernio'da `hot_lead`, `yaniti_var` etiketler
  3. 30-60sn delay sonrası 3 varyant arasından random seçip otomatik 2. mesaj gönderir
  4. `oto_yanit_gonderildi` etiketi ekler
  5. `inbound_log.csv`'ye yazar
- **3 varyant:** günlük dil, yüz yüze görüşme önerili, kapanış sorulu (lead_monitor.py içinde `AUTO_REPLIES` listesinde)
- **Send endpoint:** `POST /v1/inbox/conversations/{conversationId}/messages` body: `{accountId, message}`

### 2.3 Anlık İstatistikler (handoff anı)
| Metrik | Değer |
|---|---|
| Master listede otel | 331 |
| Bugün gönderildi | ~42 (16:50 itibarıyla) |
| Yanıt veren | 2 (İde Beach Home, Bono Residence) |
| İlk yanıt verene gönderilen | İde Beach Home — özel manuel yanıt |
| Bono Residence | Monitor tarafından yakalandı, oto-yanıt gönderildi mi: log'a bak |

---

## 3. ZERNIO API REFERANS (calismis endpoint'ler)

```
BASE = https://api.zernio.com/v1
Header: Authorization: Bearer sk_bbd6bbced7a54fe6af777ffc13c8ee5a66782b4e532eb305d35a7bfda0351957

PROFILE_ID         = 69e7cc66625d802f5bff8c11   (slowdays profile)
WA_ACCOUNT_ID      = 69ecc2273a63baf2053dfc21   (WhatsApp +90 541 931 55 50)
FB_ACCOUNT_ID      = 69ecbd243a63baf2053dd3a7   (Slowdays Bodrum FB Page)
META_ADS_ACCOUNT   = 69ecbd393a63baf2053dd441   (parent metaads)
INSTA_ACCOUNT      = 69e7d2607dea335c2b1e1eef   (@slowdaysai)
LI_ACCOUNT         = 69ebcbe73a63baf20538a50a   (Slowdays AI organization)

Meta Ads alt hesaplari (TRY):
  act_4187240218264078
  act_2347737169004873  (Slowdays AI - kullanilacak ana hesap)
  act_1288641972777101
```

**Çalışan endpoint'ler:**
- `GET  /v1/profiles` — profil listesi
- `GET  /v1/accounts` — bağlı hesaplar
- `GET  /v1/ads/accounts?accountId=<metaads_id>` — Meta ad hesapları
- `GET  /v1/ads/interests?q=<term>&accountId=<fb_id>` — Meta interest arama
- `GET  /v1/whatsapp/contacts?accountId=<wa_id>&limit=100&skip=N` — contact listesi (paginated)
- `GET  /v1/whatsapp/templates?accountId=<wa_id>` — template listesi
- `POST /v1/contacts/bulk` — body: `{profileId, accountId, platform:"whatsapp", contacts:[{name, platformIdentifier, tags}]}`
- `POST /v1/whatsapp/bulk` — TEMPLATE gönder. body: `{accountId, template:{name, language:"tr"}, recipients:[{phone:"+90...", variables:["otel_adi"]}]}`
- `GET  /v1/inbox/conversations?accountId=<wa_id>&limit=100` — konuşma listesi
- `POST /v1/inbox/conversations/{conversationId}/messages` — FREE-FORM mesaj. body: `{accountId, message:"metin"}`
- `PATCH /v1/contacts/{contactId}` — body: `{tags:[...]}`

**Çalışmayan / yanılgı:**
- `/v1/whatsapp/messages` → 404
- `/v1/messages` → 404
- MCP zernio tool'lari → 401 (eski API key cache, Claude Desktop restart gerek)

---

## 4. ONAYLI WHATSAPP TEMPLATELERI

| Template | Kullanım | {{1}} |
|---|---|---|
| **ege_otel_yaz_sezon_v1** ⭐ | Otel kampanyası — kullanılan | otel adı |
| slowdays_yaz_demo_v2 | Genel yaz demo | kişi adı |
| yaz_demo_sicak_v1 | Genel demo | kişi adı |
| ucretsiz_web_demo_v1 | Demo davet | kişi adı |

`ege_otel_yaz_sezon_v1` body:
> Merhaba {{1}}, Ben Seyma. Yaz sezonu acildi. Ege otelleri icin en yogun donem su an basliyor. Gecen yil birlikte calistigimiz bir Ege otelinde sadece Instagram uzerinden 40'tan fazla dogrudan rezervasyon geldi. Dogru hedefleme yapildiginda bu artik mumkun. ... slowdaysai.com ... Seyma - Slowdays AI

---

## 5. HEDEF KİTLE — META ADS

**Coğrafi:** Bodrum, Marmaris, Fethiye, Göcek (25km radius) + B2B genişletme: Türkiye geneli

**Interest ID'leri (toplandı):**
- `6003359052437` Hospitality management studies (~10M)
- `6003147405549` Boutique hotel (~18M)
- `6777460559594` Seyahat Acenteleri ve Rezervasyon (~850k)
- `6003240159610` İkram sektörü (~41M)
- `6002884511422` Küçük işletme (~177M)
- `6003572379887` Oteller / konaklama (~603M)

**Yaş:** 28-58
**Dil:** TR
**B2B not:** Meta'da otel sahibi direkt seçilemez → lokasyon + interest + iş ünvanı kombinasyon

---

## 6. WHATSAPP LEAD AKIŞI (Alt-agent tasarımı)

**5 adımlık akış:**
1. Karşılama + niyet sorma (otel tipi, lokasyon)
2. Mevcut durum (reklam yapıyor mu, sosyal medya aktif mi)
3. Acı noktası (doluluk / Booking komisyonu / direct booking)
4. Çözüm sunumu (3 paket: Başlangıç / Sezon / Premium)
5. Randevu/demo kapama

**Sequence (cold lead):** +1 saat / +24 saat / +3 gün / +7 gün

**Etiketler (Zernio CRM):**
- Segment: `butik_otel`, `pansiyon`, `villa_kiralama`, `zincir_otel`
- Bölge: `bolge_bodrum`, `bolge_marmaris`, `bolge_fethiye`, `bolge_gocek`, `bolge_dalaman`
- Sıcaklık: `hot_lead`, `warm_lead`, `cold_lead`, `dead_lead`
- Aksiyon: `demo_istedi`, `teklif_gonderildi`, `fiyat_sordu`, `dusunme_asamasi`, `mevcut_ajansli`
- Bütçe: `butce_baslangic`, `butce_sezon`, `butce_premium`
- Sezon: `sezon_2026`
- Kaynak: `kaynak_googleplaces`
- Kampanya: `otel_kampanya_mayis2026`
- Otomasyon: `oto_yanit_gonderildi`, `yaniti_var`, `manual_review`

---

## 7. PIXEL & WEB SITE DURUMU (PENDING)

**slowdaysai.com kontrol durumu:**
- ❓ Meta Pixel — kullanıcı web reposundan kontrol ediyor (cevap bekleniyor)
- ✅ `/sektorel/otel` landing page var
- ✅ Form alanları: İsim, Tesis Adı, E-posta, Telefon, Mesaj + KVKK
- ⚠️ Form action `/iletisim`'e gidiyor — dedicated thank-you yok
- ❌ WhatsApp tıklanabilir buton yok

**Kullanıcıya gönderilen pixel kontrol prompt'u:** 10 maddelik liste (Pixel ID, CAPI, events, KVKK, domain verification, UTM yakalama, vb.) — `slowdaysai-web` reposunda Claude'a soruluyor.

**Sonraki adım:** Pixel cevabı gelir gelmez Conversion kampanyası seçimi:
- (A) Web Conversion (pixel + thank-you sayfa şart)
- (B) Meta Lead Form (on-platform, pixel'a gerek yok)
- (C) Hibrit — önerilen: 240 TL Lead Form + 160 TL CTW

---

## 8. CANVA AGENT PROMPT (HAZIR — kullanıcı ayrı oturumda çalıştıracak)

3 Reels (Awareness) + 3 Statik (Conversion) görsel seti.
- Marka: lacivert (#001338) + krem, premium-minimal
- Hedef: küçük otel sahibi (B2B)
- Mesaj: "Büyük zincirler kapalı, sıra sende"
- Ölçüler: 1080x1920 (Reels), 1080x1080 + 1080x1350 (statik)
- Teslimat: Canva URL/PNG/MP4 + caption (<125ch) + CTA buton

---

## 9. DOSYA ENVANTERİ

**Üretilenler (bu oturumda):**
- `bodrum_otel_scraper.py` (zaten vardı)
- `marmaris_otel_scraper.py` (yeni — 280 mobil otel buldu)
- `OTEL_YENI_MOBIL_BODRUM_MARMARIS.csv` (307 yeni otel)
- `otel_master_liste.py` (birleştirme scripti)
- `otel_master.csv` (331 otel, skor sıralı) ⭐
- `import_yeni_oteller.py` (Zernio bulk import — çalıştırıldı)
- `otel_gonderim.py` (ana gönderim) ⭐ ÇALIŞIYOR
- `lead_monitor.py` (auto-reply + tag) ⭐ ÇALIŞIYOR
- `gonderim_log.csv` (gönderim kayıtları)
- `inbound_log.csv` (yanıt verenler)
- `HANDOFF.md` (bu dosya)

**Veri kaynakları:**
- `bodrum_otel_leads.csv` (516 satır, ön taranmış)
- `marmaris_otel_leads.csv` (280 satır, yeni taranmış)
- `.env` → `ZERNIO_API_KEY=sk_bbd6...`, `GOOGLE_MAPS_API_KEY=AIzaSy...`

---

## 10. SONRAKİ AGENT İÇİN AKSİYON LİSTESİ

### Hemen (gönderim devam ederken)
- [ ] **Yanıt geldikçe izle:** `inbound_log.csv` dosyasına bak. Yeni satır = sıcak lead. Şeyma'ya bilgi ver, gerekirse insan handoff için özel mesaj hazırla.
- [ ] **Pixel cevabı geldiğinde:** `slowdaysai-web` reposundan dönen 10 maddelik raporu yorumla, eksikleri sırala.
- [ ] **Canva görselleri geldiğinde:** Meta Ads creative'lerine bağla.

### Bu hafta
- [ ] **Awareness kampanyası** (Reels) Meta Ads tarafında paused olarak oluştur:
  - act_2347737169004873
  - 200 TL/gün CBO
  - Yerleşim: IG/FB Reels + Stories
  - Hedef: AWARENESS, Reach optimizasyonlu
  - Lokasyon: Bodrum/Marmaris/Fethiye/Göcek 25km
  - Yaş 28-58
- [ ] **Conversion kampanyası** (Lead Form veya Web):
  - act_2347737169004873
  - 400 TL/gün (240 Lead Form + 160 CTW önerilen hibrit)
  - Statik creative
- [ ] **Gün 2 gönderim:** Kalan ~91 mesaj (script otomatik devam eder, restart yeterli)
- [ ] **Yanıt analizi:** İlk 24 saat sonra reply rate hesabı, varyant performansı, Quality rating kontrolü (RED olmamalı)

### Önemli kurallar
- ❌ **otel_gonderim.py task'ını DURDURMA** (bnklv9qm9)
- ❌ **lead_monitor.py task'ını DURDURMA** (be2pfuvdx)
- ❌ **gonderim_log.csv'yi SİLME / DEĞİŞTİRME** (resume mantığı)
- ❌ **inbound_log.csv'yi SİLME** (auto-reply dedupe)
- ✅ Yeni yanıt geldiğinde manuel özel mesaj YAZILABİLİR (lead_monitor send eder veya manuel `/v1/inbox/conversations/{id}/messages` POST)
- ✅ MCP zernio bozuk → her zaman direct curl + API key kullan
- ✅ Otomatik 2. mesaja müşteri 3. mesajla cevap verirse → İNSAN devralır

---

## 11. KULLANICI HAKKINDA NOTLAR

- Türkçe konuşur, kısa direkt iletişim ister
- Profesyonel iş çıkarmak ister, "ultra uzmanlık" bekler
- Karışıklığı sevmez, adım adım gitmek ister
- Test numarası: **+905439335595** (yanlış olan +905423537732 — kullanma)
- İş telefonu (WA business hat): **+90 541 931 55 50**
- E-posta: seymaakrs@gmail.com
- Memory dosyası: `C:\Users\asus\.claude\projects\C--Users-asus-OneDrive-Desktop-REKLAM-AGENT\memory\MEMORY.md`
