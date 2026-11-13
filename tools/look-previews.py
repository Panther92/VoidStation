#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Vorschaubilder fuer die Spalte "Bildstil" der Emulator-Optionen (launcher/shaders/previews/<Kachel>/<Option>-<Wert>.jpg).

Jedes Bild zeigt einen Ausschnitt einer selbst gezeichneten Testszene (keine Spielgrafik – die duerfte nicht ins Repo),
durch den echten Shader des Emulators gerechnet: die Quelltexte der Emulatoren werden hier nur gelesen und mit einem
kleinen Nachbau ihrer Shader-Umgebung auf Software-OpenGL (Mesa llvmpipe) ausgefuehrt. Was sich so nicht rechnen laesst
(die ReShade-Shader von DuckStation, *.fx), bekommt kein Bild; die Karte zeigt dann keins.

Benoetigt: pip install moderngl numpy pillow, Mesa mit EGL (llvmpipe reicht)
Quelltexte: git clone --depth 1 von stenzek/duckstation, PCSX2/pcsx2, dosbox-staging/dosbox-staging (Tag v0.82.2);
            die Shader von mGBA liegen im Repo (launcher/shaders/mgba).
Aufruf:     python3 tools/look-previews.py --duckstation DIR --pcsx2 DIR --dosbox DIR [--out DIR] [--only gba,dosbox]
            python3 tools/look-previews.py --scenes DIR      -> nur die Testszenen als PNG (zum Ansehen)

Ausschnitte und Massstab (wie auf einem 1080p-Fernseher bzw. etwas kleiner, Bild 480 Punkte breit):
  gba          120×80 Spielpixel  -> 480×320 (4-fach)
  dosbox        96×72 (VGA 320×200) -> 480×360 (5-fach, wie DOSBox es bei 1080p waehlt)
  duckstation, pcsx2   120×90 Konsolenpixel, mit 2-facher Aufloesung gerechnet (240×180) -> 480×360
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SHADERS = REPO / "launcher" / "shaders"

# ------------------------------------------------------------------------------------------------------------------
#  Testszenen
# ------------------------------------------------------------------------------------------------------------------
CAT = [                       # 16×16, eigene Figur: . frei, k Kontur, o Fell, c hell, e Auge, n Nase
    "..k..........k..",
    ".kok........kok.",
    ".kook......kook.",
    ".koookkkkkkoook.",
    ".koooooooooooook",
    "kooooooooooooook",
    "koookkooookkoook",
    "kooekkooookkeook",
    "koooooonnooooook",
    "kooccoonnooccook",
    ".kocccccccccook.",
    ".kooccccccccok..",
    "..kooooooooook..",
    "..kook.kk.kook..",
    "..kook....kook..",
    "...kk......kk...",
]
CAT_COLORS = {"k": (40, 24, 32), "o": (248, 144, 32), "c": (255, 232, 176), "e": (48, 208, 96), "n": (248, 96, 120)}


def scene_pixel(w, h):
    """Pixelgrafik im Stil eines Handheld- bzw. VGA-Spiels: kraeftige Farben, harte Kanten, Schraegen, Raster, Schrift."""
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                                          # Schrift ohne Glaettung, wie Pixelschrift
    horizon = int(h * 0.52)
    for y in range(horizon):                                   # Himmel in 5-Bit-Stufen
        t = y / max(1, horizon - 1)
        col = (int(72 + 120 * t), int(144 + 88 * t), 248)
        d.line([(0, y), (w, y)], fill=tuple(c & 0xF8 for c in col))
    d.ellipse([w * 0.74, h * 0.06, w * 0.74 + h * 0.2, h * 0.26], fill=(255, 240, 96))
    for cx, cy, r in ((0.16, 0.14, 0.07), (0.24, 0.12, 0.09), (0.33, 0.15, 0.06), (0.56, 0.24, 0.05), (0.62, 0.23, 0.07)):
        d.ellipse([w * cx - h * r, h * cy - h * r * 0.6, w * cx + h * r, h * cy + h * r * 0.6], fill=(248, 248, 248))
    for x0, peak, x1, col in ((-0.1, 0.22, 0.55, (96, 88, 184)), (0.3, 0.2, 0.9, (120, 104, 208)), (0.62, 0.3, 1.2, (88, 80, 168))):
        px, py = w * (x0 + x1) / 2, h * peak
        d.polygon([(w * x0, horizon), (px, py), (w * x1, horizon)], fill=col)
        d.polygon([(px - h * 0.07, py + h * 0.07), (px, py), (px + h * 0.07, py + h * 0.07), (px, py + h * 0.04)], fill=(240, 248, 255))
    d.rectangle([0, horizon, w, h], fill=(56, 184, 72))
    px = im.load()
    for y in range(horizon, h):                                # Wiese: Raster aus zwei Gruen, dunkler nach unten
        for x in range(w):
            if (x + y) % 2 == 0 and (y - horizon) % 6 < 3:
                px[x, y] = (40, 152, 64)
            if (x * 7 + y * 13) % 53 == 0:
                px[x, y] = (248, 232, 80) if (x + y) % 3 else (248, 120, 160)
    d.polygon([(w * 0.42, h), (w * 0.62, h), (w * 0.52, horizon + 2), (w * 0.49, horizon + 2)], fill=(232, 200, 136))   # Weg
    # Haus
    hx, hy, hw, hh = int(w * 0.08), int(h * 0.36), int(w * 0.3), int(h * 0.3)
    d.rectangle([hx, hy, hx + hw, hy + hh], fill=(248, 224, 176), outline=(64, 40, 40))
    d.polygon([(hx - 4, hy), (hx + hw // 2, hy - int(h * 0.16)), (hx + hw + 4, hy)], fill=(216, 56, 48), outline=(64, 24, 24))
    for i in range(3, hw + 4, 6):                              # Dachziegel
        d.line([(hx - 4 + i, hy - 1), (hx + hw // 2, hy - int(h * 0.16) + 2)], fill=(168, 40, 40))
    d.rectangle([hx + hw * 0.4, hy + hh * 0.45, hx + hw * 0.6, hy + hh], fill=(136, 80, 40), outline=(64, 40, 40))
    for wx in (0.12, 0.7):
        d.rectangle([hx + hw * wx, hy + hh * 0.25, hx + hw * (wx + 0.18), hy + hh * 0.55], fill=(112, 200, 248), outline=(64, 40, 40))
        d.line([(hx + hw * wx + 2, hy + hh * 0.25 + 2), (hx + hw * (wx + 0.18) - 2, hy + hh * 0.55 - 2)], fill=(232, 248, 255))
    # Baum
    tx, ty = int(w * 0.8), int(h * 0.5)
    d.rectangle([tx - 3, ty, tx + 3, ty + int(h * 0.16)], fill=(120, 72, 40), outline=(56, 32, 24))
    d.ellipse([tx - h * 0.14, ty - h * 0.2, tx + h * 0.14, ty + h * 0.04], fill=(24, 136, 56), outline=(16, 64, 40))
    d.ellipse([tx - h * 0.1, ty - h * 0.18, tx + h * 0.04, ty - h * 0.06], fill=(72, 192, 80))
    # Figur
    fx, fy = int(w * 0.5) - 8, int(h * 0.56)
    for j, row in enumerate(CAT):
        for i, ch in enumerate(row):
            if ch != ".":
                px[fx + i, fy + j] = CAT_COLORS[ch]
    # Textkasten
    font = ImageFont.load_default()
    bx0, by0, bx1, by1 = int(w * 0.06), int(h * 0.76), int(w * 0.94), int(h * 0.95)
    d.rectangle([bx0, by0, bx1, by1], fill=(24, 40, 112), outline=(248, 248, 248))
    d.rectangle([bx0 + 2, by0 + 2, bx1 - 2, by1 - 2], outline=(120, 152, 248))
    d.text((w * 0.5 - 62, by0 + 4), "Miau! VoidStation 100%", fill=(248, 248, 248), font=font)
    d.text((w * 0.5 - 28, by0 + 4 + (by1 - by0 - 8) // 2), "Bildstil", fill=(255, 224, 96), font=font)
    return im


def scene_3d(w, h):
    """3D-Szene im Stil der ersten Konsolen mit Polygonen: karierter Boden, Kisten und Saeule mit groben Texturen, harte
    Kanten ohne Glaettung, Verlauf am Himmel. Strahl je Bildpunkt (numpy), also so treppig wie ein Emulator ohne Glaettung."""
    rng = np.random.default_rng(7)
    tex_wood = (np.array([150, 96, 48]) + rng.integers(-18, 18, (16, 16, 1)) + (np.arange(16)[None, :, None] % 4 == 0) * -40).clip(0, 255)
    tex_stone = (np.array([150, 150, 160]) + rng.integers(-28, 28, (16, 16, 1))
                 + ((np.arange(16)[:, None, None] % 8 == 0) | ((np.arange(16)[None, :, None] + 4 * (np.arange(16)[:, None, None] // 8)) % 8 == 0)) * -60).clip(0, 255)
    ys, xs = np.mgrid[0:h, 0:w]
    u = (xs + 0.5) / w * 2 - 1
    v = 1 - (ys + 0.5) / h * 2
    aspect = w / h
    cam = np.array([0.0, 1.3, -4.2])
    fwd = np.array([0.0, -0.16, 1.0]); fwd /= np.linalg.norm(fwd)
    right = np.array([1.0, 0.0, 0.0])
    up = np.cross(fwd, right)
    dirs = fwd[None, None, :] + (u * aspect * 0.62)[..., None] * right + (v * 0.62)[..., None] * up
    dirs /= np.linalg.norm(dirs, axis=2, keepdims=True)
    light = np.array([-0.5, 0.8, -0.35]); light /= np.linalg.norm(light)
    # Himmel
    t = (dirs[..., 1] * 2.2 + 0.25).clip(0, 1)[..., None]
    col = (1 - t) * np.array([255, 200, 150]) + t * np.array([60, 110, 230])
    depth = np.full((h, w), 1e9)
    # Boden y = 0
    with np.errstate(divide="ignore", invalid="ignore"):
        tf = -cam[1] / dirs[..., 1]
    hit = (dirs[..., 1] < 0) & (tf > 0)
    fx = cam[0] + dirs[..., 0] * tf
    fz = cam[2] + dirs[..., 2] * tf
    check = ((np.floor(fx) + np.floor(fz)) % 2 == 0)
    fine = ((np.floor(fx * 8) + np.floor(fz * 8)) % 2 == 0)
    floor = np.where(check[..., None], np.array([70, 150, 90]), np.array([40, 100, 70])) + fine[..., None] * 12
    fog = np.exp(-np.where(hit, tf, 0) * 0.045)[..., None]
    col = np.where(hit[..., None], floor * fog + np.array([255, 200, 150]) * (1 - fog), col)
    depth = np.where(hit, tf, depth)

    def box(lo, hi, tex, tint):
        nonlocal col, depth
        lo, hi = np.array(lo, float), np.array(hi, float)
        with np.errstate(divide="ignore", invalid="ignore"):
            t0 = (lo - cam) / dirs
            t1 = (hi - cam) / dirs
        tn = np.minimum(t0, t1); tx = np.maximum(t0, t1)
        tnear = tn.max(axis=2); tfar = tx.min(axis=2)
        ok = (tnear < tfar) & (tnear > 0) & (tnear < depth)
        axis = tn.argmax(axis=2)
        p = cam + dirs * tnear[..., None]
        normal = np.zeros_like(p)
        for a in range(3):
            normal[..., a] = np.where(axis == a, -np.sign(dirs[..., a]), 0)
        ua = np.where(axis == 0, p[..., 2], p[..., 0])
        va = np.where(axis == 1, p[..., 2], p[..., 1])
        tu = (np.floor(ua * 16) % 16).astype(int)
        tv = (np.floor(va * 16) % 16).astype(int)
        shade = (0.45 + 0.55 * (normal @ light).clip(0, 1))[..., None]
        c = tex[tv, tu] * shade * np.array(tint)
        col = np.where(ok[..., None], c, col)
        depth = np.where(ok, tnear, depth)

    box((-1.9, 0, 0.4), (-0.7, 1.2, 1.6), tex_wood, (1, 1, 1))
    box((-1.6, 1.2, 0.7), (-0.9, 1.9, 1.4), tex_wood, (1.1, 0.95, 0.8))
    box((0.9, 0, 1.4), (1.5, 2.6, 2.0), tex_stone, (1, 1, 1))
    box((0.2, 0, -1.2), (1.0, 0.8, -0.4), tex_wood, (0.75, 0.85, 1.2))
    # schraege Flaeche: Rampe als Halbraum-Schnitt einer Kiste
    box((-3.4, 0, 2.6), (3.6, 0.5, 3.0), tex_stone, (0.9, 0.85, 0.8))
    img = Image.fromarray(col.clip(0, 255).astype(np.uint8), "RGB")
    return img


def hud(im, scale):
    """Anzeige wie ein 2D-Overlay der Konsole: in Konsolenpixeln gezeichnet, grob vergroessert."""
    w, h = im.size[0] // scale, im.size[1] // scale
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.fontmode = "1"
    font = ImageFont.load_default()
    d.text((5, 4), "LAP 2/3", fill=(0, 0, 0, 255), font=font)
    d.text((4, 3), "LAP 2/3", fill=(255, 240, 64, 255), font=font)
    d.rectangle([w - 46, 6, w - 6, 12], outline=(255, 255, 255, 255), fill=(32, 32, 32, 255))
    d.rectangle([w - 45, 7, w - 20, 11], fill=(240, 64, 48, 255))
    layer = layer.resize(im.size, Image.NEAREST)
    out = im.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


# ------------------------------------------------------------------------------------------------------------------
#  OpenGL
# ------------------------------------------------------------------------------------------------------------------
GL_SRGB8, GL_SRGB8_ALPHA8, GL_FRAMEBUFFER_SRGB = 0x8C41, 0x8C43, 0x8DB9
_ctx = None


def ctx():
    global _ctx
    if _ctx is None:
        import moderngl
        _ctx = moderngl.create_standalone_context(backend="egl")
    return _ctx


def tex_from(im, flip, linear, srgb=False, border=False):
    """flip: Zeile 0 der Textur ist die unterste Bildzeile (OpenGL-Sitte) – sonst die oberste."""
    im = im.convert("RGBA")
    if flip:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    import moderngl
    t = ctx().texture(im.size, 4, im.tobytes(), internal_format=GL_SRGB8_ALPHA8 if srgb else None)
    t.filter = (moderngl.LINEAR, moderngl.LINEAR) if linear else (moderngl.NEAREST, moderngl.NEAREST)
    t.repeat_x = t.repeat_y = False
    if border:
        t.border_color = (0.0, 0.0, 0.0, 1.0)
    return t


def target(size, srgb=False):
    t = ctx().texture(size, 4, internal_format=GL_SRGB8_ALPHA8 if srgb else None)
    t.repeat_x = t.repeat_y = False
    return t, ctx().framebuffer(color_attachments=[t])


def read(fbo, flip):
    im = Image.frombytes("RGBA", fbo.size, fbo.read(components=4)).convert("RGB")
    return im.transpose(Image.FLIP_TOP_BOTTOM) if flip else im


def draw(prog, fbo, attr, uniforms, textures, blend=False, srgb_fb=False, clear=True):
    """Ein Rechteck ueber das ganze Ziel. attr: Name des Positions-Attributs (vec2/vec4, Clip-Koordinaten)."""
    import moderngl
    c = ctx()
    fbo.use()
    if clear:
        fbo.clear(0.0, 0.0, 0.0, 1.0)
    for name, val in uniforms.items():
        if name in prog:
            try:
                prog[name].value = val
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"Uniform {name}={val!r}: {e}") from e
    for i, (name, t) in enumerate(textures):
        t.use(i)
        if name in prog:
            prog[name].value = i
    quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4")
    vbo = c.buffer(quad.tobytes())
    vao = c.vertex_array(prog, [(vbo, "2f", attr)])
    if blend:
        c.enable(moderngl.BLEND)
        c.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    else:
        c.disable(moderngl.BLEND)
    (c.enable_direct if srgb_fb else c.disable_direct)(GL_FRAMEBUFFER_SRGB)
    vao.render(moderngl.TRIANGLE_STRIP)
    c.disable_direct(GL_FRAMEBUFFER_SRGB)
    vao.release(); vbo.release()


COPY_VS = "#version 330\nin vec2 pos; out vec2 uv; void main(){ gl_Position = vec4(pos, 0.0, 1.0); uv = pos * 0.5 + 0.5; }"
COPY_FS = "#version 330\nin vec2 uv; out vec4 o; uniform sampler2D t; void main(){ o = vec4(texture(t, uv).rgb, 1.0); }"


def scale(im, size, linear):
    """Bild mit OpenGL vergroessern (naechster Nachbar oder bilinear) – so wie ein Emulator ohne Shader ausgibt."""
    t = tex_from(im, True, linear)
    _, fbo = target(size)
    draw(ctx().program(vertex_shader=COPY_VS, fragment_shader=COPY_FS), fbo, "pos", {}, [("t", t)])
    return read(fbo, True)


# ------------------------------------------------------------------------------------------------------------------
#  mGBA (src/platform/opengl/gles2.c, Stand 0.10.5): Kopfzeilen und Ablauf der Durchgaenge von dort
# ------------------------------------------------------------------------------------------------------------------
MGBA_VH = "#version 150 core\n#define attribute in\n#define varying out\n"
MGBA_FH = ("#version 150 core\n#define varying in\n#define texture2D texture\nout vec4 compat_FragColor;\n"
           "#define gl_FragColor compat_FragColor\n")
MGBA_NULL_VS = ("attribute vec4 position;\nvarying vec2 texCoord;\nvoid main() {\n\tgl_Position = position;\n"
                "\ttexCoord = (position.st + vec2(1.0, 1.0)) * vec2(0.5, 0.5);\n}")
MGBA_NULL_FS = ("varying vec2 texCoord;\nuniform sampler2D tex;\nvoid main() {\n\tvec4 color = texture2D(tex, texCoord);\n"
                "\tcolor.a = 1.;\n\tgl_FragColor = color;\n}")


def ini(path):
    out: dict[str, dict[str, str]] = {}
    sec = None
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]; out.setdefault(sec, {})
        elif sec is not None and "=" in s and not s.startswith((";", "#")):
            k, v = s.split("=", 1); out[sec][k.strip()] = v.strip()
    return out


def mgba_uniforms(man, n):
    out = {}
    for sec, vals in man.items():
        m = re.fullmatch(rf"pass\.{n}\.uniform\.(.+)", sec)
        if not m:
            continue
        typ = vals.get("type", "float")
        comps = sorted((k for k in vals if k.startswith("default[")), key=lambda k: [int(x) for x in re.findall(r"\d+", k)])
        raw = [vals[k] for k in comps] if comps else ([vals["default"]] if "default" in vals else [])
        if not raw:
            continue
        nums = [float(x) for x in raw]
        if typ in ("int", "bool") or typ.startswith("ivec"):
            nums = [int(x) for x in nums]
        out[m.group(1)] = nums[0] if len(nums) == 1 else tuple(nums)
    return out


def mgba(folder, src, out_size):
    """src: Bild in Spielaufloesung. Durchgaenge wie _drawShader: width/height 0 = Ausgabegroesse, < 0 = Vielfaches der
    Spielaufloesung; texSize ist immer die Spielaufloesung; zum Schluss unveraendert auf den Bildschirm."""
    man = ini(folder / "manifest.ini")
    cur = tex_from(src, True, False)
    gw, gh = src.size
    for n in range(int(man["shader"].get("passes", "1"))):
        p = man.get(f"pass.{n}", {})
        w, h = int(p.get("width", "0")), int(p.get("height", "0"))
        dw = out_size[0] if w == 0 else (-w * gw if w < 0 else w)
        dh = out_size[1] if h == 0 else (-h * gh if h < 0 else h)
        if int(p.get("integerScaling", "0")):
            dw -= dw % gw; dh -= dh % gh
        vs = (folder / p["vertexShader"]).read_text(encoding="utf-8") if p.get("vertexShader") else MGBA_NULL_VS
        fs = (folder / p["fragmentShader"]).read_text(encoding="utf-8") if p.get("fragmentShader") else MGBA_NULL_FS
        prog = ctx().program(vertex_shader=MGBA_VH + vs, fragment_shader=MGBA_FH + fs)
        import moderngl
        cur.filter = (moderngl.LINEAR, moderngl.LINEAR) if int(p.get("filter", "0")) else (moderngl.NEAREST, moderngl.NEAREST)
        t, fbo = target((dw, dh))
        uni = dict(mgba_uniforms(man, n), texSize=(float(gw), float(gh)))
        draw(prog, fbo, "position", uni, [("tex", cur)], blend=bool(int(p.get("blend", "0"))))
        cur = t
    import moderngl
    cur.filter = (moderngl.NEAREST, moderngl.NEAREST)
    _, fbo = target(out_size)
    draw(ctx().program(vertex_shader=COPY_VS, fragment_shader=COPY_FS), fbo, "pos", {}, [("t", cur)])
    return read(fbo, True)


# ------------------------------------------------------------------------------------------------------------------
#  DOSBox Staging 0.82.2 (src/gui/shader_manager.cpp, sdlmain.cpp): eine Datei mit VERTEX/FRAGMENT, #pragma-Schalter
# ------------------------------------------------------------------------------------------------------------------
DOS_VH = "#version 330\n#define attribute in\n#define varying out\n#define VERTEX 1\n"
DOS_FH = ("#version 330\n#define varying in\n#define texture2D texture\nout vec4 compat_FragColor;\n"
          "#define gl_FragColor compat_FragColor\n#define FRAGMENT 1\n")


def dosbox(path, src, out_size):
    """src: 320×200-Ausschnitt in einfacher Abtastung. Ohne force_single_scan/force_no_pixel_doubling bekommt der Shader
    das Bild wie von der VGA-Karte: jede Zeile bzw. jeden Punkt doppelt."""
    code = path.read_text(encoding="utf-8", errors="replace")
    prag = set(re.findall(r"^#pragma\s+(\w+)\s*$", code, re.M))
    body = re.sub(r"^#version.*$", "", code, count=1, flags=re.M)
    w, h = src.size
    if "force_no_pixel_doubling" not in prag:
        w *= 2
    if "force_single_scan" not in prag:
        h *= 2
    img = src.resize((w, h), Image.NEAREST)
    t = tex_from(img, False, "use_nearest_texture_filter" not in prag, srgb="use_srgb_texture" in prag)
    prog = ctx().program(vertex_shader=DOS_VH + body, fragment_shader=DOS_FH + body)
    _, fbo = target(out_size, srgb="use_srgb_framebuffer" in prag)
    uni = {"rubyInputSize": (float(w), float(h)), "rubyTextureSize": (float(w), float(h)),
           "rubyOutputSize": (float(out_size[0]), float(out_size[1])), "rubyFrameCount": 1}
    draw(prog, fbo, "a_position", uni, [("rubyTexture", t)], srgb_fb="use_srgb_framebuffer" in prag)
    return read(fbo, True)


# ------------------------------------------------------------------------------------------------------------------
#  DuckStation, GLSL-Shader (src/util/postprocessing_shader_glsl.cpp, shadergen.cpp): Kopf und Hilfsfunktionen von dort
# ------------------------------------------------------------------------------------------------------------------
DUCK_UNIFORMS = ["float4 u_src_rect", "float2 u_src_size", "float2 u_window_size", "float2 u_rcp_window_size",
                 "float2 u_viewport_size", "float2 u_window_to_viewport_ratio", "float2 u_internal_size",
                 "float2 u_internal_pixel_size", "float2 u_norm_internal_pixel_size", "float2 u_native_size",
                 "float2 u_native_pixel_size", "float2 u_norm_native_pixel_size", "float u_upscale_multiplier", "float u_time"]


def duck_header(src_dir):
    gen = (src_dir / "src/util/shadergen.cpp").read_text(encoding="utf-8")
    block = gen[gen.index('ss << "#define GLSL 1\\n";'):gen.index('ss << "#define HLSL 1\\n";')]
    defs = "".join(m.group(1).encode().decode("unicode_escape") for m in re.finditer(r'"(#define [^"]*\\n)"', block))
    defs = defs.replace("#define FOR_UNROLL", "#define FOR_UNROLL for //").replace("#define FOR_LOOP", "#define FOR_LOOP for //")
    pp = (src_dir / "src/util/postprocessing_shader_glsl.cpp").read_text(encoding="utf-8")
    a = pp.index("layout(location = 0) out float4 o_col0;")
    helpers = pp[a:pp.index(')";', a)]
    return defs, helpers


def duck_options(code):
    """[configuration]-Block wie GLSLShader::LoadOptions: Name und Vorgabe je Option."""
    m = re.search(r"\[configuration\](.*?)\[/configuration\]", code, re.S)
    out, cur = [], None
    for line in (m.group(1) if m else "").splitlines():
        s = line.strip()
        if s.startswith("[Option"):
            cur = {"type": s.strip("[]")}
            out.append(cur)
        elif cur is not None and "=" in s:
            k, v = (x.strip() for x in s.split("=", 1))
            cur[k] = v
    return [o for o in out if o.get("OptionName")]


def duck_glsl(src_dir, path, frame, internal, native):
    """frame: das schon auf Bildschirmgroesse gerechnete Bild (so bekommt es die Kette "PostProcessing")."""
    defs, helpers = duck_header(src_dir)
    code = path.read_text(encoding="utf-8", errors="replace")
    opts, decl = duck_options(code), ""
    uni: dict[str, Any] = {}
    for o in opts:
        vals = [x.strip() for x in o.get("DefaultValue", "0").split(",")]
        if o["type"] == "OptionBool":
            decl += f"uniform int {o['OptionName']};\n"
            uni[o["OptionName"]] = 1 if vals[0].lower() == "true" else 0
        elif o["type"] == "OptionRangeInteger":
            decl += f"uniform {'int' if len(vals) == 1 else 'ivec' + str(len(vals))} {o['OptionName']};\n"
            uni[o["OptionName"]] = int(vals[0]) if len(vals) == 1 else tuple(int(x) for x in vals)
        else:
            decl += f"uniform {'float' if len(vals) == 1 else 'vec' + str(len(vals))} {o['OptionName']};\n"
            uni[o["OptionName"]] = float(vals[0]) if len(vals) == 1 else tuple(float(x) for x in vals)
    sat = "".join(f"{t} saturate({t} value) {{ return clamp(value, 0.0, 1.0); }}\n" for t in ("float", "vec2", "vec3", "vec4"))
    head = "#version 450 core\n#define API_OPENGL 1\n" + defs + sat + "".join(f"uniform {u};\n" for u in DUCK_UNIFORMS) + decl
    vs = head + ("in vec2 pos;\nout vec2 v_tex0;\nvoid main(){ gl_Position = vec4(pos, 0.0, 1.0);\n"
                 "  v_tex0 = u_src_rect.xy + u_src_size * vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5); }\n")
    fs = head + "layout(binding = 0) uniform sampler2D samp0;\nin vec2 v_tex0;\n" + helpers + code
    prog = ctx().program(vertex_shader=vs, fragment_shader=fs)
    ww, wh = frame.size
    f = float
    uni.update({
        "u_src_rect": (0.0, 0.0, (ww - 1) / ww, (wh - 1) / wh), "u_src_size": (1.0, 1.0),
        "u_window_size": (f(ww), f(wh)), "u_rcp_window_size": (1 / ww, 1 / wh), "u_viewport_size": (f(ww), f(wh)),
        "u_window_to_viewport_ratio": (1.0, 1.0), "u_internal_size": (f(internal[0]), f(internal[1])),
        "u_internal_pixel_size": (ww / internal[0], wh / internal[1]),
        "u_norm_internal_pixel_size": (1 / internal[0], 1 / internal[1]), "u_native_size": (f(native[0]), f(native[1])),
        "u_native_pixel_size": (ww / native[0], wh / native[1]), "u_norm_native_pixel_size": (1 / native[0], 1 / native[1]),
        "u_upscale_multiplier": internal[0] / native[0], "u_time": 1.0})
    t = tex_from(frame, False, False, border=True)
    _, fbo = target((ww, wh))
    draw(prog, fbo, "pos", uni, [("samp0", t)])
    return read(fbo, True)


# ------------------------------------------------------------------------------------------------------------------
#  PCSX2 (bin/resources/shaders/opengl/present.glsl, shadeboost.glsl, common/fxaa.fx; Einstieg wie GSDeviceOGL)
# ------------------------------------------------------------------------------------------------------------------
PCSX2_VS = ("#version 420 core\nin vec2 pos;\nout vec4 PSin_p;\nout vec2 PSin_t;\nout vec4 PSin_c;\n"
            "void main(){ gl_Position = vec4(pos, 0.5, 1.0); PSin_p = gl_Position;\n"
            "  PSin_t = vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5); PSin_c = vec4(1.0); }\n")
PCSX2_TV = {"0": "ps_copy", "1": "ps_filter_scanlines", "2": "ps_filter_diagonal", "3": "ps_filter_triangular",
            "4": "ps_filter_complex", "5": "ps_filter_lottes", "6": "ps_4x_rgss", "7": "ps_automagical_supersampling"}


def pcsx2_pass(src_dir, rel, entry, src, out_size, uniforms, extra=""):
    code = (src_dir / "bin/resources/shaders" / rel).read_text(encoding="utf-8", errors="replace")
    fs = f"#version 420 core\n#define FRAGMENT_SHADER 1\n{extra}#define {entry} main\n" + code
    prog = ctx().program(vertex_shader=PCSX2_VS, fragment_shader=fs)
    t = tex_from(src, False, True)
    _, fbo = target(out_size)
    draw(prog, fbo, "pos", uniforms, [("TextureSampler", t)])
    return read(fbo, True)


def pcsx2_present(src_dir, value, src, out_size):
    sw, sh = src.size
    ow, oh = out_size
    f = float
    uni = {"u_source_rect": (0.0, 0.0, 1.0, 1.0), "u_target_rect": (0.0, 0.0, f(ow), f(oh)), "u_source_size": (f(sw), f(sh)),
           "u_target_size": (f(ow), f(oh)), "u_target_resolution": (f(ow), f(oh)), "u_rcp_target_resolution": (1 / ow, 1 / oh),
           "u_source_resolution": (f(sw), f(sh)), "u_rcp_source_resolution": (1 / sw, 1 / sh), "u_time": 1.0}
    return pcsx2_pass(src_dir, "opengl/present.glsl", PCSX2_TV[value], src, out_size, uni)


def pcsx2_fxaa(src_dir, src):
    return pcsx2_pass(src_dir, "common/fxaa.fx", "ps_main", src, src.size, {}, extra="#define FXAA_GLSL_130 1\n")


def pcsx2_boost(src_dir, src, params):
    return pcsx2_pass(src_dir, "opengl/shadeboost.glsl", "ps_main", src, src.size, {"params": tuple(p / 50.0 for p in params)})


# ------------------------------------------------------------------------------------------------------------------
def save(im, out, tile, opt, value):
    f = out / tile / f"{opt}-{str(value).replace('/', '_')}.jpg"
    f.parent.mkdir(parents=True, exist_ok=True)
    im.save(f, "JPEG", quality=82, subsampling=0, optimize=True)
    return f


def launcher_lists():
    """Listen der Stile aus launcher.py (ohne den Launcher zu laden)."""
    src = (REPO / "launcher" / "launcher.py").read_text(encoding="utf-8")
    ns = {"BASE": REPO / "launcher", "Path": Path}
    a, b = src.index("_OFF = {"), src.index("_DUCK_LOOK_IO = ")
    exec(src[a:b], ns)  # noqa: S102 – eigener Quelltext
    return ns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duckstation"); ap.add_argument("--pcsx2"); ap.add_argument("--dosbox")
    ap.add_argument("--out", default=str(SHADERS / "previews"))
    ap.add_argument("--only", default="")
    ap.add_argument("--scenes")
    a = ap.parse_args()
    out = Path(a.out)
    only = {x for x in a.only.split(",") if x}
    gba_full = scene_pixel(240, 160)
    dos_full = scene_pixel(320, 200)
    ps_full = scene_3d(640, 480)                              # 2-fache Aufloesung einer Konsole mit 320×240
    gba = gba_full.crop((60, 70, 180, 150))                   # 120×80: Haus, Figur, Textkasten
    dos = dos_full.crop((104, 96, 200, 168))                  # 96×72
    ps = hud(ps_full.crop((190, 70, 430, 250)), 2)            # 240×180 = 120×90 Konsolenpixel: Kisten, Saeule, Anzeige
    if a.scenes:
        d = Path(a.scenes); d.mkdir(parents=True, exist_ok=True)
        for name, im in (("gba", gba_full), ("dos", dos_full), ("ps", ps_full), ("gba-crop", gba), ("dos-crop", dos), ("ps-crop", ps)):
            im.save(d / f"{name}.png")
        return
    L = launcher_lists()
    done, failed = [], []

    def attempt(tile, opt, value, fn):
        try:
            done.append(save(fn(), out, tile, opt, value))
        except Exception as e:  # noqa: BLE001
            failed.append((tile, opt, value, str(e).strip().splitlines()[-1][:160] if str(e).strip() else repr(e)))

    if not only or "gba" in only:
        size = (480, 320)
        attempt("gba", "look", "off", lambda: scale(gba, size, False))
        attempt("gba", "look", "orig", lambda: mgba(SHADERS / "mgba" / "gba-color.shader", gba, size))
        attempt("gba", "look", "klar", lambda: mgba(SHADERS / "mgba" / "voidstation-klar.shader", gba, size))
        for v, _ in L["MGBA_LOOKS"]:
            attempt("gba", "look", v, lambda v=v: mgba(SHADERS / "mgba" / f"{v}.shader", gba, size))
    if a.dosbox and (not only or "dosbox" in only):
        size, base = (480, 360), Path(a.dosbox) / "contrib/resources/glshaders"
        # was DOSBox bei einem 320×200-Spiel auf 1080p aus den Kurznamen macht (shader_manager.cpp)
        files = {"sharp": "interpolation/sharp", "nearest": "interpolation/nearest", "bilinear": "interpolation/bilinear",
                 "crt-auto": "crt/vga-1080p-fake-double-scan", "crt-auto-machine": "crt/vga-1080p-fake-double-scan",
                 "crt-auto-arcade": "crt/arcade-1440p", "crt-auto-arcade-sharp": "crt/arcade-sharp-1440p"}
        for c in L["DOSBOX_LOOKS"]:
            attempt("dosbox", "shader", c["v"], lambda c=c: dosbox(base / (files.get(c["v"], c["v"]) + ".glsl"), dos, size))
    if a.duckstation and (not only or "duckstation" in only):
        size, d = (480, 360), Path(a.duckstation)
        frame = scale(ps, size, True)                           # Display/Scaling: bilinear (Standard)
        res = d / "data/resources/shaders"
        attempt("duckstation", "look", "off", lambda: frame)
        attempt("duckstation", "color", "nat", lambda: frame)
        for v, name, _ in L["DUCK_LOOKS"]:
            own = SHADERS / "duckstation" / f"{name}.glsl"
            f = own if own.is_file() else res / f"{name}.glsl"
            if f.is_file():
                attempt("duckstation", "look", v, lambda f=f: duck_glsl(d, f, frame, ps.size, (ps.size[0] // 2, ps.size[1] // 2)))
        for v, name in L["DUCK_COLORS"].items():
            attempt("duckstation", "color", v, lambda name=name: duck_glsl(
                d, SHADERS / "duckstation" / f"{name}.glsl", frame, ps.size, (ps.size[0] // 2, ps.size[1] // 2)))
        if a.pcsx2:                                             # FXAA 3.11 in der Renderaufloesung, dann aufs Display
            fx = lambda: scale(pcsx2_fxaa(Path(a.pcsx2), ps), size, True)  # noqa: E731
            for v in ("auto", "on"):
                attempt("duckstation", "fxaa", v, fx)
            attempt("duckstation", "fxaa", "off", lambda: frame)
    if a.pcsx2 and (not only or "pcsx2" in only):
        size, d = (480, 360), Path(a.pcsx2)
        for v in L["PCSX2_LOOKS"]:
            attempt("pcsx2", "look", v["v"], lambda v=v: pcsx2_present(d, v["v"], ps, size))
        attempt("pcsx2", "fxaa", "true", lambda: pcsx2_present(d, "0", pcsx2_fxaa(d, ps), size))
        attempt("pcsx2", "fxaa", "false", lambda: pcsx2_present(d, "0", ps, size))
        for c in L["PCSX2_COLORS"]:                             # ShadeBoost mit den Werten aus launcher.py
            params = None if c["set"]["ShadeBoost"] == "false" else tuple(
                int(c["set"][f"ShadeBoost_{k}"]) for k in ("Brightness", "Contrast", "Saturation", "Gamma"))
            attempt("pcsx2", "color", c["v"], lambda params=params: pcsx2_present(
                d, "0", pcsx2_boost(d, ps, params) if params else ps, size))
    print(f"{len(done)} Bilder nach {out}")
    for t in failed:
        print("  ohne Bild:", *t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
