# Remotion Araştırması ve Entegrasyon Planı

**Tarih:** 2026-04-11
**Durum:** 🟡 Ertelendi — önce Claude Code üzerinden kullanıcı denemesi yapılacak
**Tetikleyen:** Bir kullanıcı [remotion-dev/remotion](https://github.com/remotion-dev/remotion) repo'sunu paylaşıp agent sistemimize alternatif bir video üretim motoru olarak önerdi.

---

## Karar (2026-04-11)

**Şimdilik agent sistemine entegre edilmeyecek.** Gerekçe:

- Remotion prompt-to-video değil, template-to-video — mevcut Veo/Kling/HeyGen ile aynı kategoride değil
- Gerçek değeri belli olana kadar altyapı yatırımı (yeni servis, Docker image, template katalogu) gereksiz
- Önce kullanıcı [Remotion + Claude Code local akışı](https://www.remotion.dev/docs/ai/claude-code) ile deneme yapsın
- Kullanıcı değerli bulursa, aşağıdaki plana dönülüp entegrasyon yapılacak

**Yeniden değerlendirme tetikleyicileri:**
- Kullanıcı Claude Code + Remotion ile anlamlı çıktılar üretmeye başlarsa
- Mevcut engine'lerin (Veo/Kling/HeyGen) yetersiz kaldığı net bir kullanım ortaya çıkarsa (özellikle **altyazı/logo/brand overlay** post-processing ihtiyacı)
- Template-driven videolara (quote card, slideshow, stats report) somut talep gelirse

---

## 1. Remotion Nedir?

React ile programatik video üretim kütüphanesi. **Generative AI değil** — compositional.

**Temel akış:**
1. React componenti yaz (`<Scene>`, `<Subtitle>`, `<Logo/>` vb.)
2. `Composition` tanımla: `id`, `durationInFrames`, `fps`, `width`, `height`, default props
3. `@remotion/renderer` headless Chrome açar, frame frame çizer, FFmpeg ile MP4'e birleştirir
4. Aynı componente farklı `inputProps` geçerek aynı template'i farklı verilerle render et

**Teknik notlar:**
- CPU-heavy (Chrome + FFmpeg)
- Alpine Linux kullanma — Rust bileşenleri yüzünden Debian'dan %35 yavaş
- Docker'da `/dev/shm` büyütmek gerekir (default 64MB yetersiz)
- `bundle()` pahalı (webpack) → uzun ömürlü servislerde cache'lenmeli
- Render pipeline: `bundle()` → `selectComposition()` → `renderMedia()`

## 2. Kullanıcının Anlattığı Akış (Doğrulandı)

Kullanıcı repoyu indirip Claude Code'a "şöyle bir video istiyorum" dediğinde aslında **resmî** bir akışı kullanıyor:

1. `npx create-video@latest` — local proje açılır
2. Kurulumda "Install Skills" seçilir → `.claude/` altına **Remotion Agent Skill** kurulur
3. `cd my-video && claude` — Claude Code skill'i okur, Remotion API'sini "bilir"
4. Doğal dil → Claude React componentleri yazar/düzenler
5. `npm run build` veya `npx remotion render` → local'de MP4 çıkar

Bu bir **developer loop**: tek kullanıcı, tek makina, tek proje. Bir prompt → bir video DEĞİL; "bu template'i şu metne göre değiştir, sonra render et" döngüsü.

## 3. Bu Akış Neden Bizim Agent Sistemine Uymuyor?

Bizim kullanımımız çok farklı:
- Orchestrator task alır → sub-agent tool çağırır → video URL döner (stateless, HTTP)
- Render makinasında Claude Code yok, React yok, bundle yok
- Her `business_id` için paralel render'lar olabilir (multi-tenant)
- Sonuç Firebase Storage'a düşmeli

Yani biz "Claude Code local'de Remotion kullansın" değil, **bir render servisini HTTP'den çağırmak** istiyoruz.

## 4. Remotion'un Bizim Stack'te Gerçek Değeri

**Önemli içgörü:** Remotion'u Veo/Kling/HeyGen'e rakip değil, **tamamlayıcı** olarak konumlandırmak gerek.

### Güçlü olduğu senaryolar
- Veo/Kling'den dönen ham videoya **altyazı + logo + CTA overlay** eklemek
- Business fotoğraflarından **slideshow/carousel reel** (Ken Burns efekti + müzik)
- Instagram metriklerinden **animasyonlu grafikli rapor videosu**
- SEO raporundan **animasyonlu bullet point Shorts**
- **Before/after** ürün karşılaştırmaları
- **Quote card** animasyonları

### Zayıf olduğu senaryolar
- "Bir kedi uçuyor" gibi generative sahneler (yapamaz — AI değil)
- Serbest biçimli, her seferinde farklı kompozisyon isteyen videolar
- Gerçekçi insan animasyonu (HeyGen'in alanı)

### Kritik fark
Veo'ya prompt yazarak "ekrana şu yazı çıksın" dersek yanlış yazı çıkarıyor. Remotion deterministik ve piksel-perfect — **text/brand** işinde çok daha iyi.

---

## 5. Entegrasyon Seçenekleri (İleride Gerekirse)

### Seçenek A: Remotion Lambda (AWS)
- **Avantaj:** En hızlı (dağıtık render), production-ready, en ucuz per-render
- **Dezavantaj:** AWS hesabı gerek — stack'imiz GCP'de. Yeni cloud provider = operasyonel yük
- **Python entegrasyon:** REST yok; `boto3` ile Lambda invoke → S3 URL → Firebase'e kopyala

### Seçenek B: Remotion Cloud Run (GCP, resmî)
- **Durum:** ❌ **Alpha, maintained değil** ([resmî doküman](https://www.remotion.dev/docs/cloudrun/))
- **Karar:** Production'da kullanma

### Seçenek C: Self-hosted Docker servisi (Cloud Run / GCE) — **ÖNERİLEN**
- **Ne:** Kendimiz küçük Node.js HTTP server yazarız: `POST /render {template, props}` → `{video_url}`. İçeride `@remotion/renderer` çağırır, sonucu Firebase Storage'a yükler. Docker image Cloud Run'a deploy edilir.
- **Avantaj:**
  - Stack'imizle %100 uyumlu (GCP + Firebase)
  - Template versioning (v1.x.x tag)
  - Python tarafı sadece `requests.post(...)`
  - Mevcut v1.18.0 Docker akışımıza doğal oturur
- **Dezavantaj:**
  - Operasyonel yük bizde (Chrome shm size, FFmpeg, font yönetimi)
  - Lambda kadar hızlı değil (paralel split yok)
  - Uzun videolarda Cloud Run 60dk timeout riski

---

## 6. Önerilen Mimari (Entegrasyon Kararı Alınırsa)

### Kritik yaklaşım farkı

Template'ler **katalog** olarak ayrı repo'da tutulur. Agent React **yazmaz** — hazır template ID'leri ve prop schema'ları arasından **seçim yapar**.

Bu yaklaşım şunları sağlar:
- Bundle süresi sıfır (önceden cache'li)
- Agent'ın kod yazarken yapacağı hatalar riski yok
- Attack surface yok (arbitrary React code execution yok)
- Template'ler versionlanabilir

### Mimari Diyagramı

```
┌─────────────────────────────────────────────────┐
│  agents-sdk (Python, mevcut)                    │
│                                                 │
│  Video Agent                                    │
│   └─ generate_video_remotion(                   │
│        template_id="product_showcase_v1",       │
│        input_props={...},                       │
│        business_id=...,                         │
│        file_name=...)                           │
│       ↓                                         │
│  src/infra/remotion_client.py                   │
│       ↓ HTTP POST                               │
└─────────────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────┐
│  remotion-render-service (YENİ repo, Node.js)   │
│                                                 │
│  Express/Fastify HTTP server                    │
│    POST /render                                 │
│      → @remotion/renderer (bundle cache'li)     │
│      → MP4 üret                                 │
│      → Firebase Storage'a yükle                 │
│      → { video_url, duration, size } dön        │
│                                                 │
│  src/templates/                                 │
│    ├─ product_showcase_v1/                      │
│    ├─ quote_card_v1/                            │
│    ├─ slideshow_v1/                             │
│    └─ stats_report_v1/                          │
│                                                 │
│  Dockerfile (node:22-bookworm-slim)             │
│   ↓                                             │
│  Cloud Run (us-central1)                        │
└─────────────────────────────────────────────────┘
```

### Eklenecek Python Tarafı

- `src/infra/remotion_client.py` → HTTP POST wrapper, structured error handling
- `src/tools/video_tools.py` → `generate_video_remotion`, `list_video_templates` tool'ları
- Template katalogu: ya hard-code instruction'da ya da dinamik `list_video_templates()` tool'u ile

### CLAUDE.md Kural #7 gereği güncellenecek yerler

Tool eklendikten sonra MUTLAKA:
- `src/tools/video_tools.py` → `get_video_tools()` return listesi
- `src/agents/instructions/video.py` → `## YOUR TOOLS` listesi (tool sayısı)
- `src/agents/instructions/video.py` → `## TOOL SELECTION` bölümü (ne zaman Remotion, ne zaman Veo/Kling/HeyGen)
- `src/agents/instructions/orchestrator.py` → video keyword routing ve NOTE satırları
- `CLAUDE.md` → Ana Tools özetinde Image/Video satırı

---

## 7. Karar Bekleyen Açık Sorular

Entegrasyona geri dönülürse şunlar netleştirilmeli:

1. **Kullanım senaryosu ne?**
   - (a) Veo'nun alternatifi: template katalogu, agent ID + prop seçer
   - (b) Post-processing: `add_branding_to_video(video_url, ...)` tarzı, Veo çıktısını süsler
   - (c) Her ikisi de
2. **Template'leri kim yazar?**
   - (a) İlk 4-5 template'i biz yazarız (product_showcase, quote_card, slideshow, stats_report)
   - (b) Kullanıcı Claude Code + Remotion Skill ile yazar, biz servisi hazırlarız
   - (c) Kullanıcılar kendi template'lerini upload eder (karmaşık — bundle izolasyonu + güvenlik)
3. **Cloud Run vs Lambda?**
   - Öneri: Cloud Run + self-host (stack uyumu)
   - Hız kritikse Lambda ama AWS hesabı yükü var
4. **Repo yapısı:**
   - (a) Ayrı repo `remotion-render-service` — temiz, farklı dil/CI
   - (b) `agents-sdk/services/remotion/` altında alt-klasör — tek repo, iki versiyon yönetmek gerek
5. **İlk PoC kapsamı:**
   - Tek template (quote_card_v1)
   - Local Docker'da çalışan servis
   - Tek tool `generate_video_remotion`
   - Yeşil yanarsa Cloud Run'a deploy + katalog genişletme

---

## 8. Kaynaklar

- [Remotion Docs — Server-Side Rendering](https://www.remotion.dev/docs/ssr)
- [Remotion Docs — Rendering using SSR APIs](https://www.remotion.dev/docs/ssr-node)
- [Remotion Docs — Dockerizing a Remotion app](https://www.remotion.dev/docs/docker)
- [Remotion Docs — SSR options comparison](https://www.remotion.dev/docs/compare-ssr)
- [Remotion Docs — Claude Code ile Prompt](https://www.remotion.dev/docs/ai/claude-code)
- [Remotion Docs — Lambda overview](https://www.remotion.dev/docs/lambda)
- [Remotion Docs — How Lambda Works](https://www.remotion.dev/docs/lambda/how-lambda-works)
- [Remotion Docs — Cloud Run (Alpha — kullanma)](https://www.remotion.dev/docs/cloudrun)
- [Remotion Docs — renderMediaOnCloudrun](https://www.remotion.dev/docs/cloudrun/rendermediaoncloudrun)
- [GitHub remotion-dev/remotion](https://github.com/remotion-dev/remotion)
- [Scott Havird — Remotion + Docker template](https://www.scotthavird.com/blog/remotion-docker-template/)
- [CrePal — Remotion Docker operasyonel notlar](https://crepal.ai/blog/aivideo/blog-how-to-run-remotion-in-docker/)
