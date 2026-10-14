#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  CHANGELOG-Werkzeug fuer tools/publish.sh (vspub --release / --hotfix / --status)
#
#  Format (CHANGELOG.md und CHANGELOG.en.md):
#    Vorspann (alles vor der ersten "## "-Ueberschrift)
#    ## Testing – JJJJ-MM-TT      noch nicht freigegeben (nur ganz oben)
#    ## 2026.11.1 – JJJJ-MM-TT    Hotfix zu 2026.11
#    ## 2026.11 – JJJJ-MM-TT      Release-Zug im November
#    ## 0.15.0 – …                alte Nummern bleiben, wie sie sind
#  Ein Eintrag beginnt mit "- " am Zeilenanfang; eingerueckte Folgezeilen gehoeren dazu.
#
#    changelog.py next --mode release|hotfix --stable <CHANGELOG.md> [--month JJJJ.MM]
#    changelog.py top <datei>                  oberste Ueberschrift: "<version> <datum>"
#    changelog.py stamp <datei> <version> <datum>      Testing -> Version (in place)
#    changelog.py added <alt> <neu>            Testing-Eintraege, die in <neu> dazugekommen sind
#    changelog.py insert <datei> <version> <datum> <eintraege>   Abschnitt oben einfuegen (in place)
#    changelog.py mergeback <main> <release> > <ergebnis>
#        Ergebnis = Vorspann von <main> + Testing von <main> ohne alles, was in <release> schon
#        freigegeben ist + alle freigegebenen Abschnitte von <release>
# =====================================================================
import argparse, re, sys
from datetime import date
from pathlib import Path

HEAD = re.compile(r"^##\s+(\S+)\s+[–-]\s+(\d{4}-\d{2}-\d{2})\s*$")
CALVER = re.compile(r"^(\d{4})\.(0[1-9]|1[0-2])(?:\.([1-9]\d*))?$")


def die(msg):
    print(f"changelog.py: {msg}", file=sys.stderr)
    sys.exit(1)


def parse(text):
    """-> (vorspann, [{"version", "date", "head", "entries": [str], "tail": str}])"""
    lines = text.splitlines(keepends=True)
    pre, sections, cur, entry = [], [], None, None
    for line in lines:
        m = HEAD.match(line.rstrip("\n"))
        if m:
            cur = {"version": m.group(1), "date": m.group(2), "head": line, "entries": [], "tail": ""}
            sections.append(cur)
            entry = None
        elif cur is None:
            pre.append(line)
        elif line.startswith("- "):
            entry = [line]
            cur["entries"].append(entry)
        elif entry is not None and (line.startswith((" ", "\t")) or not line.strip()):
            entry.append(line)                       # Folgezeile oder Leerzeile
        else:
            cur["tail"] += line                      # sonstiger Text im Abschnitt (selten)
    for s in sections:
        s["entries"] = ["".join(e).rstrip() + "\n" for e in s["entries"]]
    return "".join(pre), sections


def norm(entry):
    return " ".join(entry.split())


def render(pre, sections):
    out = [pre if pre.endswith("\n\n") or not pre else pre.rstrip("\n") + "\n\n"]
    for s in sections:
        out.append(s["head"] if s["head"].endswith("\n") else s["head"] + "\n")
        out.extend(s["entries"])
        if s["tail"].strip():
            out.append(s["tail"].rstrip("\n") + "\n")
        out.append("\n")
    return "".join(out).rstrip("\n") + "\n"


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        die(f"{path}: {e}")


def vkey(v):
    m = CALVER.match(v)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
    return None


def cmd_next(a):
    _, secs = parse(read(a.stable))
    released = [s["version"] for s in secs if s["version"] != "Testing"]
    if not released:
        die(f"{a.stable}: keine freigegebene Version")
    cal = [v for v in released if vkey(v)]
    month = a.month or date.today().strftime("%Y.%m")
    if not CALVER.match(month) or CALVER.match(month).group(3):
        die(f"ungueltiger Monat: {month}")
    if a.mode == "hotfix" and cal:
        base = ".".join(cal[0].split(".")[:2])       # Hotfix gehoert zur aktuellen Stable-Version
    else:
        base = month                                  # Release-Zug (oder erster Hotfix nach den 0.x-Versionen)
    same = [vkey(v)[2] for v in cal if v == base or v.startswith(base + ".")]
    new = base if not same else f"{base}.{max(same) + 1}"
    if cal and vkey(new) <= vkey(cal[0]):
        die(f"{new} waere nicht neuer als die aktuelle Version {cal[0]} – Datum/Uhr pruefen")
    print(new)


def cmd_top(a):
    _, secs = parse(read(a.file))
    if not secs:
        die(f"{a.file}: keine Abschnitte")
    print(secs[0]["version"], secs[0]["date"])


def cmd_stamp(a):
    pre, secs = parse(read(a.file))
    if not secs or secs[0]["version"] != "Testing":
        die(f"{a.file}: oben steht kein Abschnitt 'Testing' – nichts freizugeben")
    if not secs[0]["entries"]:
        die(f"{a.file}: der Abschnitt 'Testing' ist leer")
    dash = "–" if "–" in secs[0]["head"] else "-"
    secs[0].update(version=a.version, date=a.date, head=f"## {a.version} {dash} {a.date}\n")
    Path(a.file).write_text(render(pre, secs), encoding="utf-8")


def testing_entries(text):
    _, secs = parse(text)
    return secs[0]["entries"] if secs and secs[0]["version"] == "Testing" else []


def cmd_added(a):
    old = {norm(e) for e in testing_entries(read(a.old))}
    for e in testing_entries(read(a.new)):
        if norm(e) not in old:
            sys.stdout.write(e)


def cmd_insert(a):
    pre, secs = parse(read(a.file))
    entries = parse("## x – 2000-01-01\n" + read(a.entries))[1][0]["entries"]
    if not entries:
        die(f"{a.entries}: keine Eintraege")
    if secs and secs[0]["version"] == "Testing":
        die(f"{a.file}: oben steht noch 'Testing' – Hotfixes gehen auf den Stable-Stand")
    secs.insert(0, {"version": a.version, "date": a.date, "head": f"## {a.version} – {a.date}\n",
                    "entries": entries, "tail": ""})
    Path(a.file).write_text(render(pre, secs), encoding="utf-8")


def cmd_mergeback(a):
    pre_main, main_secs = parse(read(a.main))
    _, rel_secs = parse(read(a.release))
    secs = [s for s in rel_secs if s["version"] != "Testing"]
    done = {norm(e) for s in secs for e in s["entries"]}
    if main_secs and main_secs[0]["version"] == "Testing":
        t = main_secs[0]
        rest = [e for e in t["entries"] if norm(e) not in done]
        if rest:
            secs.insert(0, dict(t, entries=rest))
    sys.stdout.write(render(pre_main, secs))


def main():
    ap = argparse.ArgumentParser(description="CHANGELOG-Werkzeug fuer vspub")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next"); p.add_argument("--mode", choices=("release", "hotfix"), required=True)
    p.add_argument("--stable", required=True); p.add_argument("--month"); p.set_defaults(f=cmd_next)
    p = sub.add_parser("top"); p.add_argument("file"); p.set_defaults(f=cmd_top)
    p = sub.add_parser("stamp"); p.add_argument("file"); p.add_argument("version"); p.add_argument("date"); p.set_defaults(f=cmd_stamp)
    p = sub.add_parser("added"); p.add_argument("old"); p.add_argument("new"); p.set_defaults(f=cmd_added)
    p = sub.add_parser("insert"); p.add_argument("file"); p.add_argument("version"); p.add_argument("date")
    p.add_argument("entries"); p.set_defaults(f=cmd_insert)
    p = sub.add_parser("mergeback"); p.add_argument("main"); p.add_argument("release")
    p.set_defaults(f=cmd_mergeback)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
