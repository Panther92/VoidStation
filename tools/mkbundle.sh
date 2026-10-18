#!/bin/bash
# =====================================================================
#  Bundle fuer vspub bauen – fuer Beitraege ohne Push auf main (z. B. Claude)
#
#    tools/mkbundle.sh [zielordner]
#
#  Ergebnis: <zielordner>/VoidStation-<commit>.bundle
#    - immer kumulativ: alles seit dem aktuellen GitHub-Stand (origin/main..main),
#      d. h. es reicht immer das neueste Bundle, aeltere koennen weg
#    - enthaelt genau die Referenz refs/heads/main (die liest vspub)
#    - wird vorher wie bei vspub auf dem GitHub-Stand probeweise eingespielt
#  Bricht ab statt ein unbrauchbares Bundle zu bauen.
#  Einspielen auf dem Herausgeber-Rechner: Bundle nach ~/share/Updates, dann  vspub
# =====================================================================
set -euo pipefail

OUT="${1:-.}"
die() { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*" >&2; }

cd "$(git rev-parse --show-toplevel)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

[ "$(git branch --show-current)" = main ] || die "Nicht auf dem Zweig main (git checkout main)."
git fetch -q origin || die "GitHub nicht erreichbar – ohne aktuellen Stand kein Bundle."
git diff --quiet && git diff --cached --quiet || die "Ungesicherte Aenderungen – erst committen (dist/ nach build.sh mit  git checkout -- dist  zuruecksetzen)."
untracked="$(git ls-files --others --exclude-standard)"
[ -z "$untracked" ] || die "Unversionierte Dateien – committen oder loeschen:
$untracked"
git merge-base --is-ancestor origin/main main || die "main baut nicht auf dem GitHub-Stand auf (vspub hat inzwischen etwas gepusht) – erst:  git rebase origin/main"
n="$(git rev-list --count origin/main..main)"
[ "$n" -gt 0 ] || die "Nichts Neues seit dem GitHub-Stand."

# dist/ und keys/ schreibt nur vspub (bauen + signieren mit dem privaten Schluessel)
git diff --quiet origin/main main -- dist keys || die "Die Commits aendern dist/ oder keys/ – das macht nur vspub. Aenderung dort zuruecknehmen."
git ls-files | grep -q '__pycache__' && die "__pycache__ ist eingecheckt – entfernen (git rm -r --cached …)."

# Was auf den Geraeten landet, braucht eine Changelog-Zeile (de + en) unter "## Testing – <datum>"
dev="$(git diff --name-only origin/main main -- launcher install-head.sh update-head.sh iso build.sh update-url)"
if [ -n "$dev" ] && [ "${VS_NO_CHANGELOG:-0}" != 1 ]; then
  git diff --quiet origin/main main -- CHANGELOG.md && die "Geraete-Dateien geaendert, aber keine Zeile in CHANGELOG.md (Ausnahme: VS_NO_CHANGELOG=1)."
  git diff --quiet origin/main main -- CHANGELOG.en.md && die "Geraete-Dateien geaendert, aber keine Zeile in CHANGELOG.en.md (Ausnahme: VS_NO_CHANGELOG=1)."
fi

# build.sh muss durchlaufen (Syntax, Sprachdateien, Changelog); dist/ danach wieder zuruecksetzen
trap 'git checkout -q -- dist 2>/dev/null || true' EXIT
./build.sh >/dev/null 2>"$OUT/.mkbundle-build.log" || { cat "$OUT/.mkbundle-build.log" >&2; die "build.sh schlaegt fehl."; }
rm -f "$OUT/.mkbundle-build.log"
git checkout -q -- dist

sha="$(git rev-parse --short main)"
f="$OUT/VoidStation-$sha.bundle"
rm -f "$f"
git bundle create -q "$f" origin/main..main

# Referenz pruefen: genau refs/heads/main, Stand = lokales main
heads="$(git bundle list-heads "$f")"
[ "$heads" = "$(git rev-parse main) refs/heads/main" ] || die "Bundle enthaelt die falschen Referenzen:
$heads"

# Probelauf wie vspub: Vorgaenger muessen auf GitHub liegen, Referenz main muss lesbar sein
reqs=0
while IFS= read -r line; do
  [ -z "$line" ] && break
  case "$line" in
    -*) r="${line#-}"; r="${r%% *}"; reqs=$((reqs + 1))
        git merge-base --is-ancestor "$r" origin/main || die "Bundle braucht $r – der liegt nicht auf GitHub (vspub koennte es nicht einspielen)." ;;
  esac
done < "$f"
[ "$reqs" -gt 0 ] || die "Bundle ohne Vorgaenger – das waere ein komplettes Repo, kein Update."
git fetch -q "$f" main:refs/mkbundle/probe || die "vspub koennte die Referenz main nicht lesen."
probe="$(git rev-parse refs/mkbundle/probe)"; git update-ref -d refs/mkbundle/probe
[ "$probe" = "$(git rev-parse main)" ] || die "Probelauf ergibt einen anderen Stand als main."
git merge-base --is-ancestor origin/main "$probe" || die "Bundle laesst sich nicht vorspulen."

echo "Bundle: $f"
echo "Basis:  $(git log -1 --format='%h %s' origin/main)"
echo "Neu ($n):"
git log --oneline --no-merges origin/main..main | sed 's/^/  /'
echo
echo "Einspielen: nach ~/share/Updates kopieren (aeltere Bundles dort loeschen), dann  vspub"
