# Instagram Metrik-Post Eşleştirme Düzeltme Planı

## Problem Özeti

Late API'ye geçişten sonra, Firestore'daki Instagram post kayıtları ile Late Analytics'ten çekilen metrikler arasında **ID uyumsuzluğu** var.

### Mevcut Durum

| Kaynak | ID Alanı | Değer Tipi | Örnek |
|--------|----------|------------|-------|
| `post_on_instagram` response | `platform_post_id` | Instagram Native ID | `17895642381234567` |
| Firestore doc ID | `instagram_media_id` | Instagram Native ID | `17895642381234567` |
| Late Analytics response | `postId` | **Late Internal ID** | `65f1c0a9e2b5af...` |

**Sorun:** Analytics'ten gelen `postId` (Late ID) ≠ Firestore'daki doc ID (Instagram ID)

### Eşleştirme İçin Kullanılabilir Ortak Alan

| Kaynak | Alan | Örnek |
|--------|------|-------|
| Firestore `instagram_posts` | `permalink` | `https://instagram.com/p/ABC123/` |
| Late Analytics | `platformPostUrl` | `https://instagram.com/p/ABC123/` |

**Çözüm:** `permalink` / `platformPostUrl` üzerinden URL bazlı eşleştirme yapılabilir.

---

## Düzeltme Planı

### Adım 1: `instagram_tools.py` Güncelleme

**Dosya:** `src/tools/instagram_tools.py`

**Değişiklikler:**
1. `late_post_id` alanı ekle (Late'in kendi ID'si için)
2. `latePostId` alanını da response'a ekle (varsa)
3. Mevcut `id` alanını daha açık isimlendirme ile korumak için yorum ekle

```python
# Line 58-74 değişecek
media_items.append({
    "id": post.get("postId"),           # Late External ID (eşleştirme için KULLANMA)
    "late_post_id": post.get("latePostId"),  # Late scheduled post ID
    "platform_post_url": post.get("platformPostUrl"),  # ✓ Eşleştirme için KULLAN
    "content": post.get("content", "")[:100] if post.get("content") else None,
    "published_at": post.get("publishedAt"),
    "status": post.get("status"),
    "metrics": { ... },
    "is_external": post.get("isExternal", False),
})
```

### Adım 2: Marketing Agent Instructions Güncelleme

**Dosya:** `src/agents/marketing_agent.py`

**Workflow #3 (Analyze Performance) bölümüne ekleme:**

```markdown
### 3. Analyze Performance
1. get_instagram_insights(limit=20)
2. get_instagram_posts() → Match using permalink/platform_post_url (NOT id!)
   - For each insight, find matching Firestore post by comparing:
     - insight.platform_post_url == post.permalink
   - This links metrics to our saved topic/theme data
3. Identify patterns...
```

### Adım 3: (Opsiyonel) Utility Fonksiyonu Ekleme

**Dosya:** `src/tools/marketing_tools.py`

Eşleştirmeyi kolaylaştırmak için yardımcı fonksiyon:

```python
@function_tool
async def match_insights_with_posts(
    business_id: str,
    insights: list[dict],
) -> dict[str, Any]:
    """
    Match Late Analytics insights with saved Instagram posts using permalink.

    Args:
        business_id: Business ID.
        insights: List of insights from get_instagram_insights.

    Returns:
        dict with matched posts (insight + saved post data merged).
    """
    # Get saved posts
    saved_posts = await get_instagram_posts(business_id, limit=100)

    # Create URL -> post mapping
    url_to_post = {
        post.get("permalink"): post
        for post in saved_posts.get("posts", [])
        if post.get("permalink")
    }

    # Match insights
    matched = []
    unmatched = []

    for insight in insights:
        url = insight.get("platform_post_url")
        if url and url in url_to_post:
            matched.append({
                **insight,
                "saved_post": url_to_post[url],
                "topic": url_to_post[url].get("topic"),
                "theme": url_to_post[url].get("theme"),
            })
        else:
            unmatched.append(insight)

    return {
        "success": True,
        "matched": matched,
        "unmatched": unmatched,
        "match_rate": len(matched) / len(insights) if insights else 0,
    }
```

---

## Değişiklik Özeti

| Dosya | Değişiklik | Zorunlu? |
|-------|------------|----------|
| `src/tools/instagram_tools.py` | `late_post_id` alanı ekle, yorum ekle | Evet |
| `src/agents/marketing_agent.py` | Eşleştirme talimatlarını güncelle | Evet |
| `src/tools/marketing_tools.py` | `match_insights_with_posts` fonksiyonu | Opsiyonel |
| `CLAUDE.md` | Eşleştirme mekanizmasını dokümante et | Evet |

---

## Dikkat Edilecekler

1. **Geriye dönük uyumluluk:** Eski Firestore kayıtlarında `permalink` boş olabilir (Late geçişinden önce). Bu postlar eşleştirilemez.

2. **External posts:** `is_external: true` olan postlar (Late dışından yapılan) Firestore'da kayıtlı olmayabilir.

3. **URL normalizasyonu:** URL'ler karşılaştırılırken trailing slash, query params gibi farklılıklar olabilir. Normalize etmek gerekebilir.

---

## Onay Bekleniyor

Yukarıdaki planı onaylıyor musunuz?

- [ ] Adım 1: instagram_tools.py güncelleme
- [ ] Adım 2: Marketing Agent instructions güncelleme
- [ ] Adım 3: match_insights_with_posts utility fonksiyonu (opsiyonel)
- [ ] CLAUDE.md dokümantasyon güncellemesi
