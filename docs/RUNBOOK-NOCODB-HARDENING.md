# NocoDB Sertleştirme Runbook

> **Amaç:** NocoDB'yi (lead defteri, `34.26.138.196`) statik IP + subdomain + SSL + reverse proxy + bot filter ile korunaklı hâle getir.
>
> **Süre:** 1 saat tek seferlik iş.
>
> **Yapan:** Şeyma (DNS + SSH gerekiyor) + bir Claude session (Caddy config + env güncelleme).

---

## Mevcut sorun (P1)

| # | Sorun | Etki |
|---|---|---|
| 1 | NocoDB `http://34.26.138.196:80` — SSL yok | Bazı ISP/kurumsal ağlar port 80'i blokluyor; "Beyza PC'sinden giremiyorum" şikayeti |
| 2 | Ephemeral IP (VM restart edilirse değişir) | IP değişince mind-agent + n8n + Cloud Run jobs + Beyza bookmark'ları kırılır |
| 3 | Bot saldırıları (`/cgi-bin/...`, `/.env`, `/wp-admin`) | NocoDB SQLite pool dolar → OOM crash → 30 sn outage |

---

## Çözüm mimarisi

```
İnternet
   │
   ▼  443 (HTTPS, Let's Encrypt SSL)
 Caddy reverse proxy  ──► junk path filter (444 close)
   │
   ▼  127.0.0.1:8080 (yalnızca localhost'tan erişilir)
 NocoDB container
   │
   ▼
 SQLite (artık dış dünyaya hiç açık değil)
```

---

## Adım 1 — Static IP rezerve et (5 dk, GCP Console)

```bash
# GCP Console: VPC Network → External IP addresses → Reserve static address
# Region: us-central1 (NocoDB VM'in bulunduğu region)
# Type: Regional → Standard tier
# Attach to: NocoDB VM (mevcut ephemeral IP'sine bağla)
```

Veya gcloud ile:
```bash
gcloud compute addresses create nocodb-static-ip \
  --region=us-central1 \
  --project=instagram-post-bot-471518

# IP'yi VM'e bağla
gcloud compute instances delete-access-config <NOCODB_VM_NAME> \
  --zone=us-central1-a --access-config-name="External NAT"

gcloud compute instances add-access-config <NOCODB_VM_NAME> \
  --zone=us-central1-a --access-config-name="External NAT" \
  --address=<RESERVED_STATIC_IP>
```

Çıktıdaki IP'yi kaydet (örn. `34.26.138.196` aynı kalabilir).

---

## Adım 2 — Subdomain DNS A record (10 dk, DNS sağlayıcı)

DNS sağlayıcında (Cloudflare / Namecheap / nereyse):

| Type | Name | Value | TTL | Proxy |
|---|---|---|---|---|
| A | `crm` | `<STATIC_IP>` | 300 | ☐ DNS only (Cloudflare proxy KAPALI) |

> **Önemli:** Cloudflare proxy'yi KAPALI tut. Caddy Let's Encrypt sertifikası alacak, proxy açıkken HTTP-01 challenge başarısız olur.

Propagation kontrolü:
```bash
dig crm.slowdaysai.com +short
# Beklenen: <STATIC_IP>
```

---

## Adım 3 — NocoDB VM'e SSH + Caddy kur (20 dk)

```bash
gcloud compute ssh <NOCODB_VM_NAME> --zone=us-central1-a

# Caddy kur (Debian/Ubuntu)
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

caddy version  # doğrula
```

---

## Adım 4 — NocoDB'yi 127.0.0.1'e bağla (5 dk)

NocoDB Docker container ise:
```bash
# Mevcut container'ı durdur
docker ps  # NocoDB container adını bul
docker stop <NOCODB_CONTAINER>
docker rm <NOCODB_CONTAINER>

# Yeniden başlat — port mapping artık SADECE localhost
docker run -d --name nocodb \
  -p 127.0.0.1:8080:8080 \
  -v /path/to/nocodb-data:/usr/app/data \
  --restart unless-stopped \
  nocodb/nocodb:latest
```

NocoDB systemd servisi ise: `/etc/systemd/system/nocodb.service` içinde `--bind 127.0.0.1` ekle.

**Doğrulama:**
```bash
curl http://localhost:8080  # OK
curl http://<STATIC_IP>:8080  # Connection refused (BAŞARI — dış dünya artık göremez)
```

---

## Adım 5 — Caddy config (10 dk)

```bash
sudo nano /etc/caddy/Caddyfile
```

İçerik:
```caddy
crm.slowdaysai.com {
    # Otomatik Let's Encrypt SSL
    encode gzip

    # Bot saldırı path'lerini sessizce reddet (444 = connection close)
    @junk {
        path /cgi-bin/* /.env /.git/* /wp-admin/* /wp-login* /phpmyadmin/* /.htaccess /xmlrpc.php
    }
    handle @junk {
        respond 444
    }

    # NocoDB'ye proxy
    reverse_proxy 127.0.0.1:8080 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Caddy access log (debugging)
    log {
        output file /var/log/caddy/nocodb-access.log {
            roll_size 100mb
            roll_keep 5
        }
        format json
    }
}
```

Test + restart:
```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart caddy
sudo systemctl status caddy  # active (running)
sudo journalctl -u caddy -n 50  # SSL certificate obtained kontrol et
```

**Doğrulama:**
```bash
curl -I https://crm.slowdaysai.com
# Beklenen: HTTP/2 200, NocoDB header'ları

curl -I https://crm.slowdaysai.com/.env
# Beklenen: connection closed (444)
```

---

## Adım 6 — Tüm referansları güncelle (10 dk)

Yeni `NOCODB_BASE_URL=https://crm.slowdaysai.com` (eski: `http://34.26.138.196`).

### 6.1 — Cloud Run service + 4 job
```bash
NEW_URL="https://crm.slowdaysai.com"

gcloud run services update agents-sdk-api --region=us-central1 \
  --update-env-vars="NOCODB_BASE_URL=$NEW_URL"

for JOB in guardian-tick outreach-tick followup-tick auto-reply-tick; do
  gcloud run jobs update "$JOB" --region=us-central1 \
    --update-env-vars="NOCODB_BASE_URL=$NEW_URL"
done
```

### 6.2 — n8n workflow'ları
n8n UI (`https://mindidai.app.n8n.cloud`):
- Tüm "NocoDB" node'larında URL'i `https://crm.slowdaysai.com` yap
- Etkilenen workflow'lar: Lead Toplama, Itiraz, Takip, Upsell, Referans, Bekçi Alert, Meta Lead Ads

### 6.3 — Beyza/Şeyma bookmark
Yeni adres: `https://crm.slowdaysai.com`

### 6.4 — Şeyma'nın PC scriptleri (eğer hâlâ çalışıyorsa)
- `otel_gonderim.py` → `NOCODB_BASE_URL` constant'ını değiştir
- `lead_monitor.py` → aynı

---

## Adım 7 — Sağlık testi (5 dk)

```bash
# Service test
curl -s https://agents-sdk-api-704233028546.us-central1.run.app/health
# Beklenen: {"status":"ok"}

# Lead query (yeni NocoDB URL üzerinden)
TOKEN=$(gcloud auth print-identity-token)
curl -s --max-time 60 -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task":"kaç sıcak lead var","business_id":"satis_dashboard","task_id":"healthcheck"}' \
  https://agents-sdk-api-704233028546.us-central1.run.app/task | tail -c 500
# Beklenen: sıcak lead sayısı

# Bekçi tick test
gcloud run jobs execute guardian-tick --region=us-central1 --wait
# Beklenen: 1/1 complete
```

---

## Rollback (sorun çıkarsa)

Hızlı geri dönüş:
```bash
# Caddy'yi durdur
sudo systemctl stop caddy

# NocoDB'yi tekrar 0.0.0.0'a bağla (eski hâl)
docker stop nocodb && docker rm nocodb
docker run -d --name nocodb -p 0.0.0.0:80:8080 ... nocodb/nocodb:latest

# Cloud Run env'leri eski URL'e geri al
gcloud run services update agents-sdk-api --region=us-central1 \
  --update-env-vars="NOCODB_BASE_URL=http://34.26.138.196"
# 4 job için de aynı
```

---

## Kazanım sonrası

- ✅ `https://crm.slowdaysai.com` (SSL kilitli)
- ✅ Her ağdan erişilebilir (port 443 her yerde açık)
- ✅ Bot saldırıları Caddy'de 444 ile düşürülüyor — NocoDB hiç görmüyor
- ✅ IP değişse bile DNS A record güncellenir, başka hiçbir yer dokunulmaz
- ✅ HTTP → HTTPS otomatik redirect (Caddy default)
- ✅ Access log var (`/var/log/caddy/nocodb-access.log`) — saldırı pattern'leri izlenebilir

## Risk
Düşük. Tek dikkat: Cloudflare proxy KAPALI olmalı (DNS only). Açıksa Let's Encrypt fail eder.

## Yeni session'da
1. Bu dokümanı oku
2. Şeyma'ya: "Adım 1-2 (Static IP + DNS) hazır mı?" diye sor
3. Hazırsa ben Adım 3-7'ye eşlik ederim (Cloud Shell + SSH yönlendirme)

---

**Yazıldı:** 2026-05-21, Claude Opus 4.7
