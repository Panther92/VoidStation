#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  Schnellpruefung vor einem Pull Request – laeuft auch in
#  .github/workflows/checks.yml. Veraendert nichts im Repo.
#
#    tools/check.sh
#
#  Prueft: Shell-Skripte (shellcheck, falls installiert, sonst bash -n / sh -n),
#  Python-Syntax, Python-Fehlerklassen (ruff) und Typen (mypy, schrittweise),
#  JSON-Dateien, Bau (build.sh: i18n vollstaendig, CHANGELOG de + en,
#  ISO-Teile) und den Bau der Webseite.
#
#  ruff und mypy: Einstellungen in pyproject.toml. Fehlen sie, wird der
#  Schritt uebersprungen (wie bei shellcheck). In der CI (CI=true) oder mit
#  VS_CHECK_INSTALL=1 holt das Skript die festen Versionen unten in ein
#  Wegwerf-venv – am System aendert sich nichts.
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

# Feste Versionen fuer die CI, damit ein neues Release dort nichts rot faerbt.
RUFF_VERSION=0.16.9
MYPY_VERSION=2.3.1
# Dateien mit offenen mypy-Funden (Stufe 1). Beim naechsten Anfassen der
# Datei die Funde beheben und den Eintrag streichen; neue Dateien kommen
# automatisch in die Pruefung.
MYPY_TODO=(
  launcher/launcher.py              # 10: Annotationen fuer leere dict/set, wiederverwendetes e
  launcher/vsx11.py                 # 2: Annotationen _atoms, _grabbed
  launcher/voidstation-installer    # 1: Annotation SECRETS
)
RUFF=(); MYPY=()
command -v ruff >/dev/null 2>&1 && RUFF=(ruff)
command -v mypy >/dev/null 2>&1 && MYPY=(mypy)
if { [ ${#RUFF[@]} -eq 0 ] || [ ${#MYPY[@]} -eq 0 ]; } \
   && { [ "${CI:-}" = true ] || [ "${VS_CHECK_INSTALL:-}" = 1 ]; }; then
  echo "(ruff/mypy fehlen – installiere ruff $RUFF_VERSION, mypy $MYPY_VERSION in ein venv)"
  if python3 -m venv "$tmp/venv" \
     && "$tmp/venv/bin/pip" install -q --disable-pip-version-check \
          "ruff==$RUFF_VERSION" "mypy==$MYPY_VERSION"; then
    RUFF=("$tmp/venv/bin/ruff"); MYPY=("$tmp/venv/bin/mypy")
  else
    bad "ruff/mypy liessen sich nicht installieren"
  fi
fi

step "Python: Fehlerklassen (ruff)"
if [ ${#RUFF[@]} -gt 0 ]; then
  "${RUFF[@]}" check --no-cache --quiet "${py_files[@]}" || bad "ruff"
  echo "${#py_files[@]} Dateien geprueft ($("${RUFF[@]}" --version))"
else
  echo "(ruff nicht installiert – uebersprungen)"
fi

step "Python: Typen (mypy, Stufe 1)"
if [ ${#MYPY[@]} -gt 0 ]; then
  mypy_files=()
  for f in "${py_files[@]}"; do
    skip=0
    for t in "${MYPY_TODO[@]}"; do [ "$f" = "$t" ] && skip=1 && break; done
    [ "$skip" = 0 ] && mypy_files+=("$f")
  done
  "${MYPY[@]}" --no-incremental --cache-dir=/dev/null "${mypy_files[@]}" || bad "mypy"
  echo "(noch ausgenommen: ${MYPY_TODO[*]})"
else
  echo "(mypy nicht installiert – uebersprungen)"
fi

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
