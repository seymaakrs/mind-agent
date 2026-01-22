import requests
import json
import datetime
import sys

url = "http://localhost:8000/task"
data = {
    "task": "test, bana kisa bir sarki sozu yaz",
    "business_id": "dImxI3K5p6zfelpS9rSE"
}

print(f"[{datetime.datetime.now().time()}] Request gonderiliyor...", flush=True)

try:
    with requests.post(url, json=data, stream=True) as r:
        print(f"[{datetime.datetime.now().time()}] Headers alindi (Status: {r.status_code})", flush=True)
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(f"[{datetime.datetime.now().time()}] Gelen: {decoded_line}", flush=True)
except Exception as e:
    print(f"Hata: {e}")
