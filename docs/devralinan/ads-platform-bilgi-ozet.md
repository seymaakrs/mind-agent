> Kaynak repo ads-mcp kaldırılmadan önce süzülen özet. Tarih: 2026-06-07.

# Reklam Platformu Bilgi Özeti (Adspirer MCP'den süzülen)

`ads-mcp` (Adspirer), Google / Meta / LinkedIn / TikTok reklam yönetimini doğal
dille yapan harici bir üründü. Ana katalog: `shared/skills/adspirer-ads/SKILL.md`
(~1039 satır). Bu doküman, bizim **"insansız reklam ajansı"** için örnek
alınması gereken **araç kategorilerini, akışları ve güvenlik kurallarını**
özetler. Kodu değil, fikir/katalog değerini aldık.

---

## 1. Güvenlik Kuralları (EN ÖNEMLİ — birebir örnek alınmalı)

Bu araçlar GERÇEK kampanya oluşturur, GERÇEK para harcar. Adspirer'ın altın
kuralları:

1. **Kampanya oluşturmadan / harcamayı değiştirmeden önce HER ZAMAN kullanıcı
   onayı al.**
2. **Hata durumunda kampanya oluşturmayı otomatik retry ETME** (mükerrer
   kampanya / çift harcama riski).
3. **Canlı bütçeleri açık onay olmadan DEĞİŞTİRME.**
4. **Tüm kampanyalar mümkünse PAUSED (durdurulmuş) statüde oluşturulur** —
   kullanıcı açıkça aktive etmeden harcama başlamaz.
5. **Harcamaya etki eden her belirsiz işlemde önce kullanıcıya sor.**

> Bu, bizim CLAUDE.md'deki "yeni lead → mail yalnız qualified + uygun aşamada"
> ve genel "veri silme, arşivle" felsefemizin reklam tarafındaki karşılığıdır.
> Otonom agent kampanya açacaksa: **default PAUSED + insan onayı + otomatik
> retry yasak.** Bunu Marketing/Reklam agent'ımıza katı kural olarak koymalıyız.

---

## 2. Zorunlu Akış İskeleti (her reklam işleminde)

Adspirer her görevi sabit bir sırayla yürütür — bizim agent'ımız için iyi bir
iskelet:

1. **Önce durumu oku:** Bağlı platformları/hesapları kontrol et
   (`get_connections_status`). Hedef platform bağlı değilse dur.
2. **Görevi sınıflandır:** Kullanıcı amacını bir "workflow"a eşle (tablo aşağıda).
3. **Araçları çalıştır:** Daima **önce oku (read), sonra yaz (act)**. Yani
   metrik/durum/yapı çek → ondan sonra oluştur/değiştir.
4. **Özetle ve öner:** Sonuçları tablo halinde, ü/alt performans vurgulayarak
   sun; uygulanabilir sonraki adımları öner.

**Read-before-write** prensibi tüm katalogda tekrar eder: oluşturmadan/
güncellemeden önce `list_*` / `discover_*` / `get_*_structure` çağrılır ve
ID'ler buradan alınır (asla uydurulmaz).

---

## 3. Araç Kategorileri (kullanıcı amacı → akış eşlemesi)

Bizim reklam agent'ımızda hangi yetenek gruplarının olması gerektiğine dair
referans katalog:

| Amaç | Akış | Örnek araç türleri |
|---|---|---|
| Kampanya metriklerini görüntüle | Performance Analysis | `get_*_campaign_performance` (platform başına) |
| Platformlar arası genel bakış | Cross-Platform Dashboard | Her platformun perf aracı, yan yana |
| Anahtar kelime bul | Keyword Research | `research_keywords` (Search kampanyalarından önce zorunlu) |
| Yeni kampanya öncesi araştırma | Campaign Research | `WebSearch`/`WebFetch` + platform araçları |
| Rakip analizi | Competitive Intelligence | `analyze_search_terms`, `research_keywords` + web |
| Kampanya oluştur | Campaign Creation | Önce research, sonra platforma özel akış (PAUSED) |
| Boşa harcamayı azalt | Budget Optimization | `optimize_budget_allocation`, `analyze_wasted_spend` |
| Reklam yorgunluğu kontrolü | Creative Management | `detect_meta_creative_fatigue`, creative perf analizi |
| Kitle anlama | Audience Analysis | `get_*_audience_insights`, `search_audiences` |
| Reklam uzantıları (Google) | Ad Extensions | sitelinks, callouts, structured snippets |
| Teklif stratejisi | Bidding Strategy | `update_bid_strategy` (trade-off'ları açıkla, kullanıcı seçsin) |
| Anahtar kelime yönetimi | Keyword Management | add/remove/update keyword, negative keywords |
| Alarm kur | Monitoring | `create_monitor`, `list_monitors` |
| Rapor zamanla | Reporting | `schedule_brief`, `generate_report_now` |

> Bizde Marketing Agent + reklam_uzmani (meta alias) zaten var. Bu tablo, o
> agent'ın araç envanterini büyütürken hangi yeteneklerin "olması güzel" değil
> "standart" sayıldığını gösterir: özellikle **performance + wasted-spend +
> creative fatigue + audience insights** dörtlüsü reklam ajansının çekirdeği.

---

## 4. Kampanya Oluşturma — "Definition of Done" (kapanış kontrolü)

Adspirer, bir kampanya "başarılı" demeden önce zorunlu doğrulama yapar. Otonom
agent'ımız için kritik fikir: **iş bitti deme, doğrula.**

Her oluşturulan kampanyada şu kontroller geçmeli:
1. Kampanya var ve statüsü `PAUSED` (kullanıcı aksini onaylamadıysa).
2. Beklenen ad group sayısı mevcut.
3. Beklenen anahtar kelimeler + planlanan eşleşme tipi (EXACT/PHRASE/BROAD).
4. En az bir RSA (responsive search ad) beklenen başlık/açıklama sayısıyla.
5. Gerekli uzantılar mevcut (sitelinks, callouts, snippets — Google için).
6. İstenen vs gerçekleşen teklif stratejisi eşleşiyor; sapma varsa açıkça belirt.

**Statü protokolü:** `SUCCESS` (tüm kontroller geçti) / `PARTIAL_SUCCESS`
(iskelet var ama bir varlık eksik) / `FAILED`. → Doğrulanamayan hiçbir şeye
`SUCCESS` deme.

**Eylem defteri (action ledger):** Her kampanya için kampanya adı + id, dokunulan
ad_group id'leri, keyword sayıları, RSA sayıları, uzantı sayıları ve PASS/FAIL
doğrulama sonucu loglanır.

> Bu "ledger + verify" deseni bizim Sales CRM mantığımızla aynı ruhta: yapılan
> her işlemi izlenebilir/idempotent tut (bkz. `upsert_lead` external_id).

---

## 5. Girdi/Format Disiplini (hata önleme)

Otomasyonda sessiz hataları engelleyen pratik kurallar:
- **ID'ler her zaman string** ("1333064875515942"), asla çıplak integer.
- **ID'leri asla değiştirme:** list/discover'dan dönen değeri birebir kopyala
  (yuvarlama/kısaltma yok).
- **Create/Update öncesi daima List/Discover çağır** (ID'ler oradan gelir).
- **Metin uzunluk limitlerine uy** (örn. Google başlık max 30 karakter); sunucu
  uzun metni reddeder.
- **Enum değerleri:** status ENABLED/PAUSED/ACTIVE/ARCHIVED; bütçeler sayı.

---

## 6. mind-agent için çıkarım

1. **Reklam/Marketing agent'ına katı güvenlik kuralları ekle:** default PAUSED,
   açık onay, otomatik retry yasak, canlı bütçeye dokunma.
2. **Read-before-write zorunlu kıl:** oluşturmadan önce mevcut durumu çek.
3. **"Definition of Done + ledger" uygula:** iş bitti demeden doğrula, her
   işlemi izlenebilir logla (CRM idempotency felsefemizle uyumlu).
4. **Araç kataloğunu kategorilerle büyüt:** performance / wasted-spend / creative
   fatigue / audience insights / keyword research çekirdek dörtlü-beşli.
5. **Bütçe notu:** Adspirer harici/ücretli bir üründü. Biz Clay/Apollo'yu maliyet
   nedeniyle kullanmıyoruz; aynı disiplinle reklam tarafında da pahalı araçlar
   yerine platformların kendi API'leri (Meta/Google) + bu kurallar tercih edilmeli.
