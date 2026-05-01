# MindBot Kullanım Kılavuzu

**Kullanıcılar:** Sadece Şeyma + ekip içi (production user yok).
**Amaç:** Portalı doğru komutlarla kullanıp ilk seferde doğru cevap almak.

---

## 1. Sistem Mantığı (Kısa)

MindBot tek bir agent değil, bir **orchestrator** + altında 5 alt-agent + tool'lardan oluşur. Sen mesaj yazınca:

1. **Orchestrator** (gpt-4.1-mini) mesajı okur, hangi alt-agent/tool'a gideceğine **karar verir**.
2. Seçilen alt-agent görevini yapar (NocoDB sorgusu, Instagram post, SEO analizi, vb).
3. Sonuç orchestrator'a döner, sana yanıt yazılır.

**Kritik nokta:** Orchestrator'ın "doğru tool'u seçmesi" senin prompt'unun netliğine bağlı. Belirsiz prompt → yanlış tool → yanlış cevap.

### Alt-agent'lar ve ne yaparlar

| Alt-agent | Görevi | Veri kaynağı |
|---|---|---|
| **meta_agent** | Lead/CRM işleri (sorgu, listeleme, kaydetme) | NocoDB |
| **marketing_agent** | Instagram post, plan, takvim, metrik | Firestore + Late API |
| **analysis_agent** | SEO, SWOT, web araştırma, rapor | Web + Firestore |
| **image_agent** | Görsel üretimi | Gemini |
| **video_agent** | Video + ses üretimi | Veo / Kling / HeyGen / fal.ai |

### Tool'lar (en sık kullanılanlar)

- `query_leads` — NocoDB'de lead arama (filtreli)
- `upsert_lead` — Lead kaydet/güncelle (idempotent)
- `fetch_business` — Firestore'dan işletme profili çek
- `query_documents` — Firestore'da rapor/plan/hafıza arama (**lead İÇİN DEĞİL**)
- `post_on_instagram` / `post_carousel_on_instagram` — Instagram'a yayınla

---

## 2. Bizim Proje Bağlamı

**Production:** Cloud Run `agents-sdk-api` — `https://agents-sdk-api-704233028546.us-central1.run.app`

**Ortam:**
- GCP project: `instagram-post-bot-471518`
- NocoDB: leadler global tabloda (business_id'ye göre filtrelenmiyor — herkes aynı tabloyu görür)
- Firestore: `businesses/{business_id}/...` altında her işletmenin kendi profili, raporları, planları
- Late API: Instagram/YouTube paylaşımı

**Mevcut işletmeler:** MindID, Slowdays (UI'daki sağ üst dropdown).

**Önemli:** `business_id="satis_dashboard"` test için kullanılan **fake** ID — Firestore'da yok. Sadece NocoDB'ye direkt giden lead testlerinde işe yarar (NocoDB business_id kullanmıyor). UI'dan gönderdiğinde gerçek işletme ID'si gider.

---

## 3. Komut Yazma Kuralları (En Önemli Bölüm)

### 🟢 İYİ Promptlar

**Lead/CRM:**
- `kaç sıcak lead var, listele`
- `bugün gelen leadleri göster`
- `+90 555 numaralı lead'i bul`
- `Meta'dan gelen son 10 lead'i listele`

**Instagram post:**
- `MindID için yarın sabaha bir post hazırla ve paylaş — konu: yapay zeka eğitimi`
- `bu görseli Instagram'a paylaş, caption: ...`
- `bu hafta planlanmış postları göster`

**SEO/Analiz:**
- `MindID websitesinin SEO analizini yap`
- `Slowdays için SWOT analizi hazırla`
- `OpenAI'ın son güncellemesini araştır, kısa rapor yaz`

**Görsel/Video:**
- `koyu mavi arka planda minimalist logo: MindID — 1080x1080`
- `bu görsele 5 saniyelik animasyon ekle, hafif zoom`

### 🔴 KÖTÜ Promptlar (ve neden)

| Prompt | Sorun | Düzelt |
|---|---|---|
| "leadler ne durumda" | "lead" var ama belirsiz | "kaç aktif lead var, durumlarına göre grupla" |
| "şuna bak" | Bağlam yok | "[Reference Ekle] ile dosya seç + 'bunu Instagram'a paylaş'" |
| "post at" | Hangi içerik, hangi işletme? | "MindID için: 'AI eğitim kayıtları başladı' postu hazırla ve paylaş" |
| "rapor hazırla" | Ne raporu, ne hakkında? | "MindID için Mayıs SEO raporunu hazırla" |

### ⚡ Pro İpuçları

1. **İşletme seçimini kontrol et** — Sağ üstteki dropdown ("MindID" / "Slowdays") doğru mu? Yanlış işletme → yanlış veri.
2. **Lead sorgularında "lead" kelimesini kullan** — Orchestrator bu kelimeyi gördüğünde otomatik meta_agent'a gider. "müşteri", "kişi" deme.
3. **Belirsiz olduğunda tool adını ekle** — Cloud Shell testlerinde gördüğümüz gibi: `query_leads ile (asama,eq,Sicak) filtreli ara` direkt çalışır.
4. **Kısa cümle iyi ama spesifik ol** — "kaç sıcak lead var" iyi, "müşteri sayısı" kötü.
5. **Yeni thread aç** karmaşık konu değişiminde — Üstteki "Geçmiş" → yeni başlat. Eski thread context'i karıştırır.
6. **Cevap "yok/bulamadım" derse** — Hemen Cloud Shell'den aynı sorguyu explicit olarak test et:
   ```bash
   TOKEN=$(gcloud auth print-identity-token)
   curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"task":"...query_leads tool ile where=... filtresi kullan...","business_id":"satis_dashboard","task_id":"debug-1"}' \
     https://agents-sdk-api-704233028546.us-central1.run.app/task | tail -c 1500
   ```
   Şu varsa → backend sağlam, prompt'u düzeltmek lazım. Yoksa → backend sorunu, hızlı bildir.

---

## 4. YAPMA Listesi

- ❌ Aynı task'ı arka arkaya 3 kez gönderme — orchestrator stuck olabilir, "Geçmiş"ten temizle.
- ❌ "lead" ve "Instagram'a paylaş"ı aynı cümlede kullanma — routing kafası karışır. Önce lead'i sorgula, sonra "bu liste için post hazırla" de.
- ❌ Aynı thread'de işletme değiştirme — yeni thread aç.
- ❌ Çok genel araştırma sorularını lead/CRM ile karıştırma.
- ❌ Production'a deploy etmeden değişikliği test etmeden bırakma.

---

## 5. Sorun Çıkarsa

### "Yanlış cevap geldi"
1. Prompt'u Cloud Shell'den explicit olarak test et (yukarıdaki ipucu #6).
2. Çalışıyorsa → routing problemi, orchestrator instruction'ı güncellenmeli.
3. Çalışmıyorsa → backend (NocoDB/Firebase/API) problemi.

### "Cevap hiç gelmiyor / takıldı"
- Cloud Run logs:
  ```bash
  gcloud run services logs read agents-sdk-api --region=us-central1 --limit=50
  ```

### "Deploy bozdu, geri al"
Eski revision'a trafiği döndür:
```bash
gcloud run services update-traffic agents-sdk-api \
  --to-revisions=<eski-revision-id>=100 \
  --region=us-central1 --project=instagram-post-bot-471518
```
Revision listesi:
```bash
gcloud run revisions list --service=agents-sdk-api --region=us-central1 --limit=10
```

### "Yeni feature/tool ekledim çalışmıyor"
`CLAUDE.md` Madde 7'yi kontrol et — yeni tool eklerken **5 yerde** güncelleme gerekiyor (instruction listesi + tool listesi + CLAUDE.md).

---

## 6. Versiyon Bilgisi (Bu kılavuzun yazıldığı an)

- Production: `v1.20.3` (2026-05-01) — orchestrator lead routing fix
- Branch: `claude/test-agent-chatbot-rNLkK`
- Bekleyen: meta_agent → sales_agent rename (kafa karıştırıcı isim)
