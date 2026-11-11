#!/bin/bash
# =====================================================================
#  vsget – Beitraege von Claude-Zweigen (claude/*) auf GitHub abholen
#  Laeuft auf dem Rechner des Herausgebers (NiPoGi), nur dort, nur von Paul.
#
#    vsget               offene claude/*-Zweige zeigen, einen als Bundle nach ~/share/Updates
#    vsget <nr|zweig>    genau diesen Zweig holen (z. B.  vsget 2  oder  vsget claude/tastatur)
#    vsget --liste       nur anzeigen, nichts holen
#
#  Ablauf: Claude pusht nie nach main, sondern auf einen eigenen Zweig claude/<thema>
#  (ein Zweig pro Chat). vsget prueft jeden Zweig gegen den aktuellen GitHub-Stand
#  (passt er konfliktfrei auf main? fasst er dist/ oder keys/ an?), baut daraus ein
#  Bundle mit der Referenz refs/heads/main – genau wie tools/mkbundle.sh – und legt
#  es nach ~/share/Updates. Eingespielt wird weiterhin nur mit  vspub.
#  Zweige, die schon in main stecken, bietet vsget zum Loeschen auf GitHub an.
#
#  vsget aendert am lokalen Repo nichts (kein Checkout, kein Merge) – nur die
#  Remote-Referenzen werden aktualisiert.
#
#  Alias – einmalig in ~/.bashrc eintragen:
#     alias vsget='bash ~/VoidStation/tools/vsget.sh'
# =====================================================================
set -euo pipefail

REPO="${VS_REPO:-$HOME/VoidStation}"
INBOX="${VS_INBOX:-$HOME/share/Updates}"
PREFIX="claude/"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*"; exit 1; }
ask()  { local a; read -r -p "$1 [j/N] " a; [ "$a" = j ] || [ "$a" = J ]; }

TMPS=()
cleanup() { [ ${#TMPS[@]} -eq 0 ] || rm -rf "${TMPS[@]}"; }
trap cleanup EXIT

ARG="${1:-}"
case "$ARG" in
  -h|--help) sed -n '3,21p' "$0" | sed 's/^# \{0,2\}//'; exit 0 ;;
esac

[ -d "$REPO/.git" ] || die "Kein Repo unter $REPO gefunden."
cd "$REPO"

git fetch -q --prune origin || die "GitHub nicht erreichbar."
git rev-parse -q --verify origin/main >/dev/null || die "origin/main fehlt."
BASE="$(git rev-parse origin/main)"

# merge-tree --write-tree gibt es ab git 2.38
MT=1
git merge-tree --write-tree "$BASE" "$BASE" >/dev/null 2>&1 || MT=0

ago() {                    # <unix-zeit> -> "vor 3 Std." / "vor 2 Tagen"
  local s=$(( $(date +%s) - $1 ))
  if   [ $s -lt 3600 ];  then echo "vor $(( s / 60 )) Min."
  elif [ $s -lt 86400 ]; then echo "vor $(( s / 3600 )) Std."
  else echo "vor $(( s / 86400 )) Tagen"; fi
}

# ---------------------------------------------------------------------
#  Zweige einsammeln
#    OPEN_*   noch nicht in main
#    DONE     schon komplett in main (eingespielt) -> darf weg
# ---------------------------------------------------------------------
OPEN_NAME=(); OPEN_TIP=(); OPEN_STATE=(); OPEN_INFO=(); DONE=()
while read -r ref; do
  [ -n "$ref" ] || continue
  name="${ref#origin/}"
  tip="$(git rev-parse "$ref")"
  if git merge-base --is-ancestor "$tip" "$BASE"; then DONE+=("$name"); continue; fi

  state="passt"; info=""
  if ! git diff --quiet "$BASE...$tip" -- dist keys; then
    state="gesperrt"; info="aendert dist/ oder keys/ – das darf nur vspub"
  elif [ "$MT" = 1 ]; then
    if ! out="$(git merge-tree --write-tree --name-only "$BASE" "$tip" 2>/dev/null)"; then
      state="Konflikt"
      info="$(printf '%s\n' "$out" | sed -n '2,/^$/p' | sed '/^$/d' | paste -sd ' ')"
    fi
  else
    state="ungeprueft"; info="git zu alt fuer die Konfliktpruefung (ab 2.38)"
  fi
  if [ "$state" = passt ] && ! git merge-base --is-ancestor "$BASE" "$tip"; then
    info="baut auf aelterem Stand auf, laesst sich aber sauber zusammenfuehren"
  fi
  OPEN_NAME+=("$name"); OPEN_TIP+=("$tip"); OPEN_STATE+=("$state"); OPEN_INFO+=("$info")
done < <(git for-each-ref --sort=committerdate --format='%(refname:short)' "refs/remotes/origin/$PREFIX")

# ---------------------------------------------------------------------
#  Anzeige
# ---------------------------------------------------------------------
say "Offene Claude-Zweige (Basis: $(git log -1 --format='%h %s' "$BASE" | cut -c1-70))"
if [ ${#OPEN_NAME[@]} -eq 0 ]; then
  echo "  (keine)"
else
  for i in "${!OPEN_NAME[@]}"; do
    t="${OPEN_TIP[i]}"
    n="$(git rev-list --count --no-merges "$BASE..$t")"
    case "${OPEN_STATE[i]}" in
      passt)    col='\033[1;32m' ;;
      Konflikt|gesperrt) col='\033[1;31m' ;;
      *)        col='\033[1;33m' ;;
    esac
    printf "  %2d) %-28s ${col}%-10s\033[0m %2d Commit(s), %s\n" \
      $((i + 1)) "${OPEN_NAME[i]}" "${OPEN_STATE[i]}" "$n" "$(ago "$(git log -1 --format=%ct "$t")")"
    printf '        %s\n' "$(git log -1 --format=%s "$t" | cut -c1-90)"
    [ -z "${OPEN_INFO[i]}" ] || printf '        \033[2m%s\033[0m\n' "${OPEN_INFO[i]}"
  done
fi

# Eingespielte Zweige aufraeumen
if [ ${#DONE[@]} -gt 0 ] && [ "$ARG" != --liste ]; then
  echo
  echo "Schon in main (eingespielt): ${DONE[*]}"
  if ask "Diese ${#DONE[@]} Zweig(e) auf GitHub loeschen?"; then
    if git push -q origin "${DONE[@]/#/:refs/heads/}"; then echo "geloescht."
    else warn "Loeschen fehlgeschlagen (Token ohne Schreibrecht?) – stoert nicht weiter."; fi
  fi
fi

[ "$ARG" != --liste ] || exit 0
[ ${#OPEN_NAME[@]} -gt 0 ] || { echo; echo "Nichts abzuholen."; exit 0; }

# ---------------------------------------------------------------------
#  Auswahl
# ---------------------------------------------------------------------
pick=""
if [ -n "$ARG" ]; then
  if [[ "$ARG" =~ ^[0-9]+$ ]]; then
    [ "$ARG" -ge 1 ] && [ "$ARG" -le ${#OPEN_NAME[@]} ] || die "Keinen Zweig Nr. $ARG."
    pick=$((ARG - 1))
  else
    want="${ARG#origin/}"; [[ "$want" == "$PREFIX"* ]] || want="$PREFIX$want"
    for i in "${!OPEN_NAME[@]}"; do [ "${OPEN_NAME[i]}" = "$want" ] && pick=$i; done
    [ -n "$pick" ] || die "Kein offener Zweig $want."
  fi
elif [ ${#OPEN_NAME[@]} -eq 1 ]; then
  pick=0
else
  echo
  read -r -p "Welchen holen? (Nummer, Enter = keinen) " a
  [ -n "$a" ] || { echo "Nichts geholt."; exit 0; }
  [[ "$a" =~ ^[0-9]+$ ]] && [ "$a" -ge 1 ] && [ "$a" -le ${#OPEN_NAME[@]} ] || die "Ungueltige Auswahl: $a"
  pick=$((a - 1))
fi

name="${OPEN_NAME[pick]}"; tip="${OPEN_TIP[pick]}"; state="${OPEN_STATE[pick]}"
case "$state" in
  gesperrt) die "$name ${OPEN_INFO[pick]}." ;;
  Konflikt) die "$name passt nicht mehr auf main (Konflikt in: ${OPEN_INFO[pick]}).
    Im zugehoerigen Chat sagen: \"Zweig auf origin/main rebasen und neu pushen\" – dann nochmal  vsget." ;;
  ungeprueft) warn "Konfliktpruefung nicht moeglich – vspub merkt einen Konflikt spaetestens beim Einspielen (und aendert dann nichts)." ;;
esac

# Nicht eingespielte Bundles im Eingang? vspub nimmt immer nur das neueste.
old="$(ls -t "$INBOX"/*.bundle 2>/dev/null || true)"
if [ -n "$old" ]; then
  die "In $INBOX liegt noch ein Bundle, das nicht eingespielt ist:
$(printf '%s\n' "$old" | sed 's|.*/|  |')
  Erst  vspub  (oder das Bundle bewusst loeschen), dann nochmal  vsget."
fi

# ---------------------------------------------------------------------
#  Bundle bauen: Referenz refs/heads/main = Zweigspitze, Vorgaenger = origin/main
#  (in einem Hilfs-Repo, das die Objekte von hier mitbenutzt – das echte main bleibt unberuehrt)
# ---------------------------------------------------------------------
say "Hole $name"
git log --reverse --no-merges --format='  %h %s' "$BASE..$tip" | cut -c1-100
sess="$(git log -1 --format='%(trailers:key=Claude-Session,valueonly)' "$tip" | head -n1)"
[ -z "$sess" ] || echo "  Chat: $sess"

mkdir -p "$INBOX"
topic="${name#"$PREFIX"}"; topic="${topic//[^A-Za-z0-9._-]/-}"
f="$INBOX/VoidStation-$(git rev-parse --short "$tip")-$topic.bundle"
tmp="$(mktemp -d)"; TMPS+=("$tmp")
git init -q --bare "$tmp/b.git"
( cd "$(git rev-parse --git-path objects)" && pwd ) > "$tmp/b.git/objects/info/alternates"
git -C "$tmp/b.git" update-ref refs/heads/main "$tip"
git -C "$tmp/b.git" update-ref refs/remotes/origin/main "$BASE"
git -C "$tmp/b.git" bundle create -q "$f.part" origin/main..main

# Probe wie vspub: passt zum Repo, enthaelt genau refs/heads/main
git bundle verify -q "$f.part" >/dev/null 2>&1 || { rm -f "$f.part"; die "Bundle passt nicht zum Repo."; }
[ "$(git bundle list-heads "$f.part")" = "$tip refs/heads/main" ] || { rm -f "$f.part"; die "Bundle enthaelt die falschen Referenzen."; }
mv "$f.part" "$f"
echo "Bundle: $f"

echo
if ask "Gleich einspielen (vspub)?"; then
  exec bash "$REPO/tools/publish.sh"
fi
echo "Einspielen spaeter mit:  vspub"
