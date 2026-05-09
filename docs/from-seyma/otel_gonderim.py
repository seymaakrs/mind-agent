"""
PROFESYONEL OTEL WHATSAPP GONDERIM
- Tek tek gonderim (insan davranisi)
- Random delay 25-90 sn
- Her 20 mesajda 4-7 dk mola
- 09:00-21:00 mesai saatleri
- 250/24h TIER limiti
- Hata retry 2x
- Resume capability (log'dan devam)
- Ctrl+C ile temiz cikis
"""
import csv, json, time, random, sys, os, signal, io
from datetime import datetime
import requests

# Windows konsol UTF-8 zorla
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

API_KEY = "sk_bbd6bbced7a54fe6af777ffc13c8ee5a66782b4e532eb305d35a7bfda0351957"
BASE = "https://api.zernio.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

WA_ACCOUNT_ID = "69ecc2273a63baf2053dfc21"
TEMPLATE_NAME = "ege_otel_yaz_sezon_v1"
TEMPLATE_LANG = "tr"

DAILY_LIMIT = 240         # TIER_250 - 10 buffer
WORK_HOURS = (9, 21)      # 09:00 - 21:00
DELAY_RANGE = (25, 90)    # saniye, gerçek + jitter
BATCH_SIZE = 20           # 20 mesajda mola
BATCH_BREAK = (240, 420)  # 4-7 dk mola
RETRY_COUNT = 2
RETRY_DELAY = 30

MASTER_CSV = "otel_master.csv"
LOG_CSV = "gonderim_log.csv"

stop_flag = False
def handle_sigint(s, f):
    global stop_flag
    print("\n\n[CTRL+C] Mevcut mesaj bittikten sonra duracak...")
    stop_flag = True
signal.signal(signal.SIGINT, handle_sigint)

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_work_hour():
    h = datetime.now().hour
    return WORK_HOURS[0] <= h < WORK_HOURS[1]

def wait_for_work_hours():
    while not is_work_hour():
        h = datetime.now().hour
        if h < WORK_HOURS[0]:
            sec = (WORK_HOURS[0] - h) * 3600
        else:
            sec = (24 - h + WORK_HOURS[0]) * 3600
        print(f"[{now_iso()}] Mesai disi (saat {h}). {sec//60} dk sonra basla...")
        time.sleep(min(sec, 600))  # max 10 dk uyu, sonra tekrar kontrol

def load_master():
    rows = []
    with open(MASTER_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def load_sent_log():
    """Daha once basariyla gonderilenleri don."""
    sent = set()
    if not os.path.exists(LOG_CSV):
        return sent
    with open(LOG_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("status") == "SENT":
                sent.add(r["telefon"])
    return sent

def count_today():
    """Bugun gonderilen sayisi."""
    today = datetime.now().strftime("%Y-%m-%d")
    n = 0
    if not os.path.exists(LOG_CSV):
        return 0
    with open(LOG_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("status") == "SENT" and r.get("timestamp", "").startswith(today):
                n += 1
    return n

def log_write(row):
    new_file = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp","isim","telefon","bolge","segment","status","messageId","error"])
        if new_file: w.writeheader()
        w.writerow(row)

def send_one(isim, telefon):
    body = {
        "accountId": WA_ACCOUNT_ID,
        "template": {"name": TEMPLATE_NAME, "language": TEMPLATE_LANG},
        "recipients": [{"phone": telefon, "variables": [isim]}]
    }
    last_err = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            r = requests.post(f"{BASE}/whatsapp/bulk", headers=HEADERS, json=body, timeout=30)
            d = r.json()
            if d.get("success") and d.get("summary", {}).get("sent", 0) >= 1:
                msg_id = d["results"][0].get("messageId", "")
                return True, msg_id, None
            else:
                err = d.get("results", [{}])[0].get("error") or d.get("error") or str(d)[:200]
                last_err = err
        except Exception as e:
            last_err = str(e)[:200]
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY)
    return False, None, last_err

def main():
    sent_phones = load_sent_log()
    today_count = count_today()
    print(f"[{now_iso()}] BAŞLANGIÇ")
    print(f"   Daha once gonderilen: {len(sent_phones)}")
    print(f"   Bugun gonderilen: {today_count}/{DAILY_LIMIT}")

    if today_count >= DAILY_LIMIT:
        print(f"   ! Gunluk limit dolu. Yarin devam.")
        sys.exit(0)

    rows = load_master()
    pending = [r for r in rows if r["telefon"] not in sent_phones]
    print(f"   Toplam: {len(rows)} | Pending: {len(pending)}")
    print(f"   Tahmini sure (40sn ortalama): {len(pending)*40/60:.0f} dk")
    print()

    sent_in_run = 0
    failed = 0

    for i, otel in enumerate(pending):
        if stop_flag:
            print("Duruldu (Ctrl+C).")
            break
        if today_count >= DAILY_LIMIT:
            print(f"\n[{now_iso()}] ✋ Gunluk limit ({DAILY_LIMIT}) doldu. Yarin devam.")
            break

        if not is_work_hour():
            wait_for_work_hours()

        isim = otel["isim"][:40]
        telefon = otel["telefon"]
        seg = otel["segment"]
        bolge = otel["bolge"]

        ok, msg_id, err = send_one(isim, telefon)
        ts = now_iso()
        if ok:
            sent_in_run += 1
            today_count += 1
            # ÖNCE log yaz, SONRA print (print crash etse bile log korunur)
            log_write({"timestamp": ts, "isim": isim, "telefon": telefon, "bolge": bolge,
                       "segment": seg, "status": "SENT", "messageId": msg_id or "", "error": ""})
            try:
                print(f"[{ts}] OK {today_count:3}/{DAILY_LIMIT} {seg:5} {bolge:8} {telefon} {isim}")
            except Exception: pass
        else:
            failed += 1
            log_write({"timestamp": ts, "isim": isim, "telefon": telefon, "bolge": bolge,
                       "segment": seg, "status": "FAILED", "messageId": "", "error": err or ""})
            try:
                print(f"[{ts}] FAIL {seg:5} {bolge:8} {telefon} {isim} | {err}")
            except Exception: pass

        # Batch break
        if sent_in_run > 0 and sent_in_run % BATCH_SIZE == 0 and not stop_flag:
            br = random.randint(*BATCH_BREAK)
            print(f"\n[{now_iso()}] -- {BATCH_SIZE}/{BATCH_SIZE} mola: {br//60}dk{br%60}sn --\n")
            for _ in range(br):
                if stop_flag: break
                time.sleep(1)
            continue

        # Insan delay
        if not stop_flag and (i + 1) < len(pending):
            d = random.randint(*DELAY_RANGE)
            time.sleep(d)

    print(f"\n[{now_iso()}] BITTI")
    print(f"   Bu run: gonderildi={sent_in_run} | basarisiz={failed}")
    print(f"   Gun toplami: {today_count}/{DAILY_LIMIT}")
    kalan = sum(1 for r in rows if r["telefon"] not in sent_phones) - sent_in_run
    print(f"   Listede kalan: {kalan}")

if __name__ == "__main__":
    main()
