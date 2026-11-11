#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  Download-Statistik von SourceForge (Live-ISOs) – nach Land und nach Sprache
#
#    tools/sf-stats.py                      seit Projektbeginn bis heute, Tabelle je Sprache
#    tools/sf-stats.py --from 2026-11-09    ab einem Tag (z. B. seit der neuen ISO)
#    tools/sf-stats.py --path 2026.11       nur ein Ordner bzw. eine Datei unter "Files"
#    tools/sf-stats.py --countries          zusaetzlich alle Laender einzeln
#    tools/sf-stats.py --days               zusaetzlich Downloads je Tag/Woche/Monat (Balken)
#    tools/sf-stats.py --md                 Tabellen als Markdown (fuer claude/voidstation-sprachen.md)
#    tools/sf-stats.py --save stats.json    Rohdaten zusaetzlich speichern
#    tools/sf-stats.py --file stats.json    gespeicherte Rohdaten auswerten (ohne Netz)
#
#  Schnittstelle: https://sourceforge.net/p/forge/documentation/Download%20Stats%20API/
#    https://sourceforge.net/projects/<projekt>/files[/<pfad>]/stats/json?start_date=…&end_date=…
#  Antwort u. a. "downloads": [["JJJJ-MM-TT 00:00:00", n], …], "countries": [["DE", n], …], "messages": […]
#  (alle Daten in UTC; Statistik gibt es erst ab der Registrierung des Projekts, 2026-10-03).
#
#  Land -> Sprache der Oberflaeche wie in claude/voidstation-sprachen.md: mehrsprachige Laender zaehlen fuer
#  ihre Hauptsprache (CH -> de, BE -> nl, CA/IN/ZA -> en, DZ/MA -> ar; --maghreb-fr zaehlt DZ/MA/TN als fr).
#  "✓" = Sprache gibt es in VoidStation (LANG_TABLE in launcher/launcher.py). Aendert nichts im Repo.
# =====================================================================
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROJECT = "voidstation"
START = "2026-10-03"                       # Registrierung des Projekts auf SourceForge

# Land (ISO 3166) -> Sprache (wie die Kennungen in LANG_TABLE)
COUNTRY_LANG = {
    # Deutsch, Englisch
    "DE": "de", "AT": "de", "CH": "de", "LI": "de", "LU": "de",
    "US": "en", "GB": "en", "IE": "en", "CA": "en", "AU": "en", "NZ": "en", "IN": "en", "ZA": "en", "MT": "en",
    "SG": "en", "PH": "en", "NG": "en", "KE": "en", "GH": "en", "PK": "en", "JM": "en", "TT": "en",
    # Romanische Sprachen
    "FR": "fr", "MC": "fr", "GP": "fr", "MQ": "fr", "RE": "fr", "GF": "fr", "NC": "fr", "PF": "fr", "SN": "fr",
    "CI": "fr", "CM": "fr", "HT": "fr",
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es", "PE": "es", "VE": "es", "UY": "es", "EC": "es",
    "BO": "es", "PY": "es", "CR": "es", "PA": "es", "DO": "es", "GT": "es", "HN": "es", "SV": "es", "NI": "es",
    "CU": "es", "PR": "es",
    "IT": "it", "SM": "it", "VA": "it",
    "BR": "pt-BR", "PT": "pt", "AO": "pt", "MZ": "pt",
    "RO": "ro", "MD": "ro",
    # Mittel-/Nordeuropa
    "NL": "nl", "BE": "nl", "SR": "nl",
    "PL": "pl", "CZ": "cs", "SK": "sk", "HU": "hu", "SI": "sl", "HR": "hr", "RS": "sr", "BA": "bs", "ME": "sr",
    "MK": "mk", "BG": "bg", "AL": "sq", "XK": "sq",
    "DK": "da", "SE": "sv", "NO": "nb", "FI": "fi", "IS": "is", "EE": "et", "LV": "lv", "LT": "lt",
    # Osteuropa, Kaukasus, Zentralasien
    "RU": "ru", "BY": "ru", "KZ": "ru", "KG": "ru", "UA": "uk", "GE": "ka", "AM": "hy", "AZ": "az", "UZ": "uz",
    # Griechisch, Tuerkisch
    "GR": "el", "CY": "el", "TR": "tr",
    # Naher Osten, Nordafrika
    "DZ": "ar", "MA": "ar", "TN": "ar", "LY": "ar", "EG": "ar", "SA": "ar", "AE": "ar", "IQ": "ar", "JO": "ar",
    "LB": "ar", "SY": "ar", "KW": "ar", "QA": "ar", "BH": "ar", "OM": "ar", "YE": "ar", "SD": "ar",
    "IL": "he", "IR": "fa", "AF": "fa",
    # Asien
    "JP": "ja", "KR": "ko", "CN": "zh-CN", "TW": "zh-TW", "HK": "zh-TW", "MO": "zh-TW",
    "TH": "th", "VN": "vi", "ID": "id", "MY": "ms", "BD": "bn", "LK": "si", "NP": "ne", "MN": "mn", "KH": "km",
}
MAGHREB = ("DZ", "MA", "TN")

LANG_NAMES = {
    "de": "Deutsch", "en": "Englisch", "fr": "Französisch", "es": "Spanisch", "it": "Italienisch",
    "pt-BR": "Portugiesisch (BR)", "pt": "Portugiesisch (PT)", "ro": "Rumänisch", "nl": "Niederländisch",
    "pl": "Polnisch", "cs": "Tschechisch", "sk": "Slowakisch", "hu": "Ungarisch", "sl": "Slowenisch",
    "hr": "Kroatisch", "sr": "Serbisch", "bs": "Bosnisch", "mk": "Mazedonisch", "bg": "Bulgarisch",
    "sq": "Albanisch", "da": "Dänisch", "sv": "Schwedisch", "nb": "Norwegisch", "fi": "Finnisch",
    "is": "Isländisch", "et": "Estnisch", "lv": "Lettisch", "lt": "Litauisch", "ru": "Russisch",
    "uk": "Ukrainisch", "ka": "Georgisch", "hy": "Armenisch", "az": "Aserbaidschanisch", "uz": "Usbekisch",
    "el": "Griechisch", "tr": "Türkisch", "ar": "Arabisch (RTL)", "he": "Hebräisch (RTL)", "fa": "Persisch (RTL)",
    "ja": "Japanisch", "ko": "Koreanisch", "zh-CN": "Chinesisch (vereinf.)", "zh-TW": "Chinesisch (trad.)",
    "th": "Thai", "vi": "Vietnamesisch", "id": "Indonesisch", "ms": "Malaiisch", "bn": "Bengalisch",
    "si": "Singhalesisch", "ne": "Nepali", "mn": "Mongolisch", "km": "Khmer", "?": "unbekannt",
}


def supported_langs():
    """Kennungen aus LANG_TABLE in launcher/launcher.py (ohne den Launcher zu importieren)."""
    try:
        src = (REPO / "launcher" / "launcher.py").read_text(encoding="utf-8")
        block = src[src.index("LANG_TABLE = ["):]
        block = block[:block.index("\n]")]
        return set(re.findall(r'^\s*\("([^"]+)",', block, re.M))
    except (OSError, ValueError):
        return set()


def fetch(project, path, start, end):
    loc = f"files/{path.strip('/')}" if path else "files"
    q = urllib.parse.urlencode({"start_date": start, "end_date": end, "country_codes": "true",
                                "os_by_country": "false"})
    url = f"https://sourceforge.net/projects/{project}/{urllib.parse.quote(loc)}/stats/json?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "VoidStation sf-stats"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        sys.exit(f"SourceForge nicht erreichbar: {e}\n  {url}")


def pct(n, total):
    return f"{100 * n / total:.1f} %".replace(".", ",") if total else "–"


def table(rows, head, md):
    """rows: Listen von Zellen (Text). Rechtsbuendig sind Spalten, deren Kopf mit '>' beginnt."""
    right = [h.startswith(">") for h in head]
    head = [h.lstrip(">") for h in head]
    if md:
        out = ["| " + " | ".join(head) + " |", "|" + "|".join("---:" if r else "---" for r in right) + "|"]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        return "\n".join(out)
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)] if rows else [len(h) for h in head]
    fmt = lambda r: "  ".join(str(c).rjust(w[i]) if right[i] else str(c).ljust(w[i]) for i, c in enumerate(r)).rstrip()
    return "\n".join([fmt(head), fmt(["-" * x for x in w])] + [fmt(r) for r in rows])


def main():
    ap = argparse.ArgumentParser(description="SourceForge-Downloads nach Land und Sprache")
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--from", dest="start", default=START, help=f"erster Tag JJJJ-MM-TT (Standard {START})")
    ap.add_argument("--to", dest="end", default=date.today().isoformat(), help="letzter Tag (Standard heute)")
    ap.add_argument("--path", default="", help="nur dieser Ordner bzw. diese Datei unter Files")
    ap.add_argument("--countries", action="store_true", help="auch alle Laender einzeln")
    ap.add_argument("--days", action="store_true", help="auch Downloads je Zeitraum")
    ap.add_argument("--md", action="store_true", help="Tabellen als Markdown")
    ap.add_argument("--maghreb-fr", action="store_true", help="Algerien, Marokko, Tunesien als Französisch zaehlen")
    ap.add_argument("--save", help="Rohdaten (JSON) zusaetzlich in diese Datei schreiben")
    ap.add_argument("--file", help="Rohdaten aus dieser Datei statt von SourceForge")
    a = ap.parse_args()

    data = json.loads(Path(a.file).read_text(encoding="utf-8")) if a.file else fetch(a.project, a.path, a.start, a.end)
    if a.save:
        Path(a.save).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in data.get("messages") or []:
        print(f"Hinweis von SourceForge: {m}", file=sys.stderr)

    countries = [(str(c).upper(), int(n)) for c, n in data.get("countries") or [] if int(n) > 0]
    days = [(str(d)[:10], int(n)) for d, n in data.get("downloads") or []]
    total = sum(n for _, n in countries)
    total_days = sum(n for _, n in days)
    have = supported_langs()

    by_lang, members, unknown = {}, {}, []
    for cc, n in countries:
        lang = "fr" if a.maghreb_fr and cc in MAGHREB else COUNTRY_LANG.get(cc)
        if not lang:
            unknown.append(cc)
            lang = "?"
        by_lang[lang] = by_lang.get(lang, 0) + n
        members.setdefault(lang, []).append(f"{cc} {n}")

    first = days[0][0] if days else a.start
    last = days[-1][0] if days else a.end
    what = f"{a.project}/{a.path}" if a.path else a.project
    print(f"{'## ' if a.md else ''}Downloads {what}: {total} aus {len(countries)} Ländern, {first} bis {last}"
          + (f" (Stand {data['stats_updated']} UTC)" if data.get("stats_updated") else ""))
    if total_days and total_days != total:
        print(f"(Summe je Tag: {total_days} – weicht von der Länderliste ab)")
    print()

    rows, cum, covered = [], 0, 0
    for i, (lang, n) in enumerate(sorted(by_lang.items(), key=lambda x: (-x[1], x[0])), 1):
        cum += n
        ok = lang in have
        covered += n if ok else 0
        rows.append([str(i), LANG_NAMES.get(lang, lang), lang, "✓" if ok else "", str(n), pct(n, total), pct(cum, total),
                     ", ".join(members[lang])])
    print(table(rows, [">#", "Sprache", "Code", "VS", ">Downloads", ">Anteil", ">kumuliert", "Länder"], a.md))
    print()
    print(f"Von VoidStation abgedeckt ({len(have)} Sprachen): {covered} von {total} Downloads ({pct(covered, total)}).")
    missing = [(lang, n) for lang, n in sorted(by_lang.items(), key=lambda x: -x[1]) if lang not in have and lang != "?"]
    if missing:
        print("Größte fehlende Sprachen: " + ", ".join(f"{LANG_NAMES.get(l, l)} {n}" for l, n in missing[:5]) + ".")
    if unknown:
        print(f"Ohne Zuordnung (COUNTRY_LANG ergänzen): {', '.join(unknown)}")

    if a.countries:
        print()
        rows = [[str(i), cc, COUNTRY_LANG.get(cc, "?"), str(n), pct(n, total)] for i, (cc, n) in enumerate(countries, 1)]
        print(table(rows, [">#", "Land", "Sprache", ">Downloads", ">Anteil"], a.md))

    if a.days and days:
        print()
        peak = max(n for _, n in days) or 1
        period = data.get("period", "")
        if a.md:
            print(table([[d, str(n)] for d, n in days], [f"Zeitraum ({period})", ">Downloads"], True))
        else:
            for d, n in days:
                print(f"{d}  {n:5d}  {'█' * round(40 * n / peak)}")


if __name__ == "__main__":
    main()
