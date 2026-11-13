# SPDX-License-Identifier: GPL-3.0-or-later
"""Spielprofile: was VoidStation fuer ein bestimmtes Spiel von selbst einstellt.

Die Listen liegen in gamedb/<system>.csv (Semikolon, erste Zeile = Spaltennamen, s. gamedb/LIESMICH.txt):
  psx.csv  titel;aliase;kategorie;sicher;notiz     kategorie: 3d | vorgerendert | 3d-sprites | 2d
  dos.csv  titel;aliase;dateien;jahr;tempo;sicher;notiz   tempo: xt | 286 | 386 | 486 | pentium | max | std

Ein Profil liefert Werte fuer Optionen der Spieleliste (launcher.py EMU_OPTS), z. B. {"texfilter": "Nearest"}.
Der Launcher traegt sie nur fuer diesen einen Start ein und nimmt sie danach zurueck; was der Nutzer fuer das Spiel
selbst gewaehlt hat, geht immer vor (launcher.py emu_opts_prepare, dosbox_game_conf).

Erkannt wird ein Spiel am Namen: Dateiname bzw. Ordner, bei PlayStation zusaetzlich der Titel, den DuckStation in
seiner eigenen Datenbank zur Seriennummer fuehrt (die Datenbank wird nur gelesen, nicht mitgeliefert). Alle Regionen
eines Spiels heissen dort gleich oder stehen als "aliase" in der Liste.

Keine Abhaengigkeit zum Launcher: laesst sich einzeln pruefen (tools/gamedb-check.py)."""
import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent / "gamedb"

# ---- PlayStation: Kategorie -> Optionen von DuckStation -------------------------------------------------------
# texfilter glaettet die Texturen der 3D-Flaechen. Sprites (Schrift, Menues, 2D-Figuren als Rechtecke) haben in
# DuckStation einen eigenen Filter, der aus bleibt. Wo Figuren oder Schrift als texturierte Flaechen gezeichnet
# werden (3d-sprites) oder alles 2D ist, bleibt der Filter aus – sonst verschwimmt die Pixelgrafik.
# fxaa (Kanten glaetten, allgemein auf "Automatik"): glaettet Treppen an den Kanten von 3D-Flaechen. Auf Pixelgrafik
# zeichnet es Schrift und Figuren weich – deshalb aus, wo die das Bild bestimmt.
PSX_CATEGORIES: dict[str, dict[str, str]] = {
    "3d": {"texfilter": "BilinearBinAlpha", "fxaa": "on"},
    "vorgerendert": {"texfilter": "BilinearBinAlpha", "fxaa": "on"},      # 3D-Figuren vor gemalten Hintergruenden
    "3d-sprites": {"texfilter": "Nearest", "fxaa": "off"},
    "2d": {"texfilter": "Nearest", "fxaa": "off"},
}
# Spiele, die nicht in der Liste stehen: nur Genres aus DuckStations Datenbank, die praktisch immer reines 3D sind.
# Alles andere bleibt, wie es allgemein eingestellt ist.
PSX_GENRES_3D = {"driving / racing", "racing", "racing / driving", "first person shooter", "flight simulation"}

# ---- DOS: Tempo -> Wert der Option "CPU-Tempo" (launcher.py EMU_OPTS dosbox/speed) ------------------------------
DOS_SPEEDS = {"xt", "286", "386", "486", "pentium", "max", "std"}

_PAREN = re.compile(r"[\(\[][^()\[\]]*[\)\]]")
_ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9"}


def norm(title):
    """Titel vergleichbar machen: ohne Klammerzusaetze ("(Europe)", "(Disc 2)"), Akzente, Satzzeichen und fuehrendes
    "The"; "Titel, The" wie "The Titel"; roemische Ziffern 2–9 als arabische (II = 2)."""
    s = unicodedata.normalize("NFKD", str(title or "")).encode("ascii", "ignore").decode().lower()
    s = _PAREN.sub(" ", s).replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"^(.*) the$", r"the \1", s)
    s = re.sub(r"^the ", "", s)
    return " ".join(_ROMAN.get(w, w) for w in s.split())


_TABLES: dict[str, Any] = {}


def table(system):
    """Liste eines Systems: {"rows": [Zeilen], "by_name": {normierter Titel/Alias: Zeile}, "by_file": {DATEI.EXE: Zeile}}."""
    if system not in _TABLES:
        rows: list[dict[str, str]] = []
        by_name: dict[str, dict[str, str]] = {}
        by_file: dict[str, dict[str, str]] = {}
        try:
            with open(DIR / f"{system}.csv", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    row = {k: (v or "").strip() for k, v in row.items() if k}
                    if not row.get("titel") or row["titel"].startswith("#"):
                        continue
                    rows.append(row)
                    for name in [row["titel"]] + [a for a in row.get("aliase", "").split("|") if a.strip()]:
                        by_name.setdefault(norm(name), row)
                    for fn in row.get("dateien", "").split("|"):
                        if fn.strip():
                            by_file.setdefault(fn.strip().upper(), row)
        except OSError:
            pass
        _TABLES[system] = {"rows": rows, "by_name": by_name, "by_file": by_file}
    return _TABLES[system]


def _sure(row):
    return row.get("sicher", "").lower() == "ja"


# ---- PlayStation ---------------------------------------------------------------------------------------------
def duck_entry(db_path, serial):
    """Eintrag einer Seriennummer in DuckStations gamedb.yaml -> {"name", "genre"} oder {} (Datei fehlt, unbekannt).
    Kein YAML-Leser noetig: Die Datei hat je Spiel einen Block "SERIAL:" mit eingerueckten Zeilen."""
    if not db_path or not serial:
        return {}
    try:
        txt = Path(db_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.search(rf"^{re.escape(str(serial))}:[ \t]*\r?\n((?:[ \t]+.*\r?\n|\r?\n)*)", txt, re.M)
    if not m:
        return {}
    block = m.group(1)

    def val(key):
        v = re.search(rf'^\s+{key}:\s*"?(.*?)"?\s*$', block, re.M)
        return v.group(1) if v else ""
    return {"name": val("name"), "genre": val("genre")}


def psx_profile(names, genre=""):
    """Optionen fuer ein PlayStation-Spiel. names: moegliche Titel (Dateiname, Titel aus DuckStations Datenbank).
    -> ({Option: Wert}, Herkunft fuers Protokoll) – ({}, "") wenn nichts bekannt ist."""
    tab = table("psx")
    for n in names:
        row = tab["by_name"].get(norm(n)) if n else None
        if row and _sure(row) and row.get("kategorie") in PSX_CATEGORIES:
            return dict(PSX_CATEGORIES[row["kategorie"]]), f"{row['titel']}: {row['kategorie']}"
    if str(genre).strip().lower() in PSX_GENRES_3D:
        return dict(PSX_CATEGORIES["3d"]), f"Genre {genre}: 3d"
    return {}, ""


# ---- DOS -----------------------------------------------------------------------------------------------------
def dos_profile(game):
    """Optionen fuer ein DOS-Spiel (Ordner oder Datei unter ROMs/dos): erst nach dem Namen des Ordners bzw. der Datei,
    dann nach kennzeichnenden Dateien im Ordner (DOOM2.EXE …). -> ({Option: Wert}, Herkunft)"""
    tab = table("dos")
    game = Path(game)
    row = tab["by_name"].get(norm(game.name if game.is_dir() else game.stem))
    if row is None:
        try:
            files = {f.name.upper() for f in (game.iterdir() if game.is_dir() else game.parent.iterdir()) if f.is_file()}
        except OSError:
            files = set()
        if not game.is_dir():
            files &= {game.name.upper()}                    # einzelne Datei: nur sie selbst zaehlt
        row = next((r for fn, r in tab["by_file"].items() if fn in files), None)
    if row is None or not _sure(row) or row.get("tempo") not in DOS_SPEEDS or row["tempo"] == "std":
        return {}, ""
    return {"speed": row["tempo"]}, f"{row['titel']}: {row['tempo']}"
