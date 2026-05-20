"""Brand-aware prefix — Faz C.

Image / Video / Marketing ajanlari calismaya basladiginda Firestore'dan
brand_identity okur ve `prompt_summary()` cikti'sini brief'in basina
ekler. Boylece her uretim marka stiline uygun olur.

Bu blok ajan talimat dosyasinin BASINA prepend edilir — mevcut talimat
icerigi aynen kalir, sadece "ilk adim" eklenir.
"""

BRAND_AWARE_PREFIX = """## ZORUNLU ILK ADIM — MARKA KIMLIGINI OKU (Faz C)

Herhangi bir uretim/yayim/aksiyon almadan ONCE su tool'u cagir:

```
fetch_brand_identity(business_id=<input'taki business_id>)
```

Donen sonuca gore:

1. **exists=True ve is_substantially_filled=True** ise:
   - `prompt_summary` alanini al
   - Onu ESLEN ENDIRMEDEN brief'in / prompt'un / caption brief'in EN
     BASINA "BRAND CONTEXT:" basligi altinda enjekte et.
   - Visual / voice / audience tercihlerine UY.
   - `voice.avoid_words` listesini caption uretirken SAYGILA — bu
     kelimeleri kullanma.
   - `voice.preferred_words` listesini ON CIKAR — bu kelimeleri tercih
     et.
   - `visual.image_donts` listesi → bu gorsel motifleri YASAK.
   - `visual.primary_colors` → renk paletinin ana kaynagi.

2. **exists=False** veya is_substantially_filled=False ise:
   - Eski yola dus: fetch_business cagir, `profile` map'inden ne
     varsa kullan, eksik kalanlar icin makul varsayim yap.
   - **Uyari satirini cevabinin sonuna ekle:** "Not: brand_identity
     henuz olusturulmamis veya eksik. brand_synthesis agent ile
     olusturulmasini oneririm."

3. **Tool hatasi (success=False)** ise:
   - Sessizce eski yola dus (fetch_business). Sistem cokmemeli.

## NIYE BU ADIM ONEMLI

Marka kimligi tek bir kaynaktan (brand_identity dokumani) okunursa:
- Image agent ile Video agent ayni renk/stil uretir → tutarlilik.
- Marketing agent caption'inda Voice agent ile uyumlu ton kullanir.
- Yasak kelime/motif filtresi tek yerden yonetilir → guvenli.

ASLA bu adimi atlamaktansa hizli ol diye gec. 1 ek tool cagrisi
sonradan tutarsizlik debug etmekten cok daha ucuz.

---

"""

__all__ = ["BRAND_AWARE_PREFIX"]
