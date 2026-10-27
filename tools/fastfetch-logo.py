#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal-Logo fuer fastfetch: das App-Icon (vier Kacheln + V) als ANSI-Grafik mit 24-Bit-Farben.

Aufruf:    python3 tools/fastfetch-logo.py          -> launcher/shell/fastfetch-logo.ansi
Braucht:   Pillow, cairosvg (pip install cairosvg)

Das V kommt aus site/assets/favicon.svg (derselbe Pfad wie in der Wortmarke), die Farben aus dem App-Icon.
32 Spalten x 16 Zeilen = 32 x 32 "Pixel" (je Zeile zwei, ueber Halbbloecke) – im Terminal quadratisch.
Geschrieben wird nur mit Leerzeichen (Hintergrundfarbe) und "▄": volle Bloecke "█"/"▀" fuellen die Zelle in
xterm nicht ganz aus, dann laufen duenne Linien durch das Logo. Endet eine Flaeche in der oberen
Zellhaelfte, wird "▄" invertiert gezeichnet (Zelle = Flaeche, Zeichen = Terminal-Hintergrund).
In fastfetch: "logo": {"type": "file-raw", "width": 32, "height": 16} (Breite zaehlt fastfetch bei
file-raw nicht selbst).
"""
import io
import re
import sys
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "launcher" / "shell" / "fastfetch-logo.ansi"
COLS = {"r": (0x7a, 0x2f, 0x33), "t": (0x2f, 0x58, 0x66), "b": (0x2d, 0x37, 0x63), "p": (0x45, 0x35, 0x5c),
        "w": (0xec, 0xeb, 0xe8)}
W, H = 32, 32               # Pixel; Kacheln 15 breit + 2 Fuge, Hoehe 16 + 1 Fuge + 15 (Fuge faellt auf eine Zeilengrenze)
TW, TH, TB, GX, GY = 15, 16, 15, 2, 1
V_HEIGHT = 0.80             # V-Hoehe im Verhaeltnis zur Logo-Hoehe
SS = 12                     # Ueberabtastung je Pixel


def hx(c):
    return "#%02x%02x%02x" % c


def raster():
    d = re.search(r' d="([^"]+)"', (ROOT / "site/assets/favicon.svg").read_text()).group(1)
    s = V_HEIGHT * H / 276.0            # Pfad: x 8..281, y 8..284 (Mitte 144/146)
    tx, ty = W / 2 - 144 * s, H / 2 - 146 * s
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect x="0" y="0" width="{TW}" height="{TH}" fill="{hx(COLS['r'])}"/>
<rect x="{TW + GX}" y="0" width="{TW}" height="{TH}" fill="{hx(COLS['t'])}"/>
<rect x="0" y="{TH + GY}" width="{TW}" height="{TB}" fill="{hx(COLS['b'])}"/>
<rect x="{TW + GX}" y="{TH + GY}" width="{TW}" height="{TB}" fill="{hx(COLS['p'])}"/>
<path transform="translate({tx:.3f} {ty:.3f}) scale({s:.5f})" fill="{hx(COLS['w'])}" d="{d}"/></svg>'''
    im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=W * SS,
                                                output_height=H * SS))).convert("RGBA")
    px = im.load()
    grid = []
    for y in range(H):
        row = ""
        for x in range(W):
            cnt = {}
            for yy in range(y * SS, y * SS + SS):
                for xx in range(x * SS, x * SS + SS):
                    r, g, b, a = px[xx, yy]
                    if a < 128:
                        k = " "
                    elif r > 200:
                        k = "w"
                    else:
                        k = min("rtbp", key=lambda c: sum((u - v) ** 2 for u, v in zip(COLS[c], (r, g, b))))
                    cnt[k] = cnt.get(k, 0) + 1
            # Weiss gewinnt schon ab 40 %, damit die Striche des V nicht abreissen
            row += "w" if cnt.get("w", 0) >= 0.40 * SS * SS else max(cnt, key=cnt.get)
        grid.append(row)
    return grid


def ansi(grid):
    out = []
    for y in range(0, len(grid), 2):
        cells = []
        for a, b in zip(grid[y], grid[y + 1]):
            if a == b == " ":
                cells.append((" ", None, None, False))
            elif a == b:
                cells.append((" ", None, a, False))
            elif a == " ":
                cells.append(("▄", b, None, False))
            elif b == " ":
                cells.append(("▄", a, None, True))
            else:
                cells.append(("▄", b, a, False))
        while cells and cells[-1] == (" ", None, None, False):
            cells.pop()
        line, cur = "", (None, None, False)
        for ch, fg, bg, rev in cells:
            if (fg, bg, rev) != cur:
                seq = "\x1b[0" + (";7" if rev else "")
                seq += ";38;2;%d;%d;%d" % COLS[fg] if fg else ""
                seq += ";48;2;%d;%d;%d" % COLS[bg] if bg else ""
                line += seq + "m"
                cur = (fg, bg, rev)
            line += ch
        out.append(line + "\x1b[0m")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    g = raster()
    if "--show" in sys.argv:
        print("\n".join(g))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(ansi(g), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {W} Spalten x {H // 2} Zeilen")
