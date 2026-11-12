#!/bin/sh
# Startet die Startseite (Python + Qt 6, qt/voidstation-home.py) im Vollbild und haelt sie am Leben.
# Gilt auch im Live-System (dort mit Installer). Die Startseite zeigt sofort Logo + Lade-Punkte und wartet
# selbst auf den Launcher.
# Beendet sie sich gleich nach dem Start (unter 15 s), wird die Pause vor dem naechsten Versuch ab dem dritten
# Mal hintereinander laenger (5 s, 10 s … hoechstens 60 s), damit ein kaputter Stand nicht im Sekundentakt
# neu startet. Fehlerausgabe: logs/home.log, Starts und Pausen: logs/frontend.log.
TV="$HOME/.local/share/voidstation"
FLOG="$TV/logs/frontend.log"
mkdir -p "$TV/logs"
note() { echo "$(date '+%F %T') $*" >>"$FLOG"; tail -n 50 "$FLOG" >"$FLOG.tmp" 2>/dev/null && mv -f "$FLOG.tmp" "$FLOG"; }
FAILS=0
while true; do
  note "Startseite: Qt"
  t0=$(date +%s)
  python3 "$TV/qt/voidstation-home.py" >"$TV/logs/home.log" 2>&1
  if [ $(( $(date +%s) - t0 )) -lt 15 ]; then FAILS=$((FAILS + 1)); else FAILS=0; fi
  pause=1
  if [ "$FAILS" -ge 3 ]; then
    pause=$(( (FAILS - 2) * 5 )); [ "$pause" -gt 60 ] && pause=60
    note "Startseite beendet sich gleich nach dem Start ($FAILS× hintereinander, siehe logs/home.log) – neuer Versuch in $pause s"
  fi
  sleep "$pause"
done
