#!/usr/bin/env bash
# H-7 — Rebase PR #27 (Faz 2 birim katmani) onto PR #24 (Sales Manager QA).
#
# Iki PR de `src/agents/instructions/sales/manager.py` dosyasini modify
# ediyor — siralama: ONCE #24 main'e merge edilir, SONRA bu script #27'yi
# guncellenmis main'e rebase eder.
#
# Beklenen tek conflict: manager.py "## EMRINDEKI ALT BIRIMLER" bolumu.
# Cozum: #24'un brand-aware refactor'unu KORU, #27'in birim baslıklarini
# (Avcilik / CX / Kalite) ust uste BIRIKTIRREK ekle.
#
# Kullanim:
#   ./scripts/rebase_pr27_onto_pr24.sh           # interaktif rebase
#   ./scripts/rebase_pr27_onto_pr24.sh --abort   # rebase'i iptal et
#
# Onkosul:
#   - main'de PR #24 merge'i tamamlandi
#   - Lokal'de claude/sales-faz2-units checkout'lu
#   - Calisma agacı temiz (git status)

set -euo pipefail

BRANCH="claude/sales-faz2-units"
BASE="main"
CONFLICT_FILE="src/agents/instructions/sales/manager.py"

usage() {
  cat <<EOF
Usage: $0 [--abort | --continue | --check]

  (no args)   Run the rebase.
  --abort     Abort an in-progress rebase.
  --continue  Continue after manually resolving conflicts.
  --check     Print current branch + base divergence info, then exit.
EOF
}

case "${1:-}" in
  --abort)    git rebase --abort; exit 0 ;;
  --continue) git rebase --continue; exit 0 ;;
  --check)
    git fetch origin "$BASE" >/dev/null 2>&1 || true
    echo "current branch: $(git branch --show-current)"
    echo "base ($BASE) HEAD: $(git rev-parse "origin/$BASE")"
    echo "ahead by:  $(git rev-list --count "origin/$BASE..HEAD")"
    echo "behind by: $(git rev-list --count "HEAD..origin/$BASE")"
    exit 0 ;;
  -h|--help) usage; exit 0 ;;
esac

if [ "$(git branch --show-current)" != "$BRANCH" ]; then
  echo "ERROR: bu script $BRANCH branch'inden calistirilmali (su an: $(git branch --show-current))" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: calisma agaci temiz degil. Once stash et veya commit'le." >&2
  exit 1
fi

echo "[1/3] origin/$BASE fetch ediliyor..."
git fetch origin "$BASE"

echo "[2/3] $BRANCH -> origin/$BASE uzerine rebase..."
if git rebase "origin/$BASE"; then
  echo "[3/3] Rebase basarili. Push:"
  echo "  git push --force-with-lease origin $BRANCH"
  exit 0
fi

# Conflict olustu
echo
echo "=== CONFLICT ALGILANDI ==="
git status --short | grep '^UU' || true
echo

if git status --short | grep -q "$CONFLICT_FILE"; then
  cat <<EOF
$CONFLICT_FILE conflict'i bekleniyordu. Cozum:

1. Dosyayi ac:
     \$EDITOR $CONFLICT_FILE

2. <<<<<<< HEAD          (PR #24 main'e indi)
   ====
   >>>>>>> $BRANCH        (PR #27 birim katmani)

   PR #24 'in brand-aware + peer wiring + post_on_* yasak metni
   GENEL CATIYI olusturur. PR #27 'in Avcilik / CX / Kalite birim
   basliklari ALT BIRIMLER bolumune yerlestirilir.

   Hedef sira:
     ## ROLUN
     ... (PR #24'ten)
     ## EMRINDEKI ALT BIRIMLER
     - Avcilik Birimi (PR #27)
     - CX Birimi (PR #27)
     - Kalite Birimi (PR #27)
     ## YAZMA YETKILERIN
     ... (PR #24'ten)
     ## YASAKLAR
     ... (PR #24'ten — post_on_* dahil)

3. Cozum tamamlaninca:
     git add $CONFLICT_FILE
     ./scripts/rebase_pr27_onto_pr24.sh --continue

4. Tests dogrula:
     python3 -m pytest tests/test_sales_manager_wiring.py \\
                       tests/test_sales_unit_tools.py \\
                       tests/test_factory_backward_compat.py -v

5. Push:
     git push --force-with-lease origin $BRANCH
EOF
else
  echo "Beklenmeyen conflict dosyasi. git status'a bakip manuel cozumle."
fi

exit 2
