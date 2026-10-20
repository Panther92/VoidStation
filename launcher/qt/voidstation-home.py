#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
VoidStation Home (Qt)
---------------------
Startseite als natives Programm: Python + Qt 6 (PySide6, QML). Ersetzt die WebKit-Shell fuer
die Kacheloberflaeche; der Installer im Live-System bleibt vorerst die Web-Oberflaeche.

Aufgaben dieses Programms (alles andere steht in qml/):
  * Fenster im Vollbild, Fenstertitel "VoidStation" (danach sucht der Launcher)
  * Verbindung zum Launcher (http://127.0.0.1:8765, dieselbe API wie die Web-Oberflaeche)
  * Texte aus web/i18n/*.json und Farben aus web/themes/*.css – eine Quelle fuer beide Oberflaechen
  * Gamepad ueber evdev (python3-evdev), Symbole als SVG
  * Controller als Maus in Programmen (uinput): rechter Stick Zeiger, R2/L2 Klicks, linker Stick scrollt, R3 umschalten

Darstellung: Qt Quick zeichnet mit OpenGL direkt auf der Grafikkarte (auch mit dem NVIDIA-Treiber).
Ohne Render-Schnittstelle (/dev/dri/renderD*) oder mit VS_QT_SOFTWARE=1 zeichnet Qt per Software.
Test ohne Geraet: VS_API=http://127.0.0.1:8766 python3 voidstation-home.py  (z. B. mit tools/qt-preview.py)
"""
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

T0 = time.monotonic()
HERE = Path(__file__).resolve().parent
WEB = Path(os.environ.get("VS_WEB") or HERE.parent / "web")
API = os.environ.get("VS_API", "http://127.0.0.1:8765").rstrip("/")
TITLE = "VoidStation"                     # muss zum Fenstertitel passen, den der Launcher sucht

if not glob.glob("/dev/dri/renderD*") or os.environ.get("VS_QT_SOFTWARE") == "1":
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
# 1 Pixel = 1 Bildpunkt: Groessen rechnet die Oberflaeche selbst (Skalierung × Bildschirmhoehe), Xft.dpi
# (vom Launcher fuer andere Programme gesetzt) wuerde sonst alles ein zweites Mal vergroessern
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ.pop("QT_SCALE_FACTOR", None)

# Updates packen alle Dateien mit festem Zeitstempel (reproduzierbarer Build: tar --mtime). Python prueft
# seinen Bytecode nur gegen Zeitstempel und Groesse – darum fuer icons.py & Co. keinen Bytecode, alte weg.
import shutil  # noqa: E402

sys.dont_write_bytecode = True
shutil.rmtree(HERE / "__pycache__", ignore_errors=True)
sys.path.insert(0, str(HERE))
import vscommon  # noqa: E402
from vscommon import Gamepad, PadPump, VsBase, drop_stale_qml_cache, PADMOUSE_NAME  # noqa: E402,F401

from PySide6.QtCore import (QTimer, QUrl, Signal, Slot)  # noqa: E402
from PySide6.QtGui import QCursor, QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401  (macht Fenster aus QML zu QQuickWindow)


vscommon.LOG_PREFIX = "home"
log = vscommon.log


# ---------------------------------------------------------------------------
#  Controller als Maus
# ---------------------------------------------------------------------------
class PadMouse:
    """Controller als Maus, solange ein Programm vorn ist (nicht die Startseite): rechter Stick bewegt den Zeiger
    (je weiter, desto schneller), R2 = Linksklick (halten zieht), L2 = Rechtsklick, linker Stick hoch/runter
    scrollt, R3 schaltet fuer das Programm um. Von selbst an oder aus je nach Kachel (/api/front: "mouse"; Spiele
    und Emulatoren aus), ganz aus mit Einstellungen -> System ("padmouse"). Virtuelle Maus ueber /dev/uinput
    (Gruppe input, sysfix.sh) – kein eigenes Programm, kein Dienst. Laeuft in einem eigenen Thread mit 100 Hz,
    fragt Fenstermanager und Launcher aber nur, waehrend am Controller etwas passiert."""
    NAME = PADMOUSE_NAME
    DEAD = 0.20                    # Totzone der Sticks (driftende Sticks bewegen nichts)
    SCROLL_DEAD = 0.35

    def __init__(self, pad, notify):
        self.pad, self.notify = pad, notify     # notify(an: bool) – Hinweis ueber dem Programm (R3)
        self.home_wins = set()     # Fenster der Startseite (setzt der Qt-Thread)
        self.screen_w = 1920       # Breite des Bildschirms (setzt der Qt-Thread), bestimmt die Geschwindigkeit
        self.ui = None
        self.broken = False
        self.override = {}         # Kachel (bzw. Fenster) -> per R3 gewaehlt, gilt bis zum Neustart der Startseite
        self.act, self.act_t = None, 0.0
        self.front, self.front_for, self.front_t = None, None, 0.0
        self.r3_prev = False
        self.last_on = True
        self.btn = {"left": False, "right": False}
        self.acc = [0.0, 0.0, 0.0]               # Reste fuer x, y, Rad (ganze Schritte gehen raus)
        try:
            import evdev  # noqa: F401
        except ImportError:
            return
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def active_window():
        try:
            r = subprocess.run(["xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW"],
                               capture_output=True, text=True, timeout=2)
            m = re.search(r"0x[0-9a-fA-F]+", r.stdout)
            return int(m.group(0), 16) if m else 0
        except (OSError, subprocess.SubprocessError):
            return 0

    @staticmethod
    def fetch_front():
        try:
            with urllib.request.urlopen(API + "/api/front", timeout=3) as r:
                return json.loads(r.read().decode())
        except (OSError, ValueError):
            return None

    def decide(self, now):
        """(Schluessel, an) fuer das Programm vorn, None = Startseite vorn bzw. Controller-Maus ganz aus."""
        if now - self.act_t > (0.25 if self.last_on else 1.5):    # im Spiel (aus) seltener nachsehen
            self.act, self.act_t = self.active_window(), now
        if not self.act or self.act in self.home_wins:
            return None
        if self.front_for != self.act or now - self.front_t > 5:
            self.front, self.front_for, self.front_t = self.fetch_front(), self.act, now
        f = self.front or {}
        if f.get("padmouse") is False:
            return None
        key = f.get("id") or ("win", self.act)
        self.last_on = self.override.get(key, f.get("mouse", True) is not False)
        return key, self.last_on

    def _device(self):
        if self.ui is None and not self.broken:
            from evdev import UInput, ecodes as E
            try:
                self.ui = UInput({E.EV_KEY: [E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE],
                                  E.EV_REL: [E.REL_X, E.REL_Y, E.REL_WHEEL]}, name=self.NAME)
                log("Controller-Maus bereit")
            except OSError as e:
                self.broken = True
                log("Controller-Maus nicht moeglich (/dev/uinput):", e)
        return self.ui

    def _buttons(self, left, right):
        from evdev import ecodes as E
        changed = False
        for name, want, code in (("left", left, E.BTN_LEFT), ("right", right, E.BTN_RIGHT)):
            if self.btn[name] != want:
                self.btn[name] = want
                if self.ui:
                    self.ui.write(E.EV_KEY, code, 1 if want else 0)
                    changed = True
        return changed

    def release(self):
        if self._buttons(False, False):
            self.ui.syn()
        self.acc = [0.0, 0.0, 0.0]

    def step(self, st, now, dt):
        """Ein Takt: Zustand der Sticks/Tasten -> Mausereignisse. Rueckgabe: ob etwas geschrieben wurde."""
        from evdev import ecodes as E
        busy = (abs(st["rx"]) > self.DEAD or abs(st["ry"]) > self.DEAD or abs(st["ly"]) > self.SCROLL_DEAD
                or st["r3"] or st["lt"] or st["rt"] or any(self.btn.values()))
        if not busy:
            self.r3_prev = False
            self.act_t = 0.0                          # nach einer Pause zuerst nachsehen, was vorn ist
            return False
        d = self.decide(now)
        if d is None:
            self.release()
            self.r3_prev = st["r3"]
            return False
        key, on = d
        if st["r3"] and not self.r3_prev:
            on = not on
            self.override[key] = on
            log("Controller-Maus", "an" if on else "aus", "fuer", key)
            self.notify(on)
        self.r3_prev = st["r3"]
        if not on or not self._device():
            self.release()
            return False
        vmax = self.screen_w * 1.1                    # Pixel je Sekunde bei vollem Ausschlag
        wrote = False
        for i, axis, code in ((0, "rx", E.REL_X), (1, "ry", E.REL_Y)):
            n = st[axis]
            if abs(n) <= self.DEAD:
                self.acc[i] = 0.0
                continue
            v = (abs(n) - self.DEAD) / (1 - self.DEAD)
            self.acc[i] += (1 if n > 0 else -1) * vmax * v * v * dt
            step = int(self.acc[i])
            if step:
                self.acc[i] -= step
                self.ui.write(E.EV_REL, code, step)
                wrote = True
        n = st["ly"]
        if abs(n) > self.SCROLL_DEAD:                 # Stick hoch = nach oben scrollen, 4 bis 16 Raststufen/s
            v = (abs(n) - self.SCROLL_DEAD) / (1 - self.SCROLL_DEAD)
            self.acc[2] += (-1 if n > 0 else 1) * (4 + 12 * v * v) * dt
            step = int(self.acc[2])
            if step:
                self.acc[2] -= step
                self.ui.write(E.EV_REL, E.REL_WHEEL, step)
                wrote = True
        else:
            self.acc[2] = 0.0
        wrote = self._buttons(st["rt"], st["lt"]) or wrote
        if wrote:
            self.ui.syn()
        return wrote

    def _run(self):
        last = time.monotonic()
        while True:
            time.sleep(0.01)
            now = time.monotonic()
            dt, last = min(now - last, 0.05), now
            try:
                self.step(self.pad.mouse_state(), now, dt)
            except Exception as e:  # noqa: BLE001  – die Startseite darf daran nicht haengen
                log("Controller-Maus:", e)
                time.sleep(1)


# ---------------------------------------------------------------------------
#  Verbindung zur Oberflaeche
# ---------------------------------------------------------------------------
class Vs(VsBase):
    """Bruecke der Startseite: dazu Controller-Maus-Hinweis, heisse Ecke, Zeitzonen (Installer), Neustart."""
    padMouse = Signal(bool)                     # Controller-Maus per R3 an/aus (Hinweis ueber dem Programm)

    @Slot(str, result=str)
    def tzTime(self, tz):
        """Uhrzeit in einer Zeitzone (fuer die Auswahl im Installer), im Format der Sprache."""
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            t = datetime.now(ZoneInfo(tz))
        except Exception:  # noqa: BLE001
            return ""
        if self._lang == "de":
            return t.strftime("%H:%M")
        return t.strftime("%I:%M %p").lstrip("0")

    @Slot(str, result=bool)
    def padDown(self, key):
        """Wird diese Gamepad-Taste gerade gehalten? (Installieren: A halten)"""
        return self.pad is not None and key in self.pad.pressed()

    @Slot(result=bool)
    def homeInFront(self):
        """Steht laut Fenstermanager (_NET_ACTIVE_WINDOW) ein Fenster der Startseite vorn? Qt haelt sich auf manchen
        Geraeten weiter fuer aktiv, obwohl ein Programm vorn ist (NiPoGi, FreeTube als Flatpak: Fokus ueber
        WM_TAKE_FOCUS) – die heisse Ecke fragt darum im Zweifel den X-Server. Nur bei Zeiger in der Ecke."""
        try:
            r = subprocess.run(["xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW"],
                               capture_output=True, text=True, timeout=2)
            m = re.search(r"0x[0-9a-fA-F]+", r.stdout)
            act = int(m.group(0), 16) if m else 0
        except (OSError, subprocess.SubprocessError):
            return True                                  # unklar: lieber kein Feld ueber der Startseite
        if not act:
            return True
        return act in {int(w.winId()) for w in QGuiApplication.topLevelWindows()}

    @Slot(result="QVariantList")
    def cornerHit(self):
        """Heisse Ecke: Steht der Mauszeiger unten rechts auf einem Bildschirm? Dann [rechte Kante, untere
        Kante] dieses Bildschirms, sonst []. Fragt die Position beim X-Server ab, geht also auch, wenn ein
        anderes Programm vorn ist.

        Getroffen ist die Ecke, wenn der Zeiger
          - am unteren Rand liegt und nicht weiter als `reach` von der rechten Kante weg ist, oder
          - am rechten Rand liegt und nicht weiter als `reach` von der unteren Kante weg ist, oder
          - in einem kleinen Quadrat (`core`) direkt in der Ecke steht.
        Am Rand bleibt der Zeiger von selbst haengen – man muss also nur grob nach unten rechts schieben, nicht
        genau das letzte Pixel treffen. Die Streifen liegen nur auf der aeussersten Pixelreihe (`edge`), dort
        liegen keine Player-Knoepfe (Vollbild & Co. sitzen ein Stueck vom Rand weg); das Quadrat bleibt
        deshalb klein. Alle Masse haengen an der kurzen Bildschirmseite (720p, 1080p und 4K gleich gross
        empfunden). VS_CORNER=<Prozent> aendert `reach` (Standard 12 % der kurzen Seite, 0 = nur das Quadrat)."""
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos)
        if scr is None:
            return []
        g = scr.geometry()
        short = max(1, min(g.width(), g.height()))
        try:
            pct = float(os.environ.get("VS_CORNER", "12"))
        except ValueError:
            pct = 12.0
        reach = short * max(0.0, min(pct, 50.0)) / 100      # 720p: 86 px · 1080p: 130 px · 2160p: 259 px
        edge = max(2, round(short * 0.004))                  # 720p: 3 px · 1080p: 4 px · 2160p: 9 px
        core = max(edge, round(short * 0.015))               # 720p: 11 px · 1080p: 16 px · 2160p: 32 px
        dx = g.right() - pos.x()                             # Abstand zur rechten Kante (0 = letztes Pixel)
        dy = g.bottom() - pos.y()                            # Abstand zur unteren Kante
        if dx < 0 or dy < 0:
            return []
        if (dx < core and dy < core) or (dy < edge and dx <= reach) or (dx < edge and dy <= reach):
            return [g.right(), g.bottom()]
        return []

    @Slot(result="QVariantList")
    def cursorScreen(self):
        """[x, y, Breite, Hoehe] des Bildschirms, auf dem der Mauszeiger steht (Hinweise ueber Programmen)."""
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        return [g.x(), g.y(), g.width(), g.height()]

    @Slot()
    def restart(self):
        """Neu starten (z. B. nach Sprachwechsel), home.sh wuerde es sonst auch tun."""
        os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    QGuiApplication.setApplicationName("voidstation")
    QGuiApplication.setApplicationDisplayName(TITLE)
    QGuiApplication.setDesktopFileName("voidstation")
    app = QGuiApplication(sys.argv)
    drop_stale_qml_cache()                       # vor dem ersten Laden von QML
    families = set(QFontDatabase.families())
    for fam in ("Noto Sans", "DejaVu Sans"):
        if fam in families:
            f = app.font()
            f.setFamily(fam)
            app.setFont(f)
            break
    vs = Vs()
    vs.pad = Gamepad()
    pump = PadPump(vs.pad)
    pump.key.connect(vs.padKey)
    pump.connected.connect(vs.padConnected)
    vs.mouse = PadMouse(vs.pad, vs.padMouse.emit)

    def mouse_info():                            # Fenster der Startseite + Bildschirmbreite fuer die Controller-Maus
        vs.mouse.home_wins = {int(w.winId()) for w in QGuiApplication.topLevelWindows()}
        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            vs.mouse.screen_w = scr.geometry().width()
    mouse_timer = QTimer()
    mouse_timer.timeout.connect(mouse_info)
    mouse_timer.start(1000)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(HERE / "qml"))
    engine.rootContext().setContextProperty("vs", vs)
    engine.rootContext().setContextProperty("vsTitle", TITLE)
    engine.rootContext().setContextProperty("vsApi", API)
    engine.rootContext().setContextProperty("vsLogo", QUrl.fromLocalFile(str(WEB / "logo.png")).toString())
    engine.rootContext().setContextProperty("vsDemo", os.environ.get("VS_DEMO") == "1")
    size = os.environ.get("VS_SIZE", "")                 # Tests: z. B. 1920x1080 (sonst ganzer Bildschirm)
    w, _, h = size.partition("x")
    engine.rootContext().setContextProperty("vsW", int(w) if w.isdigit() else 0)
    engine.rootContext().setContextProperty("vsH", int(h) if h.isdigit() else 0)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        log("QML konnte nicht geladen werden")
        sys.exit(1)
    log(f"Startseite bereit nach {time.monotonic() - T0:.2f} s ({os.environ.get('QT_QUICK_BACKEND') or 'GPU'})")
    # Nur fuer Tests (tools/qt-preview.py): Gamepad-Druecke abspielen, Bildschirmfotos speichern
    #   VS_KEYS="right,right,a,shot:radio.png,b"  (w = kurz warten), VS_SCREENSHOT=datei.png zum Schluss
    steps = [k for k in os.environ.get("VS_KEYS", "").split(",") if k]
    shot = os.environ.get("VS_SCREENSHOT")
    if steps or shot:
        win = engine.rootObjects()[0]
        gap = int(os.environ.get("VS_KEYS_GAP", "450"))
        t = int(os.environ.get("VS_SCREENSHOT_DELAY", "2500"))
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        def press(name):                                  # k:Return, k:Escape, k:Left …, t:Text, c:x:y (Mausklick)
            if name.startswith("m:"):                     # m:x:y – Maus nur bewegen
                from PySide6.QtCore import QPointF
                from PySide6.QtGui import QMouseEvent
                pos = QPointF(*(float(v) for v in name[2:].split(":")))
                QGuiApplication.sendEvent(win, QMouseEvent(QEvent.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
                return
            if name.startswith("c:"):
                from PySide6.QtCore import QPointF
                from PySide6.QtGui import QMouseEvent
                pos = QPointF(*(float(v) for v in name[2:].split(":")))
                for typ in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                    btn = Qt.NoButton if typ == QEvent.MouseMove else Qt.LeftButton
                    QGuiApplication.sendEvent(win, QMouseEvent(typ, pos, pos, btn, Qt.LeftButton if typ == QEvent.MouseButtonPress else Qt.NoButton, Qt.NoModifier))
                return
            if name.startswith("t:"):
                for ch in name[2:]:
                    for typ in (QEvent.KeyPress, QEvent.KeyRelease):
                        QGuiApplication.sendEvent(win, QKeyEvent(typ, 0, Qt.NoModifier, ch))
                return
            if name.startswith(("kd:", "ku:")):                  # Taste nur druecken / nur loslassen (halten)
                key = getattr(Qt, "Key_" + name[3:])
                QGuiApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress if name[1] == "d" else QEvent.KeyRelease, key, Qt.NoModifier))
                return
            key = getattr(Qt, "Key_" + name[2:])
            for typ in (QEvent.KeyPress, QEvent.KeyRelease):
                QGuiApplication.sendEvent(win, QKeyEvent(typ, key, Qt.NoModifier))
        for k in steps:
            if k.startswith(("k:", "t:", "c:", "m:", "kd:", "ku:")):
                QTimer.singleShot(t, lambda k=k: press(k))
            elif k.startswith("shot:"):
                QTimer.singleShot(t, lambda f=k[5:]: win.grabWindow().save(f))
            elif k != "w":
                QTimer.singleShot(t, lambda k=k: vs.padKey.emit(k))
            t += gap
        if shot:
            QTimer.singleShot(t + 600, lambda: (win.grabWindow().save(shot), app.quit()))
        else:
            QTimer.singleShot(t + 600, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
