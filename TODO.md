# TODO — Ertelenen Kararlar ve Gelecek İşler

Bu dosya **karar verilmiş ama henüz uygulanmamış** işleri ve **tarihli yeniden değerlendirme** notlarını tutar. Tek kaynak — sohbet geçmişi sıfırlansa bile burada durur.

Her madde:
- **Ne?** kısa açıklama
- **Niye?** sebebi / motivasyonu
- **Ne zaman?** ne zaman ele alınacak (sıra veya tarih)

---

## 🟢 Aktif sırada (yapılacak)

### Langfuse entegrasyonu v2 (MCP'yi kırmadan)
- **Ne:** Her LLM çağrısını izleyen observability aracı. v1 denendi (PR #16), MCP ile çakıştı, geri alındı (PR #17).
- **Niye:** Maliyeti düşürmeden önce **ölçmek gerek**. LiteLLM'den önce şart.
- **Yöntem:** `@observe` decorator (manuel sarma) veya `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=httpx` env var ile httpx auto-instrumentation'ı kapatma.
- **Ne zaman:** Sıradaki teknik adım.

### LiteLLM entegrasyonu (Langfuse'den sonra)
- **Ne:** 100+ LLM sağlayıcısını tek OpenAI formatında kullanılır kılar. Basit görevleri Groq/Gemini Flash'a yıkayıp Claude'u sadece kritik işlere bırakmak.
- **Niye:** Fatura %50-80 düşebilir. Ama önce Langfuse ile baseline alınmadan denenmemeli.
- **Ne zaman:** Langfuse 1 hafta veri topladıktan sonra.

---

## 🛒 Satış Müdürü (Sales Manager) — Mimari Yol Haritası

Önceki "Sales Analyst" agent'ı **Sales Manager (Satış Müdürü)** olarak yeniden konumlandı. Şu anki versiyon iskelet: persona güncel, mevcut read tool'lar koruldu, orchestrator yeni wrapper'a bağlandı. Aşağıdaki yetenekler **bilinçli olarak** sonraki PR'lara bırakıldı.

### A. Yazma yetkileri (manager aksiyonları)
- **outreach_pause / outreach_resume** — Bekçi otomatik pause yapıyor; Müdür manuel override edebilmeli (ve gerekçe NocoDB system_settings'e yazılmalı).
- **lead_reassign(lead_id, new_owner)** — Bir lead'i Şeyma'dan başka birine devret.
- **lead_priority_set(lead_id, priority)** — Önceliğe göre sıralama.
- **auto_reply_template_update** — Auto-reply Yanıtlayıcı template'ını güncelleme.
- **outreach_daily_limit_set** — günlük outreach kapasitesini ayarla (ban riskine göre).

### B. Yatay iletişim — Meta (Reklam Uzmanı) ile ⏳ (2026-05-20 kısmi)
- ✅ **Peer handoff onerisi** instructions'ta: Müdür çıktısında "[Reklam Uzmanı'na yönlendir]" bloğu üretir → Şef `meta_agent_tool`'u tetikler. Tasarım kararı: meta_agent_tool Şef'te kalsın (peer via Şef).
- 🔜 Lead kalite geri bildirimi: Müdür "şu kaynak düşük dönüştü" derse Meta agent bütçeyi öbür gruba kaydırsın (otomasyon).

### C. Alt birim kontrolü (Avcı + DM Yanıtlayıcı)
- Otonom runner'lar şu an cron ile çalışıyor. Müdür **olay bazlı tetikleme** yapabilmeli:
  - `trigger_outreach_for_lead(lead_id)` — bir kişiye hemen outreach gönder.
  - `trigger_auto_reply_for_message(message_id)` — beklemiş mesaja hemen yanıt.
- Bu tool'lar runner'ların `_handle_single` fonksiyonlarını sarmalı.

### D. Hafıza
- `get_sales_memory(business_id)` / `update_sales_memory` — kullanıcı tercihlerini, geçmiş kararları hatırla.
- "Beyza her pazartesi sıcak lead listesi ister" → öneri olarak sun.

### E. Marka kimliği ✅ (2026-05-20)
- ~~BRAND_AWARE_PREFIX bu agent'a da ekle.~~ Çözüldü: Sales Manager artık `fetch_brand_identity` tool'una sahip + BRAND_AWARE_PREFIX instructions'a prepend edildi. Raporlar marka tonuna göre yorumlanabilir.

### F. Trend / karşılaştırma
- `compare_periods(metric, from1, to1, from2, to2)` — bu hafta vs geçen hafta otomatik karşılaştırma.

### G. `outreach_health` ↔ `get_guardian_status` çakışmasını çöz ✅ (2026-05-20)
- ~~Bekçi pause durumunu iki ayrı tool döndürüyor.~~ Çözüldü: `outreach_health` artık `get_guardian_status` sonucunu sarmalıyor (tek SoT). Geri uyumlu API (paused/active/reason) korundu.

### H. Sales Analyst tamamen kaldır
- Eski `sales_analyst` registry kaydı + factory + wrapper hâlâ duruyor (deprecate ama silinmedi). REST API + portal hazır olduğunda tamamen kaldırılır.
- **TODO 6 ay** sonra: Sales Analyst kullanımı sıfıra inerse silinir.

---

## 🔌 REST API + Portal Render (Sales Manager için)

Hedef: Sales raporlarının **kullanıcıya doğrudan portal butonu** ile sunulması. LLM'den geçmeden, ucuz, hızlı, deterministik.

### Mimari hedef
```
Portal (mind-id, Next.js)
   └─► /api/sales/* (Next.js proxy)
        └─► mind-agent /sales/* (FastAPI, REST)
             └─► reporting_tools (mevcut Python kodu)
                  └─► NocoDB
```

### Yapılacak adımlar
1. `mind-agent/src/app/sales_api.py` — FastAPI router, mevcut `_impl` fonksiyonlarını HTTP olarak expose et.
2. Endpoint'ler:
   - `GET /sales/leads/count?asama=Sicak&kaynak=Meta+Ads&date_from=&date_to=`
   - `GET /sales/leads/list?asama=&sort=&limit=`
   - `GET /sales/leads/funnel?date_from=&date_to=`
   - `GET /sales/leads/channel-breakdown?date_from=&date_to=`
   - `GET /sales/leads/stale?asama=&days=`
   - `GET /sales/leads/timeline?ad_soyad=&limit=`
   - `GET /sales/digest/daily?date=`
   - `GET /sales/outreach/status`
   - `GET /sales/outreach/health`
   - `GET /sales/auto-reply/status`
3. Auth: Bearer token (env var, mind-id ile paylaşılan secret).
4. `mind-id/app/api/sales/[...path]/route.ts` — proxy route, server-side, token saklı.
5. `mind-id/app/businesses/[id]/sales/page.tsx` — Sales dashboard sayfası, recharts ile chart.
6. **Doğal dil katmanı şu an kapalı** — Sales Manager LLM hâlâ var ama portal artık ona ihtiyaç duymadan rapor üretir. LLM geri eklenirse "intent router" rolünde kullanılır.

### NocoDB → mind-agent webhook (event-driven mimari)
- Avcı + DM Yanıtlayıcı şu an cron polling yapıyor (her saat). Event-driven daha verimli.
- NocoDB webhook → `mind-agent /webhook/nocodb` → ilgili lob tetiklenir.
- İlk hedef: yeni lead eklendiğinde DM Yanıtlayıcı'yı anında çağır.
- TODO: webhook signature doğrulama (HMAC), idempotency key (aynı olay 2 kere gelirse).

---

## 🟡 Pazarlamacı (Marketing Agent) İyileştirmeleri

### #2 — Caption örnek bloğu (yapıldı, PR #18) ✅
### #4 — Best-time-to-post (yapıldı, PR #18) ✅

### A/B test desteği
- **Ne:** Pazarlamacı iki farklı caption üretsin, hangi etkileşim aldıysa kazananı not etsin.
- **Niye:** Şu an tek caption deniyor, en iyiyi bulma şansı yok.
- **Ne zaman:** Langfuse hazır olduktan sonra (ölçülebilmesi için).

### DM Yanıtlayıcı ↔ Pazarlamacı bağlantısı
- **Ne:** Ortak Firestore event log koleksiyonu. DM Yanıtlayıcı sıcak lead'i konuşunca, Pazarlamacı yeni post atınca → kuyruğa olay yazılır.
- **Niye:** Otonom loblar tek yönlü çalışıyor; şef + diğer agentlar haberdar olmuyor.
- **Ne zaman:** Pazarlamacı + Sales Manager iyileştirmeleri sonrası.

---

## 🔵 Mimari / Departman İşleri

### Faz C — Marka kimliği (yapıldı, PR #20) ✅
Image / Video / Marketing artık brand_identity okuyor.

### TODO: Faz C-2 — Brand Synthesis Agent'ı Şef'e bağla
- Şu an Brand Synthesis Agent registry'de ama orchestrator çağırmıyor.
- Şef'e bir "marka kimliği oluştur" niyeti gelirse otomatik çağırsın.

### Art Direktör katmanı
- **Ne:** Pazarlamacı'nın altına bir "Art Direktör" lobu — görsel/video brief'ini yapılandıran (JSON çıktılı) küçük model.
- **Niye:** Tutarlılık + retry azaltma.
- **Ne zaman:** Faz C tamamlandı; tekrar değerlendir — brand_identity zaten doğrudan okunduğu için belki gereksiz.

### `post_on_instagram` tool'unu Şef listesinden çıkar ✅ (2026-05-20)
- ~~Şef bu tool'a teknik olarak erişebiliyor.~~ Çözüldü: tüm `post_on_*` tool'ları (instagram/tiktok/youtube/linkedin + carousel'ler) Şef'in `get_orchestrator_tools()` return listesinden çıkarıldı. Marketing/Video agent'lar üzerinden delege edilir. Defense-in-depth: instruction yasağı + dosya erişimi yok.

---

## ⏰ Tarihli Yeniden Değerlendirme

### 2026-08-20 — Grafana yeniden değerlendir
- Şu an gerekli değil (Langfuse LLM tarafını izleyecek). Backend servis sayısı 3'ü aşarsa düşün.

### 2026-11-20 — Sales Analyst dosyalarını sil
- 6 ay sonra `sales_analyst_agent.py` + `sales_analyst_wrapper` + `SALES_ANALYST_INSTRUCTIONS` + registry alias kaldırılabilir mi kontrol et.

---

## 📚 Referans / Bookmark (entegrasyon yok)

### public-apis (https://github.com/public-apis/public-apis)
- **Ne:** Ücretsiz API listesinin curated README'si.
- **Kullanım:** Yeni özellik için bedava API aranınca buraya bak. Kod entegrasyonu yok.

---

## ❌ Değerlendirildi — Kullanılmayacak

### Ruflo (https://github.com/ruvnet/ruflo)
- **Niye atlandı:** TypeScript + Rust stack. Python projemize entegrasyonu 3 kat karmaşıklık, sıfır kazanç. Mind-agent zaten OpenAI Agents SDK ile orchestration yapıyor.

### OpenClaw (https://github.com/openclaw/openclaw)
- **Niye atlandı:** Tek kullanıcı kişisel asistan + local-first. Sen B2B multi-tenant ajansısın. WhatsApp/IG köprüsü zaten Zernio'da var. Kullanılsa iki çakışan sistem olur.
