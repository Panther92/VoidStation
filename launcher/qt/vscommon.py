# SPDX-License-Identifier: GPL-3.0-or-later
"""
Gemeinsame Teile der Qt-Programme (Startseite voidstation-home.py und Player voidstation-player.py):
  * Farben aus den CSS-Themes (web/themes/<name>.css), Texte aus web/i18n/<sprache>.json
  * Gamepad ueber evdev (python3-evdev) mit Tastenwiederholung wie im Web
  * VsBase: Bruecke zur QML-Oberflaeche (Launcher-Aufrufe in Threads, Texte, Farben, Symbole)
  * QML-Zwischenspeicher nach Updates verwerfen
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

T0 = time.monotonic()
HERE = Path(__file__).resolve().parent
WEB = Path(os.environ.get("VS_WEB") or HERE.parent / "web")
API = os.environ.get("VS_API", "http://127.0.0.1:8765").rstrip("/")
PADMOUSE_NAME = "VoidStation Controller-Maus"    # virtuelle Maus der Startseite – kein Controller
LOG_PREFIX = "home"                              # setzt das jeweilige Programm


def log(*a):
    print(f"[{LOG_PREFIX}]", *a, file=sys.stderr, flush=True)


sys.path.insert(0, str(HERE))
from icons import ICONS  # noqa: E402


# ---------------------------------------------------------------------------
#  Farben aus den CSS-Themes (web/themes/<name>.css)
# ---------------------------------------------------------------------------
def _hex2(v):
    return f"{max(0, min(255, int(round(v)))):02x}"


def css_color(v):
    """CSS-Farbe -> Qt-Farbe (#rrggbb oder #aarrggbb). rgba(...) kennt QML nicht."""
    v = v.strip()
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+%?)\s*)?\)$", v)
    if m:
        r, g, b = (float(x) for x in m.groups()[:3])
        a = m.group(4)
        alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return "#" + (_hex2(alpha * 255) if alpha < 1 else "") + _hex2(r) + _hex2(g) + _hex2(b)
    if re.match(r"#[0-9a-fA-F]{3}$", v):
        return "#" + "".join(c * 2 for c in v[1:])
    if re.match(r"#[0-9a-fA-F]{8}$", v):                       # CSS #rrggbbaa -> Qt #aarrggbb
        return "#" + v[7:9] + v[1:7]
    return v


def _camel(name):
    return re.sub(r"-([a-z0-9])", lambda m: m.group(1).upper(), name)


def _lum(col):
    c = col.lstrip("#")[-6:]
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def theme_names():
    found = sorted(p.stem for p in (WEB / "themes").glob("*.css"))
    return found or ["default-dark"]


def theme_tokens(name):
    """Alle --variablen eines Themes (Grundlage: default-dark), aufgeloeste var(), Qt-Farben, camelCase."""
    raw = {}

    def read(n):
        try:
            css = (WEB / "themes" / f"{n}.css").read_text(encoding="utf-8")
        except OSError:
            return ""
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        root = re.search(r"^[^{]*:root[^{]*\{(.*?)\}", css, re.S | re.M)
        for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", root.group(1) if root else ""):
            raw[k] = v.strip()
        return css

    read("default-dark")
    css = read(name) if name != "default-dark" else read("default-dark")

    def resolve(v, depth=0):
        m = re.fullmatch(r"var\(--([\w-]+)\)", v.strip())
        if m and depth < 8:
            return resolve(raw.get(m.group(1), ""), depth + 1)
        return v

    out = {}
    for k, v in raw.items():
        v = resolve(v)
        if k in ("f", "u", "rows", "gap", "pad-x", "ease", "focus-ring"):
            continue
        out[_camel(k)] = css_color(v)
    # Abgeleitet: Schrift auf farbigen Kacheln und auf aktiven Knoepfen (helle Themes ueberschreiben das im CSS)
    light = _lum(out.get("bgMain", "#000000")) > 0.5
    out["light"] = light
    out["tileText"] = "#ffffff" if light else out.get("textPrimary", "#ecebe8")
    out["tileSub"] = "#d9ffffff" if light else out.get("textSecondary", "#b8ecebe8")
    m = re.search(r"\.pill\.on[^{]*\{[^}]*?color:\s*([^;]+);", css or "")
    out["pillOnText"] = css_color(m.group(1)) if m else out.get("textPrimary", "#ecebe8")
    return out


# ---------------------------------------------------------------------------
#  Gamepad (evdev): Zustand im Lese-Thread, Tastendruecke + Wiederholung im Qt-Thread
# ---------------------------------------------------------------------------
class Gamepad:
    REPEAT = {"left", "right", "up", "down", "lb", "rb", "lt", "rt"}
    # Controller mit Kernel-Treiber (Xbox, PlayStation, Switch, 8BitDo, Steam …): einheitliche Tasten
    KEYS = {304: "a", 305: "b", 307: "x", 308: "y", 310: "lb", 311: "rb", 312: "lt", 313: "rt",
            314: "select", 315: "start", 544: "up", 545: "down", 546: "left", 547: "right"}
    # Einfache USB-Pads ohne eigenen Treiber (DragonRise u. a., Tasten ab BTN_TRIGGER): Taste 3 unten = A,
    # Taste 2 rechts = B (SNES- wie PlayStation-Nachbauten)
    GENERIC = {288: "y", 289: "b", 290: "a", 291: "x", 292: "lb", 293: "rb", 294: "lt", 295: "rt",
               296: "select", 297: "start"}
    # Joysticks / Flugsteuerung: Abzug = A, Daumentaste = B
    JOY = {288: "a", 289: "b", 290: "x", 291: "y", 292: "lb", 293: "rb", 294: "select", 295: "start"}
    # Arcade-Sticks u. ae. mit Tasten ab BTN_0
    MISC = {256: "a", 257: "b", 258: "x", 259: "y", 260: "lb", 261: "rb", 262: "select", 263: "start"}
    OVERRIDE = Path.home() / ".config/voidstation/pads.json"   # {"<Geraetename oder vid:pid>": {"<Code>": "a", …}}

    @classmethod
    def keymap(cls, dev, keys, abs_codes):
        """Tastenbelegung fuer ein Geraet; None = kein Controller."""
        from evdev import ecodes as E
        info = dev.info
        ids = (dev.name, f"{info.vendor:04x}:{info.product:04x}")
        try:
            own = json.loads(cls.OVERRIDE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            own = {}
        for i in ids:
            if isinstance(own.get(i), dict):
                return {int(k): str(v) for k, v in own[i].items() if str(k).isdigit()}
        if E.BTN_SOUTH in keys:
            return dict(cls.KEYS)
        pen = keys & {E.BTN_TOUCH, E.BTN_TOOL_PEN, E.BTN_STYLUS, E.BTN_TOOL_FINGER}
        if E.BTN_TRIGGER in keys and not pen:
            stick = abs_codes & {E.ABS_THROTTLE, E.ABS_RUDDER}    # Schubregler/Ruder: Flugsteuerung
            m = dict(cls.JOY if stick else cls.GENERIC)
            m.update({k: v for k, v in cls.KEYS.items() if k >= 544})      # Steuerkreuz als Tasten
            return m
        if E.BTN_0 in keys and not pen and {E.ABS_X, E.ABS_Y} <= abs_codes and "wacom" not in dev.name.lower():
            return dict(cls.MISC)
        return None

    def __init__(self):
        self.state = {}            # (geraet, taste) -> gedrueckt
        self.lock = threading.Lock()
        self.names = []            # neu erkannte Controller (fuer die Meldung)
        self.trig = set()          # (geraet, achse): Achse ist eine Schultertaste (LT/RT)
        self.raw = {}              # (geraet, "rx"/"ry"/"ly"/"r3") -> Stick -1…1 bzw. gedrueckt (Controller-Maus)
        self.rx_dev = set()        # Geraete mit eigenem rechten Stick (ABS_RX/RY)
        self.generic = set()       # einfache USB-Pads (Tasten ab BTN_TRIGGER, R3 = BTN_BASE6)
        try:
            import evdev  # noqa: F401
        except ImportError:
            log("python3-evdev fehlt – Gamepad aus")
            return
        threading.Thread(target=self._run, daemon=True).start()

    def pressed(self):
        with self.lock:
            return {k for (_d, k), v in self.state.items() if v}

    def _set(self, dev, key, on):
        with self.lock:
            self.state[(dev, key)] = on

    def _raw(self, dev, key, val):
        with self.lock:
            self.raw[(dev, key)] = val

    def mouse_state(self):
        """Fuer die Controller-Maus: staerkster Ausschlag je Achse ueber alle Controller, R3, LT/RT."""
        out = {"rx": 0.0, "ry": 0.0, "ly": 0.0, "r3": False, "lt": False, "rt": False}
        with self.lock:
            for (_d, k), v in self.raw.items():
                if k == "r3":
                    out["r3"] = out["r3"] or bool(v)
                elif abs(v) > abs(out[k]):
                    out[k] = v
            for (_d, k), v in self.state.items():
                if k in ("lt", "rt") and v:
                    out[k] = True
        return out

    def _run(self):
        import selectors
        import evdev
        from evdev import ecodes as E
        sel = selectors.DefaultSelector()
        known = {}                 # pfad -> (geraet, achsen-info)
        last = 0.0
        while True:
            if time.monotonic() - last > 3:
                last = time.monotonic()
                for path in evdev.list_devices():
                    if path in known:
                        continue
                    try:
                        dev = evdev.InputDevice(path)
                        caps = dev.capabilities()
                        keys = set(caps.get(E.EV_KEY, []))
                        axes = {}
                        for code, info in caps.get(E.EV_ABS, []):
                            axes[code] = info
                        kmap = self.keymap(dev, keys, set(axes))
                        if kmap is None or dev.name == PADMOUSE_NAME:
                            dev.close()
                            continue
                        known[path] = (dev, axes, kmap)
                        if E.ABS_RX in axes:
                            self.rx_dev.add(path)
                        if kmap.get(296) == "select":
                            self.generic.add(path)
                        sel.register(dev, selectors.EVENT_READ)
                        with self.lock:
                            self.names.append(dev.name)
                        log("Controller:", dev.name)
                    except OSError:
                        pass
            for key, _ in sel.select(timeout=1):
                dev = key.fileobj
                _d, axes, kmap = known.get(dev.path, (None, {}, {}))
                try:
                    for ev in dev.read():
                        if ev.type == E.EV_KEY and ev.code in kmap:
                            self._set(dev.path, kmap[ev.code], ev.value != 0)
                        elif ev.type == E.EV_KEY and (ev.code == E.BTN_THUMBR or
                                                      (ev.code == E.BTN_BASE6 and dev.path in self.generic)):
                            self._raw(dev.path, "r3", ev.value != 0)
                        elif ev.type == E.EV_ABS:
                            self._abs(dev.path, ev.code, ev.value, axes.get(ev.code))
                except OSError:
                    sel.unregister(dev)
                    known.pop(dev.path, None)
                    with self.lock:
                        for k in [k for k in self.state if k[0] == dev.path]:
                            del self.state[k]
                        for k in [k for k in self.raw if k[0] == dev.path]:
                            del self.raw[k]

    def _abs(self, dev, code, value, info):
        from evdev import ecodes as E
        if code in (E.ABS_HAT0X, E.ABS_HAT0Y):
            neg, pos = ("left", "right") if code == E.ABS_HAT0X else ("up", "down")
            self._set(dev, "hat" + neg, value < 0)
            self._set(dev, "hat" + pos, value > 0)
            return
        if not info:
            return
        span = (info.max - info.min) or 1
        n = max(-1.0, min(1.0, (value - (info.max + info.min) / 2) / (span / 2)))
        if code in (E.ABS_X, E.ABS_Y):
            neg, pos = ("left", "right") if code == E.ABS_X else ("up", "down")
            self._set(dev, "stick" + neg, n < -0.55)
            self._set(dev, "stick" + pos, n > 0.55)
            if code == E.ABS_Y:
                self._raw(dev, "ly", n)
        elif code in (E.ABS_RX, E.ABS_RY):
            self._raw(dev, "rx" if code == E.ABS_RX else "ry", n)
        elif code in (E.ABS_Z, E.ABS_RZ):
            # Schultertasten als Achse (Xbox, DualSense): nur wenn die Achse in Ruhe am Anfang steht
            if info.min >= 0 and ((dev, code) in self.trig or (info.value - info.min) / span < 0.2):
                self.trig.add((dev, code))
                self._set(dev, "lt" if code == E.ABS_Z else "rt", (value - info.min) / span > 0.6)
            elif dev not in self.rx_dev:              # einfache Pads: rechter Stick auf Z (waagrecht) / RZ
                self._raw(dev, "rx" if code == E.ABS_Z else "ry", n)


class PadPump(QObject):
    """Fragt den Gamepad-Zustand ab (60 Hz) und meldet Druecke wie im Web: 380 ms bis zur Wiederholung, dann alle 140 ms."""
    key = Signal(str)
    connected = Signal(str)

    def __init__(self, pad, active=None):
        super().__init__()
        self.pad, self.held, self.next = pad, {}, {}
        # Wann gehoert der Controller diesem Programm? Standard: eines seiner Fenster ist vorn
        self.active = active or (lambda: QGuiApplication.focusWindow() is not None)
        self.t = QTimer(self)
        self.t.timeout.connect(self.tick)
        self.t.start(16)

    def tick(self):
        with self.pad.lock:
            names, self.pad.names = self.pad.names, []
        for n in names:
            self.connected.emit(n.split("(")[0].strip())
        if not self.active():                          # nicht vorn: Controller gehoert dem anderen Programm
            self.held = {}
            return
        raw = self.pad.pressed()
        now = time.monotonic()
        want = {k for k in raw if not k.startswith(("hat", "stick"))}
        want |= {k[3:] for k in raw if k.startswith("hat")} | {k[5:] for k in raw if k.startswith("stick")}
        for k in list(self.held):
            if k not in want:
                del self.held[k]
        for k in want:
            if k not in self.held:
                self.held[k] = True
                self.next[k] = now + 0.38
                self.key.emit(k)
            elif k in Gamepad.REPEAT and now >= self.next.get(k, 0):
                self.next[k] = now + 0.14
                self.key.emit(k)



# ---------------------------------------------------------------------------
#  Verbindung zur Oberflaeche
# ---------------------------------------------------------------------------
class VsBase(QObject):
    """Bruecke zur QML-Oberflaeche (Startseite und Player): Launcher-Aufrufe, Texte, Farben, Symbole."""
    replied = Signal(int, bool, int, str)       # id, ok, HTTP-Status, Antwort (JSON-Text)
    themeChanged = Signal()
    stringsChanged = Signal()
    padKey = Signal(str)
    padConnected = Signal(str)

    def __init__(self):
        super().__init__()
        self._theme_name = "default-dark"
        self._theme = theme_tokens(self._theme_name)
        self._lang = "de"
        self._strings = {}
        self._de = self._load_lang("de")
        self._set_lang("de")
        self._icons = {}
        self.pad = None

    # ---- HTTP (in Threads, Antwort per Signal) ----
    @Slot(int, str, str, str)
    def request(self, rid, method, path, body):
        threading.Thread(target=self._do, args=(rid, method, path, body), daemon=True).start()

    def _do(self, rid, method, path, body):
        data = body.encode() if method == "POST" else None
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"X-TV": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                self.replied.emit(rid, True, r.status, r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            try:
                txt = e.read().decode("utf-8", "replace")
            except OSError:
                txt = ""
            self.replied.emit(rid, False, e.code, txt)
        except (OSError, ValueError) as e:
            self.replied.emit(rid, False, 0, json.dumps({"error": str(e)}))

    # ---- Texte ----
    def _load_lang(self, lang):
        try:
            return json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _set_lang(self, lang):
        ok = bool(lang) and all(c.isalnum() or c == "-" for c in lang) and (WEB / "i18n" / f"{lang}.json").exists()
        self._lang = lang if ok else "de"
        # Rueckfall wie im Web: Sprache -> Englisch -> Deutsch (Deutsch selbst faellt nicht auf Englisch zurueck,
        # sonst kaemen z. B. die englischen App-Beschreibungen statt der deutschen aus catalog.json)
        s = dict(self._de)
        for l in [] if self._lang == "de" else (["en"] if self._lang == "en" else ["en", self._lang]):
            d = self._load_lang(l)
            labels = {**s.get("labels", {}), **d.get("labels", {})}
            s.update(d)
            s["labels"] = labels
        self._strings = s

    def _get_strings(self):
        return self._strings

    def _get_lang(self):
        return self._lang

    strings = Property("QVariantMap", _get_strings, notify=stringsChanged)
    lang = Property(str, _get_lang, notify=stringsChanged)

    @Slot(str)
    def setLang(self, lang):
        if lang != self._lang or not self._strings:
            self._set_lang(lang)
            self.stringsChanged.emit()

    # ---- Farben ----
    def _get_theme(self):
        return self._theme

    def _get_theme_name(self):
        return self._theme_name

    theme = Property("QVariantMap", _get_theme, notify=themeChanged)
    themeName = Property(str, _get_theme_name, notify=themeChanged)

    @Slot(str)
    def setTheme(self, name):
        name = name if name in theme_names() else "default-dark"
        if name == self._theme_name:
            return
        self._theme_name = name
        self._theme = theme_tokens(name)
        self._icons.clear()
        self.themeChanged.emit()

    # ---- Symbole ----
    @Slot(str, str, result=str)
    def icon(self, name, color):
        key = (name, color)
        if key not in self._icons:
            svg = ICONS.get(name) or ICONS["globe"]
            col = color if len(color) != 9 else "#" + color[3:]           # SVG kennt kein #aarrggbb
            op = "" if len(color) != 9 else f' opacity="{int(color[1:3], 16) / 255:.2f}"'
            svg = svg.replace("currentColor", col)
            if "xmlns" not in svg:
                svg = svg.replace("<svg ", f'<svg xmlns="http://www.w3.org/2000/svg"{op} ', 1)
            self._icons[key] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        return self._icons[key]

    @Slot(result=float)
    def uptime(self):
        return time.monotonic() - T0

    @Slot(str)
    def log(self, msg):
        log(msg)


def drop_stale_qml_cache(here=HERE):
    """Qt speichert kompiliertes QML in ~/.cache/voidstation/qmlcache. Qt 6.11 (Void) prueft dabei nur den
    Zeitstempel der Quelldatei – und der ist nach jedem Update derselbe (tar --mtime im Build). Ohne diese Pruefung
    liefe nach einem Update weiter das alte QML (in Qt 6.11.2 nachgestellt). Darum: Pruefsumme ueber den Inhalt
    aller QML-Dateien merken und den Cache verwerfen, sobald sie sich aendert. Kostet beim Start wenige ms."""
    from PySide6.QtCore import QStandardPaths
    h = hashlib.sha256()
    for p in sorted((here / "qml").rglob("*")):
        if p.is_file() and (p.suffix in (".qml", ".js") or p.name == "qmldir"):
            h.update(str(p.relative_to(here)).encode())
            h.update(p.read_bytes())
    stamp = h.hexdigest()[:16]
    cache = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "qmlcache"
    mark = cache / ".voidstation-qml"
    try:
        if mark.read_text(encoding="utf-8").strip() == stamp:
            return
    except OSError:
        pass
    shutil.rmtree(cache, ignore_errors=True)
    try:
        cache.mkdir(parents=True, exist_ok=True)
        mark.write_text(stamp + "\n", encoding="utf-8")
    except OSError as e:
        log("QML-Cache: Kennung nicht gespeichert:", e)
    log("QML-Cache verworfen (Oberflaeche geaendert):", stamp)
