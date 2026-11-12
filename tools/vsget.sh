#!/bin/bash
# =====================================================================
#  vsget – Beitraege von Claude-Zweigen (claude/*) auf GitHub abholen
#  Laeuft auf dem Rechner des Herausgebers (NiPoGi), nur dort, nur von Paul.
#
#    vsget               offene claude/*-Zweige zeigen, einen oder mehrere als ein Bundle nach ~/share/Updates
#    vsget <auswahl>     genau diese Zweige holen, z. B.  vsget 2   vsget 1,3   vsget 1-3   vsget alle
#                        oder  vsget claude/tastatur  (Name, auch mehrere)
#    vsget --liste       nur anzeigen, nichts holen
#
#  Auswahl (auch bei der Frage "Welche holen?"): Nummern mit Komma oder Leerzeichen
#  ("1, 2"), Bereiche ("1-3"), "alle". Mehrere Zweige werden in Listenreihenfolge
#  auf main zusammengefuehrt und landen in EINEM Bundle – ein vspub, eine Passphrase.
#
#  Ablauf: Claude pusht nie nach main, sondern auf einen eigenen Zweig claude/<thema>
#  (ein Zweig pro Chat). vsget prueft jeden Zweig gegen den aktuellen GitHub-Stand
#  (passt er konfliktfrei auf main? fasst er dist/ oder keys/ an?), fuehrt ihn mit
#  main zusammen, baut daraus ein Bundle mit der Referenz refs/heads/main – genau wie
#  tools/mkbundle.sh – und legt es nach ~/share/Updates. Eingespielt wird weiterhin
#  nur mit  vspub.
#  CHANGELOG.md/CHANGELOG.en.md: Jeder Zweig setzt seinen Eintrag ganz oben ein, das
#  ergaebe bei jedem zweiten Zweig einen Konflikt. Beim Zusammenfuehren behaelt vsget
#  deshalb beide Seiten (Git-Treiber "union", nur im Hilfs-Repo von vsget), die
#  Eintraege des Zweigs oben. Konflikte in anderen Dateien bleiben Konflikte.
#  Zweige, die schon in main stecken (auch per Squash oder Rebase), bietet vsget
#  zum Loeschen auf GitHub an.
#
#  vsget aendert am lokalen Repo nichts (kein Checkout, kein Merge) – nur die
#  Remote-Referenzen werden aktualisiert. Zusammengefuehrt wird in einem Hilfs-Repo,
#  das die Objekte von hier mitbenutzt.
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

ARG="$*"
case "${1:-}" in
  -h|--help) sed -n '3,36p' "$0" | sed 's/^# \{0,2\}//'; exit 0 ;;
esac

[ -d "$REPO/.git" ] || die "Kein Repo unter $REPO gefunden."
cd "$REPO"

git fetch -q --prune origin || die "GitHub nicht erreichbar."
git rev-parse -q --verify origin/main >/dev/null || die "origin/main fehlt."
BASE="$(git rev-parse origin/main)"

# Hilfs-Repo: benutzt die Objekte von hier mit, Changelogs werden beim Zusammenfuehren
# vereinigt statt als Konflikt gemeldet (info/attributes gilt nur dort).
HELP="$(mktemp -d)"; TMPS+=("$HELP"); HB="$HELP/b.git"
git init -q --bare "$HB"
( cd "$(git rev-parse --git-path objects)" && pwd ) > "$HB/objects/info/alternates"
printf '%s\n' 'CHANGELOG.md merge=union' 'CHANGELOG.en.md merge=union' > "$HB/info/attributes"
hg() { git -C "$HB" "$@"; }

# merge-tree --write-tree gibt es ab git 2.38
MT=1
hg merge-tree --write-tree "$BASE" "$BASE" >/dev/null 2>&1 || MT=0

merge_tree() {             # <a> <b> – Baum von a+b (Changelog-Zeilen von a oben); bei Konflikt Dateiliste, rc 1
  local out
  if out="$(hg merge-tree --write-tree --name-only "$1" "$2" 2>/dev/null)"; then
    printf '%s\n' "$out" | head -n1; return 0
  fi
  printf '%s\n' "$out" | sed -n '2,/^$/p' | sed '/^$/d' | paste -sd ' '; return 1
}

included() {               # <tip> – steckt der Zweig schon in main? (Merge, Rebase oder "Squash and merge")
  local tip="$1" mb pid out
  git merge-base --is-ancestor "$tip" "$BASE" && return 0
  mb="$(git merge-base "$BASE" "$tip")" || return 1
  # Rebase/Cherry-pick: jeder Commit des Zweigs hat ein Gegenstueck in main
  out="$(git cherry "$BASE" "$tip" 2>/dev/null || true)"
  if [ -n "$out" ] && ! printf '%s\n' "$out" | grep -q '^+'; then return 0; fi
  # Squash: die Gesamtaenderung des Zweigs steckt als ein Commit in main (gleiche patch-id)
  pid="$(git diff "$mb" "$tip" | git patch-id --stable | cut -d' ' -f1)"
  [ -n "$pid" ] || return 0                                                    # Zweig aendert nichts
  git log -p --no-merges "$mb..$BASE" | git patch-id --stable | cut -d' ' -f1 | grep -qxF "$pid"
}

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
  if included "$tip"; then DONE+=("$name"); continue; fi

  state="passt"; info=""
  if ! git diff --quiet "$BASE...$tip" -- dist keys; then
    state="gesperrt"; info="aendert dist/ oder keys/ – das darf nur vspub"
  elif [ "$MT" = 1 ]; then
    if ! out="$(merge_tree "$tip" "$BASE")"; then
      state="Konflikt"; info="$out"
    fi
  else
    state="ungeprueft"; info="git zu alt fuer die Konfliktpruefung (ab 2.38)"
  fi
  if [ "$state" = passt ] && ! git merge-base --is-ancestor "$BASE" "$tip"; then
    info="baut auf aelterem Stand auf, laesst sich aber zusammenfuehren"
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
#  Auswahl: "2", "1, 3", "1 3", "1-3", "alle", Zweignamen – auch gemischt
# ---------------------------------------------------------------------
PICKS=()
add_pick() { local p; for p in "${PICKS[@]}"; do [ "$p" = "$1" ] && return 0; done; PICKS+=("$1"); }
parse_sel() {              # <text> -> PICKS (Indizes ab 0), sonst Abbruch
  local tok a b i want found toks
  set -f; read -r -a toks <<< "${1//,/ }"; set +f
  for tok in "${toks[@]}"; do
    case "$tok" in
      alle|a|\*) for i in "${!OPEN_NAME[@]}"; do add_pick "$i"; done ;;
      *-*) if [[ "$tok" =~ ^([0-9]+)-([0-9]+)$ ]]; then
             a="${BASH_REMATCH[1]}"; b="${BASH_REMATCH[2]}"
             [ "$a" -ge 1 ] && [ "$b" -le ${#OPEN_NAME[@]} ] && [ "$a" -le "$b" ] || die "Ungueltiger Bereich: $tok"
             for (( i = a; i <= b; i++ )); do add_pick $((i - 1)); done
           else
             want="${tok#origin/}"; [[ "$want" == "$PREFIX"* ]] || want="$PREFIX$want"; found=""
             for i in "${!OPEN_NAME[@]}"; do [ "${OPEN_NAME[i]}" = "$want" ] && found=$i; done
             [ -n "$found" ] || die "Kein offener Zweig $want."; add_pick "$found"
           fi ;;
      *) if [[ "$tok" =~ ^[0-9]+$ ]]; then
           [ "$tok" -ge 1 ] && [ "$tok" -le ${#OPEN_NAME[@]} ] || die "Keinen Zweig Nr. $tok."
           add_pick $((tok - 1))
         else
           want="${tok#origin/}"; [[ "$want" == "$PREFIX"* ]] || want="$PREFIX$want"; found=""
           for i in "${!OPEN_NAME[@]}"; do [ "${OPEN_NAME[i]}" = "$want" ] && found=$i; done
           [ -n "$found" ] || die "Kein offener Zweig $want."; add_pick "$found"
         fi ;;
    esac
  done
  [ ${#PICKS[@]} -gt 0 ] || die "Ungueltige Auswahl: $1"
  # Reihenfolge wie in der Liste (aelteste zuerst)
  mapfile -t PICKS < <(printf '%s\n' "${PICKS[@]}" | sort -n)
}

if [ -n "$ARG" ]; then
  parse_sel "$ARG"
elif [ ${#OPEN_NAME[@]} -eq 1 ]; then
  PICKS=(0)
else
  echo
  read -r -p "Welche holen? (z. B. 2 oder 1,3 oder 1-3 oder alle; Enter = keinen) " a
  [ -n "$a" ] || { echo "Nichts geholt."; exit 0; }
  parse_sel "$a"
fi

for pick in "${PICKS[@]}"; do
  name="${OPEN_NAME[pick]}"
  case "${OPEN_STATE[pick]}" in
    gesperrt) die "$name ${OPEN_INFO[pick]}." ;;
    Konflikt) die "$name passt nicht mehr auf main (Konflikt in: ${OPEN_INFO[pick]}).
    Im zugehoerigen Chat sagen: \"Zweig auf origin/main rebasen und neu pushen\" – dann nochmal  vsget." ;;
    ungeprueft) warn "$name: Konfliktpruefung nicht moeglich – vspub merkt einen Konflikt spaetestens beim Einspielen (und aendert dann nichts)." ;;
  esac
done

# Nicht eingespielte Bundles im Eingang? vspub nimmt immer nur das neueste.
old="$(ls -t "$INBOX"/*.bundle 2>/dev/null || true)"
if [ -n "$old" ]; then
  die "In $INBOX liegt noch ein Bundle, das nicht eingespielt ist:
$(printf '%s\n' "$old" | sed 's|.*/|  |')
  Erst  vspub  (oder das Bundle bewusst loeschen), dann nochmal  vsget."
fi

# ---------------------------------------------------------------------
#  Zusammenfuehren (im Hilfs-Repo): von main aus jeden gewaehlten Zweig dazu –
#  vorspulen, wo es geht, sonst Merge-Commit (Changelogs vereinigt).
#  Bundle: Referenz refs/heads/main = Ergebnis, Vorgaenger = origin/main.
# ---------------------------------------------------------------------
cur="$BASE"; topics=(); names=()
for pick in "${PICKS[@]}"; do
  name="${OPEN_NAME[pick]}"; tip="${OPEN_TIP[pick]}"
  say "Hole $name"
  if hg merge-base --is-ancestor "$tip" "$cur"; then
    echo "  steckt schon in den vorher gewaehlten Zweigen"
  else
    hg log --reverse --no-merges --format='  %h %s' "$cur..$tip" | cut -c1-100
    sess="$(hg log -1 --format='%(trailers:key=Claude-Session,valueonly)' "$tip" | head -n1)"
    [ -z "$sess" ] || echo "  Chat: $sess"
    if hg merge-base --is-ancestor "$cur" "$tip"; then
      cur="$tip"
    else
      [ "$MT" = 1 ] || die "git zu alt zum Zusammenfuehren (ab 2.38) – Zweige einzeln holen."
      tree="$(merge_tree "$tip" "$cur")" || die "$name passt nicht zu den vorher gewaehlten Zweigen (Konflikt in: $tree).
    Einzeln holen und einspielen, dann den Rest im zugehoerigen Chat neu auf main setzen lassen."
      cur="$(hg commit-tree "$tree" -p "$cur" -p "$tip" -m "$name zusammengefuehrt (vsget)")"
    fi
  fi
  topic="${name#"$PREFIX"}"; topics+=("${topic//[^A-Za-z0-9._-]/-}"); names+=("$name")
done
[ "$cur" != "$BASE" ] || { echo; echo "Nichts Neues – alles steckt schon in main."; exit 0; }

mkdir -p "$INBOX"
label="$(IFS=+; echo "${topics[*]}")"; label="${label:0:80}"
f="$INBOX/VoidStation-$(hg rev-parse --short "$cur")-$label.bundle"
hg update-ref refs/heads/main "$cur"
hg update-ref refs/remotes/origin/main "$BASE"
hg bundle create -q "$f.part" origin/main..main

# Probe wie vspub: passt zum Repo, enthaelt genau refs/heads/main
git bundle verify -q "$f.part" >/dev/null 2>&1 || { rm -f "$f.part"; die "Bundle passt nicht zum Repo."; }
[ "$(git bundle list-heads "$f.part")" = "$cur refs/heads/main" ] || { rm -f "$f.part"; die "Bundle enthaelt die falschen Referenzen."; }
mv "$f.part" "$f"
echo
[ ${#names[@]} -eq 1 ] || echo "Zusammen: ${names[*]}"
echo "Bundle: $f"

echo
if ask "Gleich einspielen (vspub)?"; then
  exec bash "$REPO/tools/publish.sh"
fi
echo "Einspielen spaeter mit:  vspub"
