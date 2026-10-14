#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  Schnellpruefung vor einem Pull Request – laeuft auch in
#  .github/workflows/checks.yml. Veraendert nichts im Repo.
#
#    tools/check.sh
#
#  Prueft: Shell-Skripte (shellcheck, falls installiert, sonst bash -n / sh -n),
#  Python-Syntax, JSON-Dateien, Bau (build.sh: i18n vollstaendig, CHANGELOG
#  de + en, ISO-Teile) und den Bau der Webseite.
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
step() { printf '\n== %s\n' "$*"; }
bad()  { echo "FEHLER: $*"; fail=1; }

# Dateien aus Git (ohne das generierte dist/), notfalls alle Dateien
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -t FILES < <(git ls-files | grep -v '^dist/')
else
  mapfile -t FILES < <(find . -type f -not -path './.git/*' -not -path './dist/*' | sed 's|^\./||')
fi

step "Shell-Skripte"
sh_files=(); sh_noshebang=()
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  first="$(head -n1 "$f" 2>/dev/null | tr -d '\0')"
  case "$first" in
    '#!/bin/sh'*|'#!/bin/bash'*|'#!/usr/bin/env bash'*|'#!/usr/bin/env sh'*) sh_files+=("$f") ;;
    *) case "$f" in *.sh) sh_noshebang+=("$f") ;; esac ;;   # z. B. runit-Core-Services
  esac
done
if command -v shellcheck >/dev/null 2>&1; then
  # SC2034 (scheinbar unbenutzte Variable) meldet Fehlalarme bei eval/source
  shellcheck -S warning -e SC2034 "${sh_files[@]}" || bad "shellcheck"
  [ ${#sh_noshebang[@]} -eq 0 ] || shellcheck -s sh -S warning -e SC2034 "${sh_noshebang[@]}" || bad "shellcheck"
else
  echo "(shellcheck nicht installiert – nur Syntaxpruefung)"
  for f in "${sh_files[@]}"; do
    case "$(head -n1 "$f")" in *bash*) bash -n "$f" ;; *) sh -n "$f" ;; esac || bad "Syntax: $f"
  done
  for f in "${sh_noshebang[@]}"; do sh -n "$f" || bad "Syntax: $f"; done
fi
echo "${#sh_files[@]} + ${#sh_noshebang[@]} Skripte geprueft"

step "Python"
py_files=()
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  case "$f" in *.py) py_files+=("$f"); continue ;; esac
  case "$(head -n1 "$f" 2>/dev/null | tr -d '\0')" in '#!'*python*) py_files+=("$f") ;; esac
done
python3 - "${py_files[@]}" <<'PYEOF' || bad "Python-Syntax"
import sys
bad = 0
for fn in sys.argv[1:]:
    try:
        compile(open(fn, encoding="utf-8").read(), fn, "exec")
    except SyntaxError as e:
        print(f"  {fn}:{e.lineno}: {e.msg}"); bad = 1
print(f"{len(sys.argv) - 1} Dateien geprueft")
sys.exit(bad)
PYEOF

step "JSON"
json_files=()
for f in "${FILES[@]}"; do case "$f" in *.json) [ -f "$f" ] && json_files+=("$f") ;; esac; done
python3 - "${json_files[@]}" <<'PYEOF' || bad "JSON"
import json, sys
bad = 0
for fn in sys.argv[1:]:
    try:
        json.load(open(fn, encoding="utf-8"))
    except ValueError as e:
        print(f"  {fn}: {e}"); bad = 1
print(f"{len(sys.argv) - 1} Dateien geprueft")
sys.exit(bad)
PYEOF

step "Bau (build.sh)"
if OUT="$tmp/dist" ./build.sh >"$tmp/build.log" 2>&1; then
  grep '^Version:' "$tmp/build.log"
else
  cat "$tmp/build.log"; bad "build.sh"
fi

step "Webseite (tools/build-site.py)"
python3 tools/build-site.py --preview --out "$tmp/site" 2>&1 | tail -n 3 || bad "build-site.py"

echo
if [ "$fail" = 0 ]; then echo "Alles in Ordnung."; else echo "Es gibt Fehler (siehe oben)."; fi
exit "$fail"
