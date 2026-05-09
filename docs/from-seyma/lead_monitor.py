"""
LEAD MONITOR + AUTO-RESPONDER
- Her 60sn Zernio CRM tarar
- Yeni yanit verenleri yakala -> tag ekle -> OTOMATIK 2. mesaj gonder
- 3 varyant arasi random (sablon spam gorunmesin)
- 30-60sn gecikme (insan davranisi)
- inbound_log.csv'ye yazar
- Ctrl+C ile durur
"""
import csv, json, time, sys, os, signal, random
from datetime import datetime, timezone, timedelta
import requests

# 3 OTOMATIK YANIT VARYANTI - dogal, samimi, yuzyuze gorusme onerili
AUTO_REPLIES = [
    "Çok teşekkürler dönüşünüz için 🙂\n\nOtelinize özel hızlı bir plan çıkaralım — hem Booking komisyonu ödemeden direkt rezervasyon, hem sosyal medyadan misafir akışı. Bodrumdayım, önümüzdeki günlerde Marmaris ve Fethiye yoluna çıkıyorum zaten.\n\nUğrayıp yüz yüze 30 dakika konuşsak hem mekanı görmüş olurum hem size özel net bir plan çıkarırım. Hangi gün uygun?",

    "Hızlı dönüşünüz için sağolun 🌿\n\nSezon başlamadan otelinize özel bir doluluk planı çıkarmak isterim. Online reklam ve sosyal medya tarafı küçük bütçeyle bile çok iş yapıyor.\n\nBu hafta içinde uğrayabilirim, bir kahve içerken 30 dakika konuşalım. Hem siz beni tanımış olursunuz hem ben mekanı görürüm. Ne gün size uyar?",

    "Çok güzel, dönüşünüz için teşekkürler 🙂\n\nSizinle yüz yüze 30 dakikalık bir görüşme yapsak hem otelinize özel hızlı bir plan çıkarırım hem de tanışmış oluruz. Bodrum tarafından geliyorum, hafta içi ya da hafta sonu fark etmez.\n\nHangi gün size daha uygun?"
]

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except: pass

API_KEY = "sk_bbd6bbced7a54fe6af777ffc13c8ee5a66782b4e532eb305d35a7bfda0351957"
BASE = "https://api.zernio.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

WA_ACCOUNT_ID = "69ecc2273a63baf2053dfc21"
GONDERIM_LOG = "gonderim_log.csv"
INBOUND_LOG = "inbound_log.csv"
POLL_SEC = 60

stop = False
def sigint(s, f):
    global stop
    print("\n[Durduruldu]")
    stop = True
signal.signal(signal.SIGINT, sigint)

def load_sent_phones():
    """Mesaj gonderilen otel telefonlari (otel_master eslesmesi icin)."""
    sent = {}  # phone -> {isim, segment, bolge}
    if not os.path.exists(GONDERIM_LOG):
        return sent
    with open(GONDERIM_LOG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("status") == "SENT":
                sent[r["telefon"]] = {
                    "isim": r["isim"], "segment": r["segment"], "bolge": r["bolge"]
                }
    return sent

def load_already_logged_inbound():
    if not os.path.exists(INBOUND_LOG):
        return set()
    s = set()
    with open(INBOUND_LOG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            s.add(r["telefon"])
    return s

def log_inbound(row):
    new = not os.path.exists(INBOUND_LOG)
    with open(INBOUND_LOG, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp","isim","telefon","bolge","segment","last_received","received_count","contact_id","oto_yanit"], extrasaction="ignore")
        if new: w.writeheader()
        w.writerow(row)

def add_tags(contact_id, tags):
    """Zernio'da contact'a tag ekle."""
    try:
        r = requests.patch(f"{BASE}/contacts/{contact_id}",
                          headers=HEADERS,
                          json={"tags": tags}, timeout=15)
        return r.status_code == 200
    except: return False

def find_conversation_id(participant_id_no_plus):
    """WA conversation ID'sini telefon (905...) ile bul."""
    try:
        skip = 0
        while True:
            r = requests.get(f"{BASE}/inbox/conversations",
                           headers=HEADERS,
                           params={"accountId": WA_ACCOUNT_ID, "limit": 100, "cursor": skip if skip else ""},
                           timeout=20)
            d = r.json()
            for c in d.get("data", []):
                if c.get("participantId") == participant_id_no_plus:
                    return c.get("id")
            if not d.get("pagination", {}).get("hasMore"):
                break
            skip += 100
            if skip > 500: break
    except Exception as e:
        print(f"   conv-fetch err: {e}")
    return None

def send_auto_reply(conversation_id, isim):
    """Random 1 varyantli otomatik yanit gonder."""
    msg = random.choice(AUTO_REPLIES)
    try:
        r = requests.post(f"{BASE}/inbox/conversations/{conversation_id}/messages",
                         headers=HEADERS,
                         json={"accountId": WA_ACCOUNT_ID, "message": msg},
                         timeout=20)
        d = r.json()
        if d.get("success"):
            return True, d.get("data", {}).get("messageId", "")
        return False, str(d)[:200]
    except Exception as e:
        return False, str(e)[:200]

def fetch_contacts():
    """Tum WA contact (paginated)."""
    out = []
    skip = 0
    while True:
        r = requests.get(f"{BASE}/whatsapp/contacts",
                        headers=HEADERS,
                        params={"accountId": WA_ACCOUNT_ID, "limit": 100, "skip": skip},
                        timeout=20)
        d = r.json()
        cs = d.get("contacts", [])
        out.extend(cs)
        if not d.get("pagination", {}).get("hasMore"):
            break
        skip += 100
        if skip > 1000: break  # safety
    return out

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] LEAD MONITOR baslatildi (polling {POLL_SEC}sn)")
    sent_phones = load_sent_phones()
    print(f"  Takip edilen otel: {len(sent_phones)}")
    seen_inbound = load_already_logged_inbound()
    print(f"  Daha once tespit edilen yanitlayan: {len(seen_inbound)}")
    print(f"  Hedef: gonderilen otellerden yanit verenleri yakala")
    print()

    while not stop:
        try:
            contacts = fetch_contacts()
        except Exception as e:
            print(f"  [HATA] CRM fetch: {e}")
            time.sleep(POLL_SEC)
            continue

        yeni_yaniti = []
        for c in contacts:
            phone = c.get("phone", "")
            last = c.get("lastMessageReceivedAt")
            if not last: continue
            if phone not in sent_phones: continue  # bizim listemizden degil
            if phone in seen_inbound: continue     # daha once yakalandi

            # Yanit var ve daha once yakalanmamis
            info = sent_phones[phone]
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = {
                "timestamp": ts,
                "isim": info["isim"],
                "telefon": phone,
                "bolge": info["bolge"],
                "segment": info["segment"],
                "last_received": last,
                "received_count": c.get("messagesReceivedCount", 0),
                "contact_id": c.get("id", "")
            }
            log_inbound(row)
            seen_inbound.add(phone)
            yeni_yaniti.append(row)

            # Tag ekle
            existing = c.get("tags", []) or []
            new_tags = list(set(existing + ["hot_lead", "yaniti_var"]))
            add_tags(c["id"], new_tags)

            # OTOMATIK YANIT - 30-60sn gecikme ile
            participant_id = phone.replace("+", "")
            conv_id = find_conversation_id(participant_id)
            if conv_id:
                delay = random.randint(30, 60)
                print(f"   >>> {delay}sn sonra otomatik yanit gonderiliyor: {info['isim']}")
                time.sleep(delay)
                ok, mid = send_auto_reply(conv_id, info["isim"])
                if ok:
                    print(f"   >>> OTO-YANIT gonderildi: {mid}")
                    add_tags(c["id"], list(set(new_tags + ["oto_yanit_gonderildi"])))
                    row["oto_yanit"] = mid
                else:
                    print(f"   >>> OTO-YANIT HATA: {mid}")
                    row["oto_yanit"] = "FAILED: " + str(mid)[:80]
            else:
                print(f"   >>> conversation bulunamadi - manuel yanit gerek")
                row["oto_yanit"] = "NO_CONV"

        if yeni_yaniti:
            print()
            print("=" * 70)
            print(f"  *** YENİ YANIT *** ({len(yeni_yaniti)} otel) - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)
            for r in yeni_yaniti:
                print(f"  > {r['segment']:5}  {r['bolge']:8}  {r['telefon']:18}  {r['isim']}")
                print(f"    Toplam yanit: {r['received_count']}  | Son: {r['last_received'][:19]}")
            print(f"  >>> Inbound log: {INBOUND_LOG}")
            print()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] sync ok | takip {len(seen_inbound)} yanit | gonderilen {len(sent_phones)} otel")

        # Bekle
        for _ in range(POLL_SEC):
            if stop: break
            time.sleep(1)

if __name__ == "__main__":
    main()
