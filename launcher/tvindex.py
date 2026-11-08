#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fernsehen: Senderverzeichnis von iptv-org als SQLite-Datei.

Die Rohdaten (channels/streams/logos.json) sind rund 18 MB gross; sie einzulesen kostete den Launcher dauerhaft
gut 100 MB, die Python nicht mehr ans System zurueckgab. Deshalb baut ein kurzlebiger Prozess (dieses Skript,
Aufruf: tvindex.py <cache-ordner>) die Datei, und der Launcher fragt nur noch die jeweils noetigen Zeilen ab.
Das Modul importiert sqlite3 erst bei Bedarf: Wer nie die Fernsehen-Kachel oeffnet, zahlt nichts dafuer."""
import hashlib
import json
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

IPTV_API = "https://iptv-org.github.io/api/"
UA = {"User-Agent": "VoidStation/4.0"}
DB_NAME = "tv.sqlite"
SCHEMA = 1                                   # bei Aenderungen der Tabelle hochzaehlen: alte Dateien werden neu gebaut
TV_PAGE = 200                                # Sender je Seite der Liste (mehr Kacheln auf einmal bremsen schwache Geraete)
TV_LETTERS = ["#"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
SEP = "\x1f"                                 # trennt Namen in den Spalten alt und folds
ALL = "key,cid,name,alt,country,cats,quality,logo,url,ref,ua,letter,folds"
PUBLIC = "key,cid,name,country,cats,quality,logo"


def tv_fold(name):
    """Name ohne Akzente und in Kleinbuchstaben: „Österreich“ sortiert und sucht wie „osterreich“."""
    s = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def tv_letter(name):
    """Anfangsbuchstabe fuer die A–Z-Leiste: erstes Zeichen ohne Akzent, A–Z, sonst „#“ (Ziffern, andere Schriften)."""
    for c in tv_fold(name):
        if c.isalnum():
            u = c.upper()
            return u if "A" <= u <= "Z" else "#"
    return "#"


def fetch(url, dest, max_age, log=print):
    """Datei herunterladen, wenn sie fehlt oder aelter als max_age Sekunden ist."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and time.time() - dest.stat().st_mtime < max_age:
        return dest
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    except Exception as e:  # noqa: BLE001
        if not dest.exists():
            raise
        log("Verzeichnis veraltet, nutze Cache:", e)
    return dest


def build_index(ch, st, lg):
    """Senderliste aus channels/streams/logos.json: ein Eintrag je Sender und Feed, sortiert wie die A–Z-Leiste."""
    chans = {c["id"]: c for c in ch if not c.get("is_nsfw") and not c.get("closed")}
    logos = {}
    for l in lg:
        if l.get("channel") and l.get("url") and not l.get("feed"):
            logos.setdefault(l["channel"], l["url"])
    index, seen = [], set()
    for s in st:
        c = chans.get(s.get("channel"))
        url = s.get("url") or ""
        if not c or not url.startswith(("http://", "https://")):
            continue
        dedup = (c["id"], s.get("feed"))
        if dedup in seen:
            continue
        seen.add(dedup)
        key = hashlib.sha1(url.encode()).hexdigest()[:12]
        e = {"key": key, "cid": c["id"], "name": c["name"], "alt": c.get("alt_names") or [],
             "country": c.get("country") or "", "cats": c.get("categories") or [],
             "quality": s.get("quality") or "", "logo": logos.get(c["id"], ""),
             "url": url, "ref": s.get("referrer") or "", "ua": s.get("user_agent") or ""}
        if s.get("feed") and s.get("title") and s.get("title") != c["name"]:
            e["name"] = s["title"]
        e["fold"] = tv_fold(e["name"])
        e["folds"] = [e["fold"]] + [tv_fold(a) for a in e["alt"]]
        e["letter"] = tv_letter(e["name"])
        index.append(e)
    # „#“ (Ziffern, andere Schriften) zuerst, dann A–Z – dieselbe Reihenfolge wie die Leiste
    index.sort(key=lambda e: (e["letter"] != "#", e["fold"]))
    return index


def write_db(index, path):
    """Schreibt die Datei und tauscht sie erst fertig aus: Der Launcher sieht immer einen vollstaendigen Stand."""
    import sqlite3
    tmp = Path(str(path) + ".part")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    try:
        db.execute("PRAGMA journal_mode=OFF")
        db.execute("PRAGMA synchronous=OFF")
        db.execute(f"PRAGMA user_version={SCHEMA}")
        db.execute("CREATE TABLE tv(rid INTEGER PRIMARY KEY, key TEXT, cid TEXT, name TEXT, alt TEXT, country TEXT, cats TEXT,"
                   " quality TEXT, logo TEXT, url TEXT, ref TEXT, ua TEXT, letter TEXT, folds TEXT)")
        db.executemany("INSERT INTO tv(key,cid,name,alt,country,cats,quality,logo,url,ref,ua,letter,folds) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       ((e["key"], e["cid"], e["name"], SEP.join(e["alt"]), e["country"],
                         "," + ",".join(e["cats"]) + "," if e["cats"] else "", e["quality"], e["logo"], e["url"], e["ref"], e["ua"],
                         e["letter"], SEP + SEP.join(e["folds"])) for e in index))
        db.execute("CREATE INDEX tv_key ON tv(key)")
        db.commit()
    finally:
        db.close()
    os.replace(tmp, path)


def connect(path):
    """Nur lesen, kleiner Zwischenspeicher: je Abfrage eine Verbindung, danach ist der Speicher wieder frei."""
    import sqlite3
    db = sqlite3.connect(f"file:{urllib.parse.quote(str(path))}?mode=ro&immutable=1", uri=True, cached_statements=0)
    db.execute("PRAGMA cache_size=-256")
    return db


def info(path):
    """(Zahl der Sender, [(Land, Anzahl)] absteigend, Zeitpunkt des Baus) oder None, wenn die Datei fehlt oder alt ist."""
    try:
        mtime = os.stat(path).st_mtime
        db = connect(path)
    except Exception:  # noqa: BLE001
        return None
    try:
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA:
            return None
        countries = db.execute("SELECT country,count(*) n FROM tv GROUP BY country ORDER BY n DESC, country").fetchall()
        n = sum(c[1] for c in countries)
        return (n, countries, mtime) if n else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        db.close()


def _public(r):
    return {"key": r[0], "cid": r[1], "name": r[2], "country": r[3], "cats": _cats(r[4]), "quality": r[5], "logo": r[6]}


def _cats(s):
    return s.strip(",").split(",") if s else []


def _entry(r):
    folds = r[12].split(SEP)[1:]
    return {"key": r[0], "cid": r[1], "name": r[2], "alt": r[3].split(SEP) if r[3] else [], "country": r[4], "cats": _cats(r[5]),
            "quality": r[6], "logo": r[7], "url": r[8], "ref": r[9], "ua": r[10], "letter": r[11], "fold": folds[0], "folds": folds}


def _where(country, cat):
    sql, args = [], []
    if country:
        sql.append("country=?")
        args.append(country)
    if cat:
        sql.append("instr(cats,?)>0")
        args.append("," + cat + ",")
    return sql, args


def _clause(sql):
    return " WHERE " + " AND ".join(sql) if sql else ""


def empty_page(limit=TV_PAGE):
    return {"items": [], "total": 0, "offset": 0, "limit": limit, "letter": "", "letters": [{"l": L, "n": 0} for L in TV_LETTERS]}


def page(path, q="", country="", cat="", letter="", offset=0, limit=TV_PAGE):
    """Eine Seite der Senderliste. Ohne Suche alphabetisch, wahlweise nur ein Anfangsbuchstabe;
    mit Suche Treffer am Namensanfang zuerst. „letters“ zaehlt je Buchstabe (Land + Thema, ohne Suche)."""
    q = tv_fold((q or "").strip())
    letter = letter if letter in TV_LETTERS else ""
    limit = max(1, min(int(limit or TV_PAGE), 1000))
    base, args = _where(country, cat)
    db = connect(path)
    try:
        counts = dict(db.execute("SELECT letter,count(*) FROM tv" + _clause(base) + " GROUP BY letter", args).fetchall())
        order, oargs = "rid", []
        if q:
            sql, a = base + ["instr(folds,?)>0"], args + [q]
            order, oargs = "instr(folds,?)=0, rid", [SEP + q]
        elif letter:
            sql, a = base + ["letter=?"], args + [letter]
        else:
            sql, a = base, args
        where = _clause(sql)
        total = db.execute("SELECT count(*) FROM tv" + where, a).fetchone()[0]
        offset = max(0, min(int(offset or 0), max(0, total - 1)))
        offset -= offset % limit
        rows = db.execute(f"SELECT {PUBLIC} FROM tv{where} ORDER BY {order} LIMIT ? OFFSET ?", a + oargs + [limit, offset]).fetchall()
    finally:
        db.close()
    return {"items": [_public(r) for r in rows], "total": total, "offset": offset, "limit": limit,
            "letter": "" if q else letter, "letters": [{"l": L, "n": counts.get(L, 0)} for L in TV_LETTERS]}


def keys(path, q="", country="", cat=""):
    """Alle Sender zu Land/Thema/Suche (ohne Buchstabe, ohne Seiten) – Reihenfolge wie die Liste."""
    q = tv_fold((q or "").strip())
    sql, args = _where(country, cat)
    if q:
        sql, args = sql + ["instr(folds,?)>0"], args + [q]
    db = connect(path)
    try:
        return [r[0] for r in db.execute("SELECT key FROM tv" + _clause(sql) + " ORDER BY rid", args)]
    finally:
        db.close()


def entries(path, wanted):
    """{Sender: voller Eintrag samt Stream-Adresse}; gibt es eine Adresse doppelt, gilt wie frueher der letzte Eintrag."""
    out = {}
    wanted = list(wanted)
    db = connect(path)
    try:
        for i in range(0, len(wanted), 500):
            part = wanted[i:i + 500]
            marks = ",".join("?" * len(part))
            for r in db.execute(f"SELECT {ALL} FROM tv WHERE key IN ({marks}) ORDER BY rid", part):
                out[r[0]] = _entry(r)
    finally:
        db.close()
    return out


def main():
    cache = Path(sys.argv[1])
    day = 86400

    def load(name, age):
        return json.loads(fetch(IPTV_API + name, cache / name, age).read_text(encoding="utf-8"))

    ch, st = load("channels.json", day), load("streams.json", day)
    try:
        lg = load("logos.json", 7 * day)
    except Exception:  # noqa: BLE001
        lg = []
    index = build_index(ch, st, lg)
    if not index:
        raise ValueError("Senderverzeichnis ist leer")
    write_db(index, cache / DB_NAME)
    print(len(index))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(e, file=sys.stderr)
        sys.exit(1)
