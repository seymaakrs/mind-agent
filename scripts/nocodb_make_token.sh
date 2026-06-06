#!/usr/bin/env bash
# =============================================================================
# nocodb_make_token.sh — Panel (UI) kapaliyken API uzerinden NocoDB API token uret.
#
# Caddy NocoDB panelini (/, /dashboard) 403 ile kapatmis olabilir; ama /api
# acik (401 donuyor). Bu script email+sifre ile API'den giris yapip kalici
# bir API token (xc-token) olusturur ve test eder.
#
# KULLANIM (Cloud Shell):
#   export NOCODB_BASE_URL='https://db.mindidai.com.tr'   # ya da http://34.26.138.196
#   export NC_EMAIL='seymaakrs@gmail.com'
#   export NC_PASSWORD='NocoDB-sifren'
#   chmod +x scripts/nocodb_make_token.sh
#   ./scripts/nocodb_make_token.sh
#
# Cikan token'i NOT AL — migration'da kullanacagiz. Hicbir veri degismez.
# =============================================================================
set -uo pipefail

BASE="${NOCODB_BASE_URL:-https://db.mindidai.com.tr}"
BASE="${BASE%/}"
EMAIL="${NC_EMAIL:-}"
PW="${NC_PASSWORD:-}"
T=20

if [ -z "$EMAIL" ] || [ -z "$PW" ]; then
  echo "HATA: once NC_EMAIL ve NC_PASSWORD export et."
  echo "  export NC_EMAIL='...'"
  echo "  export NC_PASSWORD='...'"
  exit 2
fi

echo "============================================================"
echo " NocoDB API token uretici  —  base: $BASE"
echo "============================================================"

# --- 1) Giris yap (JWT al). NocoDB v1 ve v2 signin yollarini sirayla dene. ---
say_try() { printf '\n>>> %s\n' "$1"; }

get_jwt() {
  local path="$1"
  curl -s -m "$T" -X POST "$BASE$path" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" 2>/dev/null
}

say_try "1) Giris deneniyor (signin)"
RESP=""
for p in "/api/v2/auth/user/signin" "/api/v1/auth/user/signin" "/api/v1/db/auth/user/signin"; do
  R="$(get_jwt "$p")"
  if printf '%s' "$R" | grep -q '"token"'; then
    RESP="$R"; echo "    OK  ->  $p"
    break
  else
    echo "    dene $p  ->  $(printf '%s' "$R" | head -c 120)"
  fi
done

JWT="$(printf '%s' "$RESP" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
if [ -z "$JWT" ]; then
  echo
  echo "HATA: Giris yapilamadi. Email/sifre yanlis olabilir, ya da signin yolu farkli."
  echo "Yukaridaki cevaplari bana yapistir."
  exit 1
fi
echo "    JWT alindi (xc-auth). Uzunluk: ${#JWT}"

# --- 2) Bu JWT ile meta API calisiyor mu? (xc-auth header) ---
say_try "2) JWT ile meta API testi (xc-auth)"
CODE=$(curl -s -m "$T" -o /dev/null -w '%{http_code}' \
  -H "xc-auth: $JWT" "$BASE/api/v2/meta/bases" 2>/dev/null)
echo "    /api/v2/meta/bases  ->  HTTP $CODE  (200 = mukemmel)"

# --- 3) Kalici API token olustur. Yine v1/v2 yollarini dene. ---
say_try "3) Kalici API token olusturuluyor"
NEW=""
for p in "/api/v2/meta/api-tokens" "/api/v1/tokens" "/api/v1/db/meta/api-tokens"; do
  R="$(curl -s -m "$T" -X POST "$BASE$p" \
        -H "xc-auth: $JWT" -H 'Content-Type: application/json' \
        -d '{"description":"mind-agent-haziran"}' 2>/dev/null)"
  TOK="$(printf '%s' "$R" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  if [ -n "$TOK" ]; then NEW="$TOK"; echo "    OK  ->  $p"; break; fi
  echo "    dene $p  ->  $(printf '%s' "$R" | head -c 120)"
done

echo
echo "============================================================"
if [ -n "$NEW" ]; then
  echo " BASARILI — yeni kalici API token:"
  echo
  echo "   $NEW"
  echo
  echo " Sonraki adim (migration dry-run):"
  echo "   export NOCODB_BASE_URL='$BASE'"
  echo "   export NOCODB_API_TOKEN='$NEW'"
  echo "   export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'"
  echo "   python scripts/migrate_qualifier_schema.py"
else
  echo " API token olusturulamadi AMA JWT calisiyorsa migration'i JWT ile de"
  echo " kosabiliriz. Yukaridaki HTTP kodlarini ve cevaplari bana gonder."
fi
echo "============================================================"
