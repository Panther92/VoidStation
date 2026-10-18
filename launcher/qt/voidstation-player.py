#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
VoidStation Player
------------------
Eigener Player fuer Fernsehen und eigene Medien (Kachel "Videos & Musik"): Python + Qt 6 (PySide6, QML).
Abgespielt wird mit mpv (libmpv ueber python3-mpv) – alles, was man sieht und bedient, ist VoidStation:
Theme, Sprachen, Gamepad zuerst, Tastatur und Maus gehen auch.

Aufruf (startet der Launcher):
  voidstation-player.py --tv [<sender>]          Fernsehen: Senderliste, Favoriten und EPG kommen vom Launcher
  voidstation-player.py --media [<datei|ordner>] Videos & Musik aus ~/share/Videos, ~/share/Musik, USB-Laufwerken

Darstellungsstufen (VS_PLAYER_LEVEL setzt der Launcher, sonst 0):
  0  Video in der Oberflaeche (libmpv ueber OpenGL, Qt mit EGL), Hardware-Decoding direkt (VA-API, NVDEC)
  1  wie 0, aber Qt mit GLX und Hardware-Decoding mit Kopie (fuer Treiber, mit denen 0 nicht laeuft)
  2  Oberflaeche ohne eingebettetes Video: mpv laeuft als eigenes Vollbildfenster und wird ueber seine
     Steuer-Schnittstelle bedient (Gamepad geht weiter). Von selbst ohne /dev/dri/renderD*, ohne python3-mpv
     oder wenn das Einbetten scheitert (Tests ohne Render-Knoten, z. B. Xvfb: VS_PLAYER_FORCE=1).
Der Launcher stuft nach Abstuerzen hoch (0 -> 1 -> 2, beim Fernsehen zuletzt das nackte mpv wie frueher).

Steuerung von aussen: lokaler Socket ~/.local/share/voidstation/player-<modus>.sock, je Zeile ein JSON-Befehl:
  {"cmd": "tune", "key": "<sender>"}   {"cmd": "open", "path": "<datei|ordner>"}   {"cmd": "quit"}

Test ohne Geraet: VS_API=http://127.0.0.1:8766 VS_SIZE=1280x720 python3 voidstation-player.py --media
"""
import ctypes
import glob
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

T0 = time.monotonic()
HERE = Path(__file__).resolve().parent
BASE = Path(os.environ.get("VS_BASE") or HERE.parent)
MODE = "tv" if "--tv" in sys.argv else "media"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
START_ARG = ARGS[0] if ARGS else ""
SOCK = BASE / f"player-{MODE}.sock"

sys.dont_write_bytecode = True                   # wie die Startseite: kein Bytecode (fester Zeitstempel im Build)


def _early_log(*a):
    print("[player]", *a, file=sys.stderr, flush=True)


def pick_level():
    """Darstellungsstufe vor dem Start von Qt festlegen (siehe oben)."""
    v = os.environ.get("VS_PLAYER_LEVEL", "")
    level = int(v) if v in ("0", "1", "2") else 0
    no_gpu = not glob.glob("/dev/dri/renderD*") and os.environ.get("VS_PLAYER_FORCE") != "1"   # FORCE: nur fuer Tests
    if no_gpu or os.environ.get("VS_QT_SOFTWARE") == "1":
        level = 2
    if level < 2:
        try:
            import mpv  # noqa: F401  (laedt libmpv)
        except (ImportError, OSError) as e:
            _early_log("python3-mpv/libmpv nicht nutzbar, Video im eigenen Fenster:", e)
            level = 2
    return level


LEVEL = pick_level()
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"     # Groessen rechnet die Oberflaeche selbst (wie die Startseite)
os.environ.pop("QT_SCALE_FACTOR", None)
if LEVEL < 2:
    # Video wird im Fenster unter die Oberflaeche gezeichnet: einfacher Renderablauf im Hauptthread – mpv ruft
    # aus eigenen Threads zurueck, so gibt es keine Wartekette zwischen Render-Thread und Python
    os.environ.setdefault("QSG_RENDER_LOOP", "basic")
    if LEVEL == 0 and "QT_XCB_GL_INTEGRATION" not in os.environ:
        try:
            from PySide6.QtCore import QLibraryInfo
            plug = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath)) / "xcbglintegrations"
            if any(plug.glob("libqxcb-egl-integration*")):
                os.environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl"    # VA-API direkt braucht EGL
        except Exception as e:  # noqa: BLE001
            _early_log("EGL-Pruefung:", e)
elif (not glob.glob("/dev/dri/renderD*") and os.environ.get("VS_PLAYER_FORCE") != "1") or os.environ.get("VS_QT_SOFTWARE") == "1":
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

sys.path.insert(0, str(HERE))
import vscommon  # noqa: E402
from vscommon import WEB, Gamepad, PadPump, VsBase, drop_stale_qml_cache, log  # noqa: E402

from PySide6.QtCore import (Property, QObject, Qt, QTimer, QUrl, Signal, Slot)  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication, QOpenGLContext  # noqa: E402
from PySide6.QtNetwork import QLocalServer  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

vscommon.LOG_PREFIX = "player"

# Fehlermeldungen von mpv/ffmpeg -> Grund fuer die Anzeige (player.err.<grund>)
ERR_PATTERNS = [
    (re.compile(r"HTTP error (401|403|451)"), "blocked"),
    (re.compile(r"HTTP error (404|410)"), "gone"),
    (re.compile(r"HTTP error \d{3}"), "failed"),
    (re.compile(r"(?i)timed out|timeout"), "timeout"),
    (re.compile(r"(?i)resolve hostname|name or service not known|temporary failure in name resolution|"
                r"network is unreachable|no route to host"), "offline"),
    (re.compile(r"(?i)connection refused"), "failed"),
    (re.compile(r"(?i)no such file|not found"), "gone"),
]
END_REASON = {0: "eof", 1: "stop", 2: "stop", 3: "quit", 4: "error", 5: "redirect"}
# beobachtete mpv-Eigenschaften -> Schluessel in player.st (fuer QML)
PROPS = {"pause": "paused", "paused-for-cache": "buffering", "playback-time": "position", "duration": "duration",
         "media-title": "title", "idle-active": "idle", "core-idle": "coreIdle", "demuxer-cache-duration": "cache",
         "track-list": "tracks", "aid": "aid", "sid": "sid", "vid": "vid", "video-params": "vparams",
         "estimated-vf-fps": "fps", "video-codec": "codec", "hwdec-current": "hwdec", "frame-drop-count": "dropped",
         "playlist-pos": "plpos", "playlist-count": "plcount", "metadata": "meta", "video-aspect-override": "aspect",
         "panscan": "panscan", "audio-codec-name": "acodec", "audio-bitrate": "abitrate", "audio-params": "aparams",
         "current-ao": "ao"}


def mpv_options(ui_lang="de"):
    """Grundeinstellungen fuer beide Wege (eingebettet und eigenes Fenster)."""
    hw = "auto-copy-safe" if LEVEL == 1 else "auto-safe"
    langs = ",".join(dict.fromkeys([ui_lang.split("-")[0], "en"]))
    return {
        "hwdec": hw, "cache": "yes", "demuxer-max-bytes": "64MiB", "demuxer-readahead-secs": "10",
        "network-timeout": "10", "stream-lavf-o": "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5",
        "keep-open": "no", "idle": "yes", "ytdl": "no", "sub-auto": "fuzzy", "slang": langs, "alang": langs,
        "audio-display": "no", "volume": "100", "volume-max": "130", "input-default-bindings": "no",
        "osc": "no", "osd-level": "0", "save-position-on-quit": "no", "hls-bitrate": "max",
        **({"ao": os.environ["VS_PLAYER_AO"]} if os.environ.get("VS_PLAYER_AO") else {}),   # Tests ohne Tonausgabe: null
    }


def opt_list(opts):
    """Optionen fuer loadfile: key=%Laenge%Wert (Werte duerfen Kommas enthalten, z. B. User-Agents)."""
    return ",".join(f"{k}=%{len(str(v).encode())}%{v}" for k, v in opts.items() if v not in (None, ""))


def classify(text):
    for rx, reason in ERR_PATTERNS:
        if rx.search(text or ""):
            return reason
    return ""


def jsonable(v):
    """mpv-Werte (lazy decoded, bytes) -> einfache Python-Typen fuer QML."""
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, dict):
        return {str(jsonable(k)): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


# ---------------------------------------------------------------------------
#  Wiedergabe: gemeinsame Oberflaeche fuer QML (player.st, Signale, Befehle)
# ---------------------------------------------------------------------------
class Engine(QObject):
    stChanged = Signal()
    ended = Signal(str, str)          # Grund (eof, error, stop, quit), Ursache (timeout, blocked, gone, offline, failed)
    loaded = Signal()                 # Datei geoeffnet
    started = Signal()                # Wiedergabe laeuft wirklich (erstes Bild bzw. erster Ton)
    _upd = Signal(str, "QVariant")
    _evt = Signal(str, str, str)      # Ereignis aus mpv-Threads -> Qt-Thread

    embeddedVideo = False

    def __init__(self):
        super().__init__()
        self._st = {"position": 0, "duration": 0, "paused": False, "buffering": False, "idle": True, "coreIdle": True,
                    "title": "", "cache": 0, "tracks": [], "aid": None, "sid": None, "vid": None, "vw": 0, "vh": 0,
                    "fps": 0, "codec": "", "hwdec": "", "dropped": 0, "plpos": -1, "plcount": 0, "meta": {},
                    "aspect": "", "panscan": 0, "level": LEVEL, "embedded": self.embeddedVideo, "active": False,
                    "acodec": "", "abitrate": 0, "asr": 0, "ach": 0, "ao": ""}
        self.last_err = ""
        self.is_started = False
        self.cur = None               # (url, opts) der laufenden Datei – fuer reload()
        self.lang = "de"
        self._dirty = False
        self._emit_t = QTimer(self)
        self._emit_t.setSingleShot(True)
        self._emit_t.setInterval(120)
        self._emit_t.timeout.connect(self._flush)
        self._upd.connect(self._apply, Qt.QueuedConnection)
        self._evt.connect(self._event, Qt.QueuedConnection)

    def _get_st(self):
        return self._st

    st = Property("QVariantMap", _get_st, notify=stChanged)

    def _get_embedded(self):
        return self.embeddedVideo

    embedded = Property(bool, _get_embedded, constant=True)

    @Slot(str, "QVariant")
    def _apply(self, key, val):
        if key == "vparams":
            d = val if isinstance(val, dict) else {}
            self._set("vw", d.get("dw") or d.get("w") or 0)
            self._set("vh", d.get("dh") or d.get("h") or 0)
            return
        if key == "aparams":                          # Abtastrate und Kanaele der dekodierten Tonspur
            d = val if isinstance(val, dict) else {}
            self._set("asr", d.get("samplerate") or 0)
            self._set("ach", d.get("channel-count") or 0)
            return
        if key == "abitrate":                         # schwankt bei VBR staendig – auf 8 kbit/s runden
            val = int(round((val or 0) / 8000.0)) * 8000
        if key == "tracks":
            val = [{"id": t.get("id"), "type": t.get("type"), "lang": t.get("lang") or "", "title": t.get("title") or "",
                    "codec": t.get("codec") or "", "selected": bool(t.get("selected")), "default": bool(t.get("default")),
                    "external": bool(t.get("external")), "albumart": bool(t.get("albumart"))}
                   for t in (val or []) if isinstance(t, dict)]
        if key == "meta":
            val = {str(k).lower(): v for k, v in (val or {}).items()} if isinstance(val, dict) else {}
        self._set(key, val)
        self._started_check()

    def _set(self, key, val):
        if self._st.get(key) == val:
            return
        self._st[key] = val
        if not self._emit_t.isActive():
            self._emit_t.start()

    def _flush(self):
        self.stChanged.emit()

    def _started_check(self):
        st = self._st
        if self.is_started or not st.get("active"):
            return
        if st.get("position") is not None and (st.get("position") or 0) > 0 and not st.get("coreIdle") \
                and not st.get("buffering"):
            self.is_started = True
            self.started.emit()

    @Slot(str, str, str)
    def _event(self, kind, a, b):
        if kind == "end":
            if a in ("eof", "error", "quit"):
                self._set("active", False)
            if a == "error" and not b and not classify(self.last_err):
                # mpv liefert Log-Meldungen nicht immer vor dem Ende der Datei – kurz auf den Grund warten
                QTimer.singleShot(400, lambda: self._ended(a, b))
                return
            self._ended(a, b)
        elif kind == "loaded":
            self.loaded.emit()
        elif kind == "log":
            self.last_err = a

    def _ended(self, a, b):
        reason = b or (classify(self.last_err) if a == "error" else "")
        if a == "error" and not reason:
            reason = "failed"
        log("Ende:", a, reason, self.last_err[:160] if a == "error" else "")
        self.ended.emit(a, reason)

    def _log_msg(self, level, prefix, text):          # aus mpv-Threads
        text = str(text or "").strip()
        if str(prefix or "").startswith(("ao", "vo", "vd", "ad", "libmpv_render", "osd")):
            return                                    # Ton-/Bildausgabe: kein Grund, warum ein Stream scheitert
        if level in ("error", "warn", "fatal") and text:
            if classify(text):
                self._evt.emit("log", f"{prefix}: {text}", "")

    # ---- Befehle aus QML ----
    def _reset_for_load(self):
        self.last_err = ""
        self.is_started = False
        for k, v in (("position", 0), ("duration", 0), ("buffering", False), ("title", ""), ("tracks", []),
                     ("dropped", 0), ("active", True), ("meta", {}), ("vw", 0), ("vh", 0), ("acodec", ""),
                     ("abitrate", 0), ("asr", 0), ("ach", 0)):
            self._st[k] = v
        self.stChanged.emit()

    @Slot(str, "QVariantMap")
    def play(self, url, opts):
        self.playList([url], 0, opts)

    @Slot("QVariantList", int, "QVariantMap")
    def playList(self, urls, index, opts):
        urls = [str(u) for u in urls or [] if u]
        if not urls:
            return
        opts = {str(k): str(v) for k, v in (opts or {}).items() if v not in (None, "")}
        self.cur = (urls, max(0, min(index, len(urls) - 1)), opts)
        self._reset_for_load()
        self._load(*self.cur)

    @Slot("QVariantMap")
    def reload(self, extra=None):
        if not self.cur:
            return
        urls, idx, opts = self.cur
        opts = dict(opts)
        opts.update({str(k): str(v) for k, v in (extra or {}).items()})
        pos = self._st.get("plpos")
        self.cur = (urls, pos if isinstance(pos, int) and pos >= 0 else idx, opts)
        self._reset_for_load()
        self._load(*self.cur)

    @Slot(str, str)
    def osdText(self, text, ms):
        """Nur im eigenen mpv-Fenster (Stufe 2): kurzer Text von mpv selbst – die QML-Anzeige ist dort verdeckt."""


# ---------------------------------------------------------------------------
#  Stufe 0/1: libmpv im Fenster (Render-API, OpenGL)
# ---------------------------------------------------------------------------
GL_DRAW_FRAMEBUFFER_BINDING = 0x8CA6
GLGETINT = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.POINTER(ctypes.c_int))
GL1U = ctypes.CFUNCTYPE(None, ctypes.c_uint)
GL2U = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_uint)
GLUI = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_int)
GL4B = ctypes.CFUNCTYPE(None, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte)


class GlReset:
    """OpenGL-Zustand vor dem mpv-Bild auf Grundwerte setzen. Qt Quick hinterlaesst nach seinem letzten Bild u. a.
    Tiefentest an (mpv-Bild faellt durch, nur der Hintergrund bleibt) und Sampler-Objekte auf den Textur-Einheiten
    (mpv-Texturen ohne Mipmaps gelten dann als unvollstaendig -> schwarzes Bild bei laufendem Ton). Qt stellt seinen
    Zustand nach endExternalCommands() selbst wieder her."""
    DISABLE = (0x0B71, 0x0C11, 0x0B90, 0x0B44, 0x0BE2, 0x8DB9)   # DEPTH, SCISSOR, STENCIL, CULL, BLEND, FRAMEBUFFER_SRGB
    PIXEL_STORE = ((0x0CF2, 0), (0x0CF3, 0), (0x0CF4, 0), (0x0CF5, 4), (0x806E, 0), (0x806D, 0))  # UNPACK_*

    def __init__(self, ctx, getint):
        def fn(name, proto):
            a = ctx.getProcAddress(name)
            return proto(int(a)) if a else None
        self.disable = fn(b"glDisable", GL1U)
        self.pixel_store = fn(b"glPixelStorei", GLUI)
        self.bind_buffer = fn(b"glBindBuffer", GL2U)
        self.bind_sampler = fn(b"glBindSampler", GL2U)      # erst ab GL 3.3 / GLES 3 – sonst gibt es keine Sampler
        self.active_texture = fn(b"glActiveTexture", GL1U)
        self.color_mask = fn(b"glColorMask", GL4B)
        n = ctypes.c_int(0)
        getint(0x8B4D, ctypes.byref(n))                     # GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS
        self.units = max(8, min(n.value or 16, 32))

    def __call__(self):
        if self.disable:
            for cap in self.DISABLE:
                self.disable(cap)
        if self.pixel_store:
            for name, val in self.PIXEL_STORE:
                self.pixel_store(name, val)
        if self.bind_buffer:
            self.bind_buffer(0x88EC, 0)                     # GL_PIXEL_UNPACK_BUFFER
            self.bind_buffer(0x88EB, 0)                     # GL_PIXEL_PACK_BUFFER
        if self.bind_sampler:
            for unit in range(self.units):
                self.bind_sampler(unit, 0)
        if self.active_texture:
            self.active_texture(0x84C0)                     # GL_TEXTURE0
        if self.color_mask:
            self.color_mask(1, 1, 1, 1)


class EmbeddedEngine(Engine):
    embeddedVideo = True

    def __init__(self, lang):
        super().__init__()
        import mpv
        self.lang = lang
        self.mpvmod = mpv
        opts = {k.replace("-", "_"): v for k, v in mpv_options(lang).items()}
        self.mpv = mpv.MPV(vo="libmpv", log_handler=self._log_msg, loglevel="warn", terminal="no", **opts)
        for name in PROPS:
            self.mpv.observe_property(name, self._prop)
        self.mpv.register_event_callback(self._mpv_event)
        self.render_ready = False
        self.pending = None
        ver = getattr(self.mpv, "mpv_version_tuple", None)
        if not ver:
            m = re.search(r"(\d+)\.(\d+)", str(getattr(self.mpv, "mpv_version", "")))
            ver = (int(m.group(1)), int(m.group(2))) if m else (0, 38)
        self.loadfile_index = tuple(ver[:2]) >= (0, 38)      # ab mpv 0.38: loadfile <url> <flags> <index> <opts>
        log("libmpv", getattr(self.mpv, "mpv_version", "?"), "Stufe", LEVEL)

    def _prop(self, name, value):                         # mpv-Thread
        self._upd.emit(PROPS[name], jsonable(value))

    def _mpv_event(self, ev):                             # mpv-Thread
        try:
            eid = ev.event_id.value
            if eid == self.mpvmod.MpvEventID.END_FILE:
                self._evt.emit("end", END_REASON.get(ev.data.reason, "stop"), "")
            elif eid == self.mpvmod.MpvEventID.FILE_LOADED:
                self._evt.emit("loaded", "", "")
        except Exception as e:  # noqa: BLE001
            log("mpv-Ereignis:", e)

    def set_render_ready(self):
        self.render_ready = True
        if self.pending:
            p, self.pending = self.pending, None
            self._load(*p)

    def _cmd(self, *args):
        try:
            self.mpv.command(*args)
            return True
        except Exception as e:  # noqa: BLE001
            log("mpv-Befehl", args[:2], "fehlgeschlagen:", e)
            return False

    def _load(self, urls, idx, opts):
        if not self.render_ready:                         # ohne Render-Kontext liefe die Datei ohne Bild
            self.pending = (urls, idx, opts)
            return
        o = opt_list(opts)
        for i, u in enumerate(urls):
            flag = "replace" if i == 0 else "append"
            if self.loadfile_index:
                self._cmd("loadfile", u, flag, -1, o)
            else:
                self._cmd("loadfile", u, flag, o)
        if idx > 0:
            self._cmd("set", "playlist-pos", str(idx))

    @Slot()
    def stop(self):
        self.pending = None
        self._set("active", False)
        self._cmd("stop")

    @Slot()
    def togglePause(self):
        self._cmd("cycle", "pause")

    @Slot(bool)
    def setPause(self, on):
        self._cmd("set", "pause", "yes" if on else "no")

    @Slot(float)
    def seek(self, rel):
        self._cmd("seek", rel, "relative")

    @Slot(float)
    def seekTo(self, pos):
        self._cmd("seek", pos, "absolute")

    @Slot(str, "QVariant")
    def setProp(self, name, value):
        if isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, float) and value.is_integer() and name not in ("panscan",):
            value = int(value)
        self._cmd("set", name, str(value))

    @Slot(int)
    def playlistGo(self, i):
        self._cmd("set", "playlist-pos", str(i))

    @Slot("QVariantList")
    def command(self, args):
        self._cmd(*[str(a) for a in args])

    def shutdown(self):
        try:
            self.mpv.terminate()
        except Exception as e:  # noqa: BLE001
            log("mpv beenden:", e)


class Video(QObject):
    """Zeichnet mpv vor der QML-Szene ins Fenster (unter der Oberflaeche); QML liegt darueber (OSD, Menues)."""
    frame = Signal()
    ready = Signal()
    failed = Signal(str)

    def __init__(self, engine, win):
        super().__init__()
        self.engine, self.win = engine, win
        self.ctx, self.dead, self._show = None, False, True
        self._gpa = engine.mpvmod.MpvGlGetProcAddressFn(self._proc_address)
        self.getint = None
        self.gl_reset = None
        self.frame.connect(win.update, Qt.QueuedConnection)
        win.beforeRenderPassRecording.connect(self._render, Qt.DirectConnection)
        win.frameSwapped.connect(self._swapped, Qt.DirectConnection)
        win.sceneGraphAboutToStop.connect(self.release, Qt.DirectConnection)
        win.update()

    @staticmethod
    def _proc_address(_ctx, name):
        c = QOpenGLContext.currentContext()
        a = c.getProcAddress(name) if c is not None else 0
        return int(a) if a else 0

    def _get_show(self):
        return self._show

    def _set_show(self, v):
        self._show = bool(v)
        self.win.update()

    showChanged = Signal()
    show = Property(bool, _get_show, _set_show, notify=showChanged)

    def _render(self):                                    # Render-Durchlauf (Hauptthread, basic loop)
        if self.dead:
            return
        if self.ctx is None:
            try:
                ctx = QOpenGLContext.currentContext()
                if ctx is None:
                    raise RuntimeError("kein OpenGL-Kontext (Qt zeichnet per Software?)")
                self.getint = GLGETINT(int(ctx.getProcAddress(b"glGetIntegerv")))
                self.gl_reset = GlReset(ctx, self.getint)
                self.ctx = self.engine.mpvmod.MpvRenderContext(
                    self.engine.mpv, "opengl", opengl_init_params={"get_proc_address": self._gpa})
                self.ctx.update_cb = self.frame.emit
                log(f"Video im Fenster bereit nach {time.monotonic() - T0:.2f} s "
                    f"({os.environ.get('QT_XCB_GL_INTEGRATION') or 'glx'})")
                QTimer.singleShot(0, self.ready.emit)
            except Exception as e:  # noqa: BLE001
                self.dead = True
                log("Video im Fenster nicht moeglich:", e)
                QTimer.singleShot(0, lambda msg=str(e): self.failed.emit(msg))
                return
        self.ctx.update()
        if not self._show:
            return
        fb = ctypes.c_int(0)
        self.getint(GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(fb))
        r = self.win.effectiveDevicePixelRatio()
        w, h = int(self.win.width() * r), int(self.win.height() * r)
        self.win.beginExternalCommands()
        try:
            self.gl_reset()
            self.ctx.render(flip_y=True, block_for_target_time=False, opengl_fbo={"w": w, "h": h, "fbo": fb.value})
        finally:
            self.win.endExternalCommands()

    def _swapped(self):
        if self.ctx is not None:
            self.ctx.report_swap()

    def release(self):
        if self.ctx is not None:
            try:
                self.ctx.free()
            except Exception as e:  # noqa: BLE001
                log("Render-Kontext freigeben:", e)
            self.ctx = None


# ---------------------------------------------------------------------------
#  Stufe 2: mpv im eigenen Fenster, gesteuert ueber die JSON-Schnittstelle
# ---------------------------------------------------------------------------
class IpcEngine(Engine):
    embeddedVideo = False

    def __init__(self, lang, title):
        super().__init__()
        self.lang = lang
        self.title = title
        self.proc = None
        self.sock = None
        self.lock = threading.Lock()
        self.path = str(BASE / f"player-{MODE}-mpv.sock")
        self.intended_stop = False
        self._front_t, self._front = 0.0, False

    def _spawn(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass
        opts = mpv_options(self.lang)
        opts.update({"input-default-bindings": "yes", "osc": "yes", "osd-level": "1"})   # Maus/Tastatur im mpv-Fenster
        args = ["mpv", "--fs", "--force-window=yes", "--no-terminal", f"--title={self.title}",
                f"--input-ipc-server={self.path}"] + [f"--{k}={v}" for k, v in opts.items()]
        log("mpv im eigenen Fenster:", " ".join(args[:6]))
        # gleiche Sitzung wie der Player: der Launcher ordnet das Fenster so der Kachel zu und beendet beide zusammen
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if self.proc.poll() is not None:
                raise RuntimeError("mpv beendet sich sofort")
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self.path)
                self.sock = s
                break
            except OSError:
                time.sleep(0.1)
        if not self.sock:
            raise RuntimeError("mpv-Steuerung nicht erreichbar")
        self.intended_stop = False
        for i, name in enumerate(PROPS, 1):
            self._send(["observe_property", i, name])
        self._send(["request_log_messages", "warn"])
        threading.Thread(target=self._reader, args=(self.sock, self.proc), daemon=True).start()

    def _send(self, cmd):
        with self.lock:
            if not self.sock:
                return False
            try:
                self.sock.sendall((json.dumps({"command": cmd}) + "\n").encode())
                return True
            except OSError:
                return False

    def _reader(self, sock, proc):
        names = list(PROPS)
        buf = b""
        while True:
            try:
                chunk = sock.recv(65536)
            except OSError:
                chunk = b""
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                ev = msg.get("event")
                if ev == "property-change":
                    i = msg.get("id", 0)
                    if 1 <= i <= len(names):
                        self._upd.emit(PROPS[names[i - 1]], msg.get("data"))
                elif ev == "end-file":
                    self._evt.emit("end", msg.get("reason") or "stop", "")
                elif ev == "file-loaded":
                    self._evt.emit("loaded", "", "")
                elif ev == "log-message":
                    self._log_msg(msg.get("level"), msg.get("prefix"), msg.get("text"))
        if proc is self.proc and not self.intended_stop:  # Fenster geschlossen (q, Alt+F4) = beendet
            self._evt.emit("end", "quit", "")

    def _load(self, urls, idx, opts):
        if not self.proc or self.proc.poll() is not None:
            try:
                self._spawn()
            except (OSError, RuntimeError) as e:
                log("mpv-Start fehlgeschlagen:", e)
                self._evt.emit("end", "error", "failed")
                return
        o = opt_list(opts)
        for i, u in enumerate(urls):
            self._send(["loadfile", u, "replace" if i == 0 else "append", -1, o])   # mpv aus Void: >= 0.38
        if idx > 0:
            self._send(["set_property", "playlist-pos", idx])

    @Slot()
    def stop(self):
        self._set("active", False)
        self.intended_stop = True
        p, self.proc = self.proc, None
        with self.lock:
            s, self.sock = self.sock, None
        if s:
            try:
                s.close()
            except OSError:
                pass
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()

    @Slot()
    def togglePause(self):
        self._send(["cycle", "pause"])

    @Slot(bool)
    def setPause(self, on):
        self._send(["set_property", "pause", bool(on)])

    @Slot(float)
    def seek(self, rel):
        self._send(["seek", rel, "relative"])

    @Slot(float)
    def seekTo(self, pos):
        self._send(["seek", pos, "absolute"])

    @Slot(str, "QVariant")
    def setProp(self, name, value):
        self._send(["set_property", name, value])

    @Slot(int)
    def playlistGo(self, i):
        self._send(["set_property", "playlist-pos", i])

    @Slot("QVariantList")
    def command(self, args):
        self._send([str(a) for a in args])

    @Slot(str, str)
    def osdText(self, text, ms):
        self._send(["show-text", text, int(ms or 3000)])

    def child_in_front(self):
        """Steht das mpv-Fenster vorn? Dann gehoert der Controller dem Player (Abfrage hoechstens alle 0,5 s)."""
        if not self.proc or self.proc.poll() is not None:
            return False
        now = time.monotonic()
        if now - self._front_t < 0.5:
            return self._front
        self._front_t = now
        try:
            r = subprocess.run(["xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True, timeout=1)
            m = re.search(r"0x[0-9a-fA-F]+", r.stdout)
            wid = m.group(0) if m else ""
            pid = 0
            if wid and int(wid, 16):
                r = subprocess.run(["xprop", "-id", wid, "-notype", "_NET_WM_PID"], capture_output=True, text=True, timeout=1)
                m = re.search(r"(\d+)\s*$", r.stdout.strip())
                pid = int(m.group(1)) if m else 0
            self._front = pid == self.proc.pid
        except (OSError, subprocess.SubprocessError, ValueError):
            self._front = False
        return self._front

    def shutdown(self):
        self.stop()


# ---------------------------------------------------------------------------
#  Bruecke zur Oberflaeche
# ---------------------------------------------------------------------------
class Bridge(VsBase):
    remote = Signal("QVariantMap")                # Befehl vom Launcher (Socket)
    engineChanged = Signal()

    def __init__(self):
        super().__init__()
        self._engine = None
        self.app = None

    def _get_engine(self):
        return self._engine

    engine = Property(QObject, _get_engine, notify=engineChanged)

    @Slot("QVariant", str, result=str)
    def fmtTime(self, secs, _unused=""):
        try:
            s = max(0, int(float(secs)))
        except (TypeError, ValueError):
            return "0:00"
        h, m, s = s // 3600, s % 3600 // 60, s % 60
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    PREFS = BASE / "player.json"

    def _prefs(self):
        try:
            d = json.loads(self.PREFS.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    @Slot(str, str, result=str)
    def prefGet(self, key, default):
        v = self._prefs().get(key)
        return str(v) if v is not None else default

    @Slot(str, str)
    def prefSet(self, key, value):
        d = self._prefs()
        d[key] = value
        try:
            tmp = self.PREFS.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.PREFS)
        except OSError as e:
            log("player.json:", e)

    @Slot(str, result=str)
    def fileUrl(self, path):
        return QUrl.fromLocalFile(path).toString()

    @Slot()
    def quit(self):
        QTimer.singleShot(0, QGuiApplication.quit)

    @Slot(str)
    def setTitle(self, t):
        if self.app is not None and self.app.win is not None:
            self.app.win.setTitle(t or "Player")
        if self._engine is not None and isinstance(self._engine, IpcEngine):
            self._engine.title = t or "Player"


class PlayerApp:
    def __init__(self):
        QGuiApplication.setApplicationName("voidstation-player")
        QGuiApplication.setApplicationDisplayName("Player")
        QGuiApplication.setDesktopFileName("voidstation")
        if LEVEL < 2:
            QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGL)
        self.qapp = QGuiApplication(sys.argv)
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")         # libmpv verlangt das (Qt setzt das Locale der Umgebung)
        drop_stale_qml_cache(HERE)
        fams = set(QFontDatabase.families())
        for fam in ("Noto Sans", "DejaVu Sans"):
            if fam in fams:
                f = self.qapp.font()
                f.setFamily(fam)
                self.qapp.setFont(f)
                break
        self.vs = Bridge()
        self.vs.app = self
        self.win = None
        self.video = None
        self.lang = self._lang()
        self.vs.setLang(self.lang)
        self.engine = self._make_engine()
        self.vs._engine = self.engine
        self.pad = Gamepad()
        self.pump = PadPump(self.pad, self._pad_active)
        self.pump.key.connect(self.vs.padKey)
        self.pump.connected.connect(self.vs.padConnected)
        self.server = None

    @staticmethod
    def _lang():
        """Sprache vorab aus den Einstellungen (fuer mpv: bevorzugte Ton- und Untertitelspur)."""
        try:
            import urllib.request
            with urllib.request.urlopen(vscommon.API + "/api/settings", timeout=3) as r:
                return json.loads(r.read().decode()).get("lang") or "de"
        except (OSError, ValueError):
            return "de"

    def _make_engine(self):
        global LEVEL
        if LEVEL < 2:
            try:
                return EmbeddedEngine(self.lang)
            except Exception as e:  # noqa: BLE001
                log("libmpv-Start fehlgeschlagen, Video im eigenen Fenster:", e)
                LEVEL = 2
        return IpcEngine(self.lang, "Player")

    def _pad_active(self):
        if QGuiApplication.focusWindow() is not None:
            return True
        return isinstance(self.engine, IpcEngine) and self.engine.child_in_front()

    def _fallback(self, why):
        """Einbetten scheitert (z. B. Render-Kontext): weiter mit mpv im eigenen Fenster, Oberflaeche bleibt."""
        global LEVEL
        log("Wechsel auf Stufe 2:", why)
        old = self.engine
        LEVEL = 2
        cur = old.cur
        try:
            old.shutdown()
        except Exception:  # noqa: BLE001
            pass
        self.engine = IpcEngine(self.lang, self.win.title() if self.win else "Player")
        self.vs._engine = self.engine
        self.vs.engineChanged.emit()
        if self.video:
            self.video.dead = True
        if cur:
            self.engine.playList(*cur)

    def _serve(self):
        try:
            SOCK.unlink()
        except OSError:
            pass
        self.server = QLocalServer()
        if not self.server.listen(str(SOCK)):
            log("Steuer-Socket nicht moeglich:", self.server.errorString())
            return
        self.server.newConnection.connect(self._client)

    def _client(self):
        while self.server.hasPendingConnections():
            c = self.server.nextPendingConnection()
            buf = {"b": b""}

            def read(c=c, buf=buf):
                buf["b"] += bytes(c.readAll().data())
                while b"\n" in buf["b"]:
                    line, buf["b"] = buf["b"].split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(msg, dict):
                        log("Befehl:", msg.get("cmd"))
                        if msg.get("cmd") == "quit":
                            QTimer.singleShot(0, self.qapp.quit)
                        else:
                            self.vs.remote.emit(msg)
                c.write(b'{"ok":true}\n')
                c.flush()
            c.readyRead.connect(read)
            c.disconnected.connect(c.deleteLater)

    def run(self):
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(HERE / "qml"))
        ctx = engine.rootContext()
        ctx.setContextProperty("vs", self.vs)
        ctx.setContextProperty("vsTitle", "Player")
        ctx.setContextProperty("vsApi", vscommon.API)
        ctx.setContextProperty("vsMode", MODE)
        ctx.setContextProperty("vsArg", START_ARG)
        ctx.setContextProperty("vsLogo", QUrl.fromLocalFile(str(WEB / "logo.png")).toString())
        size = os.environ.get("VS_SIZE", "")
        w, _, h = size.partition("x")
        ctx.setContextProperty("vsW", int(w) if w.isdigit() else 0)
        ctx.setContextProperty("vsH", int(h) if h.isdigit() else 0)
        engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Player.qml")))
        if not engine.rootObjects():
            log("QML konnte nicht geladen werden")
            return 1
        self.win = engine.rootObjects()[0]
        if isinstance(self.engine, EmbeddedEngine):
            self.video = Video(self.engine, self.win)
            self.video.ready.connect(self.engine.set_render_ready)
            self.video.failed.connect(self._fallback)
            self.win.setProperty("videoItem", self.video)
        self._serve()
        self.qapp.aboutToQuit.connect(self._shutdown)
        log(f"Player ({MODE}) bereit nach {time.monotonic() - T0:.2f} s, Stufe {LEVEL}")
        self._test_hooks()
        return self.qapp.exec()

    def _shutdown(self):
        try:
            self.engine.stop()
        except Exception:  # noqa: BLE001
            pass
        if self.video is not None and self.win is not None:
            self.win.hide()                               # Szenengraph stoppt -> Render-Kontext wird freigegeben
            self.video.release()
        try:
            self.engine.shutdown()
        except Exception:  # noqa: BLE001
            pass
        if self.server is not None:
            self.server.close()
        try:
            SOCK.unlink()
        except OSError:
            pass

    def _test_hooks(self):
        """Nur fuer Tests: VS_KEYS="a,w,down,shot:datei.png" (w = kurz warten), VS_SCREENSHOT=datei.png zum Schluss."""
        steps = [k for k in os.environ.get("VS_KEYS", "").split(",") if k]
        shot = os.environ.get("VS_SCREENSHOT")
        if not (steps or shot):
            return
        gap = int(os.environ.get("VS_KEYS_GAP", "450"))
        t = int(os.environ.get("VS_SCREENSHOT_DELAY", "2500"))
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        def target():                                     # ohne Fenstermanager (Xvfb) ist das Fenster nie aktiv
            self.win.requestActivate()
            fi = self.win.activeFocusItem()
            kids = self.win.contentItem().childItems()
            return fi or (kids[0] if kids else self.win.contentItem())

        def typed(text):                                  # t:Text – echte Tastatur (z. B. in die Bildschirmtastatur)
            for ch in text:
                for typ in (QEvent.KeyPress, QEvent.KeyRelease):
                    QGuiApplication.sendEvent(target(), QKeyEvent(typ, 0, Qt.NoModifier, ch))

        def keyed(name):                                  # k:Return, k:Escape …
            key = getattr(Qt, "Key_" + name)
            for typ in (QEvent.KeyPress, QEvent.KeyRelease):
                QGuiApplication.sendEvent(target(), QKeyEvent(typ, key, Qt.NoModifier))
        for k in steps:
            if k.startswith("t:"):
                QTimer.singleShot(t, lambda x=k[2:]: typed(x))
            elif k.startswith("k:"):
                QTimer.singleShot(t, lambda x=k[2:]: keyed(x))
            elif k.startswith("shot:"):
                QTimer.singleShot(t, lambda f=k[5:]: self.win.grabWindow().save(f))
            elif k.startswith("remote:"):
                QTimer.singleShot(t, lambda m=k[7:]: self.vs.remote.emit(json.loads(m)))
            elif k != "w":
                QTimer.singleShot(t, lambda k=k: self.vs.padKey.emit(k))
            t += gap
        QTimer.singleShot(t + 600, lambda: (self.win.grabWindow().save(shot) if shot else None, self.qapp.quit()))


def main():
    # schon ein Player in diesem Modus? Dann nur den Auftrag weitergeben (der Launcher holt das Fenster nach vorn)
    if SOCK.exists():
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(str(SOCK))
            msg = {"cmd": "tune", "key": START_ARG} if MODE == "tv" else {"cmd": "open", "path": START_ARG}
            s.sendall((json.dumps(msg) + "\n").encode())
            s.close()
            _early_log("Player laeuft schon, Auftrag weitergegeben")
            return 0
        except OSError:
            pass
    return PlayerApp().run()


if __name__ == "__main__":
    sys.exit(main())
