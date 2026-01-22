import requests
import json
import datetime

url = "http://localhost:8000/task"
# 20 saniyelik bir islem simule etmek icin karmasik bir task verelim
data = {"task": "instagram hesabimi analiz et, son postlarima bak ve bana detayli bir rapor cikar."}

print(f"[{datetime.datetime.now()}] Request gonderiliyor...")

try:
    with requests.post(url, json=data, stream=True) as r:
        print(f"[{datetime.datetime.now()}] Headers alindi (Status: {r.status_code})")
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(f"[{datetime.datetime.now()}] Gelen veri: {decoded_line}")
except Exception as e:
    print(f"Hata: {e}")
