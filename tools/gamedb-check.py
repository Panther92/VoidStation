#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Spielprofile pruefen (launcher/gamedb/*.csv, gelesen von launcher/gameprofiles.py).

    tools/gamedb-check.py                       Aufbau: Spalten, erlaubte Werte, doppelte Namen
    tools/gamedb-check.py --duck gamedb.yaml    zusaetzlich: Findet jeder PlayStation-Titel mindestens eine Seriennummer
                                                in DuckStations Datenbank (data/resources/gamedb.yaml)? Sonst greift
                                                der Eintrag nur ueber den Dateinamen.
Laeuft ohne --duck in tools/check.sh mit. Rueckgabe 1 bei Fehlern im Aufbau."""
import argparse
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "launcher"))
import gameprofiles as G  # noqa: E402

COLUMNS = {"psx": ["titel", "aliase", "kategorie", "sicher", "notiz"],
           "dos": ["titel", "aliase", "dateien", "jahr", "tempo", "sicher", "notiz"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duck", help="gamedb.yaml von DuckStation")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    bad = 0
    for system, cols in COLUMNS.items():
        path = G.DIR / f"{system}.csv"
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.reader(f, delimiter=";")
            head = next(rd)
            if head != cols:
                print(f"{path.name}: Spalten {head}, erwartet {cols}")
                bad += 1
            seen: dict = {}
            n = 0
            for i, row in enumerate(rd, 2):
                if not row or not row[0].strip() or row[0].startswith("#"):
                    continue
                n += 1
                if len(row) != len(cols):
                    print(f"{path.name}:{i}: {len(row)} Spalten statt {len(cols)}: {row[0]}")
                    bad += 1
                    continue
                r = dict(zip(cols, (c.strip() for c in row)))
                if r["sicher"] not in ("ja", "nein"):
                    print(f"{path.name}:{i}: sicher = {r['sicher']!r} (ja/nein)")
                    bad += 1
                if system == "psx" and r["kategorie"] not in G.PSX_CATEGORIES:
                    print(f"{path.name}:{i}: Kategorie {r['kategorie']!r} unbekannt")
                    bad += 1
                if system == "dos" and r["tempo"] not in G.DOS_SPEEDS:
                    print(f"{path.name}:{i}: Tempo {r['tempo']!r} unbekannt")
                    bad += 1
                if system == "dos" and r["jahr"] and not re.fullmatch(r"19[89]\d", r["jahr"]):
                    print(f"{path.name}:{i}: Jahr {r['jahr']!r}")
                    bad += 1
                for name in [r["titel"]] + [x for x in r["aliase"].split("|") if x.strip()]:
                    k = G.norm(name)
                    if not k:
                        print(f"{path.name}:{i}: leerer Name")
                        bad += 1
                    elif k in seen and seen[k] != i:
                        print(f"{path.name}:{i}: {name!r} steht schon in Zeile {seen[k]}")
                        bad += 1
                    seen[k] = i
                for fn in (r.get("dateien") or "").split("|"):
                    if fn.strip() and not re.fullmatch(r"[A-Z0-9!#$%&'()@^_`{}~-]{1,8}\.[A-Z0-9]{1,3}", fn.strip().upper()):
                        print(f"{path.name}:{i}: Datei {fn!r} ist kein DOS-Name")
                        bad += 1
                    elif fn.strip() and len(fn.strip().split(".")[0]) < 4:
                        print(f"{path.name}:{i}: Datei {fn!r} ist zu kurz, um ein Spiel sicher zu erkennen (mind. 4 Zeichen)")
                        bad += 1
            print(f"{path.name}: {n} Eintraege")
    if a.duck:
        names: dict = {}
        serial = None
        for line in Path(a.duck).read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^([A-Z0-9][A-Z0-9-]+):\s*$", line)
            if m:
                serial = m.group(1)
                continue
            m = re.match(r'^  name:\s*"?(.*?)"?\s*$', line)
            if m and serial:
                names.setdefault(G.norm(m.group(1)), []).append(serial)
        tab = G.table("psx")
        miss = 0
        for r in tab["rows"]:
            keys = [G.norm(x) for x in [r["titel"]] + [y for y in r["aliase"].split("|") if y.strip()]]
            hits = sorted({s for k in keys for s in names.get(k, [])})
            if not hits:
                miss += 1
                print("ohne Treffer in DuckStations Datenbank:", r["titel"])
            elif a.verbose:
                print(f"{r['titel']}: {len(hits)} ({', '.join(hits[:4])}{' …' if len(hits) > 4 else ''})")
        print(f"psx.csv: {len(tab['rows']) - miss} von {len(tab['rows'])} Titeln in DuckStations Datenbank gefunden")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
