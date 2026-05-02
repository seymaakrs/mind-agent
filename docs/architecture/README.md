# Mimari Dokümantasyonu

Bu klasör, **mind-agent** prototipinin yaşayan mimari dokümantasyonudur. Kod ile birlikte güncellenir — eskimez.

## Amaç

> "Bu sistem nasıl çalışır?" sorusuna **15 dakikada** cevap verebilmek.
> "Yeni özelliği nereye eklerim?" sorusuna **şüphe duymadan** cevap verebilmek.

## Bu Klasördeki Dokümanlar

| Dosya | Konu | Durum |
|-------|------|-------|
| `01-system-hierarchy.md` | Katmanlar, kontrol akışı, bağımlılık kuralları | ✅ |
| `02-agents.md` | Her agent'ın sorumluluğu, tool envanteri, instruction yapısı | ⏳ |
| `03-tools.md` | Tool kategorileri, naming convention, I/O sözleşmeleri | ⏳ |
| `04-data-model.md` | Firestore koleksiyon yapısı, hangi katman nereye yazar | ⏳ |
| `05-flows.md` | Tipik kullanıcı akışları (post oluştur, SEO analizi, vb.) | ⏳ |
| `06-external-services.md` | Dış servis listesi, hata davranışları, rate limit'ler | ⏳ |

## Yazım Kuralları (Bu Dokümanlar İçin)

1. **Mevcut durum + olması gereken** birlikte yazılır (öğrenci de görür, hedef de bellidir).
2. **Diyagramlar ASCII** veya Mermaid — render gerekmesin, terminal'de de okunabilsin.
3. Bilinen **ihlaller** açıkça listelenir ("şu dosyada şu kural çiğneniyor").
4. Yeni bir agent/tool/servis eklenince ilgili doküman **aynı PR içinde** güncellenir.

## Neden Ayrı Klasör?

`docs/` altında çeşitli dokümanlar var (stream events, remotion research). Mimari dokümanı **çoklu dosyaya** ihtiyaç duyduğu için kendi klasörünü hak ediyor: katman, agent, tool, data model, flow, dış servis — bunlar zamanla büyür ve bağımsız okunmalı.
