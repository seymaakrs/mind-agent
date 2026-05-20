# Frontend Tasarım Brief'i — mind-agent

> **Hedef okuyucu:** Web tasarımcısı (UX/UI)
> **Hazırlayan:** Backend mimari ekibi
> **İlgili teknik dokümanlar:** `docs/STREAM_EVENTS_SPEC.md`, `docs/architecture/01-system-hierarchy.md`

---

## 1. Sistem Nedir? (Mental Model)

> **mind-agent**, bir işletmenin (kafe, marka, ajans...) **AI çalışanlardan oluşan dijital ekibini** yönettiği bir komuta panosudur.
>
> Kullanıcı bir görev yazar ("logo yap ve Instagram'a paylaş"). Arka planda **5 AI çalışan** (orchestrator + image + video + marketing + analysis) sırayla devreye girip işi tamamlar. Her adım canlı olarak ekranda akar.

**Tasarım metaforu:** "AI ekibine iş veren bir yönetici paneli."
- Sol taraf → **Ne yapabilirim?** (kapasite listesi)
- Orta → **Komut kutusu + canlı iş akışı** (chat-like + workflow tree)
- Sağ → **Üretilen içerik / sonuç** (görsel, video, rapor önizleme)

---

## 2. Sayfa Hiyerarşisi

```
┌──────────────────────────────────────────────────────────────┐
│                       TOP BAR                                 │
│  [logo] [İşletme seçici ▼]              [bildirim] [profil]  │
├──────────┬───────────────────────────────────┬───────────────┤
│          │                                   │               │
│          │                                   │               │
│ SOL      │      ANA ALAN                    │   SAĞ PANEL   │
│ MENÜ     │  ┌───────────────────────────┐   │  (opsiyonel)  │
│          │  │ Workflow Canvas / Konuşma │   │               │
│ • Görsel │  │   (canlı akış)            │   │  Üretilen     │
│ • Video  │  │                           │   │  içerik:      │
│ • Sosyal │  │                           │   │  - görsel     │
│ • Analiz │  │                           │   │  - video      │
│ • Dosya  │  └───────────────────────────┘   │  - rapor      │
│          │  ┌───────────────────────────┐   │               │
│ Geçmiş   │  │ Komut girişi              │   │  Referans     │
│ ───────  │  │ [_____________] [Gönder]  │   │  ekleyici     │
│ • Task 1 │  └───────────────────────────┘   │               │
│ • Task 2 │                                   │               │
└──────────┴───────────────────────────────────┴───────────────┘
```

**Önemli:** Sol menü, `GET /capabilities` endpoint'inden **dinamik** doldurulur. Statik değildir.

---

## 3. Sol Menü — Kapasite (Capability) Haritası

Backend bu yapıyı `/capabilities` endpoint'inden döner:

```
🖼️  Görsel Üretme
    • Görsel Oluşturma           (sıfırdan görsel)
    • Kaynaktan Görsel Üretme    (logo + referans görsel)

🎬  Video Üretme
    • Video (Veo 3.1)
    • Video (Kling 3.0)
    • Video (HeyGen — kurumsal)
    • Videoya Ses Ekleme

📱  Instagram & Sosyal Medya
    • Instagram Post Paylaşma
    • Carousel Post
    • Haftalık İçerik Planı
    • Plana Göre Paylaşım
    • Instagram Analitik

📊  Analiz & Araştırma
    • SWOT Analizi
    • SEO Analizi (100p + GEO)
    • Rakip Analizi
    • SERP Sıralama Kontrolü
    • Özel Araştırma Raporu

💾  Dosya & Veri Yönetimi
    • Dosya Yönetimi
    • Otomatik Kayıt
```

**Tasarım kararı için soru:** Bu menüye tıklayınca ne olur?
- (a) Komut kutusuna örnek prompt yapıştırır
- (b) Sağda detay sayfası açar (özellik açıklaması + butonu)
- (c) Direkt görevi çalıştırır (form gerektirenler hariç)

> Önerim: **(a)** — En düşük sürtünme. Kullanıcı tıklar, prompt hazır gelir, Enter'a basar.

---

## 4. Etkileşim Modeli — "Chat + Live Workflow"

Kullanıcının deneyimi şu sırayla:

```
1.  Kullanıcı bir komut yazar
        ↓
2.  Backend NDJSON streaming başlatır
        ↓
3.  Ekranda canlı olarak:
    • Orchestrator agent doğar
    • "Düşünüyor..." animasyonu
    • Karar açıklaması (Türkçe konuşma balonu)
    • Alt agent doğar (Image / Video / Marketing / Analysis)
    • Tool çalışır (görsel üretiliyor...)
    • Sonuç çıkar (görsel URL, post URL, rapor)
        ↓
4.  Final sonuç sağ panelde gösterilir
```

**KRİTİK:** Bu **statik bir sonuç sayfası değil**. Backend her saniye 5-10 event yolluyor. Tasarım **canlı/animasyonlu** bir ağaç (workflow tree) düşünmek zorunda.

---

## 5. UI Bileşenleri (Tasarım Listesi)

### 5.1 Capabilities Browser (Sol Menü)
- **Veri:** `GET /capabilities`
- **Yapı:** Kategoriler kollabsable, içlerinde feature item'ları
- **Etkileşim:** Tıkla → komut kutusuna örnek prompt yapıştır
- **Boş durum:** Yok (her zaman dolu gelir)

### 5.2 Business Selector (Top Bar)
- **Veri:** Kullanıcının Firebase'deki `businesses` koleksiyonu
- **Etkileşim:** Seçim → tüm sonraki istekler bu `business_id` ile gider
- **UI:** Avatar + isim + sektör badge

### 5.3 Task Input (Komut Kutusu)
- **Bileşenler:**
  - Çok satırlı textarea
  - "Referans ekle" butonu (Firebase item picker'ı açar)
  - "Gönder" butonu
- **Davranış:**
  - Enter → gönder
  - Shift+Enter → satır atla
- **Reference chip'leri:** Seçilen referanslar input'un üstünde küçük çipler olarak gösterilir (örn. "📷 Geçen haftanın görseli")

### 5.4 Workflow Canvas (Asıl Sihir)
> Bu en kritik bileşen. Backend'in NDJSON event'lerini canlı bir ağaca dönüştürür.

**Düğüm tipleri:**
| Tip | İkon | Şekil | Aktif Renk | Bitmiş |
|-----|------|-------|------------|--------|
| Orchestrator | 🎯 | Büyük yuvarlatılmış | Mavi | Yeşil |
| Image Agent | 🎨 | Orta yuvarlatılmış | Mor | Yeşil |
| Video Agent | 🎬 | Orta yuvarlatılmış | Turuncu | Yeşil |
| Marketing Agent | 📱 | Orta yuvarlatılmış | Pembe | Yeşil |
| Analysis Agent | 📊 | Orta yuvarlatılmış | Turkuaz | Yeşil |
| Tool (sıradan) | ⚙️ | Küçük pill | Gri | Yeşil |
| Hata | ❌ | Küçük pill | Kırmızı | Kırmızı |

**Düğüm durumları (state machine):**
```
idle → thinking → decided → executing → waiting → completed
                                     ↘
                                       error
```

**Animasyonlar:**
| Durum | Animasyon |
|-------|-----------|
| `thinking` | Pulsing glow / spinning beyin ikonu |
| `decided` | Kısa flash + konuşma balonu |
| `executing` | Akan noktalar (kenar üzerinde) |
| `completed` | Yeşil tik + hafif scale |
| `error` | Kırmızı shake |

**Kenarlar (Edge):**
- Sub-agent çağrısı → kalın çizgi, üzerinde prompt önizlemesi
- Sıradan tool çağrısı → ince çizgi, üzerinde parametre özeti
- Geri dönüş (output) → noktali çizgi, sonuç önizlemesi

> 📚 Detay için `docs/STREAM_EVENTS_SPEC.md` (özellikle "Frontend Workflow Visualisation Guide" bölümü).

### 5.5 Result Panel (Sağ Panel)
- Üretilen görsel/video → büyük önizleme + indirme + Instagram'da paylaş butonu
- Üretilen rapor → markdown render + PDF export
- Boş durum: "Henüz bir görev çalıştırılmadı"

### 5.6 Reference Picker (Modal)
Kullanıcı bir komutta "şu görseli kullan", "geçen haftanın raporunu referans al" diyebilir.

**Filtre tipleri:**
- 📷 Görseller (`type: "image"`)
- 🎬 Videolar (`type: "video"`)
- 📱 Instagram postları (`type: "instagram_post"`)
- 📝 Raporlar (`type: "report"`)
- 📅 Planlar (`type: "plan"`)
- 📂 Medya (`type: "media"`)

**Seçilen item'lar** input'a chip olarak eklenir.

### 5.7 Task History (Sol Alt)
- Son 20 görev listesi
- Tıklayınca → o görevin workflow canvas'ı geri açılır (replay)

---

## 6. Tipik Kullanıcı Akış Senaryoları

### Senaryo A — "Logo yap ve Instagram'da paylaş"

```
1. Kullanıcı sol menüden "Görsel Oluşturma"ya tıklar
   → Komut kutusuna örnek prompt yapışır
2. Kullanıcı düzenler: "Cafe Moda için minimalist logo, kahve temalı"
3. "Gönder" → Workflow canvas'ta:
   🎯 orchestrator (mavi, thinking)
       💭 "Logo yapacağım, sonra paylaşacağım"
   🎯 → 🎨 image_agent doğar (mor, executing)
              ⚙️ generate_image (5 saniye akan noktalar)
              ✅ tamamlandı → URL döner
   🎯 (waiting → thinking)
       💭 "Şimdi Instagram'a paylaşıyorum"
   🎯 → ⚙️ post_on_instagram (executing)
              ✅ Post URL: instagram.com/p/abc
4. Sağ panelde: oluşan logo + Instagram post linki
```

### Senaryo B — "Haftalık SEO analizi yap"

```
1. Sol menü → "SEO Analizi"
2. Komut: "Websitemizin SEO analizini yap"
3. Workflow:
   🎯 orchestrator → 📊 analysis_agent
                            ⚙️ fetch_business
                            ⚙️ scrape_for_seo (~30 saniye!)
                            ⚙️ web_search (rakipler)
                            ⚙️ scrape_competitors (~60 saniye!)
                            ⚙️ check_serp_position
                            ⚙️ save_seo_keywords
                            ⚙️ save_seo_report
                            ⚙️ save_seo_summary
4. Sağ panelde: SEO skoru kartı (100 üzerinden) + öneriler
```

> ⚠️ Bu senaryoda **90+ saniye** çalışma süresi var. Tasarım uzun bekleme deneyimini düşünmeli (progress göstergesi, "şu an X yapılıyor" mesajları).

### Senaryo C — Hata Durumu

```
1. Kullanıcı: "Yeni video oluştur, balerin dansı"
2. Workflow başlar
3. Veo API → CONTENT_POLICY hatası
4. Event: tool_error
   {
     error_code: "CONTENT_POLICY",
     retryable: false,
     user_message_tr: "İçerik politikası nedeniyle..."
   }
5. UI:
   - İlgili düğüm kırmızı shake animasyonu
   - Toast: "İçerik politikası nedeniyle oluşturulamadı"
   - "Tekrar dene" butonu (retryable: true ise)
```

### Senaryo D — Referans Kullanımı

```
1. Kullanıcı "Referans ekle" → modal açılır
2. Filter: "Görseller" → geçen haftaki logoyu seçer
3. Chip ekrana eklenir: [📷 Cafe Moda Logosu]
4. Komut: "Bu logoyu kullanarak Instagram banner'ı yap"
5. Backend'e gönderilen payload:
   {
     task: "Bu logoyu kullanarak Instagram banner'ı yap",
     business_id: "abc123",
     references: [
       { type: "image", id: "businesses/abc/media/logo_xxx",
         url: "https://...", label: "Cafe Moda Logosu" }
     ]
   }
```

---

## 7. API Kontratı (Tasarımcının Bilmesi Gerekenler)

### 7.1 Endpoint Özeti

| Endpoint | Method | Amaç | Frontend kullanımı |
|----------|--------|------|---------------------|
| `/capabilities` | GET | Sol menü içeriği | Sayfa yüklenirken bir kez |
| `/task` | POST | Görev çalıştır (streaming) | Her komut gönderiminde |
| `/health` | GET | Sistem sağlığı | İsteğe bağlı |

### 7.2 `/task` İstek Şekli

```typescript
{
  task: string;                  // Kullanıcının yazdığı komut
  business_id: string;           // Üst bar'daki seçili işletme
  task_id?: string;              // İstemci tarafında üretilen UUID (geçmiş için)
  thread_id?: string;            // Konuşma devamı için (yoksa yeni başlar)
  references?: Reference[];      // Reference picker'dan seçilenler
  extras?: Record<string, any>;  // Esnek alan (opsiyonel)
}
```

### 7.3 `/task` Yanıt — NDJSON Stream

```
event: progress  (agent_start, llm_start, llm_end, tool_start, tool_end, ...)
event: heartbeat (2 saniyede bir, sadece bağlantıyı canlı tut)
event: result    (en son — başarı veya hata)
```

> 📚 **Tam şema için `docs/STREAM_EVENTS_SPEC.md` zorunlu okuma.**

---

## 8. Görsel Kimlik Önerileri

### Renk Paleti
| Renk | Kullanım |
|------|----------|
| 🔵 Mavi | Orchestrator + birincil aksiyonlar |
| 🟣 Mor | Görsel üretimi (Image) |
| 🟠 Turuncu | Video üretimi |
| 🩷 Pembe | Sosyal medya/Marketing |
| 🩵 Turkuaz | Analiz/Araştırma |
| 🟢 Yeşil | Başarı / tamamlanan |
| 🔴 Kırmızı | Hata |
| ⚪ Gri | Sıradan tool / pasif |

### Tipografi
- **Komut kutusu:** Monospace (kod hissi) veya regular sans-serif
- **AI mesajları:** Italic, biraz açık renk (kişilik hissi)
- **Düğüm etiketleri:** Bold, kısa

### Anahtar Animasyonlar
1. **Thinking** — Pulsing glow (1s döngü) veya 3 nokta animasyonu
2. **Executing** — Edge üzerinde akan parçacıklar
3. **Completed** — Yeşil tik + 200ms scale-up
4. **Error** — Kırmızı shake (300ms)
5. **Düğüm doğumu** — Fade-in + grow

---

## 9. Mobile vs Desktop

| Boyut | Yaklaşım |
|-------|----------|
| 📱 Mobile | Tek kolon: workflow tree dikey scroll, sağ panel modal olarak açılır |
| 💻 Tablet | İki kolon: sol menü + ana alan; sağ panel açılır kapanır |
| 🖥️ Desktop | Üç kolon klasik düzen |

**Önerim:** Workflow canvas mobile'da deneyimi bozar — desktop-first tasarla, mobile'da "son sonuç + sade chat" göster.

---

## 10. Empty States

| Durum | Mesaj | CTA |
|-------|-------|-----|
| Hiç görev yok | "AI ekibine ilk görevi ver" | "Görsel Oluşturma" butonu |
| Workflow canvas (başlangıç) | "Bir komut yazınca ekip işe başlar" | — |
| Sağ panel (başlangıç) | "Üretilen içerik burada görünecek" | — |
| Geçmiş boş | "Henüz görev çalıştırılmadı" | — |
| Hata | "Bir şey ters gitti: {user_message_tr}" | "Tekrar dene" (retryable=true ise) |

---

## 11. Erişilebilirlik (a11y) Kontrol Listesi

- [ ] Renk körlüğü için **renk + ikon** birlikte (sadece renkle anlam verme)
- [ ] Workflow canvas için **klavye gezinme** (Tab ile düğümler arası)
- [ ] LLM mesajları **screen reader** uyumlu (aria-live="polite")
- [ ] Animasyonları kapatma seçeneği (`prefers-reduced-motion`)
- [ ] Streaming sırasında "loading" yerine **anlamlı progress** ("Logo üretiliyor...")

---

## 12. Tasarımcının Cevaplaması Gereken Sorular

### Strateji
1. **Workflow canvas mı, chat mi öncelik?**
   Saf chat (mesaj listesi) daha tanıdık ama ağacın gücünü kaybeder.
   Saf canvas daha "tech" ama mobil deneyimi zorlaştırır.
   → İkisinin **toggle ile geçişi** olmalı mı?

2. **Capabilities menüsü hep açık mı, gizleyebilir mi?**
   Power user için gizlenebilir olmalı; yeni kullanıcı için her zaman görünür yararlı.

3. **Sağ panel açılıp kapanır mı, sabit mi?**
   Üretilen içerik olmadığında değerli alan kaplar mı?

### Görsel Dil
4. **AI agent'lara avatar mı, soyut şekil mi?**
   Avatar daha eğlenceli ama kurumsal hisse zarar verebilir.

5. **Animasyon yoğunluğu nasıl?**
   Az → durağan görünür; çok → dikkat dağıtır.

### Akış
6. **Kullanıcı çalışan görevi durdurabilmeli mi?**
   Backend şu an iptal desteklemiyor — backend eklesin mi, yoksa UI sadece "arka planda devam" mı dese?

7. **Aynı anda 2+ görev paralel çalışabilmeli mi?**
   Şu an her komut yeni stream açıyor — UI tek görev odaklı mı, çoklu tab gibi mi?

---

## 13. Teslimat Kontrol Listesi

Tasarımcı bu maddeleri teslim ederse implementation hazırdır:

- [ ] Sayfa düzeni (desktop + tablet + mobile)
- [ ] Sol menü bileşeni (kategori + feature item)
- [ ] Komut kutusu (reference chip'leri dahil)
- [ ] **Workflow canvas tasarımı** (en kritik — 5 düğüm tipi, 7 state, kenarlar)
- [ ] Sağ panel (görsel, video, rapor preview)
- [ ] Reference picker modal
- [ ] Task history list item
- [ ] Empty states (5+)
- [ ] Error toast / inline error
- [ ] Loading / thinking animasyonları
- [ ] Renk paleti + token'lar (CSS variables uyumlu)
- [ ] Tipografi sistemi
- [ ] İkon seti (agent + tool + durum)

---

## 14. Ek Kaynaklar

| Dosya | Ne içerir? |
|-------|------------|
| `docs/STREAM_EVENTS_SPEC.md` | Tam JSON event şeması, TypeScript interface'leri, örnek stream |
| `docs/architecture/01-system-hierarchy.md` | Sistemin katmanları, akışları |
| `src/app/capabilities.py` | Sol menünün canlı kaynağı (versiyonlama burada) |
| `src/app/api.py` | API request/response model'leri (Pydantic) |

---

> **Son not:** Bu doküman canlıdır. Backend yeni capability ekleyince **bu dosya güncellenir**. Tasarımcı son versiyonu repo'dan çekmelidir.
