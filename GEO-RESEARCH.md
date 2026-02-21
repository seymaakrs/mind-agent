# GEO (Generative Engine Optimization) - Kapsamli Arastirma Raporu

**Tarih:** 2026-02-08
**Amac:** GEO kavraminin anlasilmasi, en iyi uygulamalarin belirlenmesi ve agents-sdk projesine entegrasyon icin temel olusturulmasi.

---

## 1. GEO Nedir?

**Generative Engine Optimization (GEO)**, dijital icerikleri ve online varliginizi **AI tabanli arama motorlarinin urettigi yanitlarda** gorunur kilmak icin optimize etme pratigi. Geleneksel SEO arama sonuc sayfalarinda (SERP) ust siralarda yer almayi hedeflerken, GEO su platformlarda **alintilanma, bahsedilme ve one cikarilmayi** hedefler:

- **Google AI Overviews** (eski adi SGE)
- **ChatGPT Search**
- **Perplexity AI**
- **Microsoft Copilot / Bing Chat**
- **Google Gemini**
- **Claude (Anthropic)**

### Temel Istatistikler (2025-2026)

| Metrik | Deger | Kaynak |
|--------|-------|--------|
| AI yonlendirmeli oturum artisi (2025 H1) | **+527%** | Sektor raporlari |
| AI ziyaretcilerinin niteligi (geleneksele gore) | **4.4x daha nitelikli** | Donusum verileri |
| Gartner tahmini: 2026'da AI odakli aramalar | **Tum aramalarin %25'i** | Gartner |
| GEO Hizmetleri Pazari (2024) | **886 milyon $** | Pazar arastirmasi |
| GEO Hizmetleri Pazari tahmini (2031) | **7.318 milyar $ (%34 CAGR)** | Pazar arastirmasi |
| GEO stratejisi olmayan markalar | **%47** | Sektor anketi |
| AI Overview sorgularinda sifir-tik orani | **%83** | Arama analitikleri |
| AI yonlendirme trafik payi (2025 Q2, ABD masaustu) | **%5.6** (Haziran 2024'te %2.48'den iki katina cikti) | Trafik verileri |

---

## 2. GEO vs SEO - Temel Farklar

| Boyut | Geleneksel SEO | GEO |
|-------|----------------|-----|
| **Hedef** | Arama sonuc sayfalari (SERP) | AI uretimi yanitlar |
| **Amac** | Bulunmak (siralama) | One cikarilmak (alintilanma) |
| **Birincil sinyal** | Anahtar kelimeler + backlinkler | Varlik otoritesi + marka bahsi |
| **Icerik formati** | Anahtar kelime optimize sayfalar | Cevap-once, veri-yogun, yapilandirilmis |
| **Basari metrigi** | Pozisyon 1-10, CTR, trafik | Alintilanma orani, ses payi, marka gorunurlugu |
| **Link insasi** | Backlinkler kritik | Baglantisiz bahisler de sayilir |
| **Otorite** | Domain Authority (DR/DA) | Konu otoritesi + Knowledge Graph varligi |
| **Guncellik** | Faydali ama kritik degil | Kritik (ozellikle ChatGPT, Perplexity icin) |
| **Schema** | Zengin snippet'lar icin faydali | AI anlamasi icin kritik (~%10 etki) |
| **Icerik uzunlugu** | Niyete gore degisir | Uzun = daha fazla alintilanma (2,900+ kelime = 5+ alinti) |
| **Kullanici etkilesimi** | Web sitesine tiklanma | Yanit AI yaniti icinde tuketilir (sifir-tik) |
| **Rekabet** | Rakiplere karsi anahtar kelimeler | Rakiplere karsi konular ve promptlar |
| **Anahtar kelime doldurma** | Cezalandirilir | Aktif olarak zararli |
| **Icerik icinde kaynak gosterme** | Iyi uygulama | %30-40 gorunurluk artisi |
| **Icerik icinde istatistik** | Iyi uygulama | %30-40 gorunurluk artisi |

### Tamamlayici Yapi

GEO ve SEO **birbirini dislamaz**. Guclu SEO (ilk 10'da siralama) AI alintilanma sansini arttirir (Google AI Overview alintilarinin %76'si ilk 10'dan gelir). GEO, SEO'nun uzerine AI tuketimine ozel ek stratejilerle bir katman ekler.

---

## 3. AI Arama Motorlari Nasil Calisir (Kaynak Secimi ve Alintilanma)

Her AI platformunun farkli alintilanma kaliplari vardir. **ChatGPT, Perplexity ve Google AI Overviews arasinda alintilanlan kaynaklarin yalnizca %12'si ortusur** - bu da platforma ozel optimizasyonu kritik kilar.

### 3.1 Google AI Overviews

- **Retrieval-Augmented Generation (RAG)** kullanir
- Alt sorgular ("fan-out") olusturarak alt konularda destekleyici sayfalar getirir
- **Alintilamalarin %76'si** organik sonuclarda ilk 10'da siralanan sayfalardan gelir
- **Alintilamalarin %14.4'u** ilk 100 disindaki URL'lerden gelir (istisnalar var)
- Yanit basina ortalama **~8 kaynak** alintilir
- **Reddit (%2.2)** ve kullanici uretimi icerigi agir bicimde tercih eder
- **Cikarilabilirlik** anahtar: listeler, tablolar, SSS'ler daha iyi performans gosterir
- Yerel isletme aramalarinin **%40.2'sinde** gorunur

### 3.2 ChatGPT Search

- RAG sistemi: sorgulari alt sorgulara boler, web indeksinden getirir, sentezler
- **En cok alintilanlan kaynak:** Wikipedia (%7.8-16.3, bazi analizlerde %43'e kadar)
- **Domain otorite esigi:** 32,000+ referring domain'e sahip siteler 3x daha fazla alintilaniyor
- **Icerik uzunlugu onemli:** 2,900+ kelimelik sayfalar ortalama 5+ alintilanirken, 800 altindakiler ~3
- **En guclu guncellik tercihi:** En cok alintilanlan sayfalarin %76.4'u son 30 gunde guncellenmis
- Uzman girdisi olan sayfalar ortalama 4+ alinti, olmayanlar ~2
- ChatGPT, AI yonlendirme trafiginin ~%90'ini olusturur

### 3.3 Perplexity AI

- **RAG** mimarisi: gercek zamanli web iceriginden dinamik yanitlar olusturur
- Birincil secim faktorleri: **Guvenilirlik > Guncellik > Ilgililik > Cikarilabilirlik**
- Icerigi gunluk indeksler (tum platformlar arasinda en guclu guncellik sinyali)
- **YouTube'u (%16.1)** kaynak olarak tercih eder
- Teknik erisim kritik: PerplexityBot robots.txt'de izin verilmeli
- Cevap-once bolumler, net basliklar, kisa paragraflar, listeler/tablolar onceliklendirilir

### 3.4 Tum Platformlarda En Cok Alintilanlan Icerik Formati

**AI alintilarinin ucte biri karsilastirmali liste yazilarindan gelir** - bu, tum AI platformlarinda en etkili icerik formatidir.

### 3.5 Platform Tercihleri Ozeti

| Platform | Tercih Edilen Icerik | En Iyi Kaynak Tipi |
|----------|---------------------|---------------------|
| Google AI Overviews | KUI (Reddit, Quora) | Reddit (%2.2) |
| ChatGPT | Ansiklopedik, olgusal | Wikipedia (%16.3) |
| Perplexity | Video, guncel icerik | YouTube (%16.1) |
| Tum platformlar | Karsilastirmali listeler | 3 alintilamadan 1'i |

---

## 4. GEO Siralama Faktorleri

### 4.1 Platformlar Arasi Siralama Faktorleri (Onem Sirasina Gore)

| Faktor | Etki | Notlar |
|--------|------|--------|
| **Icerik derinligi (kelime sayisi)** | En guclu pozitif korelasyon | 2,900+ kelime = ChatGPT'de 5+ alinti |
| **Marka otorite sinyalleri** | Backlinklerden daha guclu | Bahisler, markali anchor'lar, arama hacmi |
| **Icerik guncelligi** | ChatGPT ve Perplexity icin kritik | ChatGPT alintilarinin %76.4'u son 30 gunden |
| **Yapisal cikarilabilirlik** | Yuksek | Listeler, tablolar, SSS, net basliklar |
| **Schema markup** | Perplexity'de ~%10 katki | FAQPage, Organization, Article, Product |
| **Domain otoritesi (geleneksel)** | Orta | 32K+ referring domain = ChatGPT'de 3x daha olasi |
| **Google siralama pozisyonu** | Guclu korelasyon | AI Overview alintilarinin %76'si ilk 10'dan |
| **Uzman yazarlik** | Onemli | Uzman girdisi = 2x daha fazla alinti |
| **Istatistik veri yogunlugu** | %30-40 gorunurluk artisi | Princeton calismasina gore |
| **Kaynak gosterme** | %30-40 gorunurluk artisi | Princeton calismasina gore |

### 4.2 Negatif Faktorler

- Anahtar kelime doldurma (GEO'da aktif olarak zararli)
- Odeme duvari, giris veya sadece JavaScript ile render edilen icerik
- robots.txt'de AI tarayicilarini engelleme
- Platformlar arasi tutarsiz marka bilgisi
- Ince icerik (800 kelimenin altinda)

---

## 5. GEO En Iyi Uygulamalar ve Stratejiler

### 5.1 Icerik Yapisi

- **Cevap-once format:** Her bolumun ilk 40-60 kelimesinde dogrudan yanitlar
- **Veri yogunlugu:** Her 150-200 kelimede istatistik
- **Kisa paragraflar:** Maksimum 2-3 cumle
- **Madde isareti ve numarali listeler** uzun paragraflar yerine
- **Her madde ozlu bir sonucla biter**
- **Net basliklar ve alt basliklar** (semantik HTML5: H1-H6)
- **SSS bolumleri** dogal sorgu kaliplarina uyan dogrudan S&C ciftleriyle
- **Karsilastirmali listeler** (tum AI platformlarinda en cok alintilanlan format)

### 5.2 Alintilanmaya Deger Icerik (Princeton Calismasi Bulgulari)

AI gorunurlugunu artirmak icin en iyi 3 strateji:
1. **Kaynak Goster:** Guvenilir, yetkili kaynaklardan alinti ekle → **%30-40 gorunurluk artisi**
2. **Istatistik Ekle:** Niteliksel ifadeleri niceliksel verilerle degistir → **%30-40 gorunurluk artisi**
3. **Alinti Ekle:** Uzmanlardan ilgili alintilar ekle → **%30-40 gorunurluk artisi**

### 5.3 Otorite Insasi

- **Marka bahisleri** (baglantisiz bahisler de sayilir) birden fazla yetkili kaynak boyunca
- **Varlik netiligi:** Marka, hizmetler, kisiler icin tum platformlarda tutarli terminoloji
- **E-E-A-T:** Kimlik bilgilerini goster, veri kaynaklarini belirt, guvenilir kaynaklara baglanti ver
- **Konu otoritesi:** Kapsamli kapsama ile konu kumelenmesi
- **Knowledge Graph varligi:** AI'nin isletmeniz hakkinda net bir varlik anlayisi olusturmasina yardim edin

### 5.4 Icerik Guncelligi

- Net yayin ve guncelleme tarihlerini goster
- Surekli icerigi duzenli olarak yenile (en az yillik)
- Icerik takvimleriyle inceleme dongulerini takip et
- ChatGPT en guclu guncellik tercihine sahip (%76.4 alintilanan sayfa son 30 gun)
- Perplexity gunluk indeksler

### 5.5 Coklu Ortam Icerigi

- Grafikler, videolar, iyi optimize edilmis gorseller alintilanma sansini arttirir
- Aciklayici gorsel alt metni, altyazilar ve cevreleyen icerik
- Gemini ve Perplexity coklu ortam aramaya agir yatirim yapiyor

---

## 6. Teknik Uygulama

### 6.1 robots.txt - AI Tarayicilari Yapilandirmasi

```
# AI tarayicilarina izin ver (GEO icin)
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Perplexity-User
Allow: /

User-agent: YouBot
Allow: /

User-agent: Applebot-Extended
Allow: /
```

### 6.2 Schema Markup (JSON-LD) - GEO icin Oncelikli Tipler

| Schema Tipi | Amac | GEO Etkisi |
|-------------|------|------------|
| **Organization** | Marka varlik tanimi | Knowledge graph icin kritik |
| **Article** | Icerik tipi sinyalleri | Yuksek - AI'nin icerigi anlamasina yardimci olur |
| **FAQPage** | S&C formati | Cok yuksek - en cikarilabilir format |
| **Person** | Yazar uzmanligi | E-E-A-T sinyalleri |
| **Product** | Urun bilgisi | Islemsel sorgular |
| **HowTo** | Adim adim talimatlar | Surec sorgulari |
| **LocalBusiness** | Yerel varlik bilgisi | Yerel GEO |
| **WebPage** | Sayfa baglami | Genel anlayis |
| **Review** | Guven sinyalleri | Guvenilirlik artisi |
| **BreadcrumbList** | Site hiyerarsisi | Navigasyon anlayisi |

### 6.3 Organization Schema Ornegi (GEO icin)

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Isletme Adi",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "description": "Net, ozlu isletme aciklamasi",
  "foundingDate": "2020",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Istanbul",
    "addressCountry": "TR"
  },
  "sameAs": [
    "https://www.instagram.com/business",
    "https://www.linkedin.com/company/business"
  ],
  "knowsAbout": ["konu1", "konu2", "konu3"]
}
```

### 6.4 LocalBusiness Schema Ornegi

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Isletme Adi",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Ornek Cad. No:123",
    "addressLocality": "Istanbul",
    "addressRegion": "Istanbul",
    "postalCode": "34000",
    "addressCountry": "TR"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 41.0082,
    "longitude": 28.9784
  },
  "telephone": "+90-xxx-xxx-xxxx",
  "openingHoursSpecification": [],
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "reviewCount": "127"
  }
}
```

### 6.5 llms.txt Dosyasi (Gelisen Standart)

Jeremy Howard tarafindan Eylul 2024'te onerilen bir standart. Web sitesinin kokundeki `/llms.txt` dosyasinda Markdown formatinda yapilandirilmis bir genel bakis sunar.

```markdown
# Isletme Adi

> Isletmenin kisa aciklamasi

## Ana Sayfalar
- [Hakkimizda](https://example.com/hakkimizda): Sirket genel bakisi
- [Hizmetler](https://example.com/hizmetler): Hizmet sunumlari
- [Blog](https://example.com/blog): Sektor icguruleri

## Anahtar Konular
- Konu 1
- Konu 2
```

**Durum:** Yalnizca onerilmis standart. Buyuk AI sirketlerinin (OpenAI, Google, Anthropic) hicbiri llms.txt kullandigini resmi olarak dogrulamamistir. Temmuz 2025 itibariyle yalnizca ~951 domain yayinlamisti.

### 6.6 Icerik Formatlama - AI Cikarilabilirligi Icin

- **Sunucu tarafi render** (JavaScript-only icerik degil)
- **200ms altinda TTFB** (AI tarayici gereksinimleri icin)
- **Semantik HTML5** elemanlari (article, section, nav, aside)
- **Temiz baslik hiyerarsisi** (tek H1, mantiksal H2-H6 ic ice)
- **Kisa, aciklayici cumleler**
- **Cevap-once paragraflar** (ters piramit stili)
- **Karsilastirmali veriler icin tablolar** (AI tarafindan yuksek cikarilabilir)
- **Tum gorsellerde aciklayici alt metin**

### 6.7 Yapilandirilmis Verinin Etkisi

Arastirma, GPT-4 performansinin **yapilsandirilmamis icerikteki %16'dan** yapilandirilmis icerik islendiginde **%54'e** ciktigini gosteriyor.

---

## 7. GEO Araclari ve Metrikleri

### 7.1 Temel GEO Metrikleri

| Metrik | Aciklama | Nasil Olculur |
|--------|----------|---------------|
| **Marka Gorunurluk Orani** | AI yanitlarinin markanizi bahsetme yuzdesi | AI izleme araclari |
| **Alintilanma Orani** | Web sitenizin kaynak olarak alintilanma sikligi | AI izleme araclari |
| **Marka Ses Payi (SoV)** | Rakiplere karsi toplam marka bahislerindeki payiniz | Rekabet analizi |
| **Model Payi (SoM)** | AI yanitlarinda markanizin rakiplere karsi gorunme sikligi | Birincil GEO KPI |
| **AI Alintilanma Sikligi (AICF)** | Platformlar arasi ham alinti sayisi | Izleme araclari |
| **Marka Temsil Dogrulugu (BRA)** | AI'nin markanizi dogru temsil edip etmedigi | Manuel + otomatik |
| **AI Yanit Payi (AIRS)** | Ilgili sorgularin yuzde kacinda gorundugunuz | Sorgu izleme |
| **Duygu Dagalimi** | Marka bahislerinin tonu/baglami | NLP analizi |

### 7.2 GEO Izleme Araclari

| Arac | Aciklama | Izlenen Platformlar |
|------|----------|---------------------|
| **Otterly.ai** | Marka bahisleri, alintilamalar, GEO denetimleri | ChatGPT, Perplexity, Google AIO, Gemini, Copilot |
| **SE Ranking Visible** | AI gorunurluk takibi + optimizasyon | Birden fazla AI platformu |
| **Superlines** | GEO optimizasyonu + takibi | ChatGPT, Perplexity, Google |
| **GenRank** | AI arama siralama takipcisi | Birden fazla platform |
| **Profound** | AI alinti analizi + kaliplar | ChatGPT, Google AIO, Perplexity |
| **xFunnel** | AI arama analitikleri | Birden fazla platform |
| **Writesonic AI Visibility** | AI icin icerik optimizasyonu | Birden fazla platform |
| **Omnius** | GEO strateji + izleme | Birden fazla platform |
| **BotRank** | Teknik GEO denetimi (robots.txt vb.) | Tarayici erisimi |

---

## 8. Akademik Arastirma

### 8.1 Temel Calısma: "GEO: Generative Engine Optimization"

**Yazarlar:** Pranjal Aggarwal (IIT Delhi), Vishvak Murahari (Princeton), Tanmay Rajpurohit, Ashwin Kalyan (Allen Institute of AI), Karthik Narasimhan (Princeton), Ameet Deshpande (Princeton)

**Yayinlandi:** ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD '24), Agustos 2024. Ilk olarak arXiv'de: Kasim 2023 (arxiv.org/abs/2311.09735)

### Temel Katkilar

1. **GEO-bench:** GEO stratejilerini degerlendirmek icin birden fazla alanda 10.000 cesitli sorgu iceren bir kiyaslama

2. **Test Edilen Dokuz Optimizasyon Yontemi:**
   - Otoriter ton
   - Anahtar kelime doldurma
   - Istatistik ekleme
   - Kaynak gosterme
   - Alinti ekleme
   - Akicilik optimizasyonu
   - Anlasilir yeniden ifade
   - Benzersiz kelimeler ekleme
   - Teknik terimler ekleme

3. **Sonuclar:**
   - **En iyi 3 performans gosteren:** Kaynak Gosterme, Alinti Ekleme, Istatistik Ekleme
   - **Gorunurluk artisi:** Position-Adjusted Word Count metriginde **%40'a kadar** iyilesme
   - **Subjektif Izlenim artisi:** %15-30
   - Anahtar kelime doldurma jeneratif motorlar icin **etkili degildi**

4. **Alana Ozgu Bulgular:**
   - "Hukuk & Hukumet" ve "Gorus" sorgulari istatistiklerden en cok fayda gorur
   - "Insanlar & Toplum", "Aciklama" ve "Tarih" alinti eklemeden fayda gorur
   - Farkli stratejiler farkli icerik alanlari icin calisir

---

## 9. Yerel Isletmeler Icin GEO

### Temel Gercekler
- AI Overviews yerel isletme aramalarinin **%40.2'sinde** gorunur
- Tuketicilerin **%97'si** yerel isletmeleri cevrimici arar
- Google AI Mode, yerel sorgular icin dis web sitelerinden **daha sik** Google Business Profile baglantilarini alintilr

### 9.1 Google Business Profile (GBP) Optimizasyonu
- **Her bir ozeligi** doldurun (dis oturma, randevu, erisilebilirlik vb.)
- Tum platformlarda dogru **NAP (Ad, Adres, Telefon)** bilgisi - tutarsizlik AI'nin isletmenizi yoksaymasina neden olur
- GBP panosuna duzenli guncellemeler
- Degerlendirmelere yanit verin (etkilesim ve guven sinyali)
- GBP'de duzenli olarak guncellemeler paylasin

### 9.2 Yerel Icerik Stratejisi
- Yerel bolgeleriniz icin **"en iyi" ve karsilastirma** icerigi olusturun
- Yerel sorulari yanitlayan icerik uretin ("istanbul'daki en iyi [hizmet]")
- Yerel schema markup ekleyin (LocalBusiness, GeoCoordinates)
- Mahalle adlari, yer isaretleri, yerel referanslardan bahsedin
- Her hizmet bolgesi icin ayri sayfalar olusturun

### 9.3 Yerel Bahisler ve Listeler
- Yerel dizinlere kaydolun (Yelp, TripAdvisor, sektore ozel)
- Yerel yayinlarda, topluluk bloglarinda bahsedilmeyi hedefleyin
- Bolgesel "en iyi" listelerinde yer alin
- Sektor toplantilarinda ve yerel isletme spotlarinda gorunun
- Her yerde tutarli bilgi (NAP tutarliligi kritik)

### 9.4 Sesli Arama / Konusma Odakli Optimizasyon
- Konusma dilindeki sorgular icin optimize edin ("yakinimda X nerede bulabilirim?")
- Dogal dil sorulariyla SSS sayfalari olusturun
- "Yakinimda" ve konuma ozel uzun kuyruk anahtar kelimeler ekleyin

---

## 10. Pratik GEO Kontrol Listesi (Isletmeler Icin Uygulanabilir Adimlar)

### Faz 1: Teknik Altyapi
- [ ] **robots.txt denetimi:** GPTBot, ChatGPT-User, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended'a izin ver
- [ ] **Sunucu/CDN kontrolu:** AI bot isteklerinin engellenmediginden emin ol (ozellikle Cloudflare)
- [ ] **Sunucu tarafi render:** Kritik icerik JavaScript calistirmasi gerektirmemeli
- [ ] **Giris/odeme duvari arkasinda icerik yok:** AI tarayicilari kapili icerlige erisamez
- [ ] **200ms altinda TTFB:** AI tarayicilari icin hizli yanit suresi
- [ ] **Schema markup uygulamasi:** Organization, Article, FAQPage, Person, Product (JSON-LD formati)
- [ ] **llms.txt dusun:** Opsiyonel ama ileri gorush (/llms.txt kokte)
- [ ] **AI tarayici erisimi dogrulamasi:** Sayfalarinizin AI botlarina erisilebilir oldugunu test edin

### Faz 2: Icerik Optimizasyonu
- [ ] **Cevap-once format:** Her bolumun ilk 40-60 kelimesinde dogrudan yanitlar
- [ ] **Kaynak goster:** Icerik boyunca guvenilir kaynaklara referans verin (%30-40 gorunurluk artisi)
- [ ] **Istatistik ekle:** Her 150-200 kelimede niceliksel veri (%30-40 gorunurluk artisi)
- [ ] **Uzman alintilari ekle:** Ilgili alintilari dahil edin (%30-40 gorunurluk artisi)
- [ ] **Kisa paragraflar:** Maksimum 2-3 cumle
- [ ] **Madde isaretleri ve listeler:** Uzun paragraflar yerine
- [ ] **SSS bolumleri:** Dogal sorgulara uyan dogrudan S&C ciftleri
- [ ] **Karsilastirmali listeler:** AI tarafindan en cok alintilanlan format (3 alintilamadan 1'i)
- [ ] **2,900+ kelime derinligi:** Anahtar sayfalar icin (daha fazla alintilanma ile korelasyon)
- [ ] **Karsilastirmalar icin tablolar:** AI tarafindan yuksek cikarilabilir
- [ ] **Net yayin/guncelleme tarihleri:** Belirgin sekilde goster
- [ ] **Uzman yazarligi:** Yazar biyografileri, kimlik bilgileri gorunur

### Faz 3: Otorite Insasi
- [ ] **Tutarli marka terminolojisi:** Her yerde ayni ad, aciklama, terminoloji
- [ ] **Knowledge graph insasi:** Varlik iliskilerini acikca tanimla
- [ ] **Konu otoritesi:** Kapsamli kapsama ile konu kumeleri olustur
- [ ] **Ucuncu taraf bahisleri:** Yetkili sitelerde bahsedilme (baglantisiz bahisler de sayilir)
- [ ] **Wikipedia varligi:** Uygunsa, dogru girisi koruyun (ChatGPT'nin en iyi kaynagi)
- [ ] **YouTube icerigi:** Perplexity alintilamalari icin onemli (en iyi kaynak %16.1)
- [ ] **Reddit varligi:** Google AI Overviews icin onemli (en cok alintilanlan kaynak %2.2)

### Faz 4: Icerik Guncelligi
- [ ] **Duzenli guncellemeler:** Icerigi en az yillik olarak yenile
- [ ] **Icerik takvimi:** Inceleme/yenileme dongularini takip et
- [ ] **Guncel istatistikler:** Eski veri noktalarini degistir
- [ ] **Haber/trend icerigi:** Guncellik agirlikli platformlar icin zamaninda icerik uret

### Faz 5: Olcum ve Izleme
- [ ] **AI izleme kur:** Otterly.ai, SE Ranking Visible veya benzeri
- [ ] **Marka gorunurlugunuzu takip edin:** ChatGPT, Perplexity, Google AIO genelinde
- [ ] **Alintilanma oranini izle:** Sitenizin ne siklikta alintilindigi
- [ ] **Ses payini takip et:** AI yanitlarinda rakiplere karsi
- [ ] **A/B icerik testi:** Bir sayfayi optimize et, AI alintisini olc, sonra olceklendir

---

## 11. Agent Sistemine Entegrasyon Onerileri

Arastirma bulgularina dayanarak, agents-sdk projesine entegre edilebilecek GEO ozellikleri:

### 11.1 Teknik Denetim Yetenekleri (Yeni Tool'lar)
- **robots.txt AI tarayici kontrolu:** GPTBot, ChatGPT-User, ClaudeBot, PerplexityBot vb. izin verilip verilmedigini kontrol et
- **Schema dogrulama:** JSON-LD schema'nin GEO icin uygun olup olmadigini degerlendirmek
- **llms.txt kontrolu:** /llms.txt dosyasinin varligini ve icerigini kontrol et
- **AI tarayici erisilebilirlik testi:** Sayfalarin AI botlarina erisilebilir oldugunu dogrula

### 11.2 Icerik Skorlama (Mevcut Analiz Genisletmesi)
- **Veri yogunlugu skoru:** Istatistik/veri noktalari oranini degerlendirmek
- **Kaynak/alinti sayisi:** Icerik icindeki kaynak gostermelerini saymak
- **Cevap-once yapilanma kontrolu:** Paragraflarin cevap-once formatta yazilip yazilmadigini degerlendirmek
- **SSS varligi:** SSS bolumlerinin varligini kontrol etmek
- **Karsilastirma tablolari:** Tablo ve karsilastirmali yapilanma kontrolu

### 11.3 Schema Markup Onerileri
- GEO icin optimize edilmis JSON-LD schema onerileri uretme
- Organization, LocalBusiness, FAQPage, Article, Product onerileri

### 11.4 AI Gorunurluk Izleme
- **ChatGPT, Perplexity, Google AIO'da marka gorunurlugu:** Sorgu bazli izleme
- **Rakip kiyaslama:** Rakiplerin AI yanitlarindaki gorunurlugu

### 11.5 Icerik Optimizasyon Onerileri
- Mevcut icerik icin GEO odakli iyilestirme onerileri
- Eksik kaynak gosterme, istatistik, uzman alintisi tespiti

---

## Kaynaklar

### Ingilizce Kaynaklar
- [Wikipedia - Generative Engine Optimization](https://en.wikipedia.org/wiki/Generative_engine_optimization)
- [Frase.io - Complete 2025 GEO Guide](https://www.frase.io/blog/what-is-generative-engine-optimization-geo)
- [Conductor - What is GEO](https://www.conductor.com/academy/generative-engine-optimization/)
- [Search Engine Land - What is GEO Complete Guide](https://searchengineland.com/guide/what-is-geo)
- [Neil Patel - GEO vs SEO](https://neilpatel.com/blog/geo-vs-seo/)
- [Princeton/IIT Delhi - GEO Paper (arXiv)](https://arxiv.org/abs/2311.09735)
- [TryProfound - AI Platform Citation Patterns](https://www.tryprofound.com/blog/ai-platform-citation-patterns)
- [Search Engine Journal - ChatGPT Citation Factors](https://www.searchenginejournal.com/new-data-top-factors-influencing-chatgpt-citations/561954/)
- [Superlines - GEO Best Practices Checklist 2026](https://www.superlines.io/articles/generative-engine-optimization-best-practices-checklist)
- [KI-Company - Schema Markup for GEO](https://www.ki-company.ai/en/blog-beitraege/schema-markup-for-geo-optimization)
- [Omniclarity - Robots.txt for GEO](https://omniclarity.io/blog/robots-txt-for-geo/)
- [llmstxt.org - The /llms.txt File](https://llmstxt.org/)
- [Otterly.ai - AI Search Monitoring Tool](https://otterly.ai/)

### Turkce Kaynaklar
- [Turkiye.ai - GEO Stratejileri ile Icerik Optimizasyonu](https://turkiye.ai/generative-engine-optimization-stratejileri-ile-icerik-optimizasyonu/)
- [Dopinggo - GEO Nedir? Nasil Yapilir?](https://www.dopinggo.com/geo/)
- [ROI Public - GEO Nedir?](https://www.roipublic.com/geo-nedir/)
- [Digipeak - GEO Nedir?](https://digipeak.org/tr/blog/geo-nedir)
- [Marketing Turkiye - SEO'dan GEO'ya Gecis](https://www.marketingturkiye.com.tr/haberler/seodan-geoya-gecis/)
