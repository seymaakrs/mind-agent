# Customer Agent Entegrasyon Sözleşmesi

**Amaç:** mind-agent'ın customer_agent ekosistemi (NocoDB + n8n + Zernio Console agent) ile nasıl konuşacağını sabitler. Bu doküman değişmeden iki tarafın paralel ilerlemesini sağlar.

---

## 1. Görev Paylaşımı

| İş | Sahibi |
|---|---|
| Lead bulma (Clay/Meta/LinkedIn) | n8n + Zernio |
| Lead skorlama | Zernio (Claude Console agent) |
| Lead'e takip mesajı | n8n (Takip Agent) |
| Lead verisi saklama | NocoDB (single source of truth) |
| Lead için SEO/SWOT raporu | **mind-agent** |
| Lead için içerik (IG/LinkedIn paylaşım) | **mind-agent** |
| Şeyma'ya pipeline raporu | **mind-agent** |

mind-agent satış otomasyonuna karışmaz; **bilgi okur, içerik üretir, sınırlı yazar.**

---

## 2. Veri Sözleşmesi (NocoDB)

**Bağlantı:**
- `NOCODB_BASE_URL` = `http://34.26.138.196`
- `NOCODB_API_TOKEN` = (env'de, git'te değil)
- `NOCODB_BASE_ID` = `ps9dj2fqrh823av`

**mind-agent'ın eriştiği tablolar (whitelist):**

| Tablo | Tablo ID | İzin |
|---|---|---|
| Leadler | `m5lcgc5ifeqh38h` | READ + sınırlı WRITE |
| Pipeline | `mnf5nyu2mx5xtej` | READ |
| Etkilesimler | `mx3kbw2vhwimxjf` | READ |

**Diğer tablolara erişim YOK.** Whitelist dışı bir tablo isteği `permission_denied` döner.

**Leadler tablosu — mind-agent'ın okuyabileceği kolonlar:**
- `lead_id`, `ad_soyad`, `email`, `sirket_adi`, `pozisyon`, `sektor`, `konum`
- `web_sitesi`, `instagram`, `linkedin_url`, `google_puani`
- `kaynak`, `asama`, `lead_skoru`, `ihtiyac_notu`
- `olusturma_tarihi`, `son_guncelleme`

**Leadler tablosu — mind-agent'ın yazabileceği kolonlar (sadece bunlar):**
- `notlar` (append, üzerine yazma yok)
- `seo_raporu_url` (yeni kolon — sözleşme onaylandığında eklenecek)
- `son_analiz_tarihi` (yeni kolon — sözleşme onaylandığında eklenecek)

**Diğer kolonlara YAZMA YOK** (lead_skoru, asama, kaynak vb. — bunlar Zernio + n8n alanı).

---

## 3. Tetikleyici Sözleşmesi (n8n Webhooks)

**Whitelist:** mind-agent sadece aşağıdaki webhook'ları çağırabilir. Liste boş başlar; ihtiyaç oldukça eklenir.

| Webhook | Yön | Amaç | Durum |
|---|---|---|---|
| (henüz yok) | mind-agent → n8n | takip mesajı tetikleme | Faz 2'de eklenecek |
| (henüz yok) | mind-agent → n8n | rapor üretildi bildirimi | Faz 2'de eklenecek |

n8n → mind-agent yönü için `/task` endpoint'i kullanılır (auth ile korumalı).

---

## 4. Hata Davranışı (Tolerant Reader)

mind-agent NocoDB veya n8n cevaplarını **dayanıklı** okur:

- **Kolon eksikse:** null gibi davranır, hata atmaz.
- **Tablo boşsa:** kullanıcıya "şu an bu tipte lead yok" der.
- **NocoDB cevap vermezse:** `ServiceError(code=NETWORK_ERROR, retryable=True)` döner, kullanıcıya "CRM'e şu an erişilemiyor" der; mind-agent kendi işlerine (image/video/marketing) devam eder.
- **Yetki hatası (403):** `permission_denied` — whitelist dışı bir şey isteniyor demektir, hata loglanır.

---

## 5. Feature Flags (Aşamalı Açılış)

Firestore: `settings/app_settings.customerAgent`

```yaml
customerAgent:
  enabled: false           # ana anahtar
  canReadLeads: false      # NocoDB Leadler/Etkilesimler okuma
  canReadPipeline: false   # Pipeline okuma + özet
  canAttachReports: false  # NocoDB sınırlı yazma (notlar, seo_raporu_url)
  canTriggerFollowup: false # n8n webhook tetikleme
  canPostForLead: false    # IG/LinkedIn paylaşım
```

**Tüm bayraklar default `false`.** Her biri ayrı açılır, her birinin kendi testi vardır. Kapalı bayrak = ilgili tool çağrılırsa `feature_disabled` döner, sistem kırılmaz.

---

## 6. Kimlik Doğrulama

- **mind-agent → NocoDB:** `xc-token` header (NocoDB API token).
- **mind-agent → n8n:** Webhook URL içinde rastgele path token (n8n standart).
- **n8n → mind-agent:** `Authorization: Bearer <MIND_AGENT_API_KEY>` header zorunlu. Bu key olmadan `/task` endpoint'i 401 döner. (Adım 3'te eklenecek.)

---

## 7. Değişiklik Yönetimi

Bu sözleşme değiştiğinde:
1. PR açılır, başlığı `contract:` ile başlar.
2. Whitelist'e tablo/kolon/webhook eklenmesi → bu dokümanda satır.
3. Yeni feature flag → bu dokümanda satır.
4. Mind-agent ve customer_agent (n8n/NocoDB) tarafı ayrı ayrı doğrulanmadan merge edilmez.
