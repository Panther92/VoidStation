# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenster verwalten ueber libX11 (ctypes) statt ueber wmctrl und xprop.

Eine Abfrage dauert so unter 0,1 ms statt rund 2,5 ms samt neuem Prozess; das zaehlt vor allem bei der Controller-Maus,
die viermal pro Sekunde nach dem aktiven Fenster fragt. Die Aufrufe entsprechen dem, was wmctrl an den Fenstermanager
schickt (EWMH). Fehlt libX11 oder laesst sich das Display nicht oeffnen, laufen die alten Befehle weiter.

Fenster-Kennungen: Rueckgaben wie bei wmctrl als Text ("0x01a00003"), Aufrufe nehmen Text oder Zahl.
Alle Zugriffe laufen unter einer Sperre ueber eine eigene Verbindung, XInitThreads ist deshalb nicht noetig."""
import ctypes
import re
import subprocess
import threading
from ctypes import POINTER, Structure, Union, byref, c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p

_lock = threading.RLock()
_x = None
_dpy = None
_root = 0
_tried = False
_atoms = {}
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
_grabbed = {}


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
