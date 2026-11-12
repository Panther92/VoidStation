#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Weltkarte fuer Mullvad VPN als Punktraster: launcher/qt/qml/vpn/worldmap.json

Laender aus Natural Earth 1:110m (gemeinfrei, mit geopandas < 1.0 als "naturalearth_lowres" dabei).
Raster gleichmaessig in Mercator: x = Laengengrad, y = Mercator-Breite in Grad, Schritt STEP. Je Zeile Laeufe
[x0, Laenge, Land] mit Land = Index in "cc" (ISO 3166-1 alpha-2, klein wie bei Mullvad, "" = unbekannt).
Die Oberflaeche (VpnMap.qml) zeichnet daraus nur den sichtbaren Ausschnitt und hebt ein Land hervor.

Aufruf:  pip install "geopandas<1" pycountry  &&  python3 tools/vpn-map.py
"""
import json
import math
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
try:
    import geopandas as gpd
    import pycountry
    from shapely.geometry import Point
    from shapely.prepared import prep
except ImportError:
    sys.exit('fehlt: pip install "geopandas<1" pycountry')

OUT = Path(__file__).resolve().parent.parent / "launcher/qt/qml/vpn/worldmap.json"
STEP = 0.5                       # Grad (x) bzw. Mercator-Grad (y)
LAT_TOP, LAT_BOT = 82.0, -58.0   # ohne Antarktis und hohe Arktis
# Natural Earth 110m hat bei einigen Laendern kein ISO-a3 ("-99")
BY_NAME = {"France": "fr", "Norway": "no", "Kosovo": "xk", "N. Cyprus": "cy", "Somaliland": "so"}


def merc(lat):
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def inv(y):
    return math.degrees(2 * math.atan(math.exp(math.radians(y))) - math.pi / 2)


def main():
    w = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    w = w[w["name"] != "Antarctica"]
    shapes, codes = [], []
    for _, r in w.iterrows():
        cc = BY_NAME.get(r["name"])
        if not cc:
            c = pycountry.countries.get(alpha_3=r["iso_a3"])
            cc = c.alpha_2.lower() if c else ""
        if cc not in codes:
            codes.append(cc)
        shapes.append((codes.index(cc), prep(r.geometry), r.geometry.bounds))
    y_top, y_bot = merc(LAT_TOP), merc(LAT_BOT)
    cols = int(round(360 / STEP))
    nrows = int((y_top - y_bot) / STEP)
    rows, dots = [], 0
    for j in range(nrows):
        lat = inv(y_top - (j + 0.5) * STEP)
        cand = [(ci, g) for ci, g, (x0, y0, x1, y1) in shapes if y0 <= lat <= y1]
        runs, cur = [], None
        for i in range(cols):
            lon = -180 + (i + 0.5) * STEP
            hit = -1
            p = Point(lon, lat)
            for ci, g in cand:
                if g.contains(p):
                    hit = ci
                    break
            if hit >= 0 and cur and cur[2] == hit and cur[0] + cur[1] == i:
                cur[1] += 1
            elif hit >= 0:
                cur = [i, 1, hit]
                runs.append(cur)
            if hit >= 0:
                dots += 1
        if runs:
            rows.append([j] + [v for r in runs for v in r])
    data = {"src": "Natural Earth 1:110m (public domain)", "step": STEP, "lonLeft": -180, "yTop": round(y_top, 4),
            "cols": cols, "rows": nrows, "cc": codes, "r": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"{OUT}: {dots} Punkte, {len(rows)} Zeilen, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
