# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenster verwalten ueber libX11 (ctypes) statt ueber wmctrl und xprop.

Eine Abfrage dauert so unter 0,1 ms statt rund 2,5 ms samt neuem Prozess; das zaehlt vor allem bei der Controller-Maus,
die viermal pro Sekunde nach dem aktiven Fenster fragt. Die Aufrufe entsprechen dem, was wmctrl an den Fenstermanager
schickt (EWMH). Fehlt libX11 oder laesst sich das Display nicht oeffnen, laufen die alten Befehle weiter.

Fenster-Kennungen: Rueckgaben wie bei wmctrl als Text ("0x01a00003"), Aufrufe nehmen Text oder Zahl.
Alle Zugriffe laufen unter einer Sperre ueber eine eigene Verbindung, XInitThreads ist deshalb nicht noetig."""
import collections
import ctypes
import queue
import re
import subprocess
import threading
import time
from ctypes import POINTER, Structure, Union, byref, c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p
from typing import Any

_lock = threading.RLock()
_x: Any = None                  # ctypes.CDLL nach _open(); Funktionen nur nach erfolgreichem _open() benutzt
_dpy = None
_root = 0
_tried = False
_atoms: dict[str, int] = {}
_ATOM_NONE = 0


class _ClientMessage(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", c_int), ("display", c_void_p), ("window", c_ulong),
                ("message_type", c_ulong), ("format", c_int), ("l", c_long * 5)]


class _KeyEvent(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", c_int), ("display", c_void_p), ("window", c_ulong), ("root", c_ulong),
                ("subwindow", c_ulong), ("time", c_ulong), ("x", c_int), ("y", c_int), ("x_root", c_int), ("y_root", c_int),
                ("state", c_uint), ("keycode", c_uint), ("same_screen", c_int)]


class _XEvent(Union):
    _fields_ = [("xclient", _ClientMessage), ("xkey", _KeyEvent), ("pad", c_long * 24)]


# Ohne eigenen Handler beendet Xlib den ganzen Prozess, sobald ein Fenster zwischendurch verschwunden ist (BadWindow)
_ERRFUNC = ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)
_ignore = _ERRFUNC(lambda _d, _e: 0)


def _open():
    """Beim ersten Aufruf verbinden; True, wenn libX11 nutzbar ist."""
    global _x, _dpy, _root, _tried
    if _tried:
        return _dpy is not None
    _tried = True
    try:
        x = ctypes.CDLL("libX11.so.6")
        x.XOpenDisplay.restype, x.XOpenDisplay.argtypes = c_void_p, [c_char_p]
        x.XDefaultRootWindow.restype, x.XDefaultRootWindow.argtypes = c_ulong, [c_void_p]
        x.XInternAtom.restype, x.XInternAtom.argtypes = c_ulong, [c_void_p, c_char_p, c_int]
        x.XGetAtomName.restype, x.XGetAtomName.argtypes = c_void_p, [c_void_p, c_ulong]
        x.XGetWindowProperty.restype = c_int
        x.XGetWindowProperty.argtypes = [c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong, POINTER(c_ulong), POINTER(c_int),
                                         POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ubyte))]
        x.XFree.restype, x.XFree.argtypes = c_int, [c_void_p]
        x.XSendEvent.restype, x.XSendEvent.argtypes = c_int, [c_void_p, c_ulong, c_int, c_long, POINTER(_XEvent)]
        x.XMapRaised.restype, x.XMapRaised.argtypes = c_int, [c_void_p, c_ulong]
        x.XSync.restype, x.XSync.argtypes = c_int, [c_void_p, c_int]
        x.XSetErrorHandler.restype, x.XSetErrorHandler.argtypes = c_void_p, [c_void_p]
        x.XKeysymToKeycode.restype, x.XKeysymToKeycode.argtypes = c_ubyte, [c_void_p, c_ulong]
        x.XGrabKey.restype, x.XGrabKey.argtypes = c_int, [c_void_p, c_int, c_uint, c_ulong, c_int, c_int, c_int]
        x.XUngrabKey.restype, x.XUngrabKey.argtypes = c_int, [c_void_p, c_int, c_uint, c_ulong]
        x.XPending.restype, x.XPending.argtypes = c_int, [c_void_p]
        x.XNextEvent.restype, x.XNextEvent.argtypes = c_int, [c_void_p, POINTER(_XEvent)]
        dpy = x.XOpenDisplay(None)
    except (OSError, AttributeError):
        return False
    if not dpy:
        return False
    _x, _dpy, _root = x, dpy, x.XDefaultRootWindow(dpy)
    return True


class _Session:
    """Sperre halten, Fehler-Handler nur solange setzen (er gilt prozessweit) und alles zum Server schicken."""

    def __enter__(self):
        _lock.acquire()
        self.ok = _open()
        self.old = _x.XSetErrorHandler(ctypes.cast(_ignore, c_void_p)) if self.ok else None
        return self.ok

    def __exit__(self, *exc):
        if self.ok:
            _x.XSync(_dpy, 0)
            _x.XSetErrorHandler(self.old)
        _lock.release()
        return False


def _atom(name):
    a = _atoms.get(name)
    if a is None:
        a = _atoms[name] = _x.XInternAtom(_dpy, name.encode(), 0)
    return a


def _atom_name(atom):
    p = _x.XGetAtomName(_dpy, atom)
    if not p:
        return ""
    try:
        return ctypes.string_at(p).decode("latin-1")
    finally:
        _x.XFree(p)


def _prop(win, name):
    """Wert einer Eigenschaft: bytes (Format 8), Liste von Zahlen (Format 32) oder None. Format 32 liefert Xlib als long."""
    typ, fmt, n, rest = c_ulong(), c_int(), c_ulong(), c_ulong()
    data = POINTER(c_ubyte)()
    rc = _x.XGetWindowProperty(_dpy, win, _atom(name), 0, 1 << 20, 0, 0, byref(typ), byref(fmt), byref(n), byref(rest), byref(data))
    if rc != 0 or not data:
        return None
    try:
        if fmt.value == 8:
            return ctypes.string_at(data, n.value)
        if fmt.value == 32:
            return list(ctypes.cast(data, POINTER(c_ulong))[:n.value])
        return None
    finally:
        _x.XFree(data)


def _send(win, name, *values):
    ev = _XEvent()
    ev.xclient.type = 33                         # ClientMessage
    ev.xclient.send_event = 1
    ev.xclient.window = win
    ev.xclient.message_type = _atom(name)
    ev.xclient.format = 32
    for i, v in enumerate(values):
        ev.xclient.l[i] = v
    # SubstructureRedirectMask | SubstructureNotifyMask: geht an den Fenstermanager
    _x.XSendEvent(_dpy, _root, 0, (1 << 20) | (1 << 19), byref(ev))


def _wid(win):
    return int(win, 16) if isinstance(win, str) else int(win)


def _tool(*cmd, timeout=5):
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _title(win):
    raw = _prop(win, "_NET_WM_NAME")
    if raw:
        return raw.decode("utf-8", "replace")
    raw = (_prop(win, "WM_NAME") or b"").replace(b"\x1b%G", b"").replace(b"\x1b%@", b"")   # COMPOUND_TEXT mit UTF-8 (xterm)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def windows():
    """Liste (Kennung, pid, Titel) aller Fenster, wie wmctrl -lp."""
    with _Session() as ok:
        if ok:
            out = []
            for w in _prop(_root, "_NET_CLIENT_LIST") or []:
                pid = _prop(w, "_NET_WM_PID")
                out.append((f"0x{w:08x}", pid[0] if pid else 0, _title(w)))
            return out
    out = []
    for row in (_tool("wmctrl", "-lp") or "").splitlines():
        parts = row.split(None, 4)
        if len(parts) >= 3 and parts[2].isdigit():
            out.append((parts[0], int(parts[2]), parts[4] if len(parts) > 4 else ""))
    return out


def active_window():
    """Zahl des aktiven Fensters (_NET_ACTIVE_WINDOW), 0 = keins oder unklar."""
    with _Session() as ok:
        if ok:
            v = _prop(_root, "_NET_ACTIVE_WINDOW")
            return v[0] if v else 0
    m = re.search(r"0x[0-9a-fA-F]+", _tool("xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW", timeout=2) or "")
    return int(m.group(0), 16) if m else 0


def window_pid(win):
    """Prozess des Fensters (_NET_WM_PID), 0 = unbekannt."""
    win = _wid(win)
    with _Session() as ok:
        if ok:
            v = _prop(win, "_NET_WM_PID")
            return v[0] if v else 0
    m = re.search(r"(\d+)\s*$", (_tool("xprop", "-id", hex(win), "-notype", "_NET_WM_PID", timeout=2) or "").strip())
    return int(m.group(1)) if m else 0


def atoms(win, name):
    """Namen in einer Atom-Liste wie _NET_WM_STATE; [] = nicht gesetzt oder Fenster weg."""
    win = _wid(win)
    with _Session() as ok:
        if ok:
            return [_atom_name(a) for a in _prop(win, name) or [] if a != _ATOM_NONE]
    out = _tool("xprop", "-id", hex(win), name, timeout=3) or ""
    return [] if "not found" in out else re.findall(r"_[A-Z0-9_]{3,}", out.partition("=")[2])


def activate(win):
    """Fenster nach vorn holen, wie wmctrl -i -a: Arbeitsflaeche wechseln, aktivieren, anheben."""
    w = _wid(win)
    with _Session() as ok:
        if ok:
            desk = _prop(w, "_NET_WM_DESKTOP")
            if desk:
                _send(_root, "_NET_CURRENT_DESKTOP", desk[0])
            _send(w, "_NET_ACTIVE_WINDOW")
            _x.XMapRaised(_dpy, w)
            return
    _tool("wmctrl", "-i", "-a", hex(w))


def close(win):
    """Hoeflich schliessen, wie Alt+F4 (Spielstaende werden gespeichert)."""
    w = _wid(win)
    with _Session() as ok:
        if ok:
            _send(w, "_NET_CLOSE_WINDOW")
            return
    _tool("wmctrl", "-i", "-c", hex(w))


def wm_state(win, action, *props):
    """Fensterzustand aendern, wie wmctrl -b: action add/remove/toggle, props z. B. fullscreen, maximized_vert."""
    w = _wid(win)
    with _Session() as ok:
        if ok:
            atom = [_atom("_NET_WM_STATE_" + p.upper()) for p in props[:2]]
            atom += [0] * (2 - len(atom))
            _send(w, "_NET_WM_STATE", {"remove": 0, "add": 1, "toggle": 2}[action], atom[0], atom[1])
            return
    _tool("wmctrl", "-i", "-r", hex(w), "-b", ",".join((action,) + props))


# Pfeiltasten, Enter und Esc fuer die heissen Ecken. Die Ecken duerfen keinen Fokus nehmen (Vollbild-Spiele minimieren sich
# sonst), deshalb holt sich die Startseite die Tasten direkt vom X-Server, solange eine Ecke offen ist.
_KEYSYMS = {0xff51: "left", 0xff52: "up", 0xff53: "right", 0xff54: "down", 0xff0d: "a", 0xff8d: "a", 0xff1b: "b"}
_MODS = (0, 0x02, 0x10, 0x12)                    # auch mit Feststelltaste und NumLock
_grabbed: dict[int, str] = {}


def grab_keys(on):
    """Tasten der Ecken vom X-Server holen (das Programm vorn bekommt sie solange nicht) bzw. wieder freigeben."""
    with _Session() as ok:
        if not ok:
            return
        if on and not _grabbed:
            for sym, name in _KEYSYMS.items():
                code = _x.XKeysymToKeycode(_dpy, sym)
                if code:
                    _grabbed[code] = name
                    for m in _MODS:
                        _x.XGrabKey(_dpy, code, m, _root, 0, 1, 1)
        elif not on and _grabbed:
            for code in _grabbed:
                for m in _MODS:
                    _x.XUngrabKey(_dpy, code, m, _root)
            _grabbed.clear()


def poll_keys():
    """Seit dem letzten Aufruf gedrueckte Tasten als Namen wie am Controller: left, right, up, down, a, b."""
    out = []
    with _Session() as ok:
        if ok:
            while _x.XPending(_dpy) > 0:
                ev = _XEvent()
                _x.XNextEvent(_dpy, byref(ev))
                if ev.xkey.type == 2 and ev.xkey.keycode in _grabbed:      # KeyPress
                    out.append(_grabbed[ev.xkey.keycode])
    return out


# ---------------------------------------------------------------------------
#  Tippen fuer die Bildschirmtastatur ueber Programmen (XTest)
# ---------------------------------------------------------------------------
# Die Tastatur ueber Programmen nimmt keinen Fokus; sie schickt Tastendruecke ueber XTest an das Fenster vorn, wie eine
# echte Tastatur. Zeichen, die auf der eingestellten X-Belegung direkt (oder mit Shift) liegen, gehen ueber ihre Taste.
# Alles andere (AltGr-Zeichen wie @ und € auf deutscher Belegung, Kyrillisch auf US, Akzente, aktive zweite Gruppe,
# Feststelltaste an) bekommt fuer die Dauer der Sitzung einen freien Tastencode mit genau diesem Zeichen auf beiden
# Ebenen - so spielen Shift, Feststelltaste und AltGr keine Rolle. type_reset() gibt die Tastencodes wieder frei.
# Laeuft in einem eigenen Thread (Reihenfolge bleibt), eine eigene X-Verbindung. Ohne libXtst: xdotool.
_NAMED = {"BackSpace": 0xff08, "Tab": 0xff09, "Return": 0xff0d, "Escape": 0xff1b, "Left": 0xff51, "Up": 0xff52,
          "Right": 0xff53, "Down": 0xff54, "Home": 0xff50, "End": 0xff57, "Delete": 0xffff}
_SHIFT_L = 0xffe1
_LOCK_MASK = 0x02


class _XkbState(Structure):
    _fields_ = [("group", c_ubyte), ("locked_group", c_ubyte), ("base_group", ctypes.c_ushort),
                ("latched_group", ctypes.c_ushort), ("mods", c_ubyte), ("base_mods", c_ubyte), ("latched_mods", c_ubyte),
                ("locked_mods", c_ubyte), ("compat_state", c_ubyte), ("grab_mods", c_ubyte), ("compat_grab_mods", c_ubyte),
                ("lookup_mods", c_ubyte), ("compat_lookup_mods", c_ubyte), ("ptr_buttons", ctypes.c_ushort)]


def keysym_of(ch):
    """X-Keysym eines Zeichens: Latin-1 direkt, alles andere als Unicode-Keysym (0x01000000 + Codepunkt)."""
    o = ord(ch)
    if ch == "\n":
        return _NAMED["Return"]
    if ch == "\t":
        return _NAMED["Tab"]
    if 0x20 <= o <= 0x7e or 0xa0 <= o <= 0xff:
        return o
    return 0x01000000 + o


class _Typer:
    PAUSE = 0.006                 # zwischen zwei Zeichen (manche Programme verschlucken sonst Tasten)
    SETTLE = 0.04                 # nach dem Umbelegen eines Tastencodes: Programme lesen die Belegung neu

    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.thread: threading.Thread | None = None
        self.ok: bool | None = None
        self.x: Any = None          # libX11, libXtst (ctypes) – gesetzt in _open()
        self.xt: Any = None
        self.dpy = None
        self.mine = collections.OrderedDict()      # Tastencode -> Keysym (von uns belegt, zuletzt benutzt hinten)
        self.lo = self.hi = 0
        self.injected = 0.0                        # Zeitpunkt des letzten Tastendrucks (monotonic)

    def _open(self):
        if self.ok is not None:
            return self.ok
        self.ok = False
        try:
            x = ctypes.CDLL("libX11.so.6")
            xt = ctypes.CDLL("libXtst.so.6")
        except OSError:
            return False
        x.XOpenDisplay.restype, x.XOpenDisplay.argtypes = c_void_p, [c_char_p]
        x.XDisplayKeycodes.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        x.XGetKeyboardMapping.restype = POINTER(c_ulong)
        x.XGetKeyboardMapping.argtypes = [c_void_p, c_ubyte, c_int, POINTER(c_int)]
        x.XChangeKeyboardMapping.argtypes = [c_void_p, c_int, c_int, POINTER(c_ulong), c_int]
        x.XKeysymToKeycode.restype, x.XKeysymToKeycode.argtypes = c_ubyte, [c_void_p, c_ulong]
        x.XkbGetState.argtypes = [c_void_p, c_uint, POINTER(_XkbState)]
        x.XFree.argtypes = [c_void_p]
        x.XFlush.argtypes = [c_void_p]
        x.XSync.argtypes = [c_void_p, c_int]
        x.XPending.argtypes = [c_void_p]
        x.XNextEvent.argtypes = [c_void_p, POINTER(_XEvent)]
        x.XSetErrorHandler.restype, x.XSetErrorHandler.argtypes = c_void_p, [c_void_p]
        xt.XTestQueryExtension.argtypes = [c_void_p] + [POINTER(c_int)] * 4
        xt.XTestFakeKeyEvent.argtypes = [c_void_p, c_uint, c_int, c_ulong]
        dpy = x.XOpenDisplay(None)
        if not dpy:
            return False
        a, b, c, d = c_int(), c_int(), c_int(), c_int()
        if not xt.XTestQueryExtension(dpy, byref(a), byref(b), byref(c), byref(d)):
            return False
        lo, hi = c_int(), c_int()
        x.XDisplayKeycodes(dpy, byref(lo), byref(hi))
        self.x, self.xt, self.dpy, self.lo, self.hi = x, xt, dpy, lo.value, hi.value
        self.ok = True
        return True

    def _drain(self):
        ev = _XEvent()                            # MappingNotify & Co. gehen an jede Verbindung: abholen, nicht sammeln
        while self.x.XPending(self.dpy) > 0:
            self.x.XNextEvent(self.dpy, byref(ev))

    def _mapping(self):
        """{Tastencode: (Ebene 1, Ebene 2)} der ersten Gruppe; freie Codes haben (0, 0)."""
        per = c_int()
        n = self.hi - self.lo + 1
        syms = self.x.XGetKeyboardMapping(self.dpy, self.lo, n, byref(per))
        if not syms:
            return {}
        w = per.value
        try:
            return {self.lo + i: (syms[i * w] if w > 0 else 0, syms[i * w + 1] if w > 1 else 0,
                                  any(syms[i * w + j] for j in range(w))) for i in range(n)}
        finally:
            self.x.XFree(syms)

    def _plain_ok(self):
        """Nur in der ersten Gruppe und ohne Feststelltaste passt die Belegung zu dem, was wir nachschlagen."""
        st = _XkbState()
        if self.x.XkbGetState(self.dpy, 0x0100, byref(st)) != 0:
            return False
        return st.group == 0 and not (st.mods & _LOCK_MASK)

    def _tap(self, code, shift=False):
        fake = self.xt.XTestFakeKeyEvent
        sc = self.x.XKeysymToKeycode(self.dpy, _SHIFT_L) if shift else 0
        if sc:
            fake(self.dpy, sc, 1, 0)
        fake(self.dpy, code, 1, 0)
        fake(self.dpy, code, 0, 0)
        if sc:
            fake(self.dpy, sc, 0, 0)
        self.x.XFlush(self.dpy)
        self.injected = time.monotonic()
        time.sleep(self.PAUSE)

    def _borrow(self, sym, mapping):
        """Freien Tastencode mit dem Zeichen belegen (beide Ebenen gleich), notfalls den am laengsten unbenutzten."""
        for code, s in self.mine.items():
            if s == sym:
                self.mine.move_to_end(code)
                return code, False
        free = [c for c in range(self.hi, self.lo - 1, -1) if c not in self.mine and not mapping.get(c, (0, 0, True))[2]]
        if free:
            code = free[0]
        elif self.mine:
            code = next(iter(self.mine))
        else:
            return 0, False
        arr = (c_ulong * 2)(sym, sym)
        self.x.XChangeKeyboardMapping(self.dpy, code, 2, arr, 1)
        self.x.XSync(self.dpy, 0)
        self.mine[code] = sym
        self.mine.move_to_end(code)
        return code, True

    def _text(self, text):
        mapping = self._mapping()
        lvl1: dict[int, int] = {}                     # Keysym -> erster Tastencode auf Ebene 1 bzw. 2
        lvl2: dict[int, int] = {}
        if self._plain_ok():
            for c, (l1, l2, _any) in mapping.items():
                if c not in self.mine:
                    if l1:
                        lvl1.setdefault(l1, c)
                    if l2:
                        lvl2.setdefault(l2, c)
        for ch in text:
            sym = keysym_of(ch)
            if sym in lvl1:
                self._tap(lvl1[sym])
            elif sym in lvl2:
                self._tap(lvl2[sym], shift=True)
            else:
                code, fresh = self._borrow(sym, mapping)
                if not code:
                    continue
                if fresh:
                    time.sleep(self.SETTLE)
                self._tap(code)
        self._drain()

    def _key(self, name):
        sym = _NAMED.get(name)
        code = self.x.XKeysymToKeycode(self.dpy, sym) if sym else 0
        if code:
            self._tap(code)
        self._drain()

    def _reset(self):
        if not self.mine:
            return
        zero = (c_ulong * 2)(0, 0)
        for code in self.mine:
            self.x.XChangeKeyboardMapping(self.dpy, code, 2, zero, 1)
        self.mine.clear()
        self.x.XSync(self.dpy, 0)
        self._drain()

    def _fallback(self, kind, arg):
        if kind == "text":
            _tool("xdotool", "type", "--clearmodifiers", "--delay", "8", "--", arg, timeout=10)
        elif kind == "key" and arg in _NAMED:
            _tool("xdotool", "key", "--clearmodifiers", arg, timeout=5)
        self.injected = time.monotonic()

    def _run(self):
        while True:
            kind, arg = self.q.get()
            try:
                if not self._open():
                    self._fallback(kind, arg)
                    continue
                old = self.x.XSetErrorHandler(ctypes.cast(_ignore, c_void_p))
                try:
                    {"text": self._text, "key": self._key, "reset": lambda _a: self._reset()}[kind](arg)
                finally:
                    self.x.XSetErrorHandler(old)
            except Exception:  # noqa: BLE001  - Tippen darf den Aufrufer nie mitreissen
                pass

    def put(self, kind, arg=None):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        self.q.put((kind, arg))


_typer = _Typer()


def type_text(text):
    """Zeichen an das Fenster mit dem Tastaturfokus schicken (Reihenfolge bleibt, kehrt sofort zurueck)."""
    if text:
        _typer.put("text", str(text))


def tap(name):
    """Sondertaste druecken: BackSpace, Tab, Return, Escape, Left, Right, Up, Down, Home, End, Delete."""
    if name in _NAMED:
        _typer.put("key", name)


def type_reset():
    """Fuer Sonderzeichen geliehene Tastencodes wieder freigeben (Tastatur zu)."""
    _typer.put("reset")


def last_typed():
    """Wann zuletzt getippt wurde (time.monotonic); 0 = noch nie."""
    return _typer.injected


class _XImage(Structure):
    _fields_ = [("width", c_int), ("height", c_int), ("xoffset", c_int), ("format", c_int), ("data", c_void_p),
                ("byte_order", c_int), ("bitmap_unit", c_int), ("bitmap_bit_order", c_int), ("bitmap_pad", c_int),
                ("depth", c_int), ("bytes_per_line", c_int), ("bits_per_pixel", c_int),
                ("red_mask", c_ulong), ("green_mask", c_ulong), ("blue_mask", c_ulong)]


def grab_screen():
    """Ganzer Bildschirm (Wurzelfenster, alle Monitore) als (Breite, Hoehe, Bytes) im Format BGRX, Zeilen ohne Luecke –
    oder None (kein libX11, anderes Pixelformat). Eigene, kurze Verbindung: XGetImage dauert bei 4K einige zehn
    Millisekunden, so lange soll die Sperre der Fensterabfragen nicht haengen. Gedacht fuer Bildschirmfotos: schneller
    als ffmpeg mit x11grab (neuer Prozess), damit das Bild vom Moment des Tastendrucks stammt."""
    with _lock:
        if not _open():
            return None
        x = _x
        x.XGetImage.restype = POINTER(_XImage)
        x.XGetImage.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint, c_ulong, c_int]
        x.XDestroyImage.argtypes = [POINTER(_XImage)]
        x.XDefaultScreen.argtypes = [c_void_p]
        x.XDisplayWidth.argtypes = x.XDisplayHeight.argtypes = [c_void_p, c_int]
        x.XCloseDisplay.argtypes = [c_void_p]
    dpy = x.XOpenDisplay(None)
    if not dpy:
        return None
    try:
        scr = x.XDefaultScreen(dpy)
        w, h = x.XDisplayWidth(dpy, scr), x.XDisplayHeight(dpy, scr)
        img = x.XGetImage(dpy, x.XDefaultRootWindow(dpy), 0, 0, w, h, 0xFFFFFFFF, 2)   # AllPlanes, ZPixmap
        if not img:
            return None
        try:
            i = img.contents
            if i.bits_per_pixel != 32 or i.byte_order != 0 or i.red_mask != 0xFF0000 or i.blue_mask != 0xFF:
                return None                                  # nur das uebliche BGRX (LSBFirst, 24/32 Bit)
            stride, row = i.bytes_per_line, i.width * 4
            raw = ctypes.string_at(i.data, stride * i.height)
            if stride != row:
                raw = b"".join(raw[y * stride:y * stride + row] for y in range(i.height))
            return i.width, i.height, raw
        finally:
            x.XDestroyImage(img)
    finally:
        x.XCloseDisplay(dpy)
