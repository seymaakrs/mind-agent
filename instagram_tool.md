

## AMAÇ

Instagram Graph API üzerinden **son N içerik (media)** için performans metriklerini çekmek.
Kısıt: endpoint `.../insights?metric=` **tek metric** alıyor (bizim tool arayüzümüz böyle). Bu yüzden tool **çoklu HTTP GET** çağrılarını kendi içinde yapacak ve tek JSON döndürecek.

---

## INPUT / OUTPUT

### Input (tool parametreleri)

* `ig_user_id` (string)
* `limit` (int, default 10) → son kaç içerik çekilecek
* `since` (optional ISO date) → sadece bu tarihten sonrası içerikleri al (filtreyi client-side da yapabilirsin)
* `include_reels_watch_time` (bool, default true)
* `include_story` (bool, default false) → şimdilik kapalı tutmak mantıklı
* `timeout_ms` (optional)
* `api_version` (string, default "v23.0") (senin Explorer’da v23.0 görünüyor)

### Output (tek JSON)

* `media_items`: içerik listesi (id, permalink, timestamp, media_type, media_product_type + metrikler)
* `errors`: per media id / per metric hatalar (fail-soft)
* `summary`: basit toplulaştırmalar (avg, top_k vb.) – opsiyonel ama faydalı

---

## 1) MEDIA LIST ÇEKME (tek çağrı)

Önce son N içeriği çek:

**GET**

```
/{ig_user_id}/media?fields=id,media_type,media_product_type,timestamp,permalink&limit={limit}
```

Notlar:

* `media_product_type` → REELS olup olmadığını anlamak için kritik.
* `timestamp` → sıralama/filtre için.
* `permalink` → raporda linklemek için.

---

## 2) METRİK SETİ (MVP – media-level)

### 2.1 Tüm medya türleri için çekilecek çekirdek metrikler (5 adet)

Bunlar Reels’te test edildi ve çalıştı; genelde diğer media tiplerinde de geçerli:

1. `reach`
2. `views`
3. `total_interactions`
4. `shares`
5. `saved`

**Her biri ayrı GET çağrısı** olacak (tool kısıtı yüzünden):

Örnek:

```
/{media_id}/insights?metric=reach
/{media_id}/insights?metric=views
/{media_id}/insights?metric=total_interactions
/{media_id}/insights?metric=shares
/{media_id}/insights?metric=saved
```

### 2.2 Reels ise ek metrikler (retention için) (2 adet)

Eğer `media_product_type == "REELS"` ve `include_reels_watch_time == true` ise ekle:

6. `ig_reels_avg_watch_time`
7. `ig_reels_video_view_total_time`

GET:

```
/{media_id}/insights?metric=ig_reels_avg_watch_time
/{media_id}/insights?metric=ig_reels_video_view_total_time
```

Not:

* `ig_reels_avg_watch_time` response title’da “milisaniye” görünüyor (ms). Bunu normalize edip saniyeye çevirmek isteyebilirsin.

---

## 3) TOOL DAVRANIŞI (fail-soft + caching)

### 3.1 Fail-soft

* Bir metric çağrısı hata verirse:

  * O metric’i `null` bırak
  * Hata objesini `errors[]` içine ekle:

    * `media_id`
    * `metric`
    * `code`, `message`, `fbtrace_id` (varsa)

Bu sayede marketing agent rapor üretmeye devam eder.

### 3.2 Parallel / rate limit

* İstekleri paralel yapmak iyi ama Meta rate limit’e takılabilir.
* Öneri: concurrency 3–5 (ayarlanabilir).
* Basit retry: 1–2 deneme, exponential backoff.

### 3.3 Cache (opsiyonel ama çok işe yarar)

* Aynı gün içinde aynı media_id için bu metrikleri tekrar çekiyorsan:

  * 10–60 dk cache yeterli (özellikle reels watch time değişebilir ama çok sık değişmez).
* Agent zaten günlük çalışacak, cache şart değil ama maliyeti düşürür.

---

## 4) OUTPUT ŞEMASI ÖNERİSİ (coding agent için)

Her media item şöyle dönsün:

```json
{
  "id": "18179226694364052",
  "media_type": "VIDEO",
  "media_product_type": "REELS",
  "timestamp": "2025-12-18T15:51:22+0000",
  "permalink": "https://www.instagram.com/reel/....",
  "metrics": {
    "reach": 116,
    "views": 133,
    "total_interactions": 0,
    "shares": 0,
    "saved": 0,
    "ig_reels_avg_watch_time_ms": 1351,
    "ig_reels_avg_watch_time_sec": 1.351,
    "ig_reels_video_view_total_time_ms": 167582,
    "ig_reels_video_view_total_time_sec": 167.582
  },
  "raw": {
    "reach": { ...full_insights_response... },
    "views": { ... },
    ...
  }
}
```

Not:

* `raw` alanını opsiyonel yapabilirsin (`include_raw=false`) çünkü payload büyütür.
* En azından `title` ve `description` gibi alanlar debugging için faydalı.

---

## 5) TOOL’UN TEK CÜMLELİK SÖZLEŞMESİ

“Verilen IG User için son N içeriği listeler ve her içerik için reach/views/total_interactions/shares/saved (+Reels’te watch time) metriklerini tek tek çekip normalize edilmiş bir snapshot JSON döndürür.”

---

## 6) DOĞRULAMA (Explorer test path’leri)

Coding agent development sırasında test etmek için:

1. Media list:

```
{ig_user_id}/media?fields=id,media_type,media_product_type,timestamp,permalink&limit=5
```

2. Bir media id için:

```
{media_id}/insights?metric=reach
{media_id}/insights?metric=views
{media_id}/insights?metric=total_interactions
{media_id}/insights?metric=shares
{media_id}/insights?metric=saved
```

3. Reels ise:

```
{media_id}/insights?metric=ig_reels_avg_watch_time
{media_id}/insights?metric=ig_reels_video_view_total_time
```

---

## Son not (özellikle önemli)

* Media insights cevaplarında çoğu zaman `period=lifetime` döner. Bu normal; senin agent’ın günlük çalışıp “aynı postun lifetime değerinin zamanla nasıl arttığını” kendi hafızasında tutacak. Bu senin planınla uyumlu.
