#!/usr/bin/env bash
# =============================================================================
# diagnose_nocodb.sh — NocoDB "Forbidden" teshis araci (SADECE OKUR, degistirmez)
#
# Amac: db.mindidai.com.tr / NocoDB IP neden 403 Forbidden veriyor anlamak.
# Cloud Shell'den (ya da NocoDB sunucusunun kendisinden) calistir.
#
# KULLANIM:
#   chmod +x scripts/diagnose_nocodb.sh
#   # token opsiyonel — vermezsen token'siz testler yapilir:
#   export NOCODB_API_TOKEN='...'        # (opsiyonel)
#   ./scripts/diagnose_nocodb.sh
#
# Hicbir veri yazmaz/silmez. Sadece GET istekleri + DNS/TLS kontrolu.
# =============================================================================
set -uo pipefail

DOMAIN="${NOCODB_DOMAIN:-db.mindidai.com.tr}"
IP="${NOCODB_IP:-34.26.138.196}"
TOKEN="${NOCODB_API_TOKEN:-}"
TIMEOUT=15

line() { printf '%s\n' "------------------------------------------------------------"; }
say()  { printf '\n>>> %s\n' "$1"; }

# Bir URL'i yoklar; HTTP kodu + onemli header'lari dondurur.
probe() {
  local url="$1"; shift
  local code headers
  headers="$(curl -s -m "$TIMEOUT" -D - -o /dev/null "$@" "$url" 2>/dev/null)"
  code="$(printf '%s' "$headers" | grep -iE '^HTTP/' | tail -1 | awk '{print $2}')"
  local server deny www loc
  server="$(printf '%s' "$headers" | grep -iE '^server:'        | head -1 | tr -d '\r')"
  deny="$(printf '%s'   "$headers" | grep -iE '^x-deny-reason:'  | head -1 | tr -d '\r')"
  www="$(printf '%s'    "$headers" | grep -iE '^www-authenticate:' | head -1 | tr -d '\r')"
  loc="$(printf '%s'    "$headers" | grep -iE '^location:'       | head -1 | tr -d '\r')"
  printf '    HTTP %-3s  %s  %s  %s  %s\n' "${code:-???}" "$server" "$deny" "$www" "$loc"
  printf '%s' "${code:-000}"
}

echo "============================================================"
echo " NocoDB Forbidden Teshis  —  $(date)"
echo " Domain: $DOMAIN   IP: $IP   Token: $([ -n "$TOKEN" ] && echo VAR || echo YOK)"
echo "============================================================"

# -----------------------------------------------------------------------------
say "1) DNS — domain hangi IP'ye gidiyor?"
line
RESOLVED="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1)"
if [ -z "$RESOLVED" ]; then
  RESOLVED="$(nslookup "$DOMAIN" 2>/dev/null | awk '/^Address: /{print $2}' | tail -1)"
fi
echo "    $DOMAIN  ->  ${RESOLVED:-COZULEMEDI}"
if [ -n "$RESOLVED" ] && [ "$RESOLVED" != "$IP" ]; then
  echo "    NOT: Domain'in gittigi IP ($RESOLVED), bekledigimiz IP'den ($IP) FARKLI."
  echo "         Demek araya bir proxy/Cloudflare/yeni sunucu girmis olabilir."
fi

# -----------------------------------------------------------------------------
say "2) Domain uzerinden HTTPS testleri"
line
C_ROOT=$(probe "https://$DOMAIN/")
C_DASH=$(probe "https://$DOMAIN/dashboard")
C_API=$(probe  "https://$DOMAIN/api/v2/meta/bases")
if [ -n "$TOKEN" ]; then
  echo "    -- token ile --"
  C_API_TOK=$(probe "https://$DOMAIN/api/v2/meta/bases" -H "xc-token: $TOKEN")
fi

# -----------------------------------------------------------------------------
say "3) IP'ye DIREKT (proxy/Caddy'i atlayarak) testler"
line
I_ROOT=$(probe "http://$IP/")
I_API=$(probe  "http://$IP/api/v2/meta/bases")
if [ -n "$TOKEN" ]; then
  I_API_TOK=$(probe "http://$IP/api/v2/meta/bases" -H "xc-token: $TOKEN")
fi

# -----------------------------------------------------------------------------
say "4) Cevap govdesi (403 ise sebebi cogu zaman burada yazar)"
line
echo "    domain / :"
curl -s -m "$TIMEOUT" "https://$DOMAIN/" 2>/dev/null | head -c 200
echo; echo "    -----"
echo "    domain /api :"
curl -s -m "$TIMEOUT" "https://$DOMAIN/api/v2/meta/bases" 2>/dev/null | head -c 200
echo

# -----------------------------------------------------------------------------
say "5) Bu makineden cikan genel IP (Caddy IP-allowlist'i icin lazim olabilir)"
line
MYIP="$(curl -s -m "$TIMEOUT" https://api.ipify.org 2>/dev/null || echo '(alinamadi)')"
echo "    Senin cikis IP'in: $MYIP"

# -----------------------------------------------------------------------------
say "6) NocoDB SUNUCUSUNDAYSAN (Cloud Shell degil) — container durumu"
line
if command -v docker >/dev/null 2>&1; then
  docker ps --format '    {{.Names}}  {{.Status}}  {{.Ports}}' 2>/dev/null | grep -iE 'noco|caddy' \
    || echo "    (noco/caddy container gorunmedi — ya bu sunucu degil ya da dusmus)"
else
  echo "    docker yok — demek bu makine NocoDB sunucusu degil (sorun degil)."
fi

# =============================================================================
say "TESHIS SONUCU (sade dil)"
line
verdict() {
  # $1 domain code, $2 ip code
  local d="$1" i="$2"
  if [ "$d" = "403" ] && [ "$i" = "200" ]; then
    echo "    -> Domain 403 ama IP 200. SUCLU: araya koydugun PROXY/CADDY."
    echo "       Caddy ya Host'u ya da senin IP'ni ($MYIP) reddediyor."
    echo "       COZUM: Caddy config'inde 'remote_ip allowlist' / Host kuralina"
    echo "       bu IP'yi ekle, ya da NocoDB'ye IP uzerinden baglan."
  elif [ "$d" = "403" ] && [ "$i" = "403" ]; then
    echo "    -> Hem domain hem IP 403. Filtre NocoDB'nin ONUNDE, her yoldan engelliyor."
    echo "       (Caddy global deny, ya da bu agdan cikis tamamen yasak.)"
  elif [ "$d" = "200" ] || [ "$d" = "401" ]; then
    echo "    -> Domain erisilebiliyor (kok / 403 olsa bile). Forbidden sadece '/'"
    echo "       yolunda olabilir. /dashboard ve /api calisiyorsa SORUN YOK,"
    echo "       migration'i kosabiliriz."
  else
    echo "    -> Karisik durum. Yukaridaki HTTP kodlarini bana aynen yapistir."
  fi
}
echo "  Domain  /=$C_ROOT  /dashboard=$C_DASH  /api=$C_API"
echo "  IP      /=$I_ROOT  /api=$I_API"
[ -n "$TOKEN" ] && echo "  Token   domain/api=${C_API_TOK:-?}  ip/api=${I_API_TOK:-?}"
echo
verdict "$C_API" "$I_API"
echo
echo "  NOT: '401 Unauthorized' iyi haberdir (sunucuya ULASTIN, sadece token lazim)."
echo "       '403 Forbidden' = bir kapi bekcisi seni iceri almiyor (token meselesi degil)."
line
echo "Bitti. Ciktinin tamamini kopyalayip bana gonder, sonraki adimi soyleyeyim."
