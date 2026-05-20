# TODO — Ertelenen Kararlar ve Gelecek İşler

Bu dosya **karar verilmiş ama henüz uygulanmamış** işleri ve **tarihli yeniden değerlendirme** notlarını tutar. Tek kaynak — sohbet geçmişi sıfırlansa bile burada durur.

Her madde:
- **Ne?** kısa açıklama
- **Niye?** sebebi / motivasyonu
- **Ne zaman?** ne zaman ele alınacak (sıra veya tarih)

---

## 🟢 Aktif sırada (yapılacak)

### Langfuse entegrasyonu (LiteLLM'den önce)
- **Ne:** Her LLM çağrısını izleyen observability aracı. Self-hosted, ücretsiz.
- **Niye:** Maliyeti düşürmeden önce **ölçmek gerek** — baseline olmadan optimizasyon körü körüne. LiteLLM koymadan önce şart.
- **Ne zaman:** Sıradaki iş. Plan onaylanınca başlanır.

### LiteLLM entegrasyonu (Langfuse'den sonra)
- **Ne:** 100+ LLM sağlayıcısını tek OpenAI formatında kullanılır kılar. Basit görevleri Groq/Gemini Flash'a yıkayıp Claude'u sadece kritik işlere bırakmak.
- **Niye:** Fatura %50-80 düşebilir. Ama önce Langfuse ile baseline alınmadan denenmemeli (kalite kaybını fark etmeyebiliriz).
- **Ne zaman:** Langfuse 1 hafta veri topladıktan sonra.

---

## 🟡 Pazarlamacı (Marketing Agent) İyileştirmeleri

### #4 — Best-time-to-post
- **Ne:** Pazarlamacı içerik planı yaparken veya kullanıcı saat belirtmediğinde Zernio MCP'nin `get_best_time_to_post` tool'unu çağırsın.
- **Niye:** Şu an saat tahminle seçiliyor. Zernio'da hazır tool var, sadece talimat güncellemesi gerek (kod yok).
- **Ne zaman:** Langfuse sonrası — etkisini ölçebilmek için.

### #2 — Caption örnek bloğu
- **Ne:** `src/agents/instructions/marketing.py` içindeki iyi/kötü caption örneklerini genişlet. Şu an Şef'tekinden daha kısa.
- **Niye:** Az örnek = tutarsız caption kalitesi.
- **Ne zaman:** Küçük PR, ne zaman olsa olur.

### A/B test desteği
- **Ne:** Pazarlamacı iki farklı caption üretsin, hangi etkileşim aldıysa kazananı not etsin.
- **Niye:** Şu an tek caption deniyor, en iyiyi bulma şansı yok.
- **Ne zaman:** Faz C (brand_identity entegrasyonu) sonrası.

### DM Yanıtlayıcı ↔ Pazarlamacı bağlantısı
- **Ne:** Ortak Firestore event log koleksiyonu. DM Yanıtlayıcı sıcak lead'i konuşunca, Pazarlamacı yeni post atınca → kuyruğa olay yazılır.
- **Niye:** Otonom loblar (DM, Avcı, Takipçi, Bekçi) şu an tek yönlü çalışıyor; şef bunlardan haber alamıyor.
- **Ne zaman:** Pazarlamacı iyileştirmeleri sonrası.

---

## 🔵 Mimari / Departman İşleri

### Faz C — Marka kimliğini agent'lara bağla
- **Ne:** Image / Video / Marketing agent'ları Firestore'dan `brand_identity/v1` okusun (`fetch_brand_identity` tool'u).
- **Niye:** Şema (Faz A) + Brand Synthesis Agent (Faz B1, PR #10) tamamlandı ama agent'lar henüz **okumuyor**. Talimat dosyalarındaki jenerik stili kullanıyorlar. Bu yapılmadan tutarlı görsel/video/caption üretimi tam çalışmaz.
- **Ne zaman:** Pazarlamacı iyileştirmelerinden sonra.

### Bekçi'yi Şef akışına bağla
- **Ne:** Bekçi (`src/agents/guardian/`) şu an ayrı çalışıyor. Şef bir aksiyon almadan önce Bekçi'ye "onay verir misin?" diye sorsun.
- **Niye:** Kural ihlali en pahalı hata. Küçük PR, yüksek değer.
- **Ne zaman:** Faz C sonrası.

### Art Direktör katmanı
- **Ne:** Pazarlamacı'nın altına bir "Art Direktör" lobu — görsel/video brief'ini yapılandıran (JSON çıktılı) küçük model.
- **Niye:** Tutarlılık + retry azaltma (token tasarrufu). Carousel/kampanya gibi çok-asset işlerde değer üretir.
- **Ne zaman:** Faz C tamamlanırsa belki gereksiz olur — önce onu yap, sonra karar ver.

### `post_on_instagram` tool'unu Şef listesinden çıkar
- **Ne:** Şu an Şef bu tool'a teknik olarak erişebiliyor (talimatla yasak ama dosyada erişim var). `orchestrator_tools`'tan tamamen kaldır.
- **Niye:** Önceki oturumdan devir — güvenlik için temizlik.
- **Ne zaman:** İlk uygun fırsatta küçük PR.

---

## ⏰ Tarihli Yeniden Değerlendirme

### 2026-08-20 — Grafana yeniden değerlendir
- **Bağlam:** Grafana endüstri-standart dashboard aracı, ücretsiz. Şu an gerekli değil çünkü:
  - Langfuse LLM tarafını izleyecek
  - Backend servis sayısı az (mind-agent + mind-id)
- **Yeniden değerlendirme tetikleyicisi:** Backend servis sayısı 3'ü aşarsa veya log/metrik karmaşası başlarsa.

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
