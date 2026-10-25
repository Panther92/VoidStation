#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
VoidStation Launcher
-----------------
Kleiner lokaler Dienst fuer die Kacheloberflaeche:
  * liefert die Startseite (web/, tiles.json) aus
  * startet Programme aus tiles.json (nur diese, keine freien Befehle)
  * mehrere Programme parallel; erneutes Oeffnen holt ein laufendes nach vorn
  * "Home" holt die Startseite nach vorn, ohne etwas zu beenden
  * Radio im Hintergrund (mpv), Sendersuche ueber radio-browser.info, Favoriten
  * Lautstaerke (wpctl)
  * optional: Guide-/Home-Taste am Gamepad (python3-evdev)
  * Bluetooth: BlueZ ueber D-Bus mit eigenem Kopplungs-Agenten (python3-gobject)

Lauscht ausschliesslich auf 127.0.0.1.
"""

import csv
import datetime
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape as html_unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("VOIDSTATION_PORT", "8765"))
BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
CONFIG = Path(os.environ.get("VOIDSTATION_CONFIG", BASE / "tiles.json"))
FAVS = BASE / "radio.json"
MPV_SOCK = str(BASE / "mpv.sock")
PLAYER_BIN = BASE / "qt" / "voidstation-player.py"    # eigener Player: Fernsehen, Videos & Musik
HOME_TITLE = "VoidStation"                      # <title> der Startseite
PAUSED_FILE = BASE / "paused.json"              # im Hintergrund angehaltene Prozesse (beim Launcher-Start fortsetzen)
RADIO_SERVERS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info",
                 "fi1.api.radio-browser.info", "at1.api.radio-browser.info"]

MIME = {
    ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml", ".webp": "image/webp",
}
POWER = {
    "poweroff": ["sudo", "-n", "/usr/bin/poweroff"],
    "reboot": ["sudo", "-n", "/usr/bin/reboot"],
    "suspend": ["sudo", "-n", "/usr/local/sbin/voidstation-pkg", "suspend"],
}


def log(*a):
    print("[voidstation]", *a, file=sys.stderr, flush=True)


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def find_tile(tile_id):
    for group in load_config().get("groups", []):
        for tile in group.get("tiles", []):
            if tile.get("id") == tile_id:
                return tile
    return None


def expand(args):
    return [os.path.expandvars(os.path.expanduser(a)) for a in args]


def run(args, timeout=5, **kw):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kw)
    except (OSError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
#  Fenster (wmctrl)
# ---------------------------------------------------------------------------
def windows():
    """Liste (id, pid, titel) aller Fenster."""
    r = run(["wmctrl", "-lp"])
    out = []
    if r and r.returncode == 0:
        for row in r.stdout.splitlines():
            parts = row.split(None, 4)
            if len(parts) >= 3 and parts[2].isdigit():
                out.append((parts[0], int(parts[2]), parts[4] if len(parts) > 4 else ""))
    return out


def session_pids(sid):
    r = run(["ps", "-e", "-o", "pid=,sid="])
    pids = set()
    if r:
        for row in r.stdout.strip().splitlines():
            p = row.split()
            if len(p) == 2 and p[1] == str(sid):
                pids.add(int(p[0]))
    return pids or {sid}


def active_window():
    """Kennung des aktiven Fensters (_NET_ACTIVE_WINDOW) oder None."""
    r = run(["xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW"])
    m = re.search(r"0x[0-9a-fA-F]+", r.stdout) if r and r.returncode == 0 else None
    wid = int(m.group(0), 16) if m else 0
    return wid or None


def media_notify(cmd):
    """Laufendem Player "Videos & Musik" bzw. "YouTube Light" Bescheid geben (ohne zu warten): "background" =
    Startseite oder anderes Programm kommt nach vorn (Videos halten an, Musik laeuft weiter), "pause" = Radio startet."""
    try:
        for tid, mode in (("media", "media"), ("ytlight", "yt")):
            if APPS._get(tid):
                threading.Thread(target=PLAYERS.send, args=(mode, {"cmd": cmd}), daemon=True).start()
    except NameError:                                   # beim Start, bevor es APPS/PLAYERS gibt
        pass


def raise_home():
    media_notify("background")
    try:
        APPS.pause_background()                         # Emulatoren anhalten, solange die Startseite vorn ist
    except NameError:
        pass
    for wid, _pid, title in windows():
        if HOME_TITLE in title:
            run(["wmctrl", "-i", "-a", wid])
            return True
    return False


# ---------------------------------------------------------------------------
#  Programme
# ---------------------------------------------------------------------------
class AppManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.procs = {}                       # tile_id -> Popen
        self.shown = set()                    # tile_ids, deren Programm schon ein Fenster hat
        self.recent = []                      # tile_ids, zuletzt gestartet / nach vorn geholt (neueste hinten)
        self.claimed = {}                     # tile_id -> Fenster-IDs ohne passende Prozess-ID (Flatpak), beim Start zugeordnet
        self.paused = {}                      # tile_id -> Prozess-IDs, die im Hintergrund angehalten sind (SIGSTOP)
        self._pwatch = False                  # Waechter fuer angehaltene Programme laeuft
        self.kinds = {}                       # tile_id -> Programm (z. B. "mgba-qt"), fuer die Vollbild-Taste

    def running(self):
        with self.lock:
            for tid in [t for t, p in self.procs.items() if p.poll() is not None]:
                del self.procs[tid]
                self.shown.discard(tid)
                self.claimed.pop(tid, None)
                self.paused.pop(tid, None)
            return list(self.procs)

    # ---- Im Hintergrund anhalten (Emulatoren) -------------------------------------------------------------
    # Emulatoren lesen den Controller auch ohne Fokus weiter: Ist die Startseite vorn, spielte das Spiel mit
    # jedem Tastendruck mit. Deshalb halten sie an (SIGSTOP, wie Pause), sobald etwas anderes nach vorn kommt,
    # und laufen weiter (SIGCONT), wenn ihr Fenster wieder vorn ist – ueber die Kachel, die heisse Ecke oder
    # sonstwie (Waechter). Die Prozess-IDs stehen in PAUSED_FILE, damit ein neu gestarteter Launcher nichts
    # angehalten zuruecklaesst.
    def _persist_paused(self):
        with self.lock:
            pids = sorted({p for ps in self.paused.values() for p in ps})
        try:
            if pids:
                PAUSED_FILE.write_text(json.dumps(pids), encoding="utf-8")
            else:
                PAUSED_FILE.unlink(missing_ok=True)
        except OSError as e:
            log("paused.json:", e)

    @staticmethod
    def _kill_all(pids, sig):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def pause_background(self, keep=None):
        """Laufende Emulatoren anhalten, ausser `keep` (die Kachel, die gerade nach vorn kommt). Nur Programme, die
        schon ein Fenster zeigen – ein Emulator, der noch startet, bliebe sonst ohne Fenster stehen."""
        changed = False
        for tid in self.running():
            if tid == keep:
                continue
            with self.lock:
                proc = self.procs.get(tid)
                skip = not proc or tid in self.paused or tid not in self.shown
            if skip or not app_suspendable(tid):
                continue
            pids = session_pids(proc.pid)
            self._kill_all(pids, signal.SIGSTOP)
            with self.lock:
                self.paused[tid] = pids
            log("angehalten (Hintergrund):", tid, sorted(pids))
            changed = True
        if changed:
            self._persist_paused()
            with self.lock:
                start, self._pwatch = not self._pwatch, True
            if start:
                threading.Thread(target=self._watch_paused, daemon=True).start()

    def resume(self, tid):
        with self.lock:
            pids = self.paused.pop(tid, None)
            proc = self.procs.get(tid)
        if pids is None:
            return
        if proc and proc.poll() is None:
            pids = pids | session_pids(proc.pid)        # inzwischen gestartete Kindprozesse auch
        self._kill_all(pids, signal.SIGCONT)
        log("laeuft weiter:", tid)
        self._persist_paused()

    def resume_all(self):
        with self.lock:
            tids = list(self.paused)
        for tid in tids:
            self.resume(tid)

    def _watch_paused(self):
        """Kommt das Fenster eines angehaltenen Programms auf anderem Weg nach vorn (Alt+Tab, Dialog), laeuft es
        weiter – sonst saehe es aus wie abgestuerzt."""
        while True:
            time.sleep(1.0)
            running = set(self.running())                # raeumt beendete Programme aus self.paused
            with self.lock:
                paused = {t: self.procs.get(t) for t in self.paused if t in running}
                if not paused:
                    self._pwatch = False
                    break
            act = active_window()
            if not act:
                continue
            wl = windows()
            for tid, proc in paused.items():
                if proc and any(int(w[0], 16) == act for w in self._windows_of(tid, proc, wl)):
                    self.resume(tid)
        self._persist_paused()

    def starting(self):
        """Laufende Programme, die noch kein Fenster zeigen (z. B. Steam bei der Ersteinrichtung)."""
        running = self.running()
        with self.lock:
            return [t for t in running if t not in self.shown]

    def _get(self, tile_id):
        with self.lock:
            p = self.procs.get(tile_id)
            return p if p and p.poll() is None else None

    def _windows_of(self, tid, proc, wl=None):
        """Fenster eines Programms: ueber die Prozess-IDs seiner Sitzung, dazu die beim Start zugeordneten.
        Flatpaks melden als Prozess-ID die aus ihrer Sandbox – die passt zu keiner Sitzung."""
        wl = windows() if wl is None else wl
        pids = session_pids(proc.pid)
        with self.lock:
            claimed = set(self.claimed.get(tid, ()))
        return [w for w in wl if (w[1] in pids or int(w[0], 16) in claimed) and HOME_TITLE not in w[2]]

    def _claim_new(self, tid, wl, before):
        """Fenster, die es vor dem Start noch nicht gab und die keinem anderen Programm gehoeren, dieser Kachel
        zuordnen (Programme, deren Fenster sich nicht ueber die Prozess-ID finden lassen, z. B. Flatpaks)."""
        with self.lock:
            others = [p for t, p in self.procs.items() if t != tid and p.poll() is None]
            taken = set().union(*self.claimed.values()) if self.claimed else set()
        other_pids = set()
        for op in others:
            other_pids |= session_pids(op.pid)
        new = [w for w in wl if int(w[0], 16) not in before and int(w[0], 16) not in taken
               and w[1] not in other_pids and HOME_TITLE not in w[2]]
        if new:
            with self.lock:
                self.claimed.setdefault(tid, set()).update(int(w[0], 16) for w in new)
            log(tid, "Fenster ohne passende Prozess-ID zugeordnet:", ", ".join(w[0] for w in new))
        return new

    def focus(self, tile_id):
        p = self._get(tile_id)
        if not p:
            return False
        self.resume(tile_id)
        self.pause_background(keep=tile_id)
        wins = self._windows_of(tile_id, p)
        for wid, _, _ in wins:
            run(["wmctrl", "-i", "-a", wid])
        if not wins:
            log("kein Fenster gefunden fuer", tile_id)
        return bool(wins)

    def _touch(self, tid):
        with self.lock:
            if tid in self.recent:
                self.recent.remove(tid)
            self.recent.append(tid)

    def launch(self, tile):
        tid = tile["id"]
        if self._get(tid):
            log("schon offen, nach vorn:", tid)
            self._touch(tid)
            self.focus(tid)
            return "focused"
        cmd = tile.get("cmd")
        if not cmd:
            raise ValueError("Kachel hat keinen Befehl")
        args = expand(cmd if isinstance(cmd, list) else ["sh", "-c", cmd])
        if Path(args[0]).name == PLAYER_BIN.name:          # Videos & Musik, YouTube Light: eigener Player (Stufe, Absturzzaehler)
            mode = "yt" if "--yt" in args[1:2] else "media"
            return PLAYERS.start(tid, args[2] if len(args) > 2 else "", mode=mode)
        media_notify("background")                         # anderes Programm: laufendes Video anhalten
        return self.start(tid, args)

    def start(self, tid, args, env=None):
        log("starte", tid, args)
        logdir = BASE / "logs"
        logdir.mkdir(exist_ok=True)
        out = open(logdir / f"{tid}.log", "w")   # Ausgaben je Programm, hilft bei Abstuerzen
        before = {int(w, 16) for w, _, _ in windows()}  # Fenster vor dem Start (Zuordnung ohne Prozess-ID)
        if Path(args[0]).name == "firefox":
            firefox_prefs(args, ui_lang(), theme_is_dark(settings_load().get("theme") or DEFAULTS["theme"]))
        if Path(args[0]).name in ("dosbox", "dosbox-staging"):
            args = dosbox_prepare(args)
        args, emu_env, wm_fs = emu_prepare(tid, args)   # Emulatoren: Vorgaben, Vollbild, Controller
        penv = app_env()
        penv.update(emu_env)
        penv.update(env or {})
        self.pause_background(keep=tid)                 # anderes Programm kommt nach vorn: Emulatoren anhalten
        proc = subprocess.Popen(args, cwd=str(Path.home()), stdin=subprocess.DEVNULL, env=penv,
                                stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        out.close()
        with self.lock:
            self.procs[tid] = proc
            self.shown.discard(tid)
            self.kinds[tid] = emu_kind(args)
        self._touch(tid)
        # Neues Fenster aktiv nach vorn holen (Openbox verhindert sonst u. U. den Fokuswechsel,
        # und das Programm laeuft unsichtbar hinter der Startseite)
        threading.Thread(target=self._bring_up, args=(tid, proc, before, wm_fs), daemon=True).start()
        return "started"

    def _bring_up(self, tid, proc, before=frozenset(), fullscreen=False):
        # Auf das erste Fenster warten: anfangs schnell, danach gemaechlich - Steam braucht
        # bei der Ersteinrichtung mehrere Minuten, bis sich ein Fenster zeigt
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1800:
            time.sleep(0.3 if time.monotonic() - t0 < 12 else 1.0)
            if proc.poll() is not None:
                log(tid, "beendet mit Code", proc.returncode)
                return
            pids = session_pids(proc.pid)
            wl = windows()
            wins = [w for w in wl if w[1] in pids and HOME_TITLE not in w[2]]
            if not wins and time.monotonic() - t0 > 1.0:  # Flatpak & Co.: neues Fenster ohne passende Prozess-ID
                wins = self._claim_new(tid, wl, before)
            if wins:
                with self.lock:
                    self.shown.add(tid)
                log(tid, f"Fenster nach {time.monotonic() - t0:.1f} s")
                time.sleep(0.4)
                for wid, _, _ in wins:
                    run(["wmctrl", "-i", "-a", wid])
                if fullscreen:                           # Emulator ohne eigene Vollbild-Option (EMU_WM_FULLSCREEN)
                    run(["wmctrl", "-i", "-r", wins[0][0], "-b", "add,fullscreen"])
                return
        with self.lock:                          # kein Fenster erkennbar -> nicht ewig "startet"
            self.shown.add(tid)

    def close(self, tile_id):
        self.resume(tile_id)                     # angehalten verarbeitet es kein "Fenster schliessen"
        with self.lock:
            proc = self.procs.pop(tile_id, None)
        if not proc or proc.poll() is not None:
            with self.lock:
                self.claimed.pop(tile_id, None)
            return
        sid = proc.pid
        wins = self._windows_of(tile_id, proc)
        with self.lock:
            self.claimed.pop(tile_id, None)
        log("schliesse", tile_id, sorted(session_pids(sid)))
        for wid, _, _ in wins:                 # hoeflich, wie Alt+F4 -> Spielstaende werden gespeichert
            run(["wmctrl", "-i", "-c", wid])
        if wins:
            for _ in range(40):
                if proc.poll() is not None:
                    return
                time.sleep(0.1)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(sid, sig)
            except ProcessLookupError:
                return
            for _ in range(20):
                if proc.poll() is not None:
                    return
                time.sleep(0.1)

    def front(self):
        """Kachel des Programms im Vordergrund (fuer die heisse Ecke), sonst None.
        1. Aktives Fenster wurde beim Start einer Kachel zugeordnet (Flatpak & Co.) -> diese.
        2. Prozess-ID des aktiven Fensters gehoert zu einem gestarteten Programm -> dieses.
        3. Sonst: unter den Programmen, denen sich kein Fenster zuordnen laesst, das zuletzt gestartete bzw.
           nach vorn geholte."""
        running = self.running()
        if not running:
            return None
        with self.lock:
            procs = {t: p for t, p in self.procs.items() if t in running}
            recent = list(self.recent)
            claimed = {t: set(w) for t, w in self.claimed.items() if t in running}
        act = active_window()
        for tid, ws in claimed.items():
            if act in ws:
                return tid
        owner = {}
        for tid, proc in procs.items():
            for pid in session_pids(proc.pid):
                owner[pid] = tid
        wins = windows()
        wid = act
        if wid:
            pid = next((p for w, p, _ in wins if int(w, 16) == wid), None)
            if pid in owner:
                return owner[pid]
        seen = {owner[p] for _, p, _ in wins if p in owner}
        cands = [t for t in running if t not in seen] or running
        for tid in reversed(recent):
            if tid in cands:
                return tid
        return cands[0] if len(cands) == 1 else None

    def close_all(self):
        for tid in self.running():
            self.close(tid)


APPS = AppManager()


# ---------------------------------------------------------------------------
#  Eigener Player (qt/voidstation-player.py): Fernsehen ("tv"), Videos & Musik ("media"), YouTube Light ("yt")
# ---------------------------------------------------------------------------
class PlayerManager:
    """Startet den Player, reicht Auftraege an einen laufenden weiter (Socket) und stuft nach Abstuerzen hoch:
    0 Video in der Oberflaeche (EGL) -> 1 GLX + Decoding mit Kopie -> 2 mpv im eigenen Fenster -> 3 (nur Fernsehen)
    nacktes mpv wie frueher. Gilt bis zum Neustart des Launchers; fest: VS_PLAYER_LEVEL=0…3."""
    CRASH = {-4, -6, -7, -8, -11}                # SIGILL, SIGABRT, SIGBUS, SIGFPE, SIGSEGV; dazu Exit-Codes > 0

    def __init__(self):
        self.lock = threading.Lock()
        self.fails = []

    def level(self):
        forced = os.environ.get("VS_PLAYER_LEVEL", "")
        if forced in ("0", "1", "2", "3"):
            return int(forced)
        if not PLAYER_BIN.exists():
            return 3
        with self.lock:
            return min(3, len(self.fails))

    @staticmethod
    def sock(mode):
        return BASE / f"player-{mode}.sock"

    def send(self, mode, msg):
        """Auftrag an einen laufenden Player; False, wenn keiner antwortet."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(str(self.sock(mode)))
                s.sendall((json.dumps(msg) + "\n").encode())
                return b"ok" in s.recv(256)
        except OSError:
            return False

    def start(self, tid, arg="", mode="media"):
        level = min(self.level(), 2)
        for other in ("tv", "media", "ytlight"):     # nur ein Video zur Zeit
            if other != tid:
                APPS.close(other)
        if tid == "tv":
            TV.raw = False
        if APPS._get(tid):
            msg = {"cmd": "tune", "key": arg} if mode == "tv" else {"cmd": "open", "path": arg}
            if (not arg and mode in ("media", "yt")) or self.send(mode, msg):
                APPS.focus(tid)
                return "focused"
            APPS.close(tid)
        args = [sys.executable, str(PLAYER_BIN), "--" + mode] + ([arg] if arg else [])
        res = APPS.start(tid, args, env={"VS_PLAYER_LEVEL": str(level)})
        proc = APPS._get(tid)
        if proc:
            threading.Thread(target=self._watch, args=(tid, proc, level), daemon=True).start()
        return res

    def _watch(self, tid, proc, level):
        t0 = time.monotonic()
        rc = proc.wait()
        if rc in self.CRASH or rc > 0:
            with self.lock:
                self.fails.append(time.time())
                n = len(self.fails)
            log(f"Player ({tid}, Stufe {level}) abgestuerzt nach {time.monotonic() - t0:.0f} s, Code {rc} – "
                f"naechster Start mit Stufe {min(3, n)} (Protokoll: logs/{tid}.log)")

    def active(self, tid):
        """Laeuft fuer diese Kachel der eigene Player (nicht das nackte mpv)?"""
        if tid in ("media", "ytlight"):
            return True
        return tid == "tv" and not TV.raw


PLAYERS = PlayerManager()
MEDIA_NOW = {}                                         # was "Videos & Musik" gerade spielt (Kachel der Startseite)


# ---------------------------------------------------------------------------
#  Radio (mpv im Hintergrund)
# ---------------------------------------------------------------------------
class Radio:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.station = None

    def _ipc(self, command):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(MPV_SOCK)
                s.sendall((json.dumps({"command": command}) + "\n").encode())
                data = b""
                while b"\n" not in data:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                for line in data.decode(errors="replace").splitlines():
                    msg = json.loads(line)
                    if "error" in msg:
                        return msg.get("data")
        except (OSError, ValueError):
            return None
        return None

    def play(self, station):
        url = station.get("url")
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError("ungueltige Stream-Adresse")
        media_notify("pause")                              # Musik/Video im Player anhalten
        self.stop()
        log("Radio:", station.get("name"), url)
        proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal", "--idle=no", "--cache=yes",
             f"--input-ipc-server={MPV_SOCK}", url],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        with self.lock:
            self.proc, self.station = proc, {k: station.get(k, "") for k in ("name", "url", "favicon", "country", "tags")}

    def stop(self):
        with self.lock:
            proc, self.proc, self.station = self.proc, None, None
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def status(self):
        with self.lock:
            alive = self.proc is not None and self.proc.poll() is None
            station = self.station if alive else None
            if not alive:
                self.proc, self.station = None, None
        title = None
        if station:
            t = self._ipc(["get_property", "media-title"])
            if t and t != station["url"] and not t.startswith("http"):
                title = t
        return {"station": station, "title": title}


RADIO = Radio()


def radio_search(query):
    params = urllib.parse.urlencode({
        "name": query, "limit": 40, "hidebroken": "true",
        "order": "clickcount", "reverse": "true",
    })
    last = None
    for host in RADIO_SERVERS:
        try:
            req = urllib.request.Request(f"https://{host}/json/stations/search?{params}",
                                         headers={"User-Agent": "VoidStation/2.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                items = json.load(r)
            return [{
                "name": (i.get("name") or "").strip(),
                "url": i.get("url_resolved") or i.get("url"),
                "favicon": i.get("favicon") or "",
                "country": i.get("countrycode") or "",
                "tags": (i.get("tags") or "")[:60],
                "bitrate": i.get("bitrate") or 0,
            } for i in items if (i.get("url_resolved") or i.get("url"))]
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"Senderverzeichnis nicht erreichbar ({last})")


def favs_load():
    try:
        return json.loads(FAVS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def favs_save(items):
    tmp = FAVS.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(FAVS)


# ---------------------------------------------------------------------------
#  Lautstaerke (PipeWire / wpctl)
# ---------------------------------------------------------------------------
def volume_get():
    r = run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
    if not r or r.returncode != 0:
        return None
    parts = r.stdout.split()                 # "Volume: 0.45 [MUTED]"
    try:
        return {"level": round(float(parts[1]) * 100), "muted": "[MUTED]" in r.stdout}
    except (IndexError, ValueError):
        return None


def volume_set(action):
    sink = "@DEFAULT_AUDIO_SINK@"
    cmds = {
        "up": ["wpctl", "set-volume", "-l", "1.0", sink, "5%+"],
        "down": ["wpctl", "set-volume", sink, "5%-"],
        "mute": ["wpctl", "set-mute", sink, "toggle"],
    }
    if action in cmds:
        run(cmds[action])
    return volume_get()


# ---------------------------------------------------------------------------
#  Einstellungen (Skalierung, Aufloesung, Audioausgang, Netzwerk)
# ---------------------------------------------------------------------------
SETTINGS = BASE / "settings.json"
DEFAULTS = {"scale": 1.75, "resolution": None, "cursor_theme": "Bibata-Modern-Ice", "cursor_size": 48, "lang": None, "theme": "default-dark",
            "sysupd_days": 90, "padmouse": True, "covers_auto": True, "covers_embed": False, "audio_auto": True,
            "emu_fullscreen": True, "save_backup": True, "rom_covers": True}
SYSUPD_DAYS = (30, 60, 90)                  # Erinnerung an Systemupdates (ohne VoidStation-Update) nach … Tagen
# Sprachen der Oberflaeche: Texte in web/i18n/<id>.json, fehlende Texte kommen aus en.json, dann aus de.json.
# Anzeige immer in der eigenen Sprache. Je Sprache auch das Locale fuer gestartete Programme (LANG/LANGUAGE) und
# die Firefox-Sprache (Menues nur mit installiertem Sprachpaket, Webseiten wie YouTube immer).
# Neue Sprache: Zeile hier + web/i18n/<id>.json (build.sh prueft Schluessel und Platzhalter gegen de.json).
LANG_TABLE = [  # (id, Name, Locale, Firefox-Sprache)
    ("de", "Deutsch", "de_DE", "de"),
    ("en", "English", "en_US", "en-US"),
    ("es", "Español", "es_ES", "es-ES"),
    ("fr", "Français", "fr_FR", "fr"),
    ("it", "Italiano", "it_IT", "it"),
    ("lv", "Latviešu", "lv_LV", "lv"),
    ("hu", "Magyar", "hu_HU", "hu"),
    ("nl", "Nederlands", "nl_NL", "nl"),
    ("pl", "Polski", "pl_PL", "pl"),
    ("pt-BR", "Português (Brasil)", "pt_BR", "pt-BR"),
    ("el", "Ελληνικά", "el_GR", "el"),
    ("ru", "Русский", "ru_RU", "ru"),
    ("uk", "Українська", "uk_UA", "uk"),
]
LANGS = [{"id": i, "label": n} for i, n, _, _ in LANG_TABLE]
CURSOR_SIZES = [32, 48, 64, 80, 96]
CURSOR_NAMES = {"Bibata-Modern-Ice": "Hell", "Bibata-Modern-Classic": "Dunkel", "Adwaita": "Adwaita"}
SCALES = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25]


def available_themes():
    td = WEB / "themes"
    if td.is_dir():
        found = [p.stem for p in sorted(td.glob("*.css"))]
        if found:
            return found
    return ["default-dark", "default-light", "high-contrast", "nord"]


def settings_load():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def cmdline_value(name):
    """Wert eines Kernel-Parameters name=wert (z. B. voidstation.lang aus dem Startmenue des Sticks)."""
    try:
        for a in Path("/proc/cmdline").read_text().split():
            if a.startswith(name + "="):
                return a.split("=", 1)[1]
    except OSError:
        pass
    return None


def ui_lang(s=None):
    """Sprache der Oberflaeche: Einstellung, im Live-System sonst die Sprache aus dem Startmenue,
    sonst aus LANG der Sitzung (pt_BR.UTF-8 -> pt-BR, en_GB.UTF-8 -> en), sonst Deutsch."""
    ids = {l["id"] for l in LANGS}
    lang = (s or settings_load()).get("lang")
    if lang in ids:
        return lang
    if Path("/etc/voidstation-live").exists() and cmdline_value("voidstation.lang") in ids:
        return cmdline_value("voidstation.lang")
    env = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").split(".")[0]
    for cand in (env.replace("_", "-"), env.split("_")[0]):
        if cand in ids:
            return cand
    return "de"


# Sprache fuer gestartete Programme: VLC, PCManFM und andere GTK-/Qt-Programme folgen LANG/LANGUAGE,
# Firefox (YouTube) bekommt Oberflaechen- und Webseiten-Sprache ueber sein Profil
LOCALES = {i: f"{loc}.UTF-8" for i, _, loc, _ in LANG_TABLE}
LANGUAGE_ENV = {i: f"{loc}:{loc.split('_')[0]}" for i, _, loc, _ in LANG_TABLE}
FIREFOX_LANG = {i: (ff, ", ".join(dict.fromkeys([loc.replace("_", "-"), loc.split("_")[0], "en-US", "en"])))
                for i, _, loc, ff in LANG_TABLE}
_LOCALES_AVAIL = None


def locale_available(name):
    global _LOCALES_AVAIL
    norm = lambda v: v.strip().lower().replace("utf-8", "utf8")
    if _LOCALES_AVAIL is None:
        try:
            out = subprocess.run(["locale", "-a"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        _LOCALES_AVAIL = {norm(l) for l in out.split()}
    return norm(name) in _LOCALES_AVAIL


def app_env():
    """Umgebung fuer Programme aus den Kacheln: Sprache der Oberflaeche. Fehlt das Locale (z. B. en_US nicht
    erzeugt), bleibt LANG wie es ist und nur LANGUAGE waehlt die Uebersetzung (gettext, Qt)."""
    lang = ui_lang()
    env = dict(os.environ)
    for k in ("LC_ALL", "LC_MESSAGES"):
        env.pop(k, None)
    if locale_available(LOCALES[lang]):
        env["LANG"] = LOCALES[lang]
    env["LANGUAGE"] = LANGUAGE_ENV[lang]
    return env


def firefox_prefs(args, lang, dark):
    """Firefox mit --profile (Kacheln: YouTube, Mediatheken, Firefox): vor jedem Start in user.js setzen
    - Sprache der Oberflaeche: intl.locale.requested (Menues), intl.accept_languages (Webseiten, z. B. YouTube)
    - hell/dunkel nach dem VoidStation-Theme: Webseiten (prefers-color-scheme) und Leisten"""
    try:
        uj = Path(args[args.index("--profile") + 1]) / "user.js"
        old = uj.read_text(encoding="utf-8")
    except (ValueError, IndexError, OSError):
        return
    req, acc = FIREFOX_LANG[lang]
    scheme = 0 if dark else 1                    # 0 = dunkel, 1 = hell (2 waere "wie das System")
    want = {"intl.locale.requested": req, "intl.accept_languages": acc,
            "layout.css.prefers-color-scheme.content-override": scheme,
            "browser.theme.toolbar-theme": scheme, "browser.theme.content-theme": scheme}
    out, seen = [], set()
    for line in old.splitlines():
        m = re.match(r'\s*user_pref\("([^"]+)"', line)
        if m and m.group(1) in want:
            if m.group(1) in seen:
                continue
            seen.add(m.group(1))
            line = f'user_pref("{m.group(1)}", {json.dumps(want[m.group(1)])});'
        out.append(line)
    out += [f'user_pref("{k}", {json.dumps(v)});' for k, v in want.items() if k not in seen]
    new = "\n".join(out) + "\n"
    if new != old:
        uj.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------------------
#  DOSBox Staging: Grundeinstellung beim ersten Start + Sprache/Tastatur/Laufwerk C vor jedem Start
# ---------------------------------------------------------------------------
# Zwei Dateien, DOSBox Staging liest sie nacheinander (spaetere gewinnt, [autoexec] wird zusammengefuegt):
#  1. ~/.config/dosbox/dosbox-staging.conf – Grundeinstellung, legt VoidStation nur an, wenn es sie noch nicht gibt;
#     danach gehoert sie dem Benutzer (eigene Aenderungen bleiben).
#  2. <BASE>/dosbox/voidstation.conf (--conf) – vor jedem Start neu: Sprache der Oberflaeche, Tastatur wie unter X,
#     Laufwerk C = ~/share/ROMs/dos. Wer davon abweichen will: dosbox --set … oder eigener Kachel-Befehl mit --conf.
DOSBOX_LANG = {"de": "de", "en": "en", "es": "es", "fr": "fr", "it": "it", "nl": "nl", "pl": "pl", "pt-BR": "br", "ru": "ru"}
# X-Tastaturbelegung -> DOS-Tastaturcode (FreeDOS KEYB); unbekannt -> auto
DOSBOX_KEYB = {"de": "gr", "at": "gr", "ch": "sg", "us": "us", "gb": "uk", "fr": "fr", "it": "it", "es": "sp",
               "nl": "nl", "be": "be", "pl": "pl", "hu": "hu", "ru": "ru", "ua": "ur", "gr": "gk", "br": "br",
               "pt": "po", "dk": "dk", "se": "sv", "no": "no", "fi": "su", "cz": "cz", "sk": "sl", "tr": "tr"}
DOSBOX_PRIMARY = """# DOSBox Staging – Grundeinstellung von VoidStation
# Angelegt beim ersten Start ueber die Kachel. Die Datei gehoert jetzt dir: Aenderungen bleiben erhalten,
# VoidStation schreibt sie nicht wieder ueber. Geloescht wird sie beim naechsten Start neu angelegt.
# Nicht aufgefuehrte Einstellungen haben den Standardwert von DOSBox Staging; alle Einstellungen
# mit Erklaerung: https://www.dosbox-staging.org/manual/
#
# Sprache, Tastatur und Laufwerk C setzt VoidStation vor jedem Start in einer eigenen Datei
# (~/.local/share/voidstation/dosbox/voidstation.conf): Sprache wie die Oberflaeche, Tastatur wie
# eingestellt, C: = Freigabe share/ROMs/dos.

[sdl]
# Fernseher: gleich im Vollbild (Alt+Enter schaltet um)
fullscreen = true

[cpu]
# 386er mit dynamischem Kern: laeuft mit den meisten DOS-Spielen. Zu schnell/zu langsam?
# Ctrl+F11 / Ctrl+F12 aendern die Geschwindigkeit um je 500 Zyklen, oder cpu_cycles hier anpassen
# (Richtwerte: 286 = 1500, 386DX-33 = 6000, 486DX/2-66 = 25000, Pentium 90 = 50000).
core                 = dynamic
cputype              = 386
cpu_cycles           = 4000
cpu_cycles_protected = 60000
cycleup              = 500
cycledown            = 500
"""


def x_keyboard_layout():
    """Erste X-Tastaturbelegung (setxkbmap -query), sonst aus 00-keyboard.conf, sonst None."""
    r = run(["setxkbmap", "-query"])
    m = re.search(r"^layout:\s*([A-Za-z]+)", r.stdout, re.M) if r and r.returncode == 0 else None
    if m:
        return m.group(1).lower()
    try:
        t = Path("/etc/X11/xorg.conf.d/00-keyboard.conf").read_text(encoding="utf-8")
        m = re.search(r'XkbLayout"\s+"([A-Za-z]+)', t)
        return m.group(1).lower() if m else None
    except OSError:
        return None


def dosbox_prepare(args):
    """Vor dem Start von DOSBox Staging: Grundeinstellung anlegen (falls noch keine da ist),
    VoidStation-Datei schreiben und per --conf anhaengen. Gibt die Befehlszeile zurueck."""
    if "--noprimaryconf" in args:
        return args
    home = Path.home()
    rom_dir = home / "share" / "ROMs" / "dos"
    vs_conf = BASE / "dosbox" / "voidstation.conf"
    try:
        rom_dir.mkdir(parents=True, exist_ok=True)
        primary = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "dosbox" / "dosbox-staging.conf"
        if not primary.exists():
            primary.parent.mkdir(parents=True, exist_ok=True)
            primary.write_text(DOSBOX_PRIMARY, encoding="utf-8")
            log("DOSBox: Grundeinstellung angelegt:", primary)
        keyb = DOSBOX_KEYB.get(x_keyboard_layout() or "", "auto")
        lang = DOSBOX_LANG.get(ui_lang(), "en")
        vs_conf.parent.mkdir(parents=True, exist_ok=True)
        vs_conf.write_text(
            "# Von VoidStation vor jedem Start von DOSBox neu geschrieben – Aenderungen hier gehen verloren.\n"
            "# Eigene Einstellungen: ~/.config/dosbox/dosbox-staging.conf\n\n"
            f"[dosbox]\nlanguage = {lang}\n\n"
            f"[dos]\nkeyboardlayout = {keyb}\n\n"
            f'[autoexec]\nmount c "{rom_dir}"\nc:\n', encoding="utf-8")
    except OSError as e:
        log("DOSBox: Einstellungen nicht geschrieben:", e)
        return args
    if str(vs_conf) in args:
        return args
    return [args[0], "--conf", str(vs_conf)] + list(args[1:])


def settings_save(s):
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS)


def cursor_themes():
    found = []
    for base in (Path("/usr/share/icons"), Path.home() / ".local/share/icons", Path.home() / ".icons"):
        for name in CURSOR_NAMES:
            if (base / name / "cursors").is_dir() and name not in found:
                found.append(name)
    return [n for n in CURSOR_NAMES if n in found]


def _ini_set(path, section, values):
    """Schluessel in einer einfachen INI-Datei setzen, Rest unveraendert lassen."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = path.read_text().splitlines()
    except OSError:
        lines = []
    if f"[{section}]" not in lines:
        lines = [f"[{section}]"] + lines
    keys = set(values)
    lines = [l for l in lines if l.split("=", 1)[0].strip() not in keys]
    idx = lines.index(f"[{section}]") + 1
    for k, v in values.items():
        lines.insert(idx, f"{k}={v}")
    path.write_text("\n".join(lines) + "\n")


def theme_is_dark(theme):
    """Dunkles VoidStation-Theme? Nach der Hintergrundfarbe (--bg-main) der Theme-Datei – so passen auch
    neue Themes ohne Liste –, sonst nach dem Namen."""
    try:
        css = (WEB / "themes" / f"{theme}.css").read_text(encoding="utf-8")
        m = re.search(r"--bg-main:\s*#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", css)
        if m:
            h = m.group(1)
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5
    except OSError:
        pass
    return "light" not in theme


def apply_color_scheme(dark):
    """Farbschema fuer Programme, die es ueber GSettings bzw. das Settings-Portal lesen (Flatpaks wie FreeTube,
    Chromium/Electron, GTK 4). Deren Einstellung "Systemvorgabe" war sonst immer hell. Laufende Programme
    bekommen die Aenderung ueber das Portal mit, soweit sie darauf hoeren."""
    if not shutil.which("gsettings"):
        return
    iface = "org.gnome.desktop.interface"
    for key, val in (("color-scheme", "prefer-dark" if dark else "prefer-light"),
                     ("gtk-theme", "Adwaita-dark" if dark else "Adwaita")):
        r = run(["gsettings", "set", iface, key, val], timeout=10)
        if (not r or r.returncode) and key == "color-scheme" and not dark:
            r = run(["gsettings", "set", iface, key, "default"], timeout=10)   # aeltere Schemas ohne prefer-light
        if not r or r.returncode:
            log("gsettings", key, "nicht gesetzt:", (r.stderr.strip() if r else "nicht ausfuehrbar"))


def apply_appearance(s):
    """Skalierung (Xft.dpi), Mauszeiger und Farbschema (hell/dunkel nach dem Theme) fuer neu gestartete
    Programme setzen."""
    home = Path.home()
    dpi = round(96 * float(s["scale"]))
    theme = s.get("cursor_theme") or DEFAULTS["cursor_theme"]
    if theme not in cursor_themes():
        theme = next(iter(cursor_themes()), "Adwaita")
    size = int(s.get("cursor_size") or DEFAULTS["cursor_size"])
    xres = home / ".Xresources"
    try:
        lines = [l for l in xres.read_text().splitlines()
                 if not l.startswith(("Xft.dpi", "Xcursor.", "XTerm*selectToClipboard", "XTerm*VT100.translations"))]
    except OSError:
        lines = []
    lines += [f"Xft.dpi: {dpi}", f"Xcursor.theme: {theme}", f"Xcursor.size: {size}"]
    # Terminal (xterm): Einfuegen aus der Zwischenablage wie ueberall – Strg+Umschalt+V, Umschalt+Einfg und Rechtsklick
    # (Controller: L2). Von Haus aus fuegt xterm nur die Markierung (PRIMARY) ein, nicht das mit Strg+C Kopierte.
    # Markieren kopiert zugleich in die Zwischenablage, Strg+Umschalt+C ebenso.
    lines += ["XTerm*selectToClipboard: true",
              "XTerm*VT100.translations: #override Ctrl Shift <Key>V: insert-selection(CLIPBOARD)\\n"
              "Ctrl Shift <Key>C: copy-selection(CLIPBOARD)\\nShift <Key>Insert: insert-selection(CLIPBOARD, PRIMARY)\\n"
              "<Btn3Down>: ignore()\\n<Btn3Up>: insert-selection(CLIPBOARD, PRIMARY)"]
    xres.write_text("\n".join(lines) + "\n")
    run(["xrdb", "-merge", str(xres)])
    dark = theme_is_dark(s.get("theme") or DEFAULTS["theme"])
    gtk_name = "Adwaita-dark" if dark else "Adwaita"
    for gtk in ("gtk-3.0", "gtk-4.0"):
        vals = {"gtk-cursor-theme-name": theme, "gtk-cursor-theme-size": str(size),
                "gtk-application-prefer-dark-theme": "true" if dark else "false"}
        if gtk == "gtk-3.0":
            vals["gtk-theme-name"] = gtk_name
        _ini_set(home / ".config" / gtk / "settings.ini", "Settings", vals)
    gtk2 = home / ".gtkrc-2.0"
    try:
        txt = gtk2.read_text()
        new = re.sub(r'(?m)^gtk-theme-name=.*$', f'gtk-theme-name="{gtk_name}"', txt)
        if new != txt:
            gtk2.write_text(new)
    except OSError:
        pass
    idx = home / ".icons" / "default" / "index.theme"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(f"[Icon Theme]\nInherits={theme}\n")
    qt_style, gtk_env = ("Adwaita-Dark", "Adwaita:dark") if dark else ("Adwaita", "Adwaita")
    (BASE / "env.sh").write_text(
        f"export XCURSOR_THEME={theme}\nexport XCURSOR_SIZE={size}\n"
        f"export QT_STYLE_OVERRIDE={qt_style}\nexport GTK_THEME={gtk_env}\n")
    os.environ.update({"XCURSOR_THEME": theme, "XCURSOR_SIZE": str(size),
                       "QT_STYLE_OVERRIDE": qt_style, "GTK_THEME": gtk_env})
    run(["xsetroot", "-cursor_name", "left_ptr"])
    threading.Thread(target=apply_color_scheme, args=(dark,), daemon=True).start()   # Start nicht aufhalten


def restart_home_later(delay=0.8):
    """Startseite neu starten, z. B. fuer den neuen Mauszeiger oder die andere Oberflaeche (home.sh startet sie neu)."""
    def _go():
        time.sleep(delay)
        run(["pkill", "-f", "voidstation-shell.py|voidstation-home.py|profiles/home"])
    threading.Thread(target=_go, daemon=True).start()


# Oberflaeche der Startseite: "qt" (Python + Qt 6, Standard, auch mit Installer im Live-System)
# oder "web" (WebKit-Shell / Firefox, Rueckfall). home.sh liest die Datei "frontend".
FRONTEND_FILE = BASE / "frontend"


def qt_available():
    try:
        import importlib.util
        return importlib.util.find_spec("PySide6") is not None and (BASE / "qt" / "voidstation-home.py").exists()
    except (ImportError, ValueError):
        return False


def frontends():
    return ["qt", "web"] if qt_available() else ["web"]


def frontend():
    try:
        f = FRONTEND_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        f = "qt"
    return f if f in frontends() else frontends()[0]


def xrandr_info():
    """Angeschlossene Ausgaenge mit Modi und Bildraten (aus xrandr --query)."""
    r = run(["xrandr", "--query"])
    outs = []
    if not r or r.returncode != 0:
        return outs
    cur = None
    for line in r.stdout.splitlines():
        if not line.startswith(" "):
            parts = line.split()
            cur = None
            if len(parts) > 1 and parts[1] == "connected":
                cur = {"name": parts[0], "modes": [], "current": None, "rate": None,
                       "preferred": None, "rates": {}}
                outs.append(cur)
        elif cur is not None:
            p = line.split()
            if not p or "x" not in p[0]:
                continue
            mode = p[0]
            if mode not in cur["modes"]:
                cur["modes"].append(mode)
            for tok in p[1:]:
                try:
                    hz = float(tok.rstrip("*+"))
                except ValueError:
                    continue
                cur["rates"].setdefault(mode, []).append(hz)
                if "*" in tok:
                    cur["current"], cur["rate"] = mode, hz
                if "+" in tok and not cur["preferred"]:
                    cur["preferred"] = mode
    return outs


def _best_rate(rates):
    """Moeglichst 60 Hz (60.00 vor 59.94), sonst die hoechste Rate."""
    if not rates:
        return None
    near = [r for r in rates if abs(r - 60) < 0.5]
    return max(near) if near else max(rates)


def _auto_mode(o):
    """Meldet der Fernseher ein Halbbild-Format (1080i) als Standard, lieber den
    groessten Vollbild-Modus mit ~60 Hz nehmen (ruhigeres Bild, YouTube ohne Ruckeln)."""
    pref = o.get("preferred") or o.get("current")
    if not pref or not pref.endswith("i"):
        return None
    prog = [m for m in o["modes"] if not m.endswith("i")
            and any(abs(r - 60) < 0.5 for r in o["rates"].get(m, []))]
    if not prog:
        return None
    return max(prog, key=lambda m: int(m.split("x")[0]) * int(m.split("x")[1].rstrip("i")))


def apply_resolution(res):
    for o in xrandr_info():
        mode = res if res in o["modes"] else (None if res else _auto_mode(o))
        if not mode:
            continue
        rate = _best_rate(o["rates"].get(mode, []))
        if mode == o["current"] and (rate is None or o["rate"] == rate):
            continue
        cmd = ["xrandr", "--output", o["name"], "--mode", mode]
        if rate:
            cmd += ["--rate", f"{rate:.2f}"]
        run(cmd)
        log("Aufloesung", o["name"], mode, f"{rate} Hz" if rate else "", "(automatisch)" if not res else "")


def pactl_json(*args):
    r = run(["pactl", "-f", "json", *args])
    if not r or r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
#  Ton: Geraete statt Rohprofile (PipeWire ueber pactl)
#    Ein "Geraet" ist das, was man als Ausgang kennt: Fernseher (HDMI, je Anschluss), Klinke, S/PDIF,
#    USB-Headset, Bluetooth-Kopfhoerer. Je Geraet ein Format (Stereo, 5.1 …; Bluetooth: Codec) und
#    das Mikrofon an/aus – daraus ergibt sich das Profil der Karte. PipeWire-Profilnamen sieht niemand mehr.
#    Gemerkt je Geraet in settings.json: audio_prefs = {schluessel: {"format": …, "mic": bool}}
#    Schluessel: Kartenname (USB, Bluetooth) bzw. Kartenname#familie+anschluss (eingebaute Karten: hdmi0, analog0 …)
# ---------------------------------------------------------------------------
AUDIO_LOCK = threading.RLock()
AUDIO_LAYOUTS = ["mono", "stereo", "surround-21", "surround-40", "surround-41", "surround-50", "surround-51", "surround-71"]
AUDIO_CODECS = {"sbc": "SBC", "sbc_xq": "SBC-XQ", "aac": "AAC", "aac_eld": "AAC-ELD", "aptx": "aptX", "aptx_hd": "aptX HD",
                "aptx_ll": "aptX LL", "aptx_ll_duplex": "aptX LL", "ldac": "LDAC", "lc3plus_h3": "LC3plus", "lc3": "LC3",
                "opus_05": "Opus", "opus_g": "Opus", "faststream": "FastStream", "faststream_duplex": "FastStream"}
# Geraete, auf die der Ton beim Einstecken nicht von selbst wechseln soll (Controller mit Kopfhoerer-Buchse, Webcams)
AUDIO_NOAUTO = re.compile(r"controller|gamepad|dualsense|dualshock|joy-?con|webcam|camera|\bcam\b", re.I)


def _audio_profile(name):
    """Profilname -> (familie, anschluss, layout, mit_eingang) oder None (kein Ausgang, Durchreichen, aus).
    output:hdmi-surround71-extra1+input:analog-stereo -> ("hdmi", 1, "surround-71", True)
    a2dp-sink-aac -> ("bt", 0, "a2dp:aac", False) · headset-head-unit-msbc -> ("bt", 0, "hfp:msbc", True)"""
    if name.startswith("output:"):
        out, _, inp = name[7:].partition("+input:")
        m = re.match(r"^(analog|hdmi|iec958)-(.+?)(?:-extra(\d+))?$", out)
        fam, lay, port = (m.group(1), m.group(2), int(m.group(3) or 0)) if m else ("other", out, 0)
        if re.search(r"(^|-)(ac3|dts|eac3|truehd)(-|$)", lay):     # Bitstream an einen AV-Receiver: nicht anbieten
            return None
        lay = {"surround": "surround-51", "surround71": "surround-71"}.get(lay, lay)   # HDMI schreibt es anders
        if lay.endswith("-fallback"):
            lay = lay[:-9]
        return fam, port, lay, bool(inp)
    if name.startswith("a2dp-sink"):
        return "bt", 0, "a2dp:" + (name[10:] or "auto"), False
    if name.startswith("headset-head-unit"):
        return "bt", 0, "hfp:" + (name[18:] or "auto"), True
    return None


def _audio_card_kind(c):
    p = c.get("properties") or {}
    name = c.get("name", "")
    if name.startswith("bluez_card.") or p.get("device.bus") == "bluetooth":
        return "bt"
    if p.get("device.bus") == "usb" or ".usb-" in name:
        return "usb"
    return "pci"


def _audio_ports(c):
    ports = c.get("ports") or {}
    return list(ports.values()) if isinstance(ports, dict) else list(ports)


def _audio_fmt(lay):
    """Format fuer die Oberflaeche: key = Sprachschluessel (Text mit {ch}), label = sprachneutral."""
    if lay.startswith("a2dp:"):
        codec = lay[5:]
        if codec == "auto":
            return {"id": lay, "key": "audio.fmt.auto", "label": ""}
        return {"id": lay, "key": "", "label": AUDIO_CODECS.get(codec, codec.upper())}
    if lay in ("mono", "stereo"):
        return {"id": lay, "key": "audio.fmt." + lay, "label": ""}
    if lay.startswith("surround-") and lay[9:].isdigit() and len(lay) == 11:
        return {"id": lay, "key": "audio.fmt.surround", "label": lay[9] + "." + lay[10]}
    return {"id": lay, "key": "", "label": lay}


def _audio_sink_of(card, sinks):
    """Name des Ausgangs (Sink), den diese Karte gerade stellt, sonst None."""
    prefix = card.replace("_card.", "_output.")          # alsa_card.… -> alsa_output.…, bluez_card.… -> bluez_output.…
    for s in sinks or []:
        props = s.get("properties") or {}
        if props.get("device.name") == card or s.get("name", "").startswith(prefix + "."):
            return s.get("name")
    return None


def audio_devices(cards, sinks, default_sink):
    """Geraeteliste aus pactl (list cards / list sinks / get-default-sink). Rein rechnend – testbar ohne PipeWire."""
    devs = {}
    for c in cards or []:
        card, kind = c.get("name", ""), _audio_card_kind(c)
        props = c.get("properties") or {}
        active = c.get("active_profile") or ""
        for pname, prof in (c.get("profiles") or {}).items():
            parsed = _audio_profile(pname)
            if not parsed:
                continue
            fam, port, lay, inp = parsed
            if kind == "pci":
                key, dkind = f"{card}#{fam}{port}", {"iec958": "spdif"}.get(fam, fam)
            else:
                key, dkind = card, kind
            d = devs.setdefault(key, {"key": key, "card": card, "kind": dkind, "cardKind": kind, "port": port,
                                      "name": "", "profiles": [], "activeProfile": None})
            d["profiles"].append({"name": pname, "fam": fam, "lay": lay, "inp": inp,
                                  "prio": prof.get("priority", 0) or 0, "avail": prof.get("available") is not False})
            if pname == active:
                d["activeProfile"] = pname
        # Namen: Bluetooth/USB/sonstige wie vom Geraet gemeldet, HDMI nach dem Bildschirm (EDID/ELD), wenn bekannt
        desc = props.get("device.description") or props.get("alsa.card_name") or card
        for d in devs.values():
            if d["card"] != card:
                continue
            if d["kind"] == "hdmi":
                names = {p["name"] for p in d["profiles"]}
                for port in _audio_ports(c):
                    pn = (port.get("properties") or {}).get("device.product.name")
                    if pn and names & set(port.get("profiles") or []):
                        d["name"] = pn
                        break
            elif d["kind"] not in ("analog", "spdif"):
                d["name"] = desc
    dsink_card = None
    for c in cards or []:
        if default_sink and _audio_sink_of(c.get("name", ""), sinks) == default_sink:
            dsink_card = c.get("name")
    out = []
    for d in devs.values():
        usable = [p for p in d["profiles"] if p["avail"]]
        if not usable and not d["activeProfile"]:
            continue                                     # z. B. HDMI-Anschluss ohne Bildschirm, Klinke ohne Stecker
        lays = {p["lay"] for p in usable if not p["lay"].startswith("hfp:")}
        def order(l):
            if l in AUDIO_LAYOUTS:
                return (0, AUDIO_LAYOUTS.index(l), "")
            if l == "a2dp:auto":
                return (1, 0, "")
            best = max((p["prio"] for p in usable if p["lay"] == l), default=0)
            return (2, -best, l)
        fmts = [_audio_fmt(l) for l in sorted(lays, key=order)]
        ap = next((p for p in d["profiles"] if p["name"] == d["activeProfile"]), None)
        cur_fmt = ap["lay"] if ap and not ap["lay"].startswith("hfp:") else None
        if d["cardKind"] == "bt":
            mic_avail = any(p["inp"] for p in usable)
        else:
            mic_avail = any(p["inp"] and p["lay"] == (cur_fmt or "stereo") for p in usable)
        out.append({"key": d["key"], "card": d["card"], "kind": d["kind"], "name": d["name"], "num": 0,
                    "active": bool(ap) and d["card"] == dsink_card, "formats": fmts, "format": cur_fmt,
                    "mic": (bool(ap and ap["inp"]) if mic_avail else None), "micAvail": mic_avail,
                    "profiles": d["profiles"], "activeProfile": d["activeProfile"]})
    # Mehrere HDMI-Ausgaenge mit gleichem Namen: durchnummerieren (Fernseher 1, Fernseher 2)
    hd = [d for d in out if d["kind"] == "hdmi"]
    for n in {d["name"] for d in hd}:
        same = sorted((d for d in hd if d["name"] == n), key=lambda d: (d["card"], d["key"]))
        if len(same) > 1:
            for i, d in enumerate(same):
                d["num"] = i + 1
    rank = {"hdmi": 0, "usb": 1, "bt": 2, "analog": 3, "spdif": 4, "other": 5}
    out.sort(key=lambda d: (rank.get(d["kind"], 9), d["name"].lower(), d["key"]))
    return out


def audio_default_format(dev):
    ids = [f["id"] for f in dev["formats"]]
    for want in ("stereo", "a2dp:auto"):
        if want in ids:
            return want
    return ids[0] if ids else None


def audio_default_mic(dev):
    return dev["kind"] == "usb"                         # USB-Headset: Mikro bereit; Bluetooth: sonst nur Sprachqualitaet


def audio_choose(dev, fmt, mic):
    """Profil fuer Format + Mikrofon. Bluetooth: Mikrofon an = Headset-Profil (HFP), sonst A2DP im gewuenschten Codec.
    Eingebaute/USB-Karten: analog vor S/PDIF (bei USB derselbe Ausgang), dann hoechste Prioritaet."""
    usable = [p for p in dev["profiles"] if p["avail"]] or dev["profiles"]
    def best(cands):
        return min(cands, key=lambda p: ({"analog": 0, "hdmi": 0, "iec958": 1}.get(p["fam"], 2), -p["prio"]))["name"] if cands else None
    if dev["kind"] == "bt" and mic:
        return best([p for p in usable if p["lay"].startswith("hfp:")]) or audio_choose(dev, fmt, False)
    same = [p for p in usable if p["lay"] == fmt] or [p for p in usable if p["lay"] == audio_default_format(dev)]
    if not same:
        same = [p for p in usable if not p["lay"].startswith("hfp:")]
    return best([p for p in same if p["inp"] == bool(mic)]) or best(same)


def audio_snapshot():
    cards = pactl_json("list", "cards")
    if cards is None:
        return None
    sinks = pactl_json("list", "sinks") or []
    r = run(["pactl", "get-default-sink"])
    default = r.stdout.strip() if r and r.returncode == 0 else ""
    return {"cards": cards, "sinks": sinks, "default": default, "devices": audio_devices(cards, sinks, default)}


def audio_info():
    snap = audio_snapshot()
    auto = bool(settings_load().get("audio_auto", True))
    if snap is None:
        return {"ok": False, "devices": [], "auto": auto}
    pub = ("key", "kind", "name", "num", "active", "formats", "format", "mic", "micAvail")
    return {"ok": True, "auto": auto, "devices": [{k: d[k] for k in pub} for d in snap["devices"]]}


def audio_select(key, fmt=None, mic=None, make_default=True):
    """Geraet waehlen (Format/Mikro aus den gemerkten Einstellungen, sonst Stereo; Mikro bei USB an) bzw. Format oder
    Mikro aendern. Setzt das Profil der Karte und – make_default – den Ausgang als Standard. Gibt False zurueck,
    wenn es das Geraet nicht (mehr) gibt."""
    with AUDIO_LOCK:
        snap = audio_snapshot()
        dev = next((d for d in (snap or {}).get("devices", []) if d["key"] == key), None)
        if not dev:
            return False
        s = settings_load()
        prefs = dict((s.get("audio_prefs") or {}).get(key) or {})
        ids = [f["id"] for f in dev["formats"]]
        picked = fmt is not None
        if not picked:                                   # Mikro umschalten: Format bleibt; Geraet waehlen: gemerktes
            fmt = dev["format"] if mic is not None and dev["format"] else prefs.get("format")
        if fmt not in ids:
            fmt = prefs.get("format") if prefs.get("format") in ids else audio_default_format(dev)
        if mic is None:
            if picked and dev["kind"] == "bt":
                mic = False                              # Codec gewaehlt = A2DP, das Headset-Profil kennt keine Codecs
            elif picked and dev["mic"] is not None:
                mic = dev["mic"]
            else:
                mic = prefs.get("mic", audio_default_mic(dev))
        prof = audio_choose(dev, fmt, mic)
        if prof and prof != dev["activeProfile"]:
            run(["pactl", "set-card-profile", dev["card"], prof])
        if make_default:
            sink = None
            for _ in range(20):                          # neuer Ausgang braucht nach dem Profilwechsel einen Moment
                sink = _audio_sink_of(dev["card"], pactl_json("list", "sinks") or [])
                if sink:
                    break
                time.sleep(0.2)
            if sink:
                run(["pactl", "set-default-sink", sink])
                run(["pactl", "set-sink-mute", sink, "0"])
        prefs.update({"format": fmt, "mic": bool(mic)})
        s = settings_load()
        s.setdefault("audio_prefs", {})[key] = prefs
        settings_save(s)
        log("Ton:", key, prof or "-", "(Standard)" if make_default else "")
        return True


def audio_tidy(snap=None):
    """Eingebaute Karten, die VoidStation zum ersten Mal sieht: HDMI von Surround auf Stereo stellen, solange niemand
    ein Format gewaehlt hat. Fernseher haben zwei Lautsprecher; bei 7.1 mischt mancher den Center-Kanal (Dialoge)
    schlecht herunter. Wer einen AV-Receiver hat, stellt Surround unter Einstellungen → Ton → Format wieder ein."""
    with AUDIO_LOCK:
        snap = snap or audio_snapshot()
        if not snap:
            return
        s = settings_load()
        seen, prefs = list(s.get("audio_seen") or []), s.get("audio_prefs") or {}
        changed = False
        for c in snap["cards"]:
            card = c.get("name", "")
            if _audio_card_kind(c) != "pci" or card in seen:
                continue
            seen.append(card)
            changed = True
            for d in snap["devices"]:
                ap = next((p for p in d["profiles"] if p["name"] == d["activeProfile"]), None)
                if d["card"] == card and d["kind"] == "hdmi" and ap and ap["lay"].startswith("surround") and d["key"] not in prefs \
                        and any(f["id"] == "stereo" for f in d["formats"]):
                    prof = audio_choose(d, "stereo", ap["inp"])
                    if prof:
                        was_default = d["active"]        # neuer Ausgangsname nach dem Wechsel: Standard mitnehmen
                        run(["pactl", "set-card-profile", card, prof])
                        log("Ton:", d["key"], "von", ap["lay"], "auf Stereo (Fernseher)")
                        for _ in range(20 if was_default else 0):
                            sink = _audio_sink_of(card, pactl_json("list", "sinks") or [])
                            if sink:
                                run(["pactl", "set-default-sink", sink])
                                break
                            time.sleep(0.2)
        if changed:
            s = settings_load()
            s["audio_seen"] = seen
            settings_save(s)


class AudioWatch:
    """Neu eingesteckte USB- bzw. eingeschaltete Bluetooth-Kopfhoerer uebernehmen den Ton (abschaltbar: audio_auto).
    Nicht beim Hochfahren und nicht direkt nach dem Standby – dann melden sich vorhandene Geraete nur neu an."""
    QUIET = 30

    def __init__(self):
        self.quiet_until = 0.0
        self.gap = self._gap()

    @staticmethod
    def _gap():
        return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()

    def run(self):
        tries = 0                                        # PipeWire startet mit der Sitzung, evtl. nach dem Launcher
        while pactl_json("info") is None:                # nicht aufgeben: kommt der Ton spaeter (langsamer Rechner,
            tries += 1                                   # WirePlumber neu gestartet), soll die Ueberwachung mitlaufen
            if tries == 90:
                log("Ton: PipeWire nach 90 s nicht erreichbar – versuche es weiter")
            time.sleep(1 if tries < 90 else 10)
        if tries >= 90:
            log("Ton: PipeWire jetzt erreichbar")
        time.sleep(8)                                    # Geraete beim Hochfahren in Ruhe ankommen lassen
        try:
            audio_tidy()
        except Exception as e:  # noqa: BLE001
            log("Ton (Vorgaben):", e)
        while True:
            try:
                p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            except OSError:
                return
            for line in p.stdout:
                m = re.match(r"Event 'new' on card #(\d+)", line.strip())
                if m:
                    threading.Thread(target=self.new_card, args=(int(m.group(1)),), daemon=True).start()
            p.wait()
            time.sleep(5)                                # PipeWire neu gestartet: wieder anmelden

    def new_card(self, index):
        g = self._gap()
        if g - self.gap > 10:                            # dazwischen lag ein Standby
            self.quiet_until = time.monotonic() + self.QUIET
        self.gap = g
        time.sleep(1.5)                                  # Profile und Ausgaenge erst fertig anlegen lassen
        try:
            snap = audio_snapshot()
            c = next((x for x in (snap or {}).get("cards", []) if x.get("index") == index), None)
            if not c:
                return
            audio_tidy(snap)
            kind = _audio_card_kind(c)
            props = c.get("properties") or {}
            label = " ".join(str(props.get(k, "")) for k in ("device.description", "device.product.name", "alsa.card_name"))
            if kind not in ("usb", "bt") or time.monotonic() < self.quiet_until or not settings_load().get("audio_auto", True):
                return
            if AUDIO_NOAUTO.search(label) or props.get("device.form_factor") in ("webcam", "microphone") \
                    or (kind == "usb" and props.get("device.vendor.id") == "0x054c"):   # Sony: DualShock/DualSense per USB
                log("Ton: neues Geraet ohne automatischen Wechsel:", c.get("name"))
                return
            dev = next((d for d in snap["devices"] if d["card"] == c.get("name")), None)
            if dev:
                audio_select(dev["key"])
                log("Ton: neues Geraet uebernimmt:", dev["key"])
        except Exception as e:  # noqa: BLE001
            log("Ton (neues Geraet):", e)


AUDIO_WATCH = AudioWatch()


def net_info():
    r = run(["ip", "-4", "-o", "addr", "show", "scope", "global"])
    addrs = []
    if r:
        for line in r.stdout.splitlines():
            p = line.split()
            if len(p) >= 4:
                addrs.append({"iface": p[1], "ip": p[3].split("/")[0]})
    return {"hostname": socket.gethostname(), "addresses": addrs}


def nm_split(line):
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def wifi_scan():
    # USB-Sticks brauchen fuer einen vollen Suchlauf oft mehr als 10 s. Reicht die Zeit nicht,
    # die zuletzt gefundenen Netze zeigen statt eines Fehlers.
    base = ["sudo", "-n", "nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    r = run(base + ["--rescan", "yes"], timeout=30)
    if not r or r.returncode != 0:
        old = run(base + ["--rescan", "no"], timeout=10)
        if old and old.returncode == 0 and old.stdout.strip():
            r = old
    if r is None:
        raise RuntimeError("WLAN-Suche dauert zu lange – ist ein WLAN-Adapter angeschlossen?")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "WLAN-Suche fehlgeschlagen")
    nets = {}
    for line in r.stdout.splitlines():
        use, ssid, sig, sec = (nm_split(line) + ["", "", "", ""])[:4]
        if not ssid:
            continue
        n = {"ssid": ssid, "signal": int(sig or 0), "secure": bool(sec and sec != "--"),
             "active": use.strip() == "*"}
        if ssid not in nets or n["signal"] > nets[ssid]["signal"]:
            nets[ssid] = n
    return sorted(nets.values(), key=lambda n: (-n["active"], -n["signal"]))


def wifi_profiles(ssid):
    """UUIDs aller gespeicherten WLAN-Profile fuer dieses Netz (Name und SSID koennen abweichen)."""
    r = run(["sudo", "-n", "nmcli", "-t", "-f", "UUID,TYPE", "connection", "show"], timeout=10)
    out = []
    if not r or r.returncode != 0:
        return out
    for line in r.stdout.splitlines():
        uuid, typ = (nm_split(line) + ["", ""])[:2]
        if typ not in ("802-11-wireless", "wifi") or not uuid:
            continue
        g = run(["sudo", "-n", "nmcli", "-g", "802-11-wireless.ssid", "connection", "show", uuid], timeout=10)
        if g and g.returncode == 0 and g.stdout.strip() == ssid:
            out.append(uuid)
    return out


def wifi_forget(uuids):
    for u in uuids:
        run(["sudo", "-n", "nmcli", "connection", "delete", "uuid", u], timeout=15)


# nmcli-Meldungen (deutsch oder englisch, je nach Locale) -> Schluessel aus web/i18n
WIFI_ERRORS = [
    ("wifi.err.password", ("secrets were required", "geheimdaten", "wireless-security.psk", "passwd-file",
                           "4-way handshake", "invalid passphrase", "property 'psk' is invalid",
                           "eigenschaft »psk« ist ungültig", "psk: ungültig", "psk: invalid")),
    ("wifi.err.notFound", ("no network with ssid", "kein netzwerk mit ssid")),
    ("wifi.err.noDevice", ("no wi-fi device", "kein wlan-gerät", "kein wi-fi-gerät")),
    ("wifi.err.timeout", ("timeout", "zeitüberschreitung", "timed out")),
]


def wifi_error(text):
    low = text.lower()
    for key, needles in WIFI_ERRORS:
        if any(n in low for n in needles):
            return key
    # sonst die eigentliche Fehlerzeile ohne Warnungen und "Error:"-Vorsatz
    lines = [l.strip() for l in text.splitlines() if l.strip()
             and not l.strip().lower().startswith(("warning:", "warnung:"))]
    msg = lines[-1] if lines else "Verbindung fehlgeschlagen"
    for pre in ("Error: ", "Fehler: "):
        if msg.startswith(pre):
            msg = msg[len(pre):]
    return msg


def wifi_connect(ssid, password):
    """Verbinden. Mit Passwort wird ein altes Profil fuer dasselbe Netz vorher entfernt (sonst nimmt
    NetworkManager dessen gespeichertes, evtl. falsches Passwort); scheitert der Versuch, wird das dabei
    angelegte Profil wieder geloescht. Fehler kommen als Schluessel "wifi.err.*" oder als Klartext."""
    before = wifi_profiles(ssid)
    if password:
        wifi_forget(before)
        before = []
    args = ["sudo", "-n", "nmcli", "--wait", "90", "device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=100)
        err = None if r.returncode == 0 else wifi_error((r.stderr or "") + "\n" + (r.stdout or ""))
    except subprocess.TimeoutExpired:
        err = "wifi.err.timeout"
    if err:
        wifi_forget([u for u in wifi_profiles(ssid) if u not in before])
        log("WLAN:", ssid, "->", err)
        raise RuntimeError(err)


def share_info():
    share = Path.home() / "share"
    r = run(["pgrep", "-x", "smbd"])
    smb = bool(r and r.returncode == 0)
    import pwd
    return {"path": str(share), "exists": share.is_dir(), "samba": smb, "name": "share",
            "user": pwd.getpwuid(os.getuid()).pw_name}


# ---------------------------------------------------------------------------
#  TV: Sender aus aller Welt (Verzeichnis von iptv-org, frei empfangbare Streams)
# ---------------------------------------------------------------------------
IPTV_API = "https://iptv-org.github.io/api/"
CACHE = BASE / "cache"
TVFAVS = BASE / "tvfavs.json"
TVRECENT = BASE / "tvrecent.json"           # zuletzt gesehene Sender (Player: Reiter „Zuletzt“)
UA = {"User-Agent": "VoidStation/4.0"}
TV_PAGE = 200                                # Sender je Seite der Liste (mehr Kacheln auf einmal bremsen schwache Geraete)
TV_LETTERS = ["#"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]


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


def fetch(url, dest, max_age):
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


class IPTV:
    def __init__(self):
        self.lock = threading.Lock()
        self.state, self.error = "idle", None
        self.index, self.by_key, self.countries = [], {}, []
        self.loaded_at = 0.0
        self.now = None
        self.zap_keys = []          # Liste, in der der Player mit ▲▼ umschaltet (aus der heraus gestartet wurde)
        self.recent = tvrecent_load()
        self.broken = {}            # Sender -> Zeitpunkt, an dem er zuletzt nicht erreichbar war
        self.failed = None          # Rueckfall (nacktes mpv): zuletzt gescheiterter Sender, fuer die Meldung
        self.raw = False            # "tv" laeuft gerade als nacktes mpv (Stufe 3)

    def ensure(self):
        with self.lock:
            fresh = self.index and time.time() - self.loaded_at < 86400
            if fresh or self.state == "loading":
                return
            self.state = "loading"
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            day = 86400
            ch = json.loads(fetch(IPTV_API + "channels.json", CACHE / "channels.json", day).read_text())
            st = json.loads(fetch(IPTV_API + "streams.json", CACHE / "streams.json", day).read_text())
            try:
                lg = json.loads(fetch(IPTV_API + "logos.json", CACHE / "logos.json", 7 * day).read_text())
            except Exception:  # noqa: BLE001
                lg = []
            index, counts = self.build_index(ch, st, lg)
            with self.lock:
                self.index = index
                self.by_key = {e["key"]: e for e in index}
                self.countries = sorted(counts.items(), key=lambda x: -x[1])
                self.loaded_at = time.time()
                self.state, self.error = "ready", None
            log(f"TV-Verzeichnis: {len(index)} Sender")
        except Exception as e:  # noqa: BLE001
            log("TV-Verzeichnis nicht ladbar:", e)
            with self.lock:
                self.state, self.error = ("ready" if self.index else "error"), str(e)

    @staticmethod
    def build_index(ch, st, lg):
        """Senderliste aus channels/streams/logos.json: ein Eintrag je Sender und Feed, sortiert wie die A–Z-Leiste."""
        chans = {c["id"]: c for c in ch if not c.get("is_nsfw") and not c.get("closed")}
        logos = {}
        for l in lg:
            if l.get("channel") and l.get("url") and not l.get("feed"):
                logos.setdefault(l["channel"], l["url"])
        index, seen, counts = [], set(), {}
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
            counts[e["country"]] = counts.get(e["country"], 0) + 1
        # „#“ (Ziffern, andere Schriften) zuerst, dann A–Z – dieselbe Reihenfolge wie die Leiste
        index.sort(key=lambda e: (e["letter"] != "#", e["fold"]))
        return index, counts

    @staticmethod
    def public(e):
        return {k: e[k] for k in ("key", "cid", "name", "country", "cats", "quality", "logo") if k in e}

    @staticmethod
    def page_of(index, q="", country="", cat="", letter="", offset=0, limit=TV_PAGE):
        """Eine Seite der Senderliste. Ohne Suche alphabetisch, wahlweise nur ein Anfangsbuchstabe;
        mit Suche Treffer am Namensanfang zuerst. „letters“ zaehlt je Buchstabe (Land + Thema, ohne Suche)."""
        q = tv_fold((q or "").strip())
        letter = letter if letter in TV_LETTERS else ""
        letters, hits = {}, []
        for e in index:
            if country and e["country"] != country:
                continue
            if cat and cat not in e["cats"]:
                continue
            L = e.get("letter") or tv_letter(e["name"])
            letters[L] = letters.get(L, 0) + 1
            if q:
                folds = e.get("folds") or [tv_fold(n) for n in [e["name"]] + list(e.get("alt") or [])]
                if any(q in n for n in folds):
                    hits.append((0 if any(n.startswith(q) for n in folds) else 1, e))
            elif not letter or L == letter:
                hits.append((0, e))
        hits.sort(key=lambda x: x[0])            # stabil: innerhalb des Rangs bleibt die A–Z-Reihenfolge
        total = len(hits)
        limit = max(1, min(int(limit or TV_PAGE), 1000))
        offset = max(0, min(int(offset or 0), max(0, total - 1)))
        offset -= offset % limit
        return {"items": [IPTV.public(e) for _, e in hits[offset:offset + limit]], "total": total,
                "offset": offset, "limit": limit, "letter": "" if q else letter,
                "letters": [{"l": L, "n": letters.get(L, 0)} for L in TV_LETTERS]}

    def page(self, q="", country="", cat="", letter="", offset=0, limit=TV_PAGE):
        self.ensure()
        res = self.page_of(self.index, q, country, cat, letter, offset, limit)
        res["items"] = [self.mark(i) for i in res["items"]]
        return res

    def mark(self, pub):
        """Oeffentlicher Eintrag + "broken", wenn der Sender in den letzten 24 h nicht erreichbar war."""
        t = self.broken.get(pub.get("key"))
        if t and time.time() - t < 86400:
            pub = dict(pub, broken=True)
        return pub

    def filtered_keys(self, q="", country="", cat=""):
        """Alle Sender zu Land/Thema/Suche (ohne Buchstabe, ohne Seiten) – Reihenfolge wie die Liste."""
        q = tv_fold((q or "").strip())
        out = []
        for e in self.index:
            if country and e["country"] != country:
                continue
            if cat and cat not in e["cats"]:
                continue
            if q:
                folds = e.get("folds") or [tv_fold(n) for n in [e["name"]] + list(e.get("alt") or [])]
                if not any(q in n for n in folds):
                    continue
            out.append(e["key"])
        return out

    def search(self, q, country, cat, limit=80):
        """Alte Schnittstelle (/api/tv/search, z. B. fuer Forks): nur die ersten Treffer als Liste."""
        return self.page(q, country, cat, limit=limit)["items"]

    def status(self):
        now = None
        if self.now and "tv" in APPS.running():
            now = self.now
        return {"state": self.state, "error": self.error, "count": len(self.index),
                "countries": [{"code": c, "n": n} for c, n in self.countries[:40]], "now": now, "failed": self.failed}

    def entry(self, key):
        e = self.by_key.get(key)
        if e:
            return e
        for f in tvfavs_load() + list(self.recent):
            if f.get("key") == key:
                return f
        return None

    def set_zap(self, key, ctx):
        """Zapp-Liste fuer den Player: Favoriten oder die Liste mit Land/Thema/Suche, aus der gestartet wurde
        (ohne Buchstaben-Filter, hoechstens 2000 Sender rund um den gewaehlten)."""
        keys = []
        if isinstance(ctx, dict):
            if ctx.get("favs"):
                keys = [f.get("key") for f in tvfavs_load() if f.get("key")]
            elif self.index:
                country = str(ctx.get("country") or "")
                keys = self.filtered_keys(str(ctx.get("q") or ""), "" if country == "*" else country, str(ctx.get("cat") or ""))
        if key not in keys:
            if not keys and key in self.zap_keys:
                return
            keys = keys or [f.get("key") for f in tvfavs_load() if f.get("key")]
            if key not in keys:
                keys = [key] + keys
        if len(keys) > 2000:
            i = keys.index(key)
            keys = keys[max(0, i - 1000):i + 1000]
        self.zap_keys = keys

    def zap(self):
        items = [self.mark(self.public(e)) for e in (self.entry(k) for k in self.zap_keys) if e]
        return {"items": items, "favs": [self.mark(self.public(f)) for f in tvfavs_load()],
                "recent": [self.mark(self.public(f)) for f in self.recent], "key": (self.now or {}).get("key")}

    def remember(self, e):
        self.recent = [e] + [r for r in self.recent if r.get("key") != e.get("key")]
        self.recent = self.recent[:15]
        tvrecent_save(self.recent)

    def tune(self, key):
        """Player schaltet um: Stream-Adresse (bleibt im Launcher-Verzeichnis, nie in den Listen) + Angaben."""
        e = self.entry(key)
        if not e:
            raise ValueError("Sender unbekannt")
        RADIO.stop()
        self.now = self.public(e)
        self.broken.pop(key, None)
        self.remember(e)
        log("TV:", e.get("name"), e.get("url"))
        return {"entry": self.mark(self.public(e)), "url": e["url"], "ref": e.get("ref") or "", "ua": e.get("ua") or "",
                "recent": [self.mark(self.public(f)) for f in self.recent]}

    def mark_broken(self, key, reason=""):
        self.broken[key] = time.time()
        e = self.entry(key)
        log("TV: nicht erreichbar:", (e or {}).get("name", key), reason)

    def play(self, key, ctx=None):
        e = self.entry(key)
        if not e:
            raise ValueError("Sender unbekannt")
        self.set_zap(key, ctx)
        RADIO.stop()
        self.failed = None
        if PLAYERS.level() < 3:
            PLAYERS.start("tv", key, mode="tv")
        else:
            self.play_raw(e)
            self.remember(e)
        self.now = self.public(e)
        return self.status()

    def play_raw(self, e):
        """Stufe 3: nacktes mpv im Vollbild (wie vor dem eigenen Player), mit Hardware-Decoding."""
        args = ["mpv", "--fs", "--force-window=immediate", "--keep-open=no",
                f"--title=TV · {e['name']}", "--cache=yes", "--demuxer-max-bytes=64MiB", "--hwdec=auto-safe",
                "--network-timeout=10",           # ohne stream-lavf-o=reconnect: bremst HLS-Sender aus (s. Player)
                "--ytdl=no"]
        if os.environ.get("VS_WEAK", "1" if os.uname().machine in ("i386", "i486", "i586", "i686") else "0") == "1":
            # schwache Hardware (32 Bit, wie im Player): Xv statt OpenGL, Software-Decoding, niedrigste Qualitaet
            args = [a for a in args if not a.startswith("--hwdec=")] + [
                "--hwdec=no", "--vo=xv,x11", "--hls-bitrate=min", "--vd-lavc-fast=yes",
                "--vd-lavc-skiploopfilter=nonref", "--sws-scaler=fast-bilinear", "--sws-allow-zimg=no"]
        if e.get("ref"):
            args.append(f"--referrer={e['ref']}")
        if e.get("ua"):
            args.append(f"--user-agent={e['ua']}")
        args.append(e["url"])
        APPS.close("media")
        APPS.close("ytlight")
        APPS.close("tv")
        APPS.start("tv", args)
        self.raw = True
        proc = APPS._get("tv")
        if proc:
            threading.Thread(target=self._watch_raw, args=(e, proc), daemon=True).start()

    def _watch_raw(self, e, proc):
        t0 = time.monotonic()
        rc = proc.wait()
        if rc not in (0, -signal.SIGTERM, -signal.SIGKILL) and time.monotonic() - t0 < 30:
            self.failed = {"key": e["key"], "name": e["name"], "t": time.time()}
            self.mark_broken(e["key"], f"mpv-Code {rc}")


def tvfavs_load():
    try:
        return json.loads(TVFAVS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def tvrecent_load():
    try:
        d = json.loads(TVRECENT.read_text(encoding="utf-8"))
        return [x for x in d if isinstance(x, dict) and x.get("key") and x.get("url")]
    except (OSError, ValueError):
        return []


def tvrecent_save(items):
    try:
        tmp = TVRECENT.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(TVRECENT)
    except OSError as e:
        log("tvrecent.json:", e)


def tvfavs_save(items):
    tmp = TVFAVS.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TVFAVS)


TV = IPTV()


# ---------------------------------------------------------------------------
#  EPG: Elektronischer Programmführer für TV-Sender
# ---------------------------------------------------------------------------
EPG_CONFIG_FILE = Path("/usr/local/share/voidstation/epg-url")


class EPGManager:
    """Verwaltet Programmvorschau (EPG) für TV-Sender."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cache_file = CACHE / "epg.json"
        self.data = {}
        self.name_map = {}
        self.loaded_at = 0.0
        self.last_attempt = 0.0
        self.loading = False
        # Beim Start nur den kompakten JSON-Cache lesen (dauert wenige Millisekunden)
        self._load_cache()

    @staticmethod
    def _get_url():
        env = os.environ.get("VOIDSTATION_EPG_URL", "").strip()
        if env:
            return env
        for p in (EPG_CONFIG_FILE, BASE / "epg-url"):
            try:
                if p.exists():
                    u = p.read_text(encoding="utf-8").strip()
                    if u:
                        return u
            except OSError:
                pass
        return ""

    def ensure(self):
        url = self._get_url()
        has_local = any(p.exists() for p in (CACHE / "epg.xml.gz", CACHE / "epg.xml", BASE / "epg.xml.gz", BASE / "epg.xml"))
        if not url and not has_local:
            return
        now = time.time()
        with self.lock:
            if self.loading:
                return
            # Daten noch aktuell (< 24 h)?
            if self.data and (now - self.loaded_at < 86400):
                return
            # Nach einem Fehler/Versuch mindestens 1 Stunde warten
            if now - self.last_attempt < 3600:
                return
            self.loading = True
            self.last_attempt = now
        threading.Thread(target=self._fetch_and_load, daemon=True).start()

    def _fetch_and_load(self):
        try:
            url = self._get_url()
            if url:
                day = 86400
                is_gz = url.split("?")[0].endswith(".gz")
                xml_dest = CACHE / ("epg.xml.gz" if is_gz else "epg.xml")
                try:
                    fetch(url, xml_dest, day)
                except Exception as e:
                    log("EPG Download fehlgeschlagen:", e)

            # XMLTV im Hintergrund parsen und in epg.json cachen
            self._parse_xml_source()
        finally:
            with self.lock:
                self.loading = False

    @staticmethod
    def _parse_ts(s):
        s = s.strip()
        if not s:
            return 0
        from datetime import datetime, timezone
        try:
            if " " in s:
                return datetime.strptime(s, "%Y%m%d%H%M%S %z").timestamp()
            return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return 0

    def _load_cache(self):
        for p in (self.cache_file, BASE / "epg.json"):
            if p.exists():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    with self.lock:
                        self.data = raw.get("programs", raw)
                        self.name_map = raw.get("name_map", {})
                        self.loaded_at = float(raw.get("loaded_at", p.stat().st_mtime))
                    return True
                except Exception as e:
                    log("EPG Cache nicht lesbar:", e)
        return False

    def _parse_xml_source(self):
        """Parst XMLTV im Hintergrund und schreibt eine kleine epg.json (nur jetzt bis +24h)."""
        import gzip
        import xml.etree.ElementTree as ET

        source_file = None
        for p in (CACHE / "epg.xml.gz", CACHE / "epg.xml", BASE / "epg.xml.gz", BASE / "epg.xml"):
            if p.exists():
                source_file = p
                break

        if not source_file:
            return

        try:
            with open(source_file, "rb") as test_f:
                magic = test_f.read(2)
            is_gz = (magic == b"\x1f\x8b")

            f = gzip.open(source_file, "rb") if is_gz else open(source_file, "rb")
            data = {}
            name_map = {}
            now_ts = time.time()
            cutoff_past = now_ts - 7200       # 2 Stunden Puffer in die Vergangenheit
            cutoff_future = now_ts + 86400    # bis +24 Stunden vorausschauend

            try:
                for event, elem in ET.iterparse(f, events=("end",)):
                    if elem.tag == "channel":
                        cid = elem.get("id", "").strip()
                        dn_el = elem.find("display-name")
                        if cid and dn_el is not None and dn_el.text:
                            n_clean = dn_el.text.strip().lower()
                            name_map[n_clean] = cid
                            name_map[n_clean.replace(" ", "")] = cid
                            name_map[n_clean.replace(" hd", "").strip()] = cid
                        elem.clear()
                    elif elem.tag == "programme":
                        ch = elem.get("channel", "").strip()
                        s_str = elem.get("start", "").strip()
                        e_str = elem.get("stop", "").strip()
                        s_ts = self._parse_ts(s_str)
                        e_ts = self._parse_ts(e_str)
                        # Nur relevante Sendungen speichern -> kleine epg.json
                        if s_ts and e_ts and e_ts >= cutoff_past and s_ts <= cutoff_future:
                            t_el = elem.find("title")
                            d_el = elem.find("desc")
                            title = t_el.text if t_el is not None and t_el.text else ""
                            desc = d_el.text if d_el is not None and d_el.text else ""
                            data.setdefault(ch, []).append({"start": s_ts, "end": e_ts, "title": title, "desc": desc})
                        elem.clear()
            finally:
                f.close()

            with self.lock:
                self.data = data
                self.name_map = name_map
                self.loaded_at = now_ts

            # Kompakte epg.json schreiben (atomarer Tmp-Write)
            try:
                CACHE.mkdir(parents=True, exist_ok=True)
                payload = json.dumps({"loaded_at": now_ts, "name_map": name_map, "programs": data}, ensure_ascii=False)
                tmp = self.cache_file.with_suffix(".tmp")
                tmp.write_text(payload, encoding="utf-8")
                tmp.replace(self.cache_file)
            except Exception as e:
                log("EPG Cache schreiben fehlgeschlagen:", e)

        except Exception as e:
            log("EPG XML-Parsing fehlgeschlagen:", e)

    def get_program(self, channel_id, channel_name=""):
        self.ensure()
        with self.lock:
            prog = self.data.get(channel_id)
            if not prog and channel_name:
                clean_name = channel_name.strip().lower()
                mapped = (self.name_map.get(clean_name) or
                          self.name_map.get(clean_name.replace(" ", "")) or
                          self.name_map.get(clean_name.replace(" hd", "").strip()))
                if mapped:
                    prog = self.data.get(mapped)
            if not prog and channel_name:
                prog = self.data.get(channel_name)

        now_ts = time.time()
        if prog and isinstance(prog, list):
            current, next_p = None, None
            for p in prog:
                start = p.get("start", 0)
                end = p.get("end", 0)
                if start <= now_ts < end:
                    dur = max(1, end - start)
                    progress = min(100, max(0, int((now_ts - start) / dur * 100)))
                    current = {
                        "title": p.get("title", ""),
                        "desc": p.get("desc", ""),
                        "start": time.strftime("%H:%M", time.localtime(start)),
                        "stop": time.strftime("%H:%M", time.localtime(end)),
                        "end": time.strftime("%H:%M", time.localtime(end)),
                        "progress": progress
                    }
                elif now_ts < start and not next_p:
                    next_p = {
                        "title": p.get("title", ""),
                        "start": time.strftime("%H:%M", time.localtime(start)),
                        "stop": time.strftime("%H:%M", time.localtime(end)),
                        "end": time.strftime("%H:%M", time.localtime(end))
                    }
            if current:
                return {"current": current, "next": next_p}
        return None


EPG = EPGManager()


# ---------------------------------------------------------------------------
#  Videos & Musik: Mediathek fuer den Player (~/share/Videos, ~/share/Musik, USB-Laufwerke)
# ---------------------------------------------------------------------------
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".wmv",
             ".flv", ".ogv", ".3gp", ".vob", ".divx"}
EMBED_EXT = {".mp3", ".m4a", ".flac"}             # Cover/Tags in die Datei schreiben (ffmpeg, ohne Neukodierung)
AUDIO_EXT = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma", ".ape", ".mka", ".wv", ".aiff", ".alac"}
COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg", "front.png", "albumart.jpg", "album.jpg")
RESUME = BASE / "resume.json"


def natural_key(name):
    """„Folge 2“ vor „Folge 10“: Zahlen als Zahlen sortieren, ohne Gross-/Kleinschreibung."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", tv_fold(name))]


class DvdDrive:
    """DVD-Laufwerk fuer "Videos & Musik": Disc erkennen (ioctl CDROM_DRIVE_STATUS – laeuft die Disc nicht an),
    Titel lesen (lsdvd, einmal je Disc, im Hintergrund), auswerfen. Abgespielt wird mit mpv: dvd://<n>/<geraet>,
    mpv zaehlt Titel ab 0, lsdvd ab 1. DVD-Menues kann mpv nicht – deshalb die Titelliste (Serien: ein Titel je Folge).
    Kopiergeschuetzte Kauf-DVDs entschluesselt libdvdread ueber libdvdcss (bei Void eine Abhaengigkeit von mpv)."""
    CDROM_DRIVE_STATUS = 0x5326
    CDS_DISC_OK = 4
    MIN_TITLE = 60                                       # kuerzere Titel (Warnhinweise, Logos, Menues) ausblenden

    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}                                  # geraet -> {"key": (status, groesse), "info": ..., "busy": bool}

    @staticmethod
    def devices():
        return sorted(str(p) for p in Path("/dev").glob("sr[0-9]*"))

    def _status(self, dev):
        import fcntl
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            return -1
        try:
            return fcntl.ioctl(fd, self.CDROM_DRIVE_STATUS, 0x7fffffff)
        except OSError:
            return -1
        finally:
            os.close(fd)

    @staticmethod
    def _size(dev):
        try:
            return int(Path(f"/sys/block/{Path(dev).name}/size").read_text().strip() or 0)
        except (OSError, ValueError):
            return 0

    @staticmethod
    def parse(text):
        """lsdvd -Ox (XML) -> {"label", "titles": [{ix, length, aspect, format, chapters, audio, subs}], "longest"}.
        Mit regulaeren Ausdruecken statt XML-Parser: lsdvd schreibt Disc-Namen ungefiltert."""
        def tag(name, block, default=""):
            m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
            return html_unescape(m.group(1).strip()) if m else default
        head = text.split("<track>", 1)[0]
        titles = []
        for block in re.findall(r"<track>(.*?)</track>", text, re.S):
            try:
                ix, length = int(tag("ix", block, "0")), float(tag("length", block, "0"))
            except ValueError:
                continue
            if ix > 0:
                titles.append({"ix": ix, "length": round(length, 1), "aspect": tag("aspect", block),
                               "format": tag("format", block), "chapters": block.count("<chapter>"),
                               "audio": block.count("<audio>"), "subs": block.count("<subp>")})
        longest = max(titles, key=lambda t: t["length"])["ix"] if titles else 0
        label = tag("title", head).replace("_", " ").strip()
        return {"label": "" if label.lower() == "unknown" else label, "titles": titles, "longest": longest}

    def _scan(self, dev, key):
        info = None
        exe = shutil.which("lsdvd")
        if exe:
            r = run([exe, "-Ox", "-v", "-a", "-c", "-s", dev], timeout=90)
            if r and r.stdout.strip():
                info = self.parse(r.stdout)
            else:
                log("DVD: lsdvd ohne Ergebnis", dev, (r.stderr.strip().splitlines() or [""])[-1][:200] if r else "")
        else:
            log("DVD: lsdvd fehlt")
        with self.lock:
            c = self.cache.get(dev)
            if c and c["key"] == key:
                c.update(info=info or {"label": "", "titles": [], "longest": 0}, busy=False)
        if info:
            log(f"DVD {dev}: „{info['label']}“, {len(info['titles'])} Titel")

    def discs(self):
        """Eingelegte Discs: [{dev, label, ready, n}]; liest neue Discs im Hintergrund ein."""
        out = []
        for dev in self.devices():
            st = self._status(dev)
            with self.lock:
                if st != self.CDS_DISC_OK:
                    self.cache.pop(dev, None)
                    continue
                key = (st, self._size(dev))
                c = self.cache.get(dev)
                if not c or c["key"] != key:
                    c = self.cache[dev] = {"key": key, "info": None, "busy": True}
                    threading.Thread(target=self._scan, args=(dev, key), daemon=True).start()
                info = c["info"]
            out.append({"dev": dev, "label": (info or {}).get("label", ""), "ready": info is not None,
                        "n": len(self.shown(info)) if info else 0})
        return out

    def shown(self, info):
        t = [x for x in (info or {}).get("titles", []) if x["length"] >= self.MIN_TITLE]
        return t or (info or {}).get("titles", [])

    def listing(self, dev):
        if dev not in self.devices():
            raise FileNotFoundError(dev)
        for _ in range(180):                             # Disc wird gerade gelesen: bis zu 90 s warten
            self.discs()
            with self.lock:
                c = self.cache.get(dev)
                if not c:
                    raise FileNotFoundError("keine Disc im Laufwerk")
                if c["info"] is not None:
                    info = c["info"]
                    break
            time.sleep(0.5)
        else:
            raise FileNotFoundError("Disc nicht lesbar")
        titles = self.shown(info)
        items = []
        if len(titles) > 1:
            items.append({"kind": "dvdall", "path": f"dvd://{titles[0]['ix'] - 1}/{dev}", "title": "", "n": len(titles)})
        for t in titles:
            items.append({"kind": "dvdtitle", "path": f"dvd://{t['ix'] - 1}/{dev}", "ix": t["ix"], "dur": t["length"],
                          "aspect": t["aspect"], "chapters": t["chapters"], "main": t["ix"] == info["longest"],
                          "title": "", "name": f"{t['ix']}", "thumb": ""})
        items.append({"kind": "eject", "path": f"dvd:{dev}", "title": ""})
        return {"path": f"dvd:{dev}", "name": info["label"], "parent": "", "items": items, "select": "",
                "audio": 0, "coversPending": 0, "dvd": dev}

    def eject(self, dev):
        if dev not in self.devices():
            raise ValueError("kein Laufwerk")
        with self.lock:
            self.cache.pop(dev, None)
        r = run(["eject", dev], timeout=20)
        return bool(r and r.returncode == 0)


DVD = DvdDrive()


class MediaLib:
    """Ordner auflisten, Vorschaubilder (ffmpegthumbnailer, zwischengespeichert), Weiterschauen (resume.json).
    Nur innerhalb von ~/share und eingehaengten Laufwerken unter /run/media und /media."""
    THUMBS = Path.home() / ".cache" / "voidstation" / "thumbs"

    def __init__(self):
        self.lock = threading.Lock()
        self.sem = threading.Semaphore(2)          # hoechstens zwei Vorschaubilder gleichzeitig (schwache Geraete)
        self.thumbnailer = shutil.which("ffmpegthumbnailer")
        self.mixed_cache = {}                      # Ordner -> (mtime, gemischt?)
        self.tags_cache = {}                       # Datei -> (mtime, Tags)
        self.art_done = {}                         # Datei -> (mtime, Kennung des Bildes) – Bild steht fest

    @staticmethod
    def share():
        return Path.home() / "share"

    @staticmethod
    def drives():
        out = []
        try:
            lines = Path("/proc/mounts").read_text().splitlines()
        except OSError:
            lines = []
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            mp = parts[1].replace("\\040", " ")
            if mp.startswith(("/run/media/", "/media/")) and mp.count("/") >= 2 and os.path.isdir(mp):
                out.append(mp)
        return sorted(set(out))

    def allowed_roots(self):
        return [self.share().resolve()] + [Path(d).resolve() for d in self.drives()]

    def resolve(self, path):
        try:
            p = Path(path).expanduser().resolve()
        except (OSError, RuntimeError):
            return None
        for r in self.allowed_roots():
            if p == r or r in p.parents:
                return p
        return None

    @staticmethod
    def own_cover(folder):
        """Cover eines Ordners: Bilddatei im Ordner (cover.jpg & Co.) oder heruntergeladenes im Zwischenspeicher."""
        for n in COVER_NAMES:
            c = folder / n
            if c.is_file():
                return c
        c = COVERS.cache_file(folder)
        return c if c.is_file() else None

    def cover_url(self, folder, depth=1):
        """Bild fuer einen Ordner; ohne eigenes das des ersten Unterordners mit Cover (Interpret -> erstes Album)."""
        c = self.own_cover(folder)
        if c is None and depth > 0:
            for sub in self._subdirs(folder)[:40]:
                c = self.own_cover(sub)
                if c is not None:
                    break
        if c is None:
            return ""
        try:
            m = int(c.stat().st_mtime)
        except OSError:
            m = 0
        if c.parent == COVERS.CACHE:
            return "/api/media/thumb?cover=" + urllib.parse.quote(str(c.name)) + f"&m={m}"
        return "/api/media/thumb?path=" + urllib.parse.quote(str(c)) + f"&m={m}"

    def thumb_url(self, p, kind, st=None):
        if kind == "video" and self.thumbnailer:
            m = int(st.st_mtime) if st else 0
            return "/api/media/thumb?path=" + urllib.parse.quote(str(p)) + f"&m={m}"
        if kind == "dir":
            return self.cover_url(p)
        if kind == "audio":                        # eigenes Bild des Titels, sonst das des Albums (art())
            c = self.own_cover(p.parent)
            try:
                cm = int(c.stat().st_mtime) if c is not None else 0
            except OSError:
                cm = 0
            m = int(st.st_mtime) if st else 0
            done = self.art_done.get(str(p))
            r = done[1] if done and st and done[0] == st.st_mtime else 0
            return "/api/media/thumb?art=" + urllib.parse.quote(str(p)) + f"&m={m}&c={cm}&r={r}"
        return ""

    def mixed(self, folder):
        """Liegen in diesem Ordner Titel aus verschiedenen Alben (z. B. alles lose in share/Musik)? Dann gibt es kein
        gemeinsames Cover – jeder Titel zeigt sein eigenes. Stichprobe ueber bis zu 8 Dateien, gemerkt bis sich der
        Ordner aendert. Ohne Album-Tags zaehlen verschiedene Interpreten."""
        folder = Path(folder)
        try:
            mt = folder.stat().st_mtime
        except OSError:
            return False
        hit = self.mixed_cache.get(str(folder))
        if hit and hit[0] == mt:
            return hit[1]
        files = COVERS._audio_files(folder)
        if len(files) < 2:
            res = False
        else:
            step = max(1, len(files) // 8)
            albums, artists, bare = set(), set(), 0
            for f in files[::step][:8]:
                t = COVERS._tags(f)
                if t.get("album"):
                    albums.add(t["album"].casefold())
                a = t.get("album_artist") or t.get("albumartist") or t.get("artist") or ""
                if a:
                    artists.add(a.casefold())
                if not t.get("album") and not a:
                    bare += 1
            # Titel mit Tags neben solchen ganz ohne: eher eine lose Sammlung als ein Album
            res = len(albums) > 1 or (not albums and len(artists) > 1) or (bare > 0 and bool(albums or artists))
        if res:
            self._drop_wrong_cover(folder, files)
        try:
            mt = folder.stat().st_mtime                # _drop_wrong_cover kann den Ordner geaendert haben
        except OSError:
            pass
        self.mixed_cache[str(folder)] = (mt, res)
        return res

    @staticmethod
    def _drop_wrong_cover(folder, files):
        """Fruehere Fassung der Cover-Suche hat in gemischten Ordnern das Bild des ersten Titels als cover.jpg
        abgelegt. Geloescht wird nur, was Byte fuer Byte genau dieses Bild ist – eigene Cover bleiben."""
        cands = [folder / "cover.jpg", COVERS.cache_file(folder)]
        cands = [c for c in cands if c.is_file()]
        if not cands or not files:
            return
        img = COVERS._embedded(files[0])
        if not img:
            return
        for c in cands:
            try:
                if c.stat().st_size == len(img) and c.read_bytes() == img:
                    c.unlink()
                    log("Cover: falsches Ordner-Cover entfernt (gemischter Ordner):", c)
            except OSError:
                pass

    def track_tags(self, p, st=None):
        st = st or p.stat()
        hit = self.tags_cache.get(str(p))
        if hit and hit[0] == st.st_mtime:
            return hit[1]
        t = COVERS._tags(p)
        self.tags_cache[str(p)] = (st.st_mtime, t)
        return t

    def art_file(self, p, online=False):
        """Bild zu einem Musiktitel, der Reihe nach:
        1. in die Datei eingebettetes Cover (einmal herausgeholt, zwischengespeichert)
        2. Cover des Ordners – ausser der Ordner mischt verschiedene Alben
        3. online gefundenes Cover zu Interpret + Album bzw. Interpret + Titel (Zwischenspeicher, gilt fuer alle
           Titel desselben Albums) – nur mit online=True wird gesucht (Hintergrund, CoverFetcher)
        Rueckgabe (Pfad oder None, fertig): fertig=False heisst, eine Suche im Netz koennte noch etwas bringen."""
        st = p.stat()
        key = hashlib.sha1(f"art:{p}:{int(st.st_mtime)}:{st.st_size}".encode()).hexdigest()
        out, none = self.THUMBS / f"{key}.jpg", self.THUMBS / f"{key}.none"
        if not out.exists() and not none.exists():
            self.THUMBS.mkdir(parents=True, exist_ok=True)
            with self.sem:
                if not out.exists() and not none.exists():
                    img = COVERS._embedded(p)
                    try:
                        if img:
                            tmp = out.with_name(f"{key}.{threading.get_ident()}.tmp.jpg")
                            tmp.write_bytes(img)
                            tmp.replace(out)
                        else:
                            none.touch()
                    except OSError:
                        pass
        if out.exists():
            return self._art_found(p, st, out)
        if not self.mixed(p.parent):
            c = self.own_cover(p.parent)
            if c is not None:
                return self._art_found(p, st, c)
        ac = COVERS.track_cache(p, self.track_tags(p, st))
        if ac is None:                                 # weder Tags noch brauchbarer Dateiname
            return self._art_found(p, st, None)
        if ac.is_file():
            return self._art_found(p, st, ac)
        if COVERS.track_missed(ac):
            return self._art_found(p, st, None)
        if online:
            ok = COVERS.fetch_track(p, self.track_tags(p, st), ac)
            if ok is None:                             # kein Netz – offen lassen
                return None, False
            return self._art_found(p, st, ac if ok else None)
        return None, False

    def _art_found(self, p, st, f):
        try:
            tag = int(f.stat().st_mtime) % 100000 + 1 if f is not None else 0
        except OSError:
            tag = 0
        self.art_done[str(p)] = (st.st_mtime, tag)
        return f, True

    def write_art(self, p, cover):
        """Cover und fehlende Tags in die Datei schreiben (MP3, M4A, FLAC) – nur wenn etwas fehlt, vorhandene Tags
        bleiben unangetastet. Ueber eine Kopie im selben Ordner, die vor dem Ersetzen geprueft wird; Aenderungszeit
        und Rechte bleiben. Schreibgeschuetzte Ordner (USB-Stick, fremde Freigaben) werden still uebersprungen."""
        if p.suffix.lower() not in EMBED_EXT or not os.access(p.parent, os.W_OK) or not os.access(p, os.W_OK):
            return False
        ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ff or not fp:
            return False
        st = p.stat()
        if cover is not None and cover.parent == self.THUMBS:  # Bild steckt schon in der Datei
            cover = None
        tags = self.track_tags(p, st)
        have = {k for k, v in tags.items() if v}
        if "album_artist" in have or "albumartist" in have:
            have.add("artist")
        # Quelle fuer fehlende Tags: gefundene Aufnahme (MusicBrainz), sonst der Dateiname "Interpret - Titel"
        meta = {}
        ac = COVERS.track_cache(p, tags)
        if ac is not None and ac.with_suffix(".json").is_file():
            try:
                meta = json.loads(ac.with_suffix(".json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
        artist, _album, title = COVERS._track_names(p, tags)
        meta["artist"] = meta.get("artist") or artist
        meta["title"] = meta.get("title") or title
        add = {k: str(meta.get(k) or "").strip() for k in ("artist", "title", "album", "date", "track")}
        add = {k: v for k, v in add.items() if v and k not in have}
        if cover is None and not add:
            return False
        ours = set(filter(None, (tags.get("voidstation") or "").split(","))) | set(add) | ({"cover"} if cover is not None else set())
        args = []
        if cover is not None:
            args += ["-i", str(cover), "-map", "0:a", "-map", "1:0", "-disposition:v:0", "attached_pic",
                     "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
        else:
            args += ["-map", "0"]
        for k, v in add.items():
            args += ["-metadata", f"{k}={v}"]
        args += ["-metadata", "VOIDSTATION=" + ",".join(sorted(ours))]   # was von VoidStation stammt (Cover neu suchen)
        if not self._rewrite(p, args):
            return False
        parts = (["Cover"] if cover is not None else []) + ([", ".join(add)] if add else [])
        log("In Datei geschrieben:", p.name, "–", " + ".join(parts))
        return True

    def _rewrite(self, p, args):
        """Datei mit ffmpeg neu schreiben (ohne Neukodierung): Kopie im selben Ordner, Pruefung (Ton da, Laenge
        gleich), dann ersetzen; Aenderungszeit und Rechte bleiben. args: weitere Eingaben, -map und -metadata."""
        ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ff or not fp:
            return False
        st = p.stat()
        tmp = p.with_name(f".{p.stem}.vs-tmp{p.suffix}")
        cmd = [ff, "-v", "error", "-y", "-i", str(p)] + args + ["-c", "copy", "-map_metadata", "0"]
        if p.suffix.lower() == ".mp3":
            cmd += ["-id3v2_version", "3", "-write_id3v1", "1"]
        if p.suffix.lower() == ".m4a":
            cmd += ["-movflags", "use_metadata_tags"]
        cmd.append(str(tmp))
        try:
            r = run(cmd, timeout=120)
            ok = bool(r and r.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 1000)
            if ok:                                     # Probe: Ton noch da, Laenge unveraendert
                def dur(f):
                    q = run([fp, "-v", "error", "-select_streams", "a:0", "-show_entries", "format=duration:stream=codec_type",
                             "-of", "json", str(f)], timeout=30)
                    d = json.loads(q.stdout) if q and q.returncode == 0 else {}
                    return float((d.get("format") or {}).get("duration") or 0), bool(d.get("streams"))
                d0, _ = dur(p)
                d1, audio = dur(tmp)
                ok = audio and d1 > 0 and abs(d1 - d0) < 1.5
            if not ok:
                log("Cover/Tags: Datei nicht geaendert (Pruefung fehlgeschlagen):", p.name)
                return False
            shutil.copymode(p, tmp)
            os.utime(tmp, (st.st_atime, st.st_mtime))
            os.replace(tmp, p)
        except Exception as e:  # noqa: BLE001
            log("Cover/Tags: Datei nicht geaendert:", p.name, e)
            return False
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        self.tags_cache.pop(str(p), None)
        return True

    def reset_art(self, p):
        """Cover neu suchen: Was VoidStation selbst in die Datei geschrieben hat (Kennzeichen VOIDSTATION; bei
        Dateien aus der ersten Fassung ohne Kennzeichen: Tags, die genau der damals gefundenen Aufnahme entsprechen),
        wieder herausnehmen und Zwischenspeicher wie "nichts gefunden" fuer diesen Titel vergessen."""
        tags = COVERS._tags(p)
        ours = set(filter(None, (tags.get("voidstation") or "").split(",")))
        if not ours and COVERS._embedded(p):           # erste Fassung schrieb immer Cover + Tags zusammen
            for c in COVERS.track_caches(p, tags):
                try:
                    meta = json.loads(c.with_suffix(".json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                same = {k for k in ("artist", "title", "album", "date", "track") if meta.get(k) and tags.get(k) == str(meta[k])}
                if not {"artist", "title"} <= same:
                    continue
                # Woher die Suche kam, sagt, was schon vorher in der Datei stand: geraten (nur Dateiname) -> alle Tags
                # von uns; ueber Interpret + Titel bzw. + Album -> diese Tags sind die eigenen der Datei
                native = {"guess": set(), "title": {"artist", "title"}, "album": {"artist", "album"}}[COVERS.cache_kind(p, tags, c)]
                ours = (same - native) | {"cover"}
                break
        orig = {k: v for k, v in tags.items() if k not in ours}
        for c in set(COVERS.track_caches(p, tags)) | set(COVERS.track_caches(p, orig)):
            COVERS.forget(c)
        if ours and p.suffix.lower() in EMBED_EXT and os.access(p.parent, os.W_OK):
            args = ["-map", "0:a" if "cover" in ours else "0"]
            for k in sorted(ours - {"cover"}):
                args += ["-metadata", f"{k}="]
            args += ["-metadata", "VOIDSTATION="]
            if self._rewrite(p, args):
                log("Cover neu suchen:", p.name, "– entfernt:", ", ".join(sorted(ours)))
        self.tags_cache.pop(str(p), None)
        self.art_done.pop(str(p), None)

    def art_pending(self, p):
        """Ist fuer diesen Titel noch offen, welches Bild er bekommt? (billig, ohne ffmpeg/ffprobe)"""
        try:
            st = p.stat()
        except OSError:
            return False
        done = self.art_done.get(str(p))
        return not (done and done[0] == st.st_mtime)

    def art(self, path):
        """Bild zu einem Musiktitel fuer /api/media/thumb?art= (siehe art_file). Fehlt eins und koennte es online
        eins geben, sucht der CoverFetcher im Hintergrund danach – die Kachel bzw. der Player fragen spaeter nochmal."""
        p = self.resolve(path)
        if not p or not p.is_file() or p.suffix.lower() not in AUDIO_EXT:
            return None
        f, final = self.art_file(p)
        if f is None:
            if not final:
                COVERS.add_track(p)
            return None
        try:
            return f.read_bytes(), MIME.get(f.suffix.lower(), "image/jpeg")
        except OSError:
            return None

    @staticmethod
    def title(name):
        stem = name.rsplit(".", 1)[0] if "." in name else name
        return re.sub(r"[._]+", " ", stem).strip() or name

    def resume_load(self):
        try:
            d = json.loads(RESUME.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def resume_set(self, path, pos, dur):
        p = self.resolve(path)
        if not p:
            raise ValueError("Pfad nicht erlaubt")
        try:
            pos, dur = float(pos), float(dur)
        except (TypeError, ValueError):
            raise ValueError("ungueltige Position")
        with self.lock:
            d = self.resume_load()
            if dur > 0 and 60 <= pos < dur * 0.95 and dur - pos > 60:
                d[str(p)] = {"pos": round(pos, 1), "dur": round(dur, 1), "t": int(time.time())}
            else:                                      # kaum angesehen oder fast fertig: nichts merken
                d.pop(str(p), None)
            if len(d) > 300:
                for k in sorted(d, key=lambda k: d[k].get("t", 0))[:len(d) - 300]:
                    del d[k]
            tmp = RESUME.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(RESUME)

    def entry(self, p, res=None):
        try:
            st = p.stat()
        except OSError:
            return None
        if p.is_dir():
            kind = "dir"
        else:
            ext = p.suffix.lower()
            kind = "video" if ext in VIDEO_EXT else "audio" if ext in AUDIO_EXT else None
            if not kind:
                return None
        e = {"name": p.name, "title": p.name if kind == "dir" else self.title(p.name), "path": str(p), "kind": kind,
             "mtime": int(st.st_mtime), "thumb": self.thumb_url(p, kind, st)}
        if kind != "dir":
            e["bytes"] = st.st_size
            r = (res or {}).get(str(p))
            if r:
                e["resume"] = {"pos": r.get("pos", 0), "dur": r.get("dur", 0)}
        return e

    def roots(self):
        share = self.share()
        out = [{"kind": "videos", "path": str(share / "Videos"), "title": "", "thumb": ""},
               {"kind": "music", "path": str(share / "Musik"), "title": "", "thumb": ""}]
        for d in self.drives():
            out.append({"kind": "drive", "path": d, "title": os.path.basename(d), "thumb": ""})
        for d in DVD.discs():                          # eingelegte DVD (Titel liest der Launcher im Hintergrund)
            out.append({"kind": "dvd", "path": "dvd:" + d["dev"], "title": d["label"], "ready": d["ready"], "n": d["n"],
                        "thumb": ""})
        res = self.resume_load()
        cont = []
        for path, r in sorted(res.items(), key=lambda kv: -kv[1].get("t", 0)):
            p = self.resolve(path)
            if p and p.is_file():
                e = self.entry(p, res)
                if e:
                    e["kind"] = "resume"
                    cont.append(e)
            if len(cont) >= 12:
                break
        return {"roots": out, "resume": cont}

    def listdir(self, path):
        if str(path).startswith("dvd:") and not str(path).startswith("dvd://"):
            return DVD.listing(str(path)[4:])
        p = self.resolve(path)
        if not p:
            raise ValueError("Ordner nicht erlaubt")
        select = ""
        if p.is_file():
            select, p = str(p), p.parent
        if not p.is_dir():
            if p in (self.share() / "Videos", self.share() / "Musik"):
                p.mkdir(parents=True, exist_ok=True)
            else:
                raise FileNotFoundError(str(p))
        res = self.resume_load()
        dirs, files = [], []
        try:
            names = sorted(os.listdir(p), key=natural_key)
        except OSError as e:
            raise FileNotFoundError(str(e))
        for n in names[:3000]:
            if n.startswith("."):
                continue
            e = self.entry(p / n, res)
            if not e:
                continue
            (dirs if e["kind"] == "dir" else files).append(e)
        roots = self.allowed_roots()
        parent = "" if p in roots or p.parent in (Path("/run/media"), Path("/media")) else str(p.parent)
        if p.parent == self.share().resolve():
            parent = ""                              # ~/share/Videos und ~/share/Musik: zurueck zur Startseite
        audio = sum(1 for f in files if f["kind"] == "audio")
        # Cover automatisch laden: dieser Ordner (hat er Musik) und die Unterordner ohne Bild
        pending = 0
        if COVERS.auto():
            if audio and MediaLib.own_cover(p) is None:
                pending += COVERS.add(p)
            for d in dirs[:60]:                    # auch Interpreten-Ordner, die schon das Bild eines Albums zeigen
                pending += COVERS.add(Path(d["path"]), deep=True)
            for f in files[:400]:                  # Titel ohne festes Bild (lose Sammlungen, Ordner ohne Cover)
                if f["kind"] == "audio" and MEDIA.art_pending(Path(f["path"])):
                    pending += COVERS.add_track(Path(f["path"]))
        return {"path": str(p), "name": p.name, "parent": parent, "items": dirs + files, "select": select,
                "audio": audio, "coversPending": pending or COVERS.busy_for(p)}

    def _subdirs(self, d):
        try:
            with os.scandir(d) as it:
                ds = [e for e in it if not e.name.startswith(".") and e.is_dir(follow_symlinks=False)]
        except OSError:
            return []
        return [Path(e.path) for e in sorted(ds, key=lambda e: natural_key(e.name))]

    def _preorder(self, root, limit=20000):
        """Alle Ordner unter root in der Reihenfolge der Mediathek (Ordner vor ihren Unterordnern, natuerlich sortiert)."""
        stack, n = [root], 0
        while stack and n < limit:
            d = stack.pop()
            n += 1
            yield d
            stack.extend(reversed(self._subdirs(d)))

    def next_folder(self, path):
        """Naechster Ordner mit Musik nach path – wie "weiter mit dem naechsten Ordner" beim MP3-Player: zuerst die
        Unterordner, dann die Nachbarn, dann weiter oben (Interpret A/Album 2 -> Interpret B/Album 1). Bleibt in
        share/Musik bzw. share/Videos oder auf dem Laufwerk. None am Ende."""
        p = self.resolve(path)
        if not p or not p.is_dir():
            raise ValueError("Ordner nicht erlaubt")
        root = next((r for r in self.allowed_roots() if p == r or r in p.parents), None)
        share = self.share().resolve()
        if root == share and p != share:
            root = share / p.relative_to(share).parts[0]
        found = False
        for d in self._preorder(root):
            if not found:
                found = d == p
                continue
            res = self.resume_load()
            files = []
            try:
                names = sorted(os.listdir(d), key=natural_key)
            except OSError:
                continue
            for n in names:
                if n.startswith(".") or Path(n).suffix.lower() not in AUDIO_EXT:
                    continue
                e = self.entry(d / n, res)
                if e and e["kind"] == "audio":
                    files.append(e)
            if files:
                return {"path": str(d), "name": d.name, "items": files}
        return None

    def thumb(self, path):
        """Vorschaubild als (Bytes, MIME): Cover-Bilder direkt, Videos ueber ffmpegthumbnailer (Cache)."""
        p = self.resolve(path)
        if not p or not p.is_file():
            return None
        ext = p.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png"):
            return p.read_bytes(), MIME.get(ext if ext != ".jpeg" else ".jpg", "image/jpeg")
        if ext not in VIDEO_EXT or not self.thumbnailer:
            return None
        st = p.stat()
        key = hashlib.sha1(f"{p}:{int(st.st_mtime)}:{st.st_size}".encode()).hexdigest()
        out = self.THUMBS / f"{key}.jpg"
        if not out.exists():
            self.THUMBS.mkdir(parents=True, exist_ok=True)
            with self.sem:
                if not out.exists():                      # inzwischen von einer anderen Anfrage erzeugt?
                    tmp = out.with_name(f"{key}.{threading.get_ident()}.tmp.jpg")
                    r = run([self.thumbnailer, "-i", str(p), "-o", str(tmp), "-s", "480", "-t", "12%", "-q", "7"], timeout=25)
                    if r and r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
                        tmp.replace(out)
                    else:
                        try:
                            tmp.unlink()
                        except OSError:
                            pass
        try:
            return out.read_bytes(), "image/jpeg"
        except OSError:
            return None


MEDIA = MediaLib()


# ---------------------------------------------------------------------------
#  Album-Cover automatisch laden (wie der Scraper in Batocera)
# ---------------------------------------------------------------------------
class CoverFetcher:
    """Fuer Musik-Ordner ohne Bild ein Cover besorgen, im Hintergrund, nacheinander:
    1. eingebettetes Bild der ersten Datei (ffmpeg) – ohne Internet
    2. Interpret + Album aus den Tags (ffprobe), sonst aus den Ordnernamen ("Interpret/Album" oder "Interpret - Album")
    3. MusicBrainz-Suche (Release-Group) -> Cover Art Archive (front-500)
    Gespeichert als cover.jpg im Ordner (sehen auch andere Player); ist der Ordner schreibgeschuetzt (USB-Stick,
    Freigabe), im Zwischenspeicher ~/.cache/voidstation/covers. Nichts gefunden: 30 Tage lang nicht erneut fragen.
    MusicBrainz erlaubt eine Anfrage pro Sekunde und verlangt einen erkennbaren User-Agent."""
    CACHE = Path.home() / ".cache" / "voidstation" / "covers"
    MISSES = CACHE / "misses.json"
    MB = os.environ.get("VS_MB_URL", "https://musicbrainz.org/ws/2/")
    CAA = os.environ.get("VS_CAA_URL", "https://coverartarchive.org/")
    UA = {"User-Agent": "VoidStation/2026 ( https://voidstation.de )", "Accept": "application/json"}

    def __init__(self):
        self.lock = threading.Lock()
        self.queue, self.queued = [], set()
        self.tqueue, self.tqueued = [], set()          # einzelne Titel (Bild je Titel)
        self.refresh = set()                           # Titel, deren Cover neu gesucht werden soll
        self.current = None
        self.stats = {"done": 0, "found": 0, "total": 0}
        self.last_mb = 0.0
        self.offline = False                           # letzte Suche scheiterte am Netz (dann nicht als "nichts da" merken)
        self.last_meta = None                          # Angaben zur zuletzt gefundenen Aufnahme
        self.misses = None
        self.worker = None

    # ---- Einstellungen / Zustand ----
    @staticmethod
    def auto():
        return bool(settings_load().get("covers_auto", True))

    @staticmethod
    def embed():
        """Gefundene Cover und fehlende Tags in die Musikdateien schreiben (Standard aus: aendert eigene Dateien)."""
        return bool(settings_load().get("covers_embed", False))

    def cache_file(self, folder):
        return self.CACHE / (hashlib.sha1(str(folder).encode()).hexdigest()[:16] + ".jpg")

    def _miss_load(self):
        if self.misses is None:
            try:
                self.misses = json.loads(self.MISSES.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.misses = {}
        return self.misses

    def _miss(self, folder):
        d = self._miss_load()
        d[str(folder)] = int(time.time())
        try:
            self.CACHE.mkdir(parents=True, exist_ok=True)
            tmp = self.MISSES.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.MISSES)
        except OSError:
            pass

    def _recent_miss(self, folder):
        t = self._miss_load().get(str(folder))
        return bool(t and time.time() - t < 30 * 86400)

    def status(self):
        with self.lock:
            return dict(self.stats, queue=len(self.queue), tracks=len(self.tqueue), embed=self.embed(),
                        running=self.current is not None or bool(self.queue) or bool(self.tqueue),
                        current=Path(self.current).name if self.current else "", auto=self.auto())

    def busy_for(self, folder):
        """Wird fuer diesen Ordner oder einen direkten Unterordner gerade ein Cover gesucht?"""
        with self.lock:
            items = list(self.queue) + list(self.tqueue) + ([self.current] if self.current else [])
        f = str(folder)
        return sum(1 for q in items if q == f or os.path.dirname(q) == f)

    # ---- Warteschlange ----
    def add(self, folder, deep=False, force=False):
        """Ordner vormerken (deep: Ordner ohne eigene Musik -> seine Unterordner eine Ebene tiefer). Rueckgabe: neu."""
        folder = Path(folder)
        if MediaLib.own_cover(folder) is not None or (not force and self._recent_miss(folder)):
            return 0
        if not self._has_audio(folder):
            if not deep:
                return 0
            return sum(self.add(sub, deep=False, force=force) for sub in MEDIA._subdirs(folder)[:40])
        with self.lock:
            if str(folder) in self.queued:
                return 0
            self.queued.add(str(folder))
            self.queue.append(str(folder))
            self.stats["total"] += 1
            self._start()
        return 1

    def add_track(self, path, force=False):
        """Titel vormerken: eingebettetes Bild pruefen, sonst Cover zu Interpret + Album (oder Titel) im Netz suchen."""
        if not force and not self.auto():
            return 0
        path = str(path)
        with self.lock:
            if path in self.tqueued:
                return 0
            self.tqueued.add(path)
            self.tqueue.append(path)
            self._start()
        return 1

    def _start(self):                                  # unter self.lock aufrufen
        if self.worker is None:                        # der Arbeiter meldet sich unter dem Lock ab (kein Wettlauf)
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def scan(self, root):
        """Ganze Sammlung (z. B. share/Musik) durchgehen – auch Ordner, fuer die es zuletzt nichts gab."""
        with self.lock:
            self.stats = {"done": 0, "found": 0, "total": len(self.queue)}
        n, t = 0, 0
        for d in MEDIA._preorder(Path(root)):
            n += self.add(d, force=True)
            if self.embed():                           # Cover/Tags auch in Dateien von Ordnern, die schon ein Bild haben
                t += sum(self.add_track(f, force=True) for f in self._audio_files(d) if f.suffix.lower() in EMBED_EXT)
        log(f"Cover: {n} Ordner ohne Bild vorgemerkt" + (f", {t} Titel fuer Cover/Tags in den Dateien" if t else ""))
        return n

    @staticmethod
    def _audio_files(folder):
        try:
            names = sorted(os.listdir(folder), key=natural_key)
        except OSError:
            return []
        return [Path(folder) / n for n in names if not n.startswith(".") and Path(n).suffix.lower() in AUDIO_EXT]

    def _has_audio(self, folder):
        return bool(self._audio_files(folder))

    def _run(self):
        while True:
            with self.lock:
                if not self.queue and not self.tqueue:
                    self.current = None
                    self.worker = None
                    return
                track = not self.queue                 # Ordner zuerst: deren Cover gilt oft schon fuer die Titel
                self.current = (self.tqueue if track else self.queue).pop(0)
            if track:
                p = Path(self.current)
                try:
                    with self.lock:
                        fresh = str(p) in self.refresh
                        self.refresh.discard(str(p))
                    if fresh and p.is_file():
                        MEDIA.reset_art(p)
                    if p.is_file():
                        f, _ = MEDIA.art_file(p, online=True)
                        if self.embed():
                            MEDIA.write_art(p, f)
                except Exception as e:  # noqa: BLE001
                    log("Cover:", p.name, e)
                with self.lock:
                    self.tqueued.discard(str(p))
                continue
            folder = Path(self.current)
            try:
                ok = self.fetch(folder)
            except Exception as e:  # noqa: BLE001
                log("Cover:", folder.name, e)
                ok = False
            with self.lock:
                self.queued.discard(str(folder))
                self.stats["done"] += 1
                self.stats["found"] += 1 if ok else 0

    # ---- Suche ----
    def fetch(self, folder):
        if MediaLib.own_cover(folder) is not None:
            return True
        files = self._audio_files(folder)
        if not files:
            return False
        if MEDIA.mixed(folder):                        # verschiedene Alben: jeder Titel zeigt sein eigenes Bild
            self._miss(folder)
            n = sum(self.add_track(f, force=True) for f in files[:400] if MEDIA.art_pending(f))
            log(f"Cover: gemischter Ordner, kein gemeinsames Cover – {folder.name} ({n} Titel einzeln)")
            return False
        img = self._embedded(files[0])
        source = "eingebettet"
        self.offline = False
        if not img:
            artist, album = self._names(folder, files[0])
            img = self._online(artist, album) if album else None
            source = f"MusicBrainz ({artist} – {album})"
        if not img:
            if self.offline:                           # kein Netz: beim naechsten Oeffnen nochmal versuchen
                return False
            self._miss(folder)
            log("Cover: nichts gefunden fuer", folder.name)
            return False
        where = self._save(folder, img)
        log("Cover:", folder.name, "<-", source, "->", where)
        return True

    @staticmethod
    def _embedded(f):
        ff = shutil.which("ffmpeg")
        if not ff:
            return None
        out = Path(tempfile_name("cover", ".jpg"))
        r = run([ff, "-v", "error", "-y", "-i", str(f), "-map", "0:v:0", "-frames:v", "1", "-an", "-vf", "scale='min(800,iw)':-2",
                 str(out)], timeout=20)
        try:
            data = out.read_bytes() if r and r.returncode == 0 and out.exists() and out.stat().st_size > 1000 else None
        finally:
            try:
                out.unlink()
            except OSError:
                pass
        return data

    @staticmethod
    def _tags(f):
        fp = shutil.which("ffprobe")
        if not fp:
            return {}
        r = run([fp, "-v", "error", "-show_entries", "format_tags", "-of", "json", str(f)], timeout=15)
        try:
            tags = json.loads(r.stdout).get("format", {}).get("tags", {}) if r and r.returncode == 0 else {}
        except ValueError:
            tags = {}
        return {str(k).lower(): str(v).strip() for k, v in tags.items()}

    def _names(self, folder, first):
        t = self._tags(first)
        artist = t.get("album_artist") or t.get("albumartist") or t.get("artist") or ""
        album = t.get("album") or ""
        if not album:                                  # Ordnernamen: "Interpret - Album" oder Interpret/Album
            name = re.sub(r"\s*[\[(]\d{4}[)\]]\s*", " ", folder.name).strip()
            if " - " in name:
                a, b = name.split(" - ", 1)
                artist, album = artist or a.strip(), b.strip()
            else:
                album = name
                parent = folder.parent
                if not artist and parent.resolve() not in MEDIA.allowed_roots() and parent.name not in ("Musik", "Music"):
                    artist = parent.name
        return artist, album

    def _mb_get(self, path):
        wait = 1.1 - (time.time() - self.last_mb)
        if wait > 0:
            time.sleep(wait)
        self.last_mb = time.time()
        req = urllib.request.Request(self.MB + path, headers=self.UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def _q(s):
        return '"' + re.sub(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)', r"\\\1", s) + '"'

    def _online(self, artist, album):
        q = "releasegroup:" + self._q(album) + (" AND artist:" + self._q(artist) if artist else "")
        try:
            d = self._mb_get("release-group/?fmt=json&limit=5&query=" + urllib.parse.quote(q))
        except Exception as e:  # noqa: BLE001
            log("Cover: MusicBrainz nicht erreichbar:", e)
            self.offline = True
            return None
        for g in (d.get("release-groups") or [])[:5]:
            if int(g.get("score") or 0) < (90 if artist else 98):
                continue
            try:
                req = urllib.request.Request(self.CAA + f"release-group/{g['id']}/front-500", headers={"User-Agent": self.UA["User-Agent"]})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                if len(data) > 1000:
                    return data
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    log("Cover Art Archive:", e)
            except Exception as e:  # noqa: BLE001
                log("Cover Art Archive:", e)
        return None

    # ---- Cover je Titel (lose Sammlungen, gemischte Ordner) ----
    @staticmethod
    def _norm(x):
        return re.sub(r"\s+", " ", JUNK.sub("", x or "")).strip().casefold()

    def _track_names(self, p, tags):
        """Interpret, Album, Titel aus den Tags; fehlen sie, aus dem Dateinamen ("01 - Interpret - Titel")."""
        artist = tags.get("album_artist") or tags.get("albumartist") or tags.get("artist") or ""
        album, title = tags.get("album") or "", tags.get("title") or ""
        if not artist or not title:
            stem = re.sub(r"^\d{1,3}[\s._-]+", "", p.stem).strip()
            if " - " in stem:
                a, t = stem.split(" - ", 1)
                artist, title = artist or a.strip(), title or t.strip()
        # "feat." und Zusaetze helfen der Suche nicht
        artist = re.split(r"\s+(?:feat\.?|ft\.?|featuring)\s+", artist, maxsplit=1, flags=re.I)[0].strip()
        return artist, JUNK.sub("", album).strip(), JUNK.sub("", title).strip()

    @staticmethod
    def _guess_text(p, tags):
        """Ohne Interpret: der Dateiname (ohne Titelnummer, Zusaetze) als Ganzes, z. B. "Beck loser"."""
        stem = re.sub(r"^\d{1,3}[\s._-]+", "", p.stem).replace("_", " ")
        stem = re.sub(r"\s+", " ", JUNK.sub("", stem)).strip()
        if len(stem.split()) >= 2:
            return stem
        return JUNK.sub("", tags.get("title") or "").strip()

    def track_cache(self, p, tags):
        """Datei im Zwischenspeicher fuer das Cover dieses Titels – gemeinsam fuer alle Titel eines Albums."""
        artist, album, title = self._track_names(p, tags)
        if not artist:                                 # nur ein Dateiname wie "Beck loser": raten (fetch_track)
            text = self._guess_text(p, tags)
            if len(text.split()) < 2:
                return None
            return self.CACHE / ("t-" + hashlib.sha1(f"guess|{self._norm(text)}".encode()).hexdigest()[:16] + ".jpg")
        if not (album or title):
            return None
        key = f"album|{self._norm(artist)}|{self._norm(album)}" if album else f"title|{self._norm(artist)}|{self._norm(title)}"
        return self.CACHE / ("t-" + hashlib.sha1(key.encode()).hexdigest()[:16] + ".jpg")

    def cache_kind(self, p, tags, cache):
        if cache.name == self._guess_cache(p, tags).name:
            return "guess"
        _artist, album, _title = self._track_names(p, tags)
        return "album" if album else "title"

    def _guess_cache(self, p, tags):
        return self.CACHE / ("t-" + hashlib.sha1(f"guess|{self._norm(self._guess_text(p, tags))}".encode()).hexdigest()[:16] + ".jpg")

    def track_caches(self, p, tags):
        """Alle Zwischenspeicher-Dateien, die fuer diesen Titel in Frage kommen (Album, Titel, geraten)."""
        out = []                                       # geraten zuerst: dessen Angaben stammen sicher von uns
        if len(self._guess_text(p, tags).split()) >= 2:
            out.append(self._guess_cache(p, tags))
        c = self.track_cache(p, tags)
        if c is not None and c not in out:
            out.append(c)
        return out

    def forget(self, cache):
        for f in (cache, cache.with_suffix(".json")):
            try:
                f.unlink()
            except OSError:
                pass
        d = self._miss_load()
        if d.pop(cache.name, None) is not None:
            try:
                self.MISSES.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass

    def refresh_track(self, path):
        """Cover dieses Titels neu suchen (Menue im Player)."""
        with self.lock:
            self.refresh.add(str(path))
        self.add_track(path, force=True)

    def track_missed(self, cache):
        return self._recent_miss(cache.name)

    def fetch_track(self, p, tags, cache):
        if cache.is_file():                            # inzwischen von einem anderen Titel desselben Albums geholt
            return True
        artist, album, title = self._track_names(p, tags)
        img, via = None, ""
        self.offline = False
        meta = None
        if not artist:
            text = self._guess_text(p, tags)
            img, via = self._online_guess(text), text
            meta = self.last_meta if img else None
        elif album:
            img, via = self._online(artist, album), f"{artist} – {album}"
        if not img and artist and title:
            img, via = self._online_recording(artist, title), f"{artist} – {title}"
            meta = self.last_meta if img else None
        if not img:
            if self.offline:                           # kein Netz: None = spaeter nochmal
                return None
            self._miss(cache.name)
            log("Cover: nichts gefunden fuer", p.name)
            return False
        try:
            self.CACHE.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".part")
            tmp.write_bytes(img)
            tmp.replace(cache)
            if meta:                                   # Angaben zur gefundenen Aufnahme (fuer fehlende Tags)
                cache.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            log("Cover: Zwischenspeicher nicht beschreibbar:", e)
            return False
        log("Cover:", p.name, "<- MusicBrainz (" + via + ")")
        return True

    def _caa(self, gid):
        try:
            req = urllib.request.Request(self.CAA + f"release-group/{gid}/front-500", headers={"User-Agent": self.UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            return data if len(data) > 1000 else None
        except urllib.error.HTTPError as e:
            if e.code != 404:
                log("Cover Art Archive:", e)
        except Exception as e:  # noqa: BLE001
            log("Cover Art Archive:", e)
        return None

    @staticmethod
    def _similar(a, b):
        import difflib
        f = lambda x: re.sub(r"[^a-z0-9]+", " ", tv_fold(x or "")).strip()    # noqa: E731
        return difflib.SequenceMatcher(None, f(a), f(b)).ratio()

    @classmethod
    def _artist_fits(cls, credit, guess):
        """"Jade" passt zu "Jade LeMac", "beck" zu "Beck" – Woerter des geratenen Namens stecken im echten."""
        if cls._similar(credit, guess) >= 0.85:
            return True
        w = lambda x: set(re.sub(r"[^a-z0-9]+", " ", tv_fold(x or "")).split())    # noqa: E731
        g = w(guess)
        return bool(g) and g <= w(credit)

    def _online_guess(self, text):
        """Nur "Beck loser" oder "Midnight Cowboy Jade": alle Aufteilungen in Interpret + Titel durchprobieren (beide
        Richtungen, hoechstens 8 Anfragen) und nur nehmen, was bei MusicBrainz in Interpret UND Titel passt."""
        words = text.split()
        if not 2 <= len(words) <= 12:
            return None
        cands = []
        for i in range(1, len(words)):
            a, t = " ".join(words[:i]), " ".join(words[i:])
            cands += [(a, t), (t, a)]
        cands.sort(key=lambda c: abs(len(c[0].split()) - 1))   # meist ist der Interpret ein Wort ("Beck", "Jade")
        for a, t in cands[:8]:
            img = self._online_recording(a, t, strict=True)
            if img or self.offline:
                return img
        return None

    def _online_recording(self, artist, title, strict=False):
        """Titel ohne Album-Tag: Aufnahme suchen, deren Album (offiziell, Studioalbum vor Single, keine
        Zusammenstellung) nehmen. strict: Interpret und Titel muessen fast genau passen (geratene Aufteilung)."""
        q = "recording:" + self._q(title) + " AND artist:" + self._q(artist)
        try:
            d = self._mb_get("recording/?fmt=json&limit=8&query=" + urllib.parse.quote(q))
        except Exception as e:  # noqa: BLE001
            log("Cover: MusicBrainz nicht erreichbar:", e)
            self.offline = True
            return None

        def rank(r, score):
            """Original vor Sampler: offiziell, keine Zusammenstellung/Live/Soundtrack (secondary-types, "Various
            Artists"), Studioalbum vor Single vor EP, dann der frueheste Termin – ueber alle Aufnahmen hinweg."""
            rg = r.get("release-group") or {}
            va = any((a.get("name") or "").casefold() in ("various artists", "verschiedene interpreten")
                     for a in r.get("artist-credit") or [])
            return (0 if r.get("status") == "Official" else 1, 1 if (rg.get("secondary-types") or va) else 0,
                    {"Album": 0, "Single": 1, "EP": 2}.get(rg.get("primary-type"), 3), r.get("date") or "9999", -score)
        best = {}
        for rec in (d.get("recordings") or [])[:8]:
            score = int(rec.get("score") or 0)
            if score < 90:
                continue
            credit = "".join((a.get("name") or "") + (a.get("joinphrase") or "") for a in rec.get("artist-credit") or []).strip()
            if strict and (self._similar(rec.get("title"), title) < 0.85 or not self._artist_fits(credit, artist)):
                continue
            for r in rec.get("releases") or []:
                gid = (r.get("release-group") or {}).get("id")
                if not gid:
                    continue
                k = rank(r, score)
                if gid in best and best[gid][0] <= k:
                    continue
                tracks = [t for m in r.get("media") or [] for t in m.get("track") or []]
                best[gid] = (k, {"title": rec.get("title") or "", "artist": credit, "album": r.get("title") or "",
                                 "date": (r.get("date") or "")[:4], "track": str(tracks[0].get("number") or "") if tracks else ""})
        self.last_meta = None
        for gid, (_k, meta) in sorted(best.items(), key=lambda x: x[1][0])[:4]:
            img = self._caa(gid)
            if img:
                self.last_meta = meta
                return img
        return None

    def _save(self, folder, data):
        target = folder / "cover.jpg"
        try:
            tmp = folder / ".cover.jpg.part"
            tmp.write_bytes(data)
            tmp.replace(target)
            return "cover.jpg"
        except OSError:
            self.CACHE.mkdir(parents=True, exist_ok=True)
            c = self.cache_file(folder)
            c.write_bytes(data)
            return "Zwischenspeicher"


def tempfile_name(prefix, suffix):
    import tempfile
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return name


COVERS = CoverFetcher()


# ---------------------------------------------------------------------------
#  Musik suchen und herunterladen (Videos & Musik -> "Musik suchen"), aehnlich wie ytmdl
# ---------------------------------------------------------------------------
DL_SOURCES = ("archive", "youtube", "soundcloud")          # Reihenfolge der Einstellungsseite
DL_DEFAULT = {"archive": False, "youtube": False, "soundcloud": False}   # keine Vorauswahl – der Nutzer kreuzt selbst an
JUNK = re.compile(r"\s*[\(\[](?:official|offizielles|music|lyric|lyrics|audio|video|hd|hq|4k|visuali[sz]er|clip|"
                  r"videoclip|remaster(?:ed)?(?: \d{4})?|explicit|live)[^\)\]]*[\)\]]", re.I)


def safe_name(s, fallback="Unbekannt"):
    """Datei-/Ordnername: keine Pfadtrenner und Steuerzeichen, hoechstens 120 Zeichen."""
    s = re.sub(r'[\x00-\x1f/\\:*?"<>|]+', " ", str(s or "")).strip().strip(".")
    s = re.sub(r"\s{2,}", " ", s)
    return s[:120] or fallback


class MusicDL:
    """Suche in mehreren Quellen und Download nach share/Musik:
      archive     Internet Archive (Netlabels, Live-Mitschnitte, Creative Commons/gemeinfrei) – ganze Alben, direkt
      youtube     YouTube ueber yt-dlp (+ Node.js fuer die Signatur-Pruefung von YouTube)
      soundcloud  SoundCloud ueber yt-dlp
    Einzelne Titel (YouTube/SoundCloud) werden zu MP3 (bestes VBR) und bekommen Tags + Cover wie bei ytmdl:
    Interpret/Titel aus den Angaben der Plattform bzw. dem Titel ("Interpret - Titel (Official Video)"), Album,
    Genre, Jahr, Titelnummer und Cover (600 px) aus der iTunes-Suche. Ablage: Musik/<Interpret>/<Album>/NN - Titel.mp3,
    ohne Album: Musik/<Interpret>/Singles/. Welche Quellen genutzt werden, waehlt man vorher selbst (Einstellungsseite)."""
    IA = os.environ.get("VS_IA_URL", "https://archive.org/")
    ITUNES = os.environ.get("VS_ITUNES_URL", "https://itunes.apple.com/search")
    UA = {"User-Agent": "VoidStation/2026 ( https://voidstation.de )"}

    def __init__(self):
        self.lock = threading.Lock()
        self.results = {}                  # key -> Treffer der letzten Suchen (Download nur ueber den Schluessel)
        self.jobs = []                     # Downloads: {key, title, artist, src, state, pct, msg, path}
        self.worker = None

    # ---- Einstellungen ----
    @staticmethod
    def settings():
        d = settings_load().get("dl") or {}
        src = dict(DL_DEFAULT)
        src.update({k: bool(v) for k, v in (d.get("sources") or {}).items() if k in DL_SOURCES})
        return {"sources": src, "configured": bool(d.get("configured"))}

    @staticmethod
    def ytdlp():
        # die eigene, aktuelle Kopie von YouTube Light (falls dort aktualisiert) vor dem Paket aus Void
        local = YtLight.LOCAL
        exe = os.environ.get("VS_YTDLP") or (str(local) if local.is_file() and os.access(local, os.X_OK) else "") \
            or shutil.which("yt-dlp")
        return exe

    def tools(self):
        exe = self.ytdlp()
        ver = ""
        if exe:
            r = run([exe, "--version"], timeout=20)
            ver = r.stdout.strip() if r and r.returncode == 0 else ""
        return {"ytdlp": ver, "node": bool(shutil.which("node")), "ffmpeg": bool(shutil.which("ffmpeg"))}

    def save_settings(self, sources):
        s = settings_load()
        src = {k: bool((sources or {}).get(k, DL_DEFAULT[k])) for k in DL_SOURCES}
        s["dl"] = {"sources": src, "configured": True}
        settings_save(s)
        log("Musik suchen: Quellen", ", ".join(k for k, v in src.items() if v) or "keine")
        return self.payload()

    def payload(self):
        return dict(self.settings(), tools=self.tools(), sources_list=list(DL_SOURCES))

    # ---- Suche ----
    def _get_json(self, url, timeout=15):
        req = urllib.request.Request(url, headers=self.UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _remember(self, items):
        with self.lock:
            for it in items:
                self.results[it["key"]] = it
            if len(self.results) > 600:
                for k in list(self.results)[:len(self.results) - 600]:
                    del self.results[k]
        return [{k: v for k, v in it.items() if k not in ("url",)} for it in items]

    def search(self, q):
        q = " ".join(str(q or "").split())[:120]
        if not q:
            return {"items": [], "errors": {}}
        src = self.settings()["sources"]
        out, errors, threads = {}, {}, []

        def one(name, fn):
            try:
                out[name] = fn(q)
            except Exception as e:  # noqa: BLE001
                log("Musik suchen:", name, e)
                errors[name] = str(e)[:200]
        for name, fn in (("archive", self._s_archive), ("youtube", self._s_youtube), ("soundcloud", self._s_soundcloud)):
            if src.get(name):
                t = threading.Thread(target=one, args=(name, fn), daemon=True)
                t.start()
                threads.append(t)
        for t in threads:
            t.join(timeout=40)
        items = []
        for name in DL_SOURCES:                          # Quellen nacheinander, je Quelle in Trefferreihenfolge
            items += out.get(name, [])
        return {"items": self._remember(items), "errors": errors}

    def _s_archive(self, q):
        term = re.sub(r'[()":\\\[\]{}^~*?]', " ", q)
        query = (f'({term}) AND mediatype:(audio) AND (licenseurl:(*creativecommons*) OR licenseurl:(*publicdomain*) '
                 f'OR collection:(etree) OR collection:(netlabels))')
        params = urllib.parse.urlencode([("q", query), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"),
                                         ("fl[]", "year"), ("fl[]", "licenseurl"), ("rows", "15"), ("output", "json"),
                                         ("sort[]", "downloads desc")])
        d = self._get_json(self.IA + "advancedsearch.php?" + params)
        items = []
        for doc in (d.get("response") or {}).get("docs") or []:
            ident = str(doc.get("identifier") or "")
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", ident):
                continue
            creator = doc.get("creator")
            creator = creator[0] if isinstance(creator, list) and creator else creator or ""
            lic = str(doc.get("licenseurl") or "")
            items.append({"key": "ia:" + ident, "src": "archive", "kind": "album", "id": ident,
                          "title": str(doc.get("title") or ident)[:150], "artist": str(creator)[:100],
                          "year": str(doc.get("year") or "")[:4], "duration": 0,
                          "license": "CC" if "creativecommons" in lic else "PD" if "publicdomain" in lic else "",
                          "thumb": self.IA + "services/img/" + ident})
        return items

    def _ytdlp_search(self, prefix, src, q):
        exe = self.ytdlp()
        if not exe:
            raise RuntimeError("yt-dlp fehlt")
        r = run([exe, "--flat-playlist", "-J", "--no-warnings", "--ignore-config", f"{prefix}12:{q}"], timeout=40)
        if not r or r.returncode != 0:
            raise RuntimeError((r.stderr.strip().splitlines() or ["yt-dlp-Fehler"])[-1] if r else "yt-dlp antwortet nicht")
        d = json.loads(r.stdout or "{}")
        items = []
        for e in d.get("entries") or []:
            url = str(e.get("url") or e.get("webpage_url") or "")
            vid = str(e.get("id") or "")
            if src == "youtube":
                if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid):
                    continue
                url = "https://www.youtube.com/watch?v=" + vid
            elif not url.startswith("https://soundcloud.com/") and not url.startswith("https://api.soundcloud.com/"):
                continue
            thumbs = e.get("thumbnails") or []
            thumb = e.get("thumbnail") or (thumbs[-1].get("url") if thumbs and isinstance(thumbs[-1], dict) else "")
            items.append({"key": f"{src}:{vid or hashlib.sha1(url.encode()).hexdigest()[:12]}", "src": src, "kind": "track",
                          "id": vid, "url": url, "title": str(e.get("title") or "")[:150],
                          "artist": str(e.get("artist") or e.get("uploader") or e.get("channel") or "")[:100],
                          "duration": int(e.get("duration") or 0), "year": "", "license": "", "thumb": str(thumb or "")})
        return items

    def _s_youtube(self, q):
        return self._ytdlp_search("ytsearch", "youtube", q)

    def _s_soundcloud(self, q):
        return self._ytdlp_search("scsearch", "soundcloud", q)

    # ---- Downloads ----
    def status(self):
        with self.lock:
            return {"jobs": [dict(j) for j in self.jobs[-40:]],
                    "active": any(j["state"] in ("queued", "running") for j in self.jobs)}

    def get(self, key):
        with self.lock:
            it = self.results.get(str(key))
            if not it:
                raise ValueError("Treffer unbekannt – bitte neu suchen")
            if any(j["key"] == it["key"] and j["state"] in ("queued", "running") for j in self.jobs):
                return self.status()
            self.jobs.append({"key": it["key"], "title": it["title"], "artist": it["artist"], "src": it["src"],
                              "state": "queued", "pct": 0, "msg": "", "path": ""})
            if self.worker is None:                    # der Arbeiter meldet sich unter dem Lock ab (kein Wettlauf)
                self.worker = threading.Thread(target=self._run, daemon=True)
                self.worker.start()
        return self.status()

    def _job(self, key, **kw):
        with self.lock:
            for j in reversed(self.jobs):
                if j["key"] == key:
                    j.update(kw)
                    return

    def _run(self):
        while True:
            with self.lock:
                job = next((j for j in self.jobs if j["state"] == "queued"), None)
                if not job:
                    self.worker = None
                    return
                job["state"] = "running"
                it = self.results.get(job["key"])
            try:
                path = self._album(it) if it["kind"] == "album" else self._track(it)
                rel = str(Path(path).relative_to(MEDIA.share())) if str(path).startswith(str(MEDIA.share())) else str(path)
                self._job(it["key"], state="done", pct=100, path=str(path), msg=rel)
                log("Musik gespeichert:", rel)
            except Exception as e:  # noqa: BLE001
                log("Musik laden fehlgeschlagen:", it.get("title"), e)
                self._job(it["key"], state="error", msg=str(e)[:200])

    def _download(self, url, dest, key=None, part=(0, 1)):
        req = urllib.request.Request(url, headers=self.UA)
        tmp = dest.with_name("." + dest.name + ".part")
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as fh:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if key and total:
                    i, n = part
                    self._job(key, pct=int((i + got / total) / n * 100))
        tmp.replace(dest)

    def _album(self, it):
        """Internet Archive: alle MP3-Titel eines Eintrags nach Musik/<Interpret>/<Titel>/ (Tags bringt das Archiv mit)."""
        meta = self._get_json(self.IA + "metadata/" + it["id"], timeout=30)
        files = meta.get("files") or []
        def pick(fmt):
            return [f for f in files if f.get("format") == fmt and f.get("name") and not f.get("name", "").startswith(("_", "."))]
        tracks = pick("VBR MP3") or pick("MP3") or pick("128Kbps MP3") or pick("Ogg Vorbis") or pick("Flac")
        if not tracks:
            raise RuntimeError("keine Musikdateien in diesem Eintrag")
        tracks.sort(key=lambda f: (int(re.match(r"\d+", str(f.get("track") or "999")).group(0)) if re.match(r"\d+", str(f.get("track") or "")) else 999,
                                   natural_key(f["name"])))
        md = meta.get("metadata") or {}
        artist = md.get("creator") or it["artist"]
        artist = artist[0] if isinstance(artist, list) and artist else artist
        folder = MEDIA.share() / "Musik" / safe_name(artist) / safe_name(md.get("title") or it["title"])
        folder.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(tracks[:200]):
            name = safe_name(Path(f["name"]).name)
            dest = folder / name
            if dest.exists():
                continue
            self._job(it["key"], msg=f"{i + 1}/{len(tracks)}")
            self._download(self.IA + "download/" + urllib.parse.quote(it["id"]) + "/" + urllib.parse.quote(f["name"]), dest,
                           it["key"], (i, len(tracks)))
        if MediaLib.own_cover(folder) is None:
            try:
                self._download(self.IA + "services/img/" + it["id"], folder / "cover.jpg")
            except Exception:  # noqa: BLE001
                pass
        return folder

    @staticmethod
    def _split(title, artist):
        """"Interpret - Titel (Official Video)" -> (Interpret, Titel); sonst Kanal als Interpret."""
        t = JUNK.sub("", title or "").strip()
        t = re.sub(r"\s*\|.*$", "", t).strip()
        m = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", t)
        if m:
            return m.group(1).strip(), m.group(2).strip().strip('"“”')
        artist = re.sub(r"\s*-\s*Topic$|VEVO$", "", artist or "").strip()
        return artist, t

    def _itunes(self, artist, title):
        term = urllib.parse.urlencode({"term": f"{artist} {title}".strip(), "entity": "song", "limit": "8", "media": "music"})
        try:
            d = self._get_json(self.ITUNES + "?" + term)
        except Exception as e:  # noqa: BLE001
            log("iTunes-Suche:", e)
            return None
        def norm(x):
            return re.sub(r"[^a-z0-9]+", " ", tv_fold(JUNK.sub("", x or ""))).strip()
        nt, na = norm(title), norm(artist)
        best, best_score = None, 0.0
        import difflib
        for r in d.get("results") or []:
            st = difflib.SequenceMatcher(None, nt, norm(r.get("trackName"))).ratio()
            sa = difflib.SequenceMatcher(None, na, norm(r.get("artistName"))).ratio() if na else 0.6
            score = st * 0.65 + sa * 0.35
            if score > best_score:
                best, best_score = r, score
        return best if best_score >= 0.72 else None

    def _track(self, it):
        exe = self.ytdlp()
        if not exe:
            raise RuntimeError("yt-dlp fehlt")
        ff = shutil.which("ffmpeg")
        if not ff:
            raise RuntimeError("ffmpeg fehlt")
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="vs-dl-"))
        try:
            args = [exe, "--ignore-config", "--no-playlist", "--newline", "--no-warnings", "-f", "bestaudio/best",
                    "-x", "--audio-format", "mp3", "--audio-quality", "0", "--write-info-json",
                    "-o", str(tmp / "a.%(ext)s"), it["url"]]
            if it["src"] == "youtube" and shutil.which("node"):
                args[1:1] = ["--js-runtimes", "node"]
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                 stdin=subprocess.DEVNULL)
            last = ""
            for line in p.stdout:
                m = re.search(r"\[download\]\s+([\d.]+)%", line)
                if m:
                    self._job(it["key"], pct=int(float(m.group(1)) * 0.9))
                elif line.strip():
                    last = line.strip()
            if p.wait() != 0:
                raise RuntimeError(last or "Download fehlgeschlagen")
            audio = tmp / "a.mp3"
            if not audio.exists():
                raise RuntimeError("keine Audiodatei erhalten")
            try:
                info = json.loads((tmp / "a.info.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                info = {}
            self._job(it["key"], msg="Tags & Cover", pct=92)
            artist, title = (info.get("artist") or "").split(",")[0].strip(), info.get("track") or ""
            if not (artist and title):
                artist, title = self._split(info.get("title") or it["title"], info.get("uploader") or it["artist"])
            album, genre, year, num = info.get("album") or "", info.get("genre") or "", str(info.get("release_year") or ""), ""
            cover = None
            hit = self._itunes(artist, title)
            if hit:
                artist, title = hit.get("artistName") or artist, hit.get("trackName") or title
                album = hit.get("collectionName") or album
                genre = hit.get("primaryGenreName") or genre
                year = (hit.get("releaseDate") or "")[:4] or year
                num = str(hit.get("trackNumber") or "")
                art = hit.get("artworkUrl100") or ""
                if art:
                    try:
                        self._download(art.replace("100x100bb", "600x600bb"), tmp / "cover.jpg")
                        cover = tmp / "cover.jpg"
                    except Exception:  # noqa: BLE001
                        cover = None
            if cover is None and it.get("thumb", "").startswith("https://"):
                try:                                      # Vorschaubild der Plattform, quadratisch zugeschnitten
                    self._download(it["thumb"], tmp / "thumb.img")
                    r = run([ff, "-v", "error", "-y", "-i", str(tmp / "thumb.img"), "-vf",
                             "crop='min(iw,ih)':'min(iw,ih)',scale=600:600", str(tmp / "cover.jpg")], timeout=30)
                    cover = tmp / "cover.jpg" if r and r.returncode == 0 else None
                except Exception:  # noqa: BLE001
                    cover = None
            artist = artist or "Unbekannt"
            folder = MEDIA.share() / "Musik" / safe_name(artist) / (safe_name(album) if album else "Singles")
            folder.mkdir(parents=True, exist_ok=True)
            name = (f"{int(num):02d} - " if num.isdigit() and album else "") + safe_name(title, "Titel") + ".mp3"
            dest = folder / name
            meta = ["-metadata", f"title={title}", "-metadata", f"artist={artist}", "-metadata", f"album_artist={artist}"]
            for k, v in (("album", album), ("genre", genre), ("date", year), ("track", num)):
                if v:
                    meta += ["-metadata", f"{k}={v}"]
            out = tmp / "tagged.mp3"
            cmd = [ff, "-v", "error", "-y", "-i", str(audio)]
            if cover:
                cmd += ["-i", str(cover), "-map", "0:a", "-map", "1:v", "-c", "copy", "-id3v2_version", "3",
                        "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)", "-disposition:v", "attached_pic"]
            else:
                cmd += ["-map", "0:a", "-c", "copy", "-id3v2_version", "3"]
            r = run(cmd + ["-map_metadata", "-1"] + meta + [str(out)], timeout=120)
            if not r or r.returncode != 0:
                raise RuntimeError("Tags konnten nicht geschrieben werden")
            shutil.move(str(out), str(dest))
            if cover and MediaLib.own_cover(folder) is None and album:
                shutil.copyfile(cover, folder / "cover.jpg")
            return dest
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


MUSICDL = MusicDL()


# ---------------------------------------------------------------------------
#  AppCenter: kuratierte optionale Programme
# ---------------------------------------------------------------------------
CATALOG = BASE / "catalog.json"
APPDIR = BASE / "apps"
PKG_HELPER = "/usr/local/sbin/voidstation-pkg"
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_app(app_id):
    return next((a for a in catalog()["apps"] if a["id"] == app_id), None)


# Architektur des Geraets ("x86_64" oder "i686" – die 32-Bit-Variante ist experimentell)
SYS_ARCH = "i686" if os.uname().machine in ("i386", "i486", "i586", "i686") else os.uname().machine


def app_archs(a):
    """Architekturen, fuer die es eine App gibt; None = alle. "arch" im Katalog geht vor, sonst aus der Quelle:
    Flathub baut kein 32-Bit-x86 mehr, AppImages im Katalog sind 64 Bit, Widevine (Netflix & Co.) gibt es unter
    Linux nur fuer 64 Bit."""
    if isinstance(a.get("arch"), list):
        return a["arch"]
    s = a.get("source", {})
    if s.get("type") in ("flatpak", "appimage") or s.get("drm"):
        return ["x86_64"]
    return None


def app_supported(a):
    archs = app_archs(a)
    return not archs or SYS_ARCH in archs


def pad_mouse_default(tile_id):
    """Controller als Maus (Startseite: rechter Stick, R2/L2) im Programm dieser Kachel von selbst an?
    Vorrang: "mouse" an der Kachel (tiles.json), dann im Katalog; Spiele und Emulatoren (Gruppe "Spiele") aus,
    weil dort rechter Stick und Schultertasten zum Spiel gehoeren – R3 schaltet trotzdem um. Sonst an."""
    if not tile_id:
        return True
    if tile_id in ("tv", "media", "ytlight") and PLAYERS.active(tile_id):   # eigener Player: komplett mit dem Controller bedienbar
        return False
    t = find_tile(tile_id) or {}
    if isinstance(t.get("mouse"), bool):
        return t["mouse"]
    try:
        a = catalog_app(tile_id)
    except (OSError, ValueError):
        a = None
    if a:
        if isinstance(a.get("mouse"), bool):
            return a["mouse"]
        return (a.get("tile") or {}).get("group") != "Spiele"
    return True


def app_suspendable(tile_id):
    """Programm dieser Kachel anhalten, solange etwas anderes vorn ist? Vorrang: "suspend" an der Kachel
    (tiles.json), dann im Katalog; von selbst bei Emulatoren (Katalog-Kategorie "Emulatoren" bzw. Kacheln, die
    Spiele aus share/ROMs starten), weil sie den Controller auch im Hintergrund lesen. Spiele mit Mehrspieler
    uebers Netz (Xonotic, Luanti …) und Steam laufen weiter."""
    t = find_tile(tile_id) or {}
    if isinstance(t.get("suspend"), bool):
        return t["suspend"]
    try:
        a = catalog_app(tile_id)
    except (OSError, ValueError):
        a = None
    if a and isinstance(a.get("suspend"), bool):
        return a["suspend"]
    if a:
        return a.get("cat") == "Emulatoren"
    return tile_id in ROMS.SYSTEM_TO_TILE.values() or tile_id in ROMS.TILE_TO_SYSTEM


def tile_ids():
    return {t.get("id") for g in load_config().get("groups", []) for t in g.get("tiles", [])}


def installed_sets():
    """Installierte Void-Pakete und (Benutzer-)Flatpaks – je ein Aufruf fuer den ganzen Katalog."""
    pkgs, fps = set(), set()
    r = run(["xbps-query", "-l"], timeout=20)
    for line in (r.stdout.splitlines() if r and r.returncode == 0 else []):
        parts = line.split(None, 2)                  # "ii paket-1.2_1 Beschreibung"
        if len(parts) >= 2 and parts[0] == "ii":
            pkgs.add(parts[1].rsplit("-", 1)[0])
    if shutil.which("flatpak"):
        r = run(["flatpak", "list", "--user", "--app", "--columns=application"], timeout=20)
        fps = {x.strip() for x in (r.stdout.splitlines() if r and r.returncode == 0 else []) if x.strip()}
    return pkgs, fps


def app_installed_in(a, pkgs, fps, tiles):
    s = a["source"]
    if s["type"] == "xbps":
        return s["pkg"] in pkgs
    if s["type"] == "flatpak":
        return s["ref"] in fps
    if s["type"] == "appimage":
        return (APPDIR / a["id"] / "AppRun").exists()
    if s["type"] in ("web", "builtin"):                    # builtin: im Player eingebaut (YouTube Light) – nur die Kachel
        return a["id"] in tiles
    return False


def app_installed(a):
    s = a["source"]
    if s["type"] == "xbps":
        r = run(["xbps-query", s["pkg"]])
        return bool(r and r.returncode == 0)
    if s["type"] == "flatpak":
        r = run(["flatpak", "info", "--user", s["ref"]])
        return bool(r and r.returncode == 0)
    if s["type"] == "appimage":
        return (APPDIR / a["id"] / "AppRun").exists()
    if s["type"] in ("web", "builtin"):
        return a["id"] in tile_ids()
    return False


def app_cmd(a):
    s = a["source"]
    if s["type"] == "web":
        kiosk = ["--kiosk"] if s.get("kiosk", True) else []      # "kiosk": false -> normaler Browser mit Leisten
        return ["firefox", *kiosk, "--no-remote", "--profile",
                f"~/.local/share/voidstation/profiles/{a['id']}", s["url"]]
    return a["cmd"]


def config_save(c):
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG)


def tile_add(a):
    c = load_config()
    if a["id"] in {t.get("id") for g in c["groups"] for t in g["tiles"]}:
        return
    t = dict(a.get("tile", {}))
    gname = t.pop("group", "Apps")
    tile = {"id": a["id"], "label": t.pop("label", a["name"]), "size": t.get("size", "medium"),
            "color": t.get("color", "#2f3238"), "icon": t.get("icon", "globe"),
            "cmd": app_cmd(a), "app": True}
    if t.get("sub"):
        tile["sub"] = t["sub"]
    grp = next((g for g in c["groups"] if g.get("name") == gname), None)
    if grp is None:
        grp = {"name": gname, "tiles": []}
        sys_idx = next((i for i, g in enumerate(c["groups"]) if g.get("name") == "System"), len(c["groups"]))
        c["groups"].insert(sys_idx, grp)
    grp["tiles"].append(tile)
    config_save(c)


def tile_remove(app_id):
    c = load_config()
    for g in c["groups"]:
        g["tiles"] = [t for t in g["tiles"] if t.get("id") != app_id]
    c["groups"] = [g for g in c["groups"] if g["tiles"]]
    config_save(c)


def gpu_vendors():
    """Verbaute Grafik: 'intel', 'amd', 'nvidia' (aus /sys, ohne Zusatzprogramme)."""
    names = {"0x8086": "intel", "0x1002": "amd", "0x10de": "nvidia"}
    found = []
    for d in Path("/sys/bus/pci/devices").glob("*"):
        try:
            if not (d / "class").read_text().startswith("0x03"):
                continue
            v = names.get((d / "vendor").read_text().strip())
        except OSError:
            continue
        if v and v not in found:
            found.append(v)
    return found


def xbps_installed(pkg):
    r = run(["xbps-query", pkg])
    return bool(r and r.returncode == 0)


# Proton-GE (offizielle Releases von GloriousEggroll) fuer natives Steam
PROTON_DIR = Path.home() / ".local/share/Steam/compatibilitytools.d"
PROTON_API = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"


def proton_latest():
    req = urllib.request.Request(PROTON_API, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


PROTON_STATE = PROTON_DIR / ".voidstation.json"      # welche Versionen VoidStation selbst installiert hat


def proton_state():
    try:
        return [e for e in json.loads(PROTON_STATE.read_text()) if e.get("tag") and e.get("dir")]
    except (OSError, ValueError, AttributeError):
        return []


def proton_state_save(entries):
    PROTON_STATE.write_text(json.dumps(entries))


def proton_installed():
    return [e["tag"] for e in proton_state() if (PROTON_DIR / e["dir"]).is_dir()]


class Jobs:
    """Genau ein Installations-/Update-Auftrag gleichzeitig, mit Protokoll fuer die Oberflaeche."""

    def __init__(self):
        self.lock = threading.Lock()
        self.job = None

    def current(self):
        with self.lock:
            return dict(self.job) if self.job else None

    def _log(self, line):
        line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).rstrip()
        if not line:
            return
        with self.lock:
            self.job["log"] = (self.job["log"] + [line])[-60:]
            self.job["n"] += 1                       # laufende Zeilennummer (fuer "vsctl update")

    def _run(self, args, cwd=None):
        self._log("$ " + " ".join(args))
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             stdin=subprocess.DEVNULL, cwd=cwd, bufsize=1, errors="replace",
                             start_new_session=True)
        for line in p.stdout:
            for part in line.replace("\r", "\n").split("\n"):
                self._log(part)
        return p.wait()

    def busy(self):
        with self.lock:
            return bool(self.job and self.job["state"] == "running")

    def start(self, action, app=None):
        with self.lock:
            if self.job and self.job["state"] == "running":
                raise RuntimeError("Es läuft schon ein Auftrag")
            name = app["name"] if app else "Updates"
            self.job = {"action": action, "app": app["id"] if app else None,
                        "name": name, "state": "running", "reboot": False,
                        "log": [], "n": 0, "started": time.time(), "result": None}
        threading.Thread(target=self._work, args=(action, app), daemon=True).start()

    def _finish(self, ok, result=None, reboot=False):
        with self.lock:
            self.job["state"] = "done" if ok else "error"
            self.job["result"] = result
            self.job["reboot"] = bool(reboot)

    def _selfupdate(self):
        ok = self._run(["sudo", "-n", PKG_HELPER, "selfupdate"]) == 0
        _VCACHE["t"] = 0.0
        return ok

    def _work(self, action, a):
        try:
            with SYS_LOCK:                           # nie gleichzeitig mit der Update-Pruefung (xbps-Sperre)
                if action == "install":
                    ok = self._install(a)
                    if ok:
                        tile_add(a)
                    self._finish(ok, a.get("note") if ok else None)
                elif action == "remove":
                    APPS.close(a["id"])
                    ok = self._remove(a)
                    if ok:
                        tile_remove(a["id"])
                    self._finish(ok)
                elif action == "update":
                    ok, result, reboot = self._update_all()
                    self._finish(ok, result, reboot)
                if action in ("install", "remove"):
                    _sys_check(sync=False)           # Paketstand hat sich geaendert
        except Exception as e:  # noqa: BLE001
            self._log(f"Fehler: {e}")
            self._finish(False)

    def _update_all(self):
        """Alle Updates in einem Durchgang: Void-Pakete (inkl. Kernel) -> Flatpak -> AppImages
        -> Proton-GE -> VoidStation. Was aktuell ist, wird uebersprungen."""
        if xbps_busy():
            self._log("xbps läuft gerade (z. B. im Terminal) – bitte warten, bis es fertig ist.")
            return False, {"busy": True}, False
        self._log("Suche nach Updates …")
        _sys_check(sync=True, logf=self._log)
        s = dict(_SCACHE)
        vs = vs_update_status(force=True)
        ok, done = True, []
        if s["pkgs"] or s["error"]:
            self._log(f"== Void-Pakete: {len(s['pkgs'])} ==")
            if self._run(["sudo", "-n", PKG_HELPER, "update"]) == 0:
                done.append("system")
            else:
                ok = False
        else:
            self._log("Void-Pakete: aktuell")
        if s["flatpak"] and shutil_which("flatpak"):
            self._log(f"== Flatpak: {len(s['flatpak'])} ==")
            ok = self._run(["flatpak", "update", "--user", "-y", "--noninteractive"]) == 0 and ok
        for app in catalog()["apps"]:
            if app["id"] in s["appimage"]:
                self._log(f"== {app['name']} (AppImage) ==")
                ok = self._appimage(app) and ok
        if s["proton"]:
            self._log(f"== Proton-GE {s['proton']} ==")
            ok = self._proton_ge() and ok
        if vs["available"]:
            self._log(f"== VoidStation {vs['remote']} ==")
            if self._selfupdate():
                done.append("voidstation")
            else:
                ok = False
        else:
            self._log("VoidStation: aktuell")
        self._log("Prüfe Stand …")
        _sys_check(sync=True)
        vs_update_status(force=True)
        rb = reboot_needed()
        return ok, {"done": done, "kernel": rb["kernel"]}, rb["kernel"] or rb["voidstation"] or "voidstation" in done

    def _install(self, a):
        s = a["source"]
        if s["type"] == "xbps":
            return self._xbps_install(s)
        if s["type"] == "flatpak":
            if not shutil_which("flatpak"):
                self._log("Flatpak fehlt – wird installiert …")
                if self._run(["sudo", "-n", PKG_HELPER, "install", "flatpak"]) != 0:
                    return False
            for pkg in s.get("host_pkgs", []):
                if self._run(["sudo", "-n", PKG_HELPER, "install", pkg]) != 0:
                    self._log(f"Hinweis: {pkg} konnte nicht installiert werden")
            self._run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB])
            if self._run(["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", s["ref"]]) != 0:
                return False
            for ext in s.get("extras", []):
                if self._run(["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", ext]) != 0:
                    self._log(f"Hinweis: Erweiterung {ext} fehlt – App spaeter im AppCenter entfernen und neu installieren")
            return True
        if s["type"] == "appimage":
            return self._appimage(a)
        if s["type"] == "builtin":                     # Teil von VoidStation: nur fehlende Pakete nachholen, dann Kachel
            for pkg in s.get("pkgs", []):
                if not xbps_installed(pkg) and self._run(["sudo", "-n", PKG_HELPER, "install", pkg]) != 0:
                    return False
            self._log("in VoidStation eingebaut – Kachel wird angelegt")
            return True
        if s["type"] == "web":
            prof = BASE / "profiles" / a["id"]
            prof.mkdir(parents=True, exist_ok=True)
            js = (BASE / "firefox" / "user-common.js").read_text()
            if s.get("ua"):
                js += f'user_pref("general.useragent.override", {json.dumps(s["ua"])});\n'
            js += 'user_pref("media.ffmpeg.vaapi.enabled", true);\n'
            if s.get("drm"):                           # Netflix & Co.: Widevine (laedt Firefox beim ersten Bedarf selbst)
                js += ('user_pref("media.eme.enabled", true);\n'
                       'user_pref("media.gmp-widevinecdm.visible", true);\n'
                       'user_pref("media.gmp-widevinecdm.enabled", true);\n'
                       'user_pref("media.gmp-manager.updateEnabled", true);\n')
            (prof / "user.js").write_text(js)
            self._log(f"Profil angelegt: {prof}")
            return True
        return False

    def _xbps_install(self, s):
        # 1. Zusatz-Repos (z. B. nonfree, multilib), danach Paketlisten neu laden
        repos = [r for r in s.get("repos", []) if not xbps_installed(r)]
        if repos:
            if self._run(["sudo", "-n", PKG_HELPER, "install", *repos]) != 0:
                return False
            self._run(["sudo", "-n", PKG_HELPER, "sync"])
        # 2. Abhaengigkeiten: fest + passend zur GPU in EINEM xbps-Durchgang (keine Einzelabfragen
        #    gegen die Repos - die sind mit multilib/nonfree gross und auf schwachen Rechnern langsam)
        gpus = gpu_vendors()
        self._log("Grafik: " + (", ".join(gpus) or "unbekannt"))
        want = list(s.get("deps", []))
        for v in gpus:
            want += s.get("gpu_deps", {}).get(v, [])
        deps = [p for p in dict.fromkeys(want) if not xbps_installed(p)]
        if self._run(["sudo", "-n", PKG_HELPER, "install", *deps, s["pkg"]]) != 0:
            return False
        # 3. Optionale Pakete einzeln - fehlt eins im Repo, geht es trotzdem weiter
        for p in s.get("optional", []):
            if xbps_installed(p):
                continue
            if self._run(["sudo", "-n", PKG_HELPER, "install", p]) == 0:
                deps.append(p)
            else:
                self._log(f"Hinweis: optionales Paket {p} nicht installiert")
        # Neu hinzugekommene Abhaengigkeiten als automatisch markieren -> beim Entfernen wieder weg
        if deps:
            self._run(["sudo", "-n", PKG_HELPER, "markauto", *deps])
        for addon in s.get("addons", []):
            if addon == "proton-ge" and not self._proton_ge():
                self._log("Hinweis: Proton-GE kommt mit dem naechsten Update (Einstellungen → Updates)")
        return True

    def _proton_ge(self):
        """Neueste Proton-GE-Version laden (SHA512 geprueft); die zwei neuesten eigenen behalten."""
        tmp, tops = None, []
        try:
            rel = proton_latest()
            tag = rel["tag_name"]
            mine = proton_state()
            if any(e["tag"] == tag and (PROTON_DIR / e["dir"]).is_dir() for e in mine):
                self._log(f"Proton-GE {tag} ist aktuell")
                return True
            assets = {x["name"]: x["browser_download_url"] for x in rel.get("assets", [])}
            tars = [n for n in assets if n.endswith("-x86_64.tar.gz")] or \
                   [n for n in assets if n.endswith(".tar.gz") and "aarch64" not in n]
            if not tars:
                self._log("Proton-GE: kein passendes Archiv im Release gefunden")
                return False
            tar_name = tars[0]
            sum_url = assets.get(tar_name[:-len(".tar.gz")] + ".sha512sum")
            if not sum_url:
                self._log("Proton-GE: Pruefsumme fehlt im Release – abgebrochen")
                return False
            with urllib.request.urlopen(urllib.request.Request(sum_url, headers=UA), timeout=30) as r:
                want = r.read().decode().split()[0].lower()
            PROTON_DIR.mkdir(parents=True, exist_ok=True)
            tmp = PROTON_DIR / f".{tar_name}.part"
            self._log(f"Lade {tar_name} …")
            h = hashlib.sha512()
            req = urllib.request.Request(assets[tar_name], headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, last = 0, 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if total and done * 10 // total > last:
                        last = done * 10 // total
                        self._log(f"… {last * 10} %")
            if h.hexdigest() != want:
                tmp.unlink(missing_ok=True)
                self._log("Proton-GE: Pruefsumme stimmt nicht – verworfen")
                return False
            self._log("Pruefsumme ok, entpacke …")
            with tarfile.open(tmp) as t:
                tops = sorted({m.name.split("/", 1)[0] for m in t.getmembers() if m.name and not m.name.startswith("/")})
                kw = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
                t.extractall(PROTON_DIR, **kw)
            tmp.unlink(missing_ok=True)
            top = next((d for d in tops if (PROTON_DIR / d / "compatibilitytool.vdf").exists()), tops[0] if tops else tag)
            mine = [{"tag": tag, "dir": top}] + [e for e in mine if e["dir"] != top]
            for e in mine[2:]:
                shutil.rmtree(PROTON_DIR / e["dir"], ignore_errors=True)
                self._log(f"alte Version entfernt: {e['dir']}")
            proton_state_save(mine[:2])
            self._log(f"Proton-GE {tag} installiert ({top})")
            return True
        except Exception as e:  # noqa: BLE001
            self._log(f"Proton-GE: {e}")
            # halbe Downloads/Entpack-Reste wegraeumen (nichts anfassen, was schon vorher da war)
            if tmp:
                tmp.unlink(missing_ok=True)
            keep = {x["dir"] for x in proton_state()}
            for d in tops:
                if d not in keep and d and d not in (".", ".."):
                    shutil.rmtree(PROTON_DIR / d, ignore_errors=True)
            return False

    def _remove(self, a):
        s = a["source"]
        if s["type"] == "xbps":
            ok = self._run(["sudo", "-n", PKG_HELPER, "remove", s["pkg"]]) == 0
            if ok and "proton-ge" in s.get("addons", []):
                self._log("Spiele, Spielstaende und Proton-GE unter ~/.local/share/Steam bleiben erhalten")
            return ok
        if s["type"] == "flatpak":
            for ext in s.get("extras", []):
                self._run(["flatpak", "uninstall", "--user", "-y", "--noninteractive", ext])
            ok = self._run(["flatpak", "uninstall", "--user", "-y", "--noninteractive", s["ref"]]) == 0
            self._run(["flatpak", "uninstall", "--user", "-y", "--noninteractive", "--unused"])
            for pkg in s.get("host_pkgs", []):
                self._run(["sudo", "-n", PKG_HELPER, "remove", pkg])
            return ok
        if s["type"] == "builtin":                     # nur die Kachel; Abos und Verlauf bleiben fuer spaeter
            return True
        if s["type"] in ("appimage", "web"):
            target = APPDIR / a["id"] if s["type"] == "appimage" else BASE / "profiles" / a["id"]
            shutil.rmtree(target, ignore_errors=True)
            self._log(f"entfernt: {target}")
            return True
        return False

    def _appimage(self, a):
        APPDIR.mkdir(parents=True, exist_ok=True)
        img = APPDIR / f"{a['id']}.AppImage"
        self._log(f"Lade {a['source']['url']}")
        req = urllib.request.Request(a["source"]["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r, open(img, "wb") as f:
            stamp = asset_stamp(r.headers)
            total = int(r.headers.get("Content-Length") or 0)
            done, last = 0, 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and done * 10 // total > last:
                    last = done * 10 // total
                    self._log(f"… {last * 10} %")
        img.chmod(0o755)
        work = APPDIR / f".{a['id']}-extract"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        # Entpacken statt direkt starten: braucht kein FUSE und startet schneller
        self._log("Entpacke …")
        subprocess.run([str(img), "--appimage-extract"], cwd=str(work),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = work / "squashfs-root"
        if not (root / "AppRun").exists():
            self._log("Entpacken fehlgeschlagen")
            return False
        dest = APPDIR / a["id"]
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(str(root), str(dest))
        shutil.rmtree(work, ignore_errors=True)
        img.unlink(missing_ok=True)
        try:
            appimage_stampfile(a).write_text(stamp)    # Vergleichswert fuer die Update-Pruefung
        except OSError:
            pass
        self._log("installiert nach " + str(dest))
        return True


# ---------------------------------------------------------------------------
#  VoidStation selbst aktualisieren (Quelle: /usr/local/share/voidstation/update-url)
# ---------------------------------------------------------------------------
URLFILE = Path("/usr/local/share/voidstation/update-url")
CHANNELFILE = Path("/usr/local/share/voidstation/channel")
CHANNELS = {"stable": "Stable", "main": "Testing"}
_VCACHE = {"t": 0.0, "remote": None, "error": None, "key": None}


def vs_channel():
    try:
        ch = CHANNELFILE.read_text().split()[0]
    except (OSError, IndexError):
        ch = "stable"
    return ch if ch in CHANNELS else "stable"


def vs_update_base():
    tmpl = URLFILE.read_text().split()[0].rstrip("/")
    return tmpl.replace("{channel}", vs_channel())


def vs_version():
    """Installierte Version: {"version": "0.4.0", "build": "…", "history": […]} (aeltere Stände: nur build)."""
    try:
        d = json.loads((BASE / "version.json").read_text(encoding="utf-8"))
        if d.get("build"):
            return d
    except (OSError, ValueError):
        pass
    try:
        b = (BASE / "VERSION").read_text().strip()
        return {"version": None, "build": b or None}
    except OSError:
        return {"version": None, "build": None}


def _fetch_remote(base):
    def get(name):
        req = urllib.request.Request(f"{base}/{name}", headers=UA)
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read(200_000).decode("utf-8", "replace")
    try:
        d = json.loads(get("version.json"))
        if not re.fullmatch(r"[0-9a-f]{6,64}", str(d.get("build", ""))):
            raise ValueError("version.json ohne gueltige Build-Kennung")
        return d
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    b = get("version.txt").strip()                # aeltere Veroeffentlichungen
    if not re.fullmatch(r"[0-9a-f]{6,64}", b):
        raise ValueError("unerwartete Antwort vom Server")
    return {"version": None, "build": b, "history": []}


def vs_update_status(force=False):
    """Vergleicht die eigene Version mit dem Update-Kanal (hoechstens alle 10 min neu)."""
    try:
        base = vs_update_base()
    except (OSError, IndexError):
        base = None
    if base and not LIVE and (force or time.time() - _VCACHE["t"] > 600 or _VCACHE["key"] != base):
        if not net_online():
            # ohne Netz gar nicht erst versuchen; naechster Aufruf prueft wieder (kein 10-min-Zwischenspeicher)
            _VCACHE.update(error="offline")
            return vs_state()
        try:
            _VCACHE.update(remote=_fetch_remote(base), error=None)
        except Exception as e:  # noqa: BLE001
            _VCACHE.update(error=str(e))
            if _VCACHE["key"] != base:
                _VCACHE["remote"] = None
        _VCACHE.update(t=time.time(), key=base)
    return vs_state()


def net_online():
    """Gibt es eine Standardroute ins Netz (IPv4 oder IPv6, nicht ueber lo)? Schnell, ohne Netzwerkzugriff."""
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if len(f) > 3 and f[1] == "00000000" and int(f[3], 16) & 1:      # Ziel 0.0.0.0, Route aktiv (RTF_UP)
                return True
    except (OSError, ValueError):
        return True                                                        # unbekannt: nicht als offline melden
    try:
        for line in Path("/proc/net/ipv6_route").read_text().splitlines():
            f = line.split()
            if len(f) == 10 and f[0] == "0" * 32 and f[1] == "00" and f[9] != "lo" and not int(f[8], 16) & 0x200:
                return True                                                # ::/0, kein Reject-Eintrag
    except (OSError, ValueError):
        pass
    return False


def vtuple(v):
    """Version -> vergleichbares Tupel; unbekannt -> None.
    "0.7.2" -> (0, 7, 2) · "2026.11" -> (2026, 11) · "2026.11.1" -> (2026, 11, 1)
    "2026.11+testing.20261020" (Testing-Stand nach 2026.11) -> (2026, 11, 0, 20261020):
    neuer als 2026.11, aber aelter als 2026.11.1 und 2026.12."""
    s = str(v or "")
    base, _, extra = s.partition("+")
    try:
        t = tuple(int(x) for x in base.split("."))
    except ValueError:
        return None
    if not extra:
        return t
    m = re.fullmatch(r"testing\.(\d{8})", extra)
    if not m:
        return None
    if len(t) == 2:
        t += (0,)                                     # Testing nach 2026.11 liegt vor 2026.11.1
    return t + (int(m.group(1)),)


def vs_state():
    """Stand aus dem Zwischenspeicher, ohne Netzwerk (fuer /api/status)."""
    local, remote = vs_version(), _VCACHE["remote"]
    available = bool(remote and remote.get("build") and remote["build"] != local.get("build"))
    lv, rv = vtuple(local.get("version")), vtuple(remote.get("version")) if remote else None
    if available and lv and rv and rv < lv:
        available = False                             # nie auf eine aeltere Version "aktualisieren" (z. B. Stable hinter Testing)
    if LIVE:
        available = False
    changes = []
    if available:
        seen = {e.get("version") for e in (local.get("history") or [])}
        for e in remote.get("history") or []:
            if e.get("version") in seen:
                break
            changes.append(e)
    ch = vs_channel()
    return {"local": local.get("version") or local.get("build"), "local_build": local.get("build"),
            "remote": (remote.get("version") or remote.get("build")) if remote else None,
            "remote_build": remote.get("build") if remote else None,
            "available": available, "changes": changes[:5], "error": _VCACHE["error"],
            "channel": ch, "channel_label": CHANNELS[ch], "checked": _VCACHE["t"] or None,
            "online": True if remote and _VCACHE["error"] != "offline" else net_online()}


# ---------------------------------------------------------------------------
#  Alle uebrigen Updates: Void-Pakete (inkl. Kernel), Flatpaks, AppImages, Proton-GE.
#  Ausgeloest wird alles nur ueber Einstellungen → Updates (ein Auftrag, siehe Jobs._update_all).
#  Updates im Terminal (sudo xbps-install -Su) werden am Paketstand erkannt.
# ---------------------------------------------------------------------------
SYS_LOCK = threading.Lock()                 # Pruefung und Auftraege nie gleichzeitig (xbps-Sperre)
XBPS_DB = Path("/var/db/xbps")
PKG_LINE = re.compile(r"^(\S+)-([^-\s]+_\d+)\s+(install|update|remove|reinstall|configure|download|hold)\b")
KERNEL_PKG = re.compile(r"^linux(\d+\.\d+)?$")
_SCACHE = {"t": 0.0, "pkgs": [], "flatpak": [], "appimage": [], "proton": None, "error": None,
           "db": None, "retry": 0.0}
BOOT_BUILD = None                           # VoidStation-Stand beim Start der Oberflaeche (main)
SYS_STAMP = BASE / "sysupdate.json"         # {"current": <Zeitpunkt, an dem zuletzt keine Void-Pakete ausstanden>}


def sysupd_days(s=None):
    d = (s or settings_load()).get("sysupd_days")
    return d if d in SYSUPD_DAYS else DEFAULTS["sysupd_days"]


def sys_current_since():
    """Seit wann gelten die Systemupdates als offen? Fehlt der Wert (Geraete vor 0.9.0),
    beginnt die Frist jetzt – kein Hinweis direkt nach dem Update auf 0.9.0."""
    try:
        return float(json.loads(SYS_STAMP.read_text())["current"])
    except (OSError, ValueError, KeyError, TypeError):
        sys_mark_current()
        return time.time()


def sys_mark_current():
    try:
        SYS_STAMP.write_text(json.dumps({"current": time.time()}))
    except OSError as e:
        log("sysupdate.json:", e)


def xbps_busy():
    """Laeuft xbps gerade (z. B. im Terminal)?"""
    r = run(["pgrep", "-x", "xbps-install|xbps-remove|xbps-reconfigure"])
    return bool(r and r.returncode == 0 and r.stdout.strip())


def pkgdb_stamp():
    try:
        return max((p.stat().st_mtime for p in XBPS_DB.glob("pkgdb-*.plist")), default=None)
    except OSError:
        return None


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


def boot_time():
    """Startzeitpunkt (Unix-Zeit) aus /proc/stat."""
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def reboot_needed():
    """kernel: seit dem Start ist ein neuerer Kernel dazugekommen (ein Neustart nimmt ihn);
    kernel_stuck: ein neuerer Kernel war schon vor dem Start da und laeuft trotzdem nicht – ein Neustart
    hilft dann nicht, also kein Dauerhinweis "Neustart noetig" ({"version", "running"} oder None);
    voidstation: Oberflaeche seit dem Start aktualisiert.
    Als Kernel zaehlt nur, was Module UND /boot/vmlinuz-<version> hat (Reste in /usr/lib/modules nicht)."""
    out = {"kernel": False, "kernel_stuck": None, "voidstation": False}
    if LIVE:
        return out
    running = os.uname().release
    try:
        ks = [d.name for d in Path("/usr/lib/modules").iterdir()
              if d.is_dir() and Path(f"/boot/vmlinuz-{d.name}").is_file()]
    except OSError:
        ks = []
    ks.sort(key=vkey)
    if ks and vkey(ks[-1]) > vkey(running):
        new = ks[-1]
        stamps = []
        for p in (Path("/usr/lib/modules") / new, Path(f"/boot/initramfs-{new}.img")):
            try:
                stamps.append(p.stat().st_mtime)   # beim Einrichten des Kernels geschrieben (depmod, dracut)
            except OSError:
                pass
        bt = boot_time()
        if stamps and bt and max(stamps) < bt:
            out["kernel_stuck"] = {"version": re.sub(r"_\d+$", "", new), "running": re.sub(r"_\d+$", "", running)}
        else:
            out["kernel"] = True
    build = vs_version().get("build")
    out["voidstation"] = bool(BOOT_BUILD and build and build != BOOT_BUILD)
    return out


def asset_stamp(headers):
    return headers.get("ETag") or f'{headers.get("Last-Modified", "")}|{headers.get("Content-Length", "")}'


def appimage_stampfile(a):
    return APPDIR / f".{a['id']}.stamp"


def appimage_outdated(a):
    try:
        req = urllib.request.Request(a["source"]["url"], headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            remote = asset_stamp(r.headers)
    except Exception:  # noqa: BLE001
        return False
    try:
        local = appimage_stampfile(a).read_text().strip()
    except OSError:
        local = None                                   # vor 0.9.0 installiert: einmal neu laden
    return remote != local


def _sys_check(sync, logf=None):
    """Sucht nach Updates ausser VoidStation selbst. Nur mit SYS_LOCK aufrufen!
    sync=False: nur Void-Pakete gegen die vorhandenen Paketlisten (schnell, ohne Netz)."""
    if LIVE:
        return
    res = {"pkgs": [], "error": None}
    r = run(["sudo", "-n", PKG_HELPER, "check"] + ([] if sync else ["--nosync"]), timeout=300)
    if r is None:
        res["error"] = "xbps antwortet nicht"
    else:
        for line in r.stdout.splitlines():
            m = PKG_LINE.match(line.strip())
            if m:
                res["pkgs"].append({"name": m[1], "version": m[2], "action": m[3]})
        if r.returncode != 0 and not res["pkgs"]:
            res["error"] = ((r.stdout + r.stderr).strip().splitlines() or [f"Fehler {r.returncode}"])[-1][:200]
    if logf:
        logf(f"Void-Pakete: {len(res['pkgs'])}" + (f" ({res['error']})" if res["error"] else ""))
    if sync:
        res.update(flatpak=[], appimage=[], proton=None)
        if shutil_which("flatpak"):
            f = run(["flatpak", "remote-ls", "--user", "--updates", "--columns=application"], timeout=120)
            if f and f.returncode == 0:
                res["flatpak"] = [x.strip() for x in f.stdout.splitlines() if x.strip()]
        apps = catalog()["apps"]
        for a in apps:
            if a["source"]["type"] == "appimage" and app_installed(a) and appimage_outdated(a):
                res["appimage"].append(a["id"])
        if any("proton-ge" in a["source"].get("addons", []) and app_installed(a) for a in apps):
            try:
                tag = proton_latest()["tag_name"]
                if tag not in proton_installed():
                    res["proton"] = tag
            except Exception as e:  # noqa: BLE001
                if logf:
                    logf(f"Proton-GE: {e}")
        if logf:
            logf(f"Flatpak: {len(res['flatpak'])}, AppImages: {len(res['appimage'])}, Proton-GE: {res['proton'] or 'aktuell'}")
        res["t"] = time.time()
    res["db"] = pkgdb_stamp()
    _SCACHE.update(res)
    if not res["pkgs"] and not res["error"]:
        sys_mark_current()                         # alles aktuell (auch nach Update im Terminal): Frist beginnt neu


def sys_check(sync):
    """Pruefung von aussen (Hintergrund, Einstellungen); False = gerade nicht moeglich."""
    if LIVE or JOBS.busy() or xbps_busy() or not SYS_LOCK.acquire(blocking=False):
        return False
    try:
        _sys_check(sync)
        return True
    finally:
        SYS_LOCK.release()


def _sys_recheck():
    if not sys_check(sync=False):
        _SCACHE["retry"] = time.time()             # xbps laeuft noch: spaeter erneut


def sys_state():
    """Stand aus dem Zwischenspeicher. Hat sich der Paketstand geaendert (Update/Installation im
    Terminal), wird kurz ohne Netz neu geprueft – so verschwinden erledigte Updates von selbst."""
    if (not LIVE and _SCACHE["t"] and pkgdb_stamp() != _SCACHE["db"]
            and time.time() - _SCACHE["retry"] > 10 and not JOBS.busy()):
        _SCACHE["retry"] = time.time()
        threading.Thread(target=_sys_recheck, daemon=True).start()
    pkgs = _SCACHE["pkgs"]
    kernel = next((p["version"] for p in pkgs if KERNEL_PKG.match(p["name"])), None)
    names = {a["id"]: a["name"] for a in catalog()["apps"]} if _SCACHE["appimage"] else {}
    count = len(pkgs) + len(_SCACHE["flatpak"]) + len(_SCACHE["appimage"]) + (1 if _SCACHE["proton"] else 0)
    days = sysupd_days()
    due_at = sys_current_since() + days * 86400 if pkgs else None
    return {"pkgs": [p["name"] for p in pkgs], "kernel": kernel, "flatpak": len(_SCACHE["flatpak"]),
            "appimage": [names.get(i, i) for i in _SCACHE["appimage"]], "proton": _SCACHE["proton"],
            "count": count, "error": _SCACHE["error"], "checked": _SCACHE["t"] or None,
            "days": days, "due_at": due_at, "due": bool(due_at and time.time() >= due_at)}


def updates_state(force=False):
    """Gesamtstand fuer Einstellungen → Updates: VoidStation + System + Neustart."""
    vs = vs_update_status(force)          # ohne force: nur, wenn der letzte Stand aelter als 10 min ist
    busy = False
    if force and not sys_check(sync=True):
        busy = JOBS.busy() or xbps_busy()
    sysst = sys_state()
    return {**vs, "system": sysst, "reboot": reboot_needed(), "busy": busy,
            "any": bool(vs["available"] or sysst["count"]), "notify": bool(vs["available"] or sysst["due"])}


def updates_badge():
    """Kurzfassung fuer /api/status (Hinweis unten rechts). Neue VoidStation-Versionen sofort,
    reine Systemupdates erst, wenn die eingestellte Frist (30/60/90 Tage) abgelaufen ist."""
    vs, sysst, rb = vs_state(), sys_state(), reboot_needed()
    return {"available": bool(vs["available"] or sysst["due"]), "version": vs["remote"] if vs["available"] else None,
            "system": sysst["count"] if sysst["due"] else 0, "reboot": rb["kernel"] or rb["voidstation"]}


def updates_background_check():
    """Prueft kurz nach dem Start und dann alle 6 Stunden auf Updates (alle Arten)."""
    time.sleep(90)
    while True:
        wait = 6 * 3600
        try:
            st = vs_update_status(force=True)
            ok = sys_check(sync=True)
            if not ok:
                wait = 600                             # Auftrag oder xbps im Terminal: in 10 min nochmal
            log("Update-Pruefung: VoidStation", "verfuegbar " + str(st["remote"]) if st["available"] else "aktuell",
                f"(Kanal {st['channel']})", st["error"] or "",
                "| System:", sys_state()["count"] if ok else "uebersprungen (xbps/Auftrag laeuft)")
        except Exception as e:  # noqa: BLE001
            log("Update-Pruefung fehlgeschlagen:", e)
        time.sleep(wait)


def kernel_autopurge():
    """Alte Kernel automatisch entfernen, sobald das System mit dem neuesten Kernel fehlerfrei laeuft:
    die Oberflaeche ist seit 10 Minuten oben und es laeuft der neueste installierte Kernel.
    Einmal je Start der Oberflaeche; laeuft gerade ein Auftrag oder xbps, spaeter nochmal."""
    time.sleep(600)
    for _ in range(12):
        try:
            rb = reboot_needed()
            if rb["kernel"] or rb["kernel_stuck"]:
                return                                 # neuester Kernel laeuft (noch) nicht: nichts anfassen
            ks = [d.name for d in Path("/usr/lib/modules").iterdir()
                  if d.is_dir() and Path(f"/boot/vmlinuz-{d.name}").is_file()]
            if len(ks) < 2:
                return
            if JOBS.busy() or xbps_busy() or not SYS_LOCK.acquire(timeout=5):
                time.sleep(600)
                continue
            try:
                r = run(["sudo", "-n", PKG_HELPER, "kernelpurge"], timeout=600)
            finally:
                SYS_LOCK.release()
            out = ((r.stdout or "") + (r.stderr or "")).strip() if r else "kein Ergebnis"
            log("Alte Kernel:", out.replace("\n", " | "))
            if r and r.returncode == 0:
                return
        except Exception as e:  # noqa: BLE001
            log("Alte Kernel entfernen fehlgeschlagen:", e)
        time.sleep(600)


def shutil_which(name):
    return shutil.which(name)


JOBS = Jobs()


# ---------------------------------------------------------------------------
#  Programme, die ausserhalb des AppCenters installiert wurden (z. B. per xbps-install im Terminal):
#  werden ueber ihre .desktop-Dateien gefunden und lassen sich als Kachel anlegen
# ---------------------------------------------------------------------------
DESKTOP_DIRS = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
                Path("/var/lib/flatpak/exports/share/applications"),
                Path.home() / ".local/share/flatpak/exports/share/applications",
                Path.home() / ".local/share/applications"]
# Teile des Systems, die keine eigene Kachel brauchen
LOCAL_SKIP = {"openbox", "obconf", "xterm", "uxterm", "pcmanfm-desktop-pref", "libfm-pref-apps", "lxshortcut",
              "gparted", "voidstation", "org.gnome.zenity", "mpv", "vlc", "firefox", "nm-connection-editor",
              "pavucontrol", "xdg-desktop-portal-gtk", "gcr-prompter", "gcr-viewer", "org.gnome.gcr",
              "display-im6.q16", "cups", "htop", "nano", "mousepad", "fastfetch", "pcmanfm", "flatpak",
              "org.freedesktop.impl.portal"}
FIELD_CODES = re.compile(r"%[fFuUdDnNickvm]")
LOCAL_ICONS = [("Game", "gamepad"), ("Emulator", "gamepad"), ("Audio", "music"), ("Video", "film"), ("AudioVideo", "film"),
               ("Graphics", "image"), ("Photography", "image"), ("WebBrowser", "globe"), ("Network", "globe"),
               ("Office", "chart"), ("Education", "store"), ("Development", "terminal"), ("System", "terminal"), ("FileManager", "folder"), ("Utility", "store")]


def _desktop_entry(path):
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    e, sect = {}, None
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("["):
            sect = line
            continue
        if sect == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            e.setdefault(k.strip(), v.strip())
    return e


def local_apps():
    """Programme mit .desktop-Datei, die weder im Katalog noch als eigene Kachel vorkommen."""
    lang = ui_lang().replace("-", "_")               # .desktop-Schluessel: Name[pt_BR], Name[fr]
    cat = catalog()
    known_bins = {Path(str(a["cmd"][0])).name for a in cat["apps"] if isinstance(a.get("cmd"), list) and a["cmd"]}
    known_bins |= {a["source"].get("pkg") for a in cat["apps"] if a["source"].get("pkg")}
    for a in cat["apps"]:                            # "for b in A B; do …" -> A und B
        m = re.match(r"for b in ([^;]+);", a.get("cmd")) if isinstance(a.get("cmd"), str) else None
        known_bins |= set(m.group(1).split()) if m else set()
    known_bins.discard("flatpak")                    # Flatpaks werden ueber ihre ID erkannt, nicht ueber "flatpak run"
    known_refs = {a["source"]["ref"] for a in cat["apps"] if a["source"].get("ref")}
    tiles = {t.get("id"): t for g in load_config().get("groups", []) for t in g.get("tiles", [])}
    tile_bins = {Path(str(t["cmd"][0])).name for t in tiles.values() if isinstance(t.get("cmd"), list) and t["cmd"]}
    out, seen = [], set()
    for d in DESKTOP_DIRS:
        for f in sorted(d.glob("*.desktop")) if d.is_dir() else []:
            stem = f.stem
            if stem in seen or stem.lower() in LOCAL_SKIP or stem.startswith(("org.gnome.Settings", "vim", "nvim")):
                continue
            e = _desktop_entry(f)
            if not e or e.get("Type") != "Application" or e.get("NoDisplay") == "true" or e.get("Hidden") == "true":
                continue
            if e.get("OnlyShowIn") or not e.get("Exec") or not e.get("Name"):
                continue
            try:
                args = [a for a in shlex.split(FIELD_CODES.sub("", e["Exec"])) if a]
            except ValueError:
                continue
            if not args or args[0] == "env" and len(args) < 2:
                continue
            binary = Path(args[0]).name
            if e.get("TryExec") and not shutil.which(e["TryExec"]):
                continue
            if not (shutil.which(args[0]) or Path(args[0]).exists()):
                continue
            aid = "desk-" + re.sub(r"[^A-Za-z0-9_.-]", "_", stem)
            if stem in known_refs or (binary == "flatpak" and known_refs & set(args)):
                continue                              # Flatpak aus dem Katalog
            if aid not in tiles and (binary in known_bins or binary in tile_bins):
                continue                              # schon als Katalog-App oder Standard-Kachel vorhanden
            seen.add(stem)
            if e.get("Terminal") == "true":
                args = ["xterm", "-fa", "DejaVu Sans Mono", "-fs", "14", "-e"] + args
            cats = e.get("Categories", "")
            icon = next((i for k, i in LOCAL_ICONS if k in cats.split(";")), "globe")
            loc = lambda k: e.get(f"{k}[{lang}]") or e.get(f"{k}[{lang.split('_')[0]}]")   # pt_BR, sonst pt
            name = loc("Name") or e["Name"]
            desc = loc("Comment") or e.get("Comment") or loc("GenericName") or e.get("GenericName") or ""
            out.append({"id": aid, "name": name, "desc": desc, "cmd": args, "icon": icon, "tile": aid in tiles,
                        "game": "Game" in cats})
    return sorted(out, key=lambda a: a["name"].lower())


def local_tile(aid, on):
    a = next((x for x in local_apps() if x["id"] == aid), None)
    if not a:
        raise RuntimeError("Programm nicht gefunden")
    if not on:
        tile_remove(aid)
        return
    palette = ["#2f3d57", "#3b2f4f", "#284843", "#4a3a2a", "#2d3763", "#453040"]
    tile_add({"id": aid, "name": a["name"], "cmd": a["cmd"], "source": {"type": "local"},
              "tile": {"group": "Spiele" if a["game"] else "Programme", "size": "medium", "icon": a["icon"],
                       "color": palette[sum(map(ord, aid)) % len(palette)]}})


LOCAL_CAT = "Auf diesem Gerät"     # ausserhalb des AppCenters installiert – erscheint nur unter "Installiert"


def apps_payload():
    """AppCenter-Daten: Kategorien in Katalog-Reihenfolge, alle Apps mit Stand. Die Seitenleiste
    ("Installiert" + Kategorien) baut die Oberflaeche selbst daraus."""
    cat = catalog()
    pkgs, fps = installed_sets()
    tiles = tile_ids()
    apps = []
    for a in cat["apps"]:
        item = {k: a[k] for k in ("id", "name", "desc", "cat")}
        item["type"] = a["source"]["type"]
        item["installed"] = app_installed_in(a, pkgs, fps, tiles)
        if not item["installed"] and not app_supported(a):      # gibt es fuer diese Architektur nicht (32 Bit)
            continue
        item["tile"] = a["id"] in tiles
        item["icon"] = a.get("tile", {}).get("icon", "globe")
        item["color"] = a.get("tile", {}).get("color", "#2f3238")
        apps.append(item)
    cats = list(cat["categories"])
    try:
        for a in local_apps():
            apps.append({"id": a["id"], "name": a["name"], "desc": a["desc"], "cat": LOCAL_CAT, "type": "local",
                         "installed": True, "tile": a["tile"], "icon": a["icon"], "color": "#2f3238"})
    except Exception as e:  # noqa: BLE001 – eine kaputte .desktop-Datei darf das AppCenter nicht verhindern
        log("Programme suchen:", e)
    return {"categories": cats, "local_cat": LOCAL_CAT, "apps": apps, "job": JOBS.current()}


def ssh_state():
    return Path("/var/service/sshd").exists()


def can_suspend():
    """Standby moeglich? Der Kernel muss "mem" oder "freeze" anbieten; im Live-System nie."""
    if LIVE:
        return False
    try:
        states = Path("/sys/power/state").read_text().split()
    except OSError:
        return False
    return "mem" in states or "freeze" in states


def _sysread(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return ""


def _suspend_counts():
    """(geglueckt, abgebrochen) aus /sys/power/suspend_stats – None, wenn nicht lesbar."""
    s, f = _sysread("/sys/power/suspend_stats/success"), _sysread("/sys/power/suspend_stats/fail")
    return (int(s), int(f)) if s.isdigit() and f.isdigit() else None


def _wakeup_counts():
    """Ereigniszaehler aller Weckquellen (/sys/class/wakeup/wakeupN/event_count)."""
    out = {}
    for w in Path("/sys/class/wakeup").glob("wakeup*"):
        n = _sysread(w / "event_count")
        if n.isdigit():
            out[w.name] = int(n)
    return out


def wake_sources(before, after, irq=True):
    """Lesbarer Weckgrund aus den gestiegenen Weckzaehlern. USB-Geraete mit Produktnamen zuerst –
    Einschaltknopf (PNP0C0C) und PCI-Bruecken zaehlen bei S3 meist mit und sagen allein wenig."""
    usb, other = [], []
    for k, n in sorted(after.items()):
        if n <= before.get(k, 0):
            continue
        w = Path("/sys/class/wakeup") / k
        name = _sysread(w / "name")
        try:
            dev = (w / "device").resolve(strict=True)
        except OSError:
            dev = None
        prod = _sysread(dev / "product") if dev else ""
        if prod:
            usb.append(f"USB {name} ({' '.join(x for x in (_sysread(dev / 'manufacturer'), prod) if x)})")
        elif name and not name.startswith("device:"):
            other.append(name)
    parts = usb or other
    if irq:
        n = _sysread("/sys/power/pm_wakeup_irq")
        if n.isdigit():
            desc = ""
            try:
                for line in Path("/proc/interrupts").read_text().splitlines():
                    if line.strip().startswith(n + ":"):
                        desc = " ".join(re.sub(r"^\s*\d+:\s+(\d+\s+)*", "", line).split())
                        break
            except OSError:
                pass
            parts = parts + [f"IRQ {n}" + (f" {desc}" if desc else "")]
    return ", ".join(parts) or "unbekannt"


def resume_watcher():
    """Nach dem Standby: Aufloesung erneut setzen (manche HDMI-Ausgaenge kommen sonst mit anderem Modus zurueck –
    apply_resolution aendert nur, was abweicht) und Weckgrund bzw. Abbruch ins Protokoll schreiben.
    Erkennt das Aufwachen an /sys/power/suspend_stats (Rueckfall: CLOCK_BOOTTIME zaehlt die Schlafzeit mit,
    CLOCK_MONOTONIC nicht). Abbruch = Standby kam gar nicht zustande, z. B. Weckereignis beim Einschlafen."""
    def gap():
        return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()

    def dur(sec):
        return f"{sec:.0f} s" if sec < 120 else f"{sec / 60:.1f} min"

    last_gap, last_cnt, last_wake = gap(), _suspend_counts(), _wakeup_counts()
    while True:
        time.sleep(5)
        g, cnt, wake = gap(), _suspend_counts(), _wakeup_counts()
        slept = g - last_gap
        if cnt is not None and last_cnt is not None:
            woke, failed = cnt[0] > last_cnt[0], cnt[1] > last_cnt[1]
        else:
            woke, failed = slept > 10, False
        if failed:
            st = "/sys/power/suspend_stats/"
            step, dev, err = (_sysread(st + x) for x in ("last_failed_step", "last_failed_dev", "last_failed_errno"))
            detail = ", ".join(x for x in (f"Schritt {step}" if step else "", f"Geraet {dev}" if dev else "",
                                           f"Fehler {err}" if err else "") if x)
            log(f"Standby abgebrochen ({detail or 'ohne Angabe'}) – ausgeloest von: "
                f"{wake_sources(last_wake, wake, irq=False)}")
        if woke:
            log(f"aus dem Standby zurueck (nach {dur(max(slept, 0))}) – geweckt von: {wake_sources(last_wake, wake)}")
            time.sleep(3)                               # Bildschirm und Treiber erst aufwachen lassen
            try:
                apply_resolution(settings_load().get("resolution"))
            except Exception as e:  # noqa: BLE001
                log("Aufloesung nach dem Standby:", e)
            g, cnt, wake = gap(), _suspend_counts(), _wakeup_counts()
        last_gap, last_cnt, last_wake = g, cnt, wake


def settings_payload():
    s = settings_load()
    return {"version": vs_version(), "ssh": ssh_state(), "live": LIVE, "standby": can_suspend(),
            "lang": ui_lang(s), "langs": LANGS,
            "scale": s["scale"], "scales": SCALES,
            "theme": s.get("theme", "default-dark"), "themes": available_themes(),
            "cursor": {"theme": s.get("cursor_theme"), "size": s.get("cursor_size"),
                       "themes": [{"id": t, "label": CURSOR_NAMES[t]} for t in cursor_themes()],
                       "sizes": CURSOR_SIZES}, "displays": xrandr_info(),
            "audio": audio_info(), "volume": volume_get(), "net": net_info(), "share": share_info(),
            "sysupd_days": sysupd_days(s), "sysupd_choices": SYSUPD_DAYS,
            "frontend": frontend(), "frontends": frontends(), "padmouse": bool(s.get("padmouse", True))}


# ---------------------------------------------------------------------------
#  Live-System und Installer (voidstation-installer laeuft als root per sudo)
# ---------------------------------------------------------------------------
LIVE = Path("/etc/voidstation-live").exists()
INSTALLER = "/usr/local/sbin/voidstation-installer"


def cmdline_flag(name):
    try:
        return name in Path("/proc/cmdline").read_text().split()
    except OSError:
        return False


class Installer:
    """Startet den Installer, liest seine JSON-Zeilen und haelt den Stand fuer die Oberflaeche bereit."""

    def __init__(self):
        self.lock = threading.RLock()                   # start() ruft status() unter derselben Sperre auf
        self.proc = None
        self.state = None
        self.autostart = LIVE and cmdline_flag("voidstation.install")
        self.probe_cache = None

    def _root(self, args, timeout=180, stdin=None):
        return subprocess.run(["sudo", "-n", INSTALLER] + args, input=stdin, capture_output=True, text=True, timeout=timeout)

    def probe(self, force=False):
        if self.probe_cache and not force:
            return self.probe_cache
        r = self._root(["probe"])
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr).strip()[-300:] or "probe fehlgeschlagen")
        p = json.loads(r.stdout)
        disp = xrandr_info()
        p["screen"] = {"name": disp[0]["name"], "mode": disp[0]["current"], "rate": disp[0].get("rate")} if disp else None
        p["favs"] = {"radio": len(favs_load()), "tv": len(tvfavs_load())}
        p["live_home"] = str(Path.home())
        p["lang"] = ui_lang() if ui_lang() in ("de", "en") else "en"   # Installer kennt bisher nur de/en
        self.probe_cache = p
        return p

    def running(self):
        return bool(self.proc and self.proc.poll() is None)

    def start(self, cfg=None, resume=False, alt=False):
        with self.lock:
            if self.running() or (self.state and self.state.get("detached")):
                raise RuntimeError("Installation laeuft bereits")
            args = ["run"] + (["--resume"] if resume else []) + (["--alt"] if alt else [])
            if not resume:
                cfg = dict(cfg or {})
                cfg["live_home"] = str(Path.home())
                self.state = {"state": "running", "pct": 0, "phase": None, "phases": {}, "detail": None,
                              "started": time.time(), "mode": cfg.get("mode")}
            else:
                self.state = dict(self.state or {"phases": {}, "started": time.time()}, state="running", error=None, detached=False)
            # eigene Sitzung: laeuft auch weiter, wenn die Startseite neu startet
            self.proc = subprocess.Popen(["sudo", "-n", INSTALLER] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, start_new_session=True)
            try:
                self.proc.stdin.write(json.dumps(cfg) if not resume else "")
                self.proc.stdin.close()
            except OSError:
                pass
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
            log("Installation gestartet", "(neuer Versuch)" if resume else "", "(Ausweichweg)" if alt else "")
            return self.status()

    def _read(self, proc):
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                st = self.state
                kind = ev.get("ev")
                if kind == "progress":
                    st.update(pct=ev.get("pct", st.get("pct")), phase=ev.get("phase"),
                              phase_pct=ev.get("phase_pct"), copy={k: ev[k] for k in ("done", "total", "eta") if k in ev} or st.get("copy"),
                              detail=ev.get("detail"))
                elif kind == "phase":
                    st["phases"][ev["phase"]] = ev["state"]
                    st["phase"] = ev["phase"]
                elif kind == "error":
                    st.update(state="error", error={k: ev.get(k) for k in ("phase", "code", "msg", "done", "foreign_untouched", "log", "alt")})
                    if ev.get("phase"):
                        st["phases"][ev["phase"]] = "error"
                elif kind == "done":
                    st.update(state="done", pct=100, result=ev)
        proc.wait()
        with self.lock:
            if self.state and self.state.get("state") == "running":
                self.state.update(state="error", error={"code": "internal", "msg": f"Installer beendet (Code {proc.returncode})",
                                                        "phase": self.state.get("phase"), "done": [], "log": [], "alt": False})
        log("Installation:", self.state.get("state") if self.state else "?")

    def status(self):
        if self.proc is None and LIVE and (self.state is None or self.state.get("detached")):
            self._reattach()
        with self.lock:
            return dict(self.state or {"state": "idle"}, running=self.running() or bool(self.state and self.state.get("detached")))

    def _reattach(self):
        """Startseite wurde neu gestartet: Stand beim Installer abfragen (laeuft er noch, als 'detached')."""
        try:
            st = json.loads(self._root(["status"], timeout=20).stdout or "{}")
        except (OSError, ValueError, subprocess.SubprocessError):
            st = {}
        if not st.get("config"):
            return
        alive = subprocess.run(["pgrep", "-f", INSTALLER + " run"], capture_output=True).returncode == 0
        done = st.get("done", [])
        weights = {"check": 2, "shrink": 8, "partition": 2, "format": 3, "copy": 60, "configure": 15, "boot": 7, "cleanup": 3}
        err = st.get("error")
        state = "done" if st.get("finished") else "running" if alive else "error"
        phases = {p: "done" for p in done}
        if alive and st.get("current"):
            phases[st["current"]] = "running"
        if err and not alive:
            phases[err.get("phase")] = "error"
        cfg = st["config"]
        self.state = {
            "state": state, "detached": alive, "phases": phases, "phase": st.get("current"), "mode": cfg.get("mode"),
            "pct": 100 if st.get("finished") else round(sum(weights.get(p, 0) for p in done) / sum(weights.values()) * 100),
            "started": st.get("started"),
            "error": None if state != "error" else dict(err or {"code": "internal", "msg": "abgebrochen", "phase": st.get("current")},
                                                        done=done, log=[], alt=(err or {}).get("phase") == "boot"),
            "result": {"user": cfg.get("user", {}).get("name"), "login": cfg.get("user", {}).get("login"),
                       "hostname": cfg.get("hostname"), "seconds": int(st["finished"] - (st.get("started") or st["finished"]))}
            if st.get("finished") else None}

    def gparted(self):
        disp = os.environ.get("DISPLAY", ":0")
        xa = os.environ.get("XAUTHORITY") or str(Path.home() / ".Xauthority")
        r = self._root(["gparted", disp, xa], timeout=30)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr).strip()[-300:] or "GParted startet nicht")
        self.probe_cache = None

    @staticmethod
    def gparted_running():
        return subprocess.run(["pgrep", "-x", "gparted"], capture_output=True).returncode == 0 or \
            subprocess.run(["pgrep", "-f", "gpartedbin"], capture_output=True).returncode == 0

    def savelog(self):
        r = self._root(["savelog"], timeout=60)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"ok": False, "code": "no_usb"}

    def log_text(self):
        return self._root(["log"], timeout=20).stdout


INSTALL = Installer()
KEYMAPS = {"de": ["de"], "us": ["us"], "gb": ["gb"]}


# ---------------------------------------------------------------------------
#  ROMs & Emulatoren: Spiele aus der Samba-Freigabe ~/share/ROMs/<system>
# ---------------------------------------------------------------------------
class ROMManager:
    """Verwaltet Spiele (ROMs) aus der Samba-Freigabe ~/share/ROMs/<system>."""
    # Mapping von Kachel-ID auf Ordnername in ~/share/ROMs/
    TILE_TO_SYSTEM = {
        "gba": "gba",
        "snes9x": "snes",
        "nestopia": "nes",
        "duckstation": "psx",
        "melonds": "nds",
        "ppsspp": "psp",
        "flycast": "dreamcast",
        "dolphin": "gamecube",
        "retroarch": "retroarch",
    }
    SYSTEM_TO_TILE = {v: k for k, v in TILE_TO_SYSTEM.items()}
    SYSTEM_TO_TILE["gbc"] = "gba"
    # Weitere Ordner, die eine Kachel mit anzeigt (erster Ordner = Hauptordner der Kachel).
    # mGBA spielt auch Game Boy (Color): Spiele aus ROMs/gba und ROMs/gbc stehen in einer Liste.
    SYSTEM_FOLDERS = {
        "gba": ["gba", "gbc"],
    }

    EXTENSIONS = {
        "gba": [".gba", ".gbc", ".gb", ".zip", ".7z"],
        "gbc": [".gbc", ".gb", ".zip", ".7z"],
        "snes": [".sfc", ".smc", ".zip", ".7z"],
        "nes": [".nes", ".zip", ".7z"],
        "psx": [".iso", ".cue", ".bin", ".chd", ".pbp"],
        "psp": [".iso", ".cso", ".pbp"],
        "nds": [".nds", ".zip"],
        "gamecube": [".iso", ".rvz", ".gcm"],
        "dreamcast": [".cdi", ".gdi", ".chd"],
        "n64": [".z64", ".n64", ".v64"],
        "c64": [".d64", ".t64", ".prg", ".crt"],
        "atari2600": [".a26", ".bin"],
        "megadrive": [".md", ".bin", ".smd", ".gen", ".zip", ".7z"],
        "genesis": [".md", ".bin", ".smd", ".gen", ".zip", ".7z"],
        "scummvm": [".scummvm"],
        "dos": [".conf", ".exe", ".bat"],
    }
    # Befehle aus catalog.json als Basis/Fallback
    EMULATOR_CMD = {
        "gba": ["mgba-qt"],
        "gbc": ["mgba-qt"],
        "snes": ["snes9x-gtk"],
        "nes": ["nestopia"],
        "psx": ["~/.local/share/voidstation/apps/duckstation/AppRun"],
        "psp": ["PPSSPPSDL", "ppsspp", "PPSSPPQt"],   # erster vorhandener
        "nds": ["melonDS"],
        "dreamcast": ["flatpak", "run", "org.flycast.Flycast"],
        "gamecube": ["dolphin-emu"],
        "megadrive": ["mednafen"],
        "genesis": ["mednafen"],
    }

    def __init__(self):
        self.rom_dir = Path.home() / "share" / "ROMs"

    def canonical_system(self, sys_or_tile):
        return self.TILE_TO_SYSTEM.get(sys_or_tile, sys_or_tile)

    def folders(self, sys_or_tile):
        """Ordner unter ~/share/ROMs, deren Spiele die Kachel bzw. das System zeigt (Hauptordner zuerst)."""
        canon = self.canonical_system(sys_or_tile)
        return list(self.SYSTEM_FOLDERS.get(canon, [canon]))

    def list_folder(self, folder):
        """Spiele genau eines Ordners ~/share/ROMs/<folder>."""
        sys_dir = self.rom_dir / folder
        if not sys_dir.is_dir():
            return []
        valid_exts = set(self.EXTENSIONS.get(folder, [".zip"]))
        roms = []
        try:
            for item in sorted(sys_dir.iterdir()):
                if item.is_file() and item.suffix.lower() in valid_exts:
                    name = item.stem
                    clean_name = re.sub(r"\s*[\(\[][^()\[\]]*[\)\]]", "", name).strip() or name
                    size_bytes = item.stat().st_size
                    size_mb = round(size_bytes / (1024 * 1024), 1)
                    size_str = f"{size_mb} MB" if size_mb >= 1 else f"{round(size_bytes / 1024)} KB"
                    roms.append({
                        "id": hashlib.sha1(str(item).encode()).hexdigest()[:10],
                        "name": clean_name,
                        "filename": item.name,
                        "system": folder,
                        "folder": folder,
                        "size": size_str,
                        "bytes": size_bytes,
                    })
        except OSError as e:
            log(f"ROMs fuer {folder} nicht lesbar:", e)
        return roms

    def list_roms(self, system):
        """Spiele einer Kachel bzw. eines Systems, aus allen zugehoerigen Ordnern, alphabetisch."""
        folders = self.folders(system)
        roms = []
        for folder in folders:
            roms += self.list_folder(folder)
        if len(folders) > 1:
            roms.sort(key=lambda r: (r["name"].casefold(), r["filename"].casefold()))
        return roms

    def launch(self, system, filename, folder=None):
        canon = self.canonical_system(system)
        safe_name = os.path.basename(filename)
        # Ordner: der vom Spiel mitgeschickte (falls er zur Kachel gehoert), sonst alle der Kachel der Reihe nach
        allowed = self.folders(system)
        cands = [folder] if folder in allowed else allowed
        target = None
        for f in cands:
            sys_dir = (self.rom_dir / f).resolve()
            t = (sys_dir / safe_name).resolve()
            if t.is_file() and t.is_relative_to(sys_dir):
                target = t
                break
        if not target:
            raise ValueError("Spieldatei nicht gefunden")

        # 1. Kachel-Befehl (tiles.json), 2. Katalog (catalog.json) – nur als Liste;
        #    Shell-Befehle (z. B. PPSSPP: "for b in ...; do exec $b; done") koennen keine Datei uebergeben
        cmd = None
        tid = self.SYSTEM_TO_TILE.get(canon, canon)
        for src in (find_tile(system), find_tile(tid), catalog_app(system), catalog_app(tid)):
            if src and isinstance(src.get("cmd"), list):
                cmd = expand(src["cmd"]) + [str(target)]
                break
        # 3. Fallback: erstes vorhandene Programm aus EMULATOR_CMD
        if not cmd and canon in self.EMULATOR_CMD:
            cands = self.EMULATOR_CMD[canon]
            if canon == "psp":
                exe = next((c for c in cands if shutil.which(c)), None)
                cmd = [exe, str(target)] if exe else None
            else:
                cmd = expand(cands) + [str(target)]
        if not cmd:
            raise ValueError(f"Kein Emulator fuer {canon} konfiguriert")

        # Unter der Kennung der Kachel starten (frueher "rom_<system>"): Nur so kennt die Startseite das Spiel als
        # laufend – Kachel holt es zurueck, Y bzw. die heisse Ecke beenden es –, und ein zweites Spiel startet
        # keine weitere, dann nicht mehr erreichbare Instanz.
        key = system if find_tile(system) else tid
        if APPS._get(key):
            log("Emulator laeuft schon, wird fuer das neue Spiel beendet:", key)
            APPS.close(key)
        media_notify("background")
        return APPS.start(key, cmd)


ROMS = ROMManager()


# ---------------------------------------------------------------------------
#  Emulatoren: Vorgaben (Vollbild, Grafik, Controller), Spielstand-Sicherung, Cover in der Spieleliste
# ---------------------------------------------------------------------------
def ini_read(path):
    """Einfache INI-Datei -> {abschnitt: {schluessel: wert}} (Gross-/Kleinschreibung bleibt, keine Interpolation)."""
    out, sec = {}, None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]
            out.setdefault(sec, {})
        elif sec is not None and "=" in s and not s.startswith((";", "#")):
            k, v = s.split("=", 1)
            out[sec][k.strip()] = v.strip()
    return out


def ini_update(path, section, values, remove=()):
    """Schluessel in genau einem Abschnitt setzen bzw. entfernen; ein fehlender Abschnitt kommt ans Ende.
    Alles andere in der Datei bleibt, wie es ist (anders als _ini_set, das Schluessel in allen Abschnitten loescht)."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    head = f"[{section}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == head), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            lines.append("")
        lines.append(head)
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    todo, drop, body = dict(values), set(remove), []
    for line in lines[start + 1:end]:
        k = line.split("=", 1)[0].strip() if "=" in line else None
        if k in drop:
            continue
        if k in todo:
            body.append(f"{k}={todo.pop(k)}")
            continue
        body.append(line)
    while body and not body[-1].strip():
        body.pop()
    body += [f"{k}={v}" for k, v in todo.items()]
    new = lines[:start + 1] + body + ([""] if end < len(lines) else []) + lines[end:]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".vs-tmp")
    tmp.write_text("\n".join(new) + "\n", encoding="utf-8")
    tmp.replace(path)


EMU_STATE = BASE / "emu-defaults.json"      # was VoidStation zuletzt in die Einstellungen der Emulatoren geschrieben hat
EMU_LOCK = threading.Lock()


def emu_state_load():
    try:
        st = json.loads(EMU_STATE.read_text(encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def emu_state_save(st):
    try:
        tmp = EMU_STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(EMU_STATE)
    except OSError as e:
        log("emu-defaults.json:", e)


def ini_defaults(app, path, section, wanted, st):
    """Vorgaben von VoidStation in eine INI schreiben – aber nur Schluessel, die fehlen oder noch genau den Wert
    haben, den VoidStation zuletzt geschrieben hat. Was der Nutzer im Programm selbst umgestellt hat, bleibt."""
    mine = st.setdefault(app, {}).setdefault(section, {})
    cur = ini_read(path).get(section, {})
    todo = {k: v for k, v in wanted.items() if (k not in cur or cur[k] == mine.get(k)) and cur.get(k) != v}
    if todo:
        ini_update(path, section, todo)
        log(f"{app}: Vorgaben gesetzt:", ", ".join(f"{k}={v}" for k, v in todo.items()))
    for k, v in wanted.items():
        if k not in cur or cur[k] == mine.get(k) or cur[k] == v:
            mine[k] = v


# ---- Controller: welche Taste ist welche? ------------------------------------------------------------------
# mGBA liest Controller roh ueber SDL (Tastennummern statt "A/B"), und die Nummern haengen am Treiber: Ein
# PS4-Nachbau, ein DualSense und ein Xbox-Pad zaehlen ihre Tasten verschieden. Woher die Belegung kommt, der Reihe nach:
#   1. eigene Belegung in ~/.config/voidstation/pads.json (dieselbe Datei wie fuer die Startseite:
#      {"<Geraetename oder vid:pid>": {"<evdev-Code>": "a"|"b"|"x"|"y"|"lb"|"rb"|"select"|"start"|"l3"|…}})
#   2. SDL selbst (dieselbe Bibliothek, die mGBA laedt): SDL kennt die meisten Controller samt Nachbauten aus seiner
#      Datenbank und sagt, welche rohe Taste "unten", "rechts", "oben" … ist (SDL_GameControllerGetBindForButton)
#   3. Notfalls die Linux-Tastencodes (BTN_SOUTH = unten, BTN_EAST = rechts …)
# Rollen wie bei SDL/Xbox nach Lage: a = unten (✕), b = rechts (○), x = links (□), y = oben (△).
# SDL zaehlt Tasten unter Linux so (joystick/linux/SDL_sysjoystick.c, ConfigJoystick): erst alle Codes ab
# BTN_JOYSTICK (0x120) aufsteigend, dann die darunter; Achsen nach Nummer ohne digitale Steuerkreuze (ABS_HAT*).
# Damit das gilt, starten Emulatoren mit SDL_JOYSTICK_HIDAPI=0 (sonst zaehlt SDL PS4/PS5/Switch ueber hidraw anders).
PADS_OVERRIDE = Path.home() / ".config/voidstation/pads.json"
SDL_PROBE = r'''
import ctypes, ctypes.util, json, os, sys
os.environ["SDL_JOYSTICK_HIDAPI"] = "0"
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
lib = None
for n in ("libSDL2-2.0.so.0", ctypes.util.find_library("SDL2") or ""):
    if n:
        try:
            lib = ctypes.CDLL(n)
            break
        except OSError:
            pass
if lib is None:
    print("[]"); sys.exit()
class Hat(ctypes.Structure):
    _fields_ = [("hat", ctypes.c_int), ("mask", ctypes.c_int)]
class Val(ctypes.Union):
    _fields_ = [("button", ctypes.c_int), ("axis", ctypes.c_int), ("hat", Hat)]
class Bind(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("value", Val)]
lib.SDL_Init.argtypes = [ctypes.c_uint32]
if lib.SDL_Init(0x200 | 0x2000) != 0:              # JOYSTICK | GAMECONTROLLER
    print("[]"); sys.exit()
lib.SDL_JoystickNameForIndex.restype = ctypes.c_char_p
has_path = hasattr(lib, "SDL_JoystickPathForIndex")
if has_path:
    lib.SDL_JoystickPathForIndex.restype = ctypes.c_char_p
lib.SDL_GameControllerOpen.restype = ctypes.c_void_p
lib.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
for f in ("SDL_GameControllerGetBindForButton", "SDL_GameControllerGetBindForAxis"):
    getattr(lib, f).restype = Bind
    getattr(lib, f).argtypes = [ctypes.c_void_p, ctypes.c_int]
def enc(b):
    if b.type == 1: return {"button": b.value.button}
    if b.type == 2: return {"axis": b.value.axis}
    if b.type == 3: return {"hat": b.value.hat.hat, "mask": b.value.hat.mask}
    return None
BTN = (("a", 0), ("b", 1), ("x", 2), ("y", 3), ("select", 4), ("guide", 5), ("start", 6), ("l3", 7), ("r3", 8),
       ("lb", 9), ("rb", 10), ("up", 11), ("down", 12), ("left", 13), ("right", 14))
AX = (("lx", 0), ("ly", 1), ("lt", 4), ("rt", 5))
out = []
for i in range(lib.SDL_NumJoysticks()):
    d = {"index": i, "name": (lib.SDL_JoystickNameForIndex(i) or b"").decode("utf-8", "replace"),
         "path": (lib.SDL_JoystickPathForIndex(i) or b"").decode() if has_path else ""}
    if lib.SDL_IsGameController(i):
        c = lib.SDL_GameControllerOpen(i)
        if c:
            d["buttons"] = {n: enc(lib.SDL_GameControllerGetBindForButton(c, k)) for n, k in BTN}
            d["axes"] = {n: enc(lib.SDL_GameControllerGetBindForAxis(c, k)) for n, k in AX}
            lib.SDL_GameControllerClose(c)
    out.append(d)
lib.SDL_Quit()
print(json.dumps(out))
'''


def sdl_probe():
    """Was SDL ueber die angeschlossenen Controller weiss (Name wie in mGBA, Pfad, Belegung). [] wenn SDL fehlt."""
    try:
        r = subprocess.run([sys.executable, "-I", "-c", SDL_PROBE], capture_output=True, text=True, timeout=10,
                           env=dict(os.environ, SDL_JOYSTICK_HIDAPI="0"))
        out = json.loads(r.stdout.strip() or "[]")
        return out if isinstance(out, list) else []
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log("SDL-Abfrage der Controller:", e)
        return []


def gamepads():
    """Angeschlossene Gamepads (evdev) in der Reihenfolge, in der SDL sie findet (nach Geraetenummer)."""
    try:
        import evdev  # type: ignore
        from evdev import ecodes as E
    except ImportError:
        return []
    out = []
    for p in sorted(evdev.list_devices(), key=lambda s: int(re.sub(r"\D", "", s) or 0)):
        try:
            d = evdev.InputDevice(p)
            caps = d.capabilities()
            name, info = d.name, d.info
            d.close()
        except OSError:
            continue
        keys = set(caps.get(E.EV_KEY, []))
        axes = {a[0] if isinstance(a, (tuple, list)) else a for a in caps.get(E.EV_ABS, [])}
        pen = keys & {E.BTN_TOUCH, E.BTN_TOOL_PEN, E.BTN_STYLUS, E.BTN_TOOL_FINGER}
        pad = (E.BTN_SOUTH in keys or E.BTN_TRIGGER in keys) and not pen
        if pad and (E.ABS_X in axes or E.ABS_HAT0X in axes or E.BTN_DPAD_UP in keys):
            out.append({"path": p, "name": name, "id": f"{info.vendor:04x}:{info.product:04x}",
                        "keys": keys, "axes": axes})
    return out


def sdl_indices(pad):
    """(Tasten, Achsen) eines Gamepads als {evdev-Code: SDL-Nummer}."""
    from evdev import ecodes as E
    keys = pad["keys"]
    order = sorted(k for k in keys if E.BTN_JOYSTICK <= k < E.KEY_MAX) + sorted(k for k in keys if k < E.BTN_JOYSTICK)
    axes = sorted(a for a in pad["axes"] if not E.ABS_HAT0X <= a <= E.ABS_HAT3Y)
    return {k: i for i, k in enumerate(order)}, {a: i for i, a in enumerate(axes)}


def pad_roles(pad, probe=None):
    """Rolle -> evdev-Code fuer ein Gamepad (a/b/x/y/lb/rb/select/start/l3/r3/up/down/left/right, soweit bekannt)
    und woher die Belegung stammt ("eigene", "SDL", "Linux")."""
    from evdev import ecodes as E
    try:
        own = json.loads(PADS_OVERRIDE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        own = {}
    for k in (pad["name"], pad.get("id")):
        if isinstance(own.get(k), dict):
            roles = {str(v): int(c) for c, v in own[k].items() if str(c).isdigit()}
            return roles, "eigene"
    btn, _ax = sdl_indices(pad)
    by_index = {i: c for c, i in btn.items()}
    sdl = next((d for d in (probe or []) if d.get("path") == pad["path"] and d.get("buttons")), None)
    if sdl:
        roles = {r: by_index[b["button"]] for r, b in sdl["buttons"].items()
                 if b and "button" in b and b["button"] in by_index}
        if "a" in roles and "b" in roles:
            return roles, "SDL"
    std = {"a": E.BTN_SOUTH, "b": E.BTN_EAST, "x": E.BTN_WEST, "y": E.BTN_NORTH, "lb": E.BTN_TL, "rb": E.BTN_TR,
           "select": E.BTN_SELECT, "start": E.BTN_START, "l3": E.BTN_THUMBL, "r3": E.BTN_THUMBR,
           "up": E.BTN_DPAD_UP, "down": E.BTN_DPAD_DOWN, "left": E.BTN_DPAD_LEFT, "right": E.BTN_DPAD_RIGHT}
    return {r: c for r, c in std.items() if c in pad["keys"]}, "Linux"


# ---- mGBA (Kachel "gba"; geprueft am Quelltext von mGBA 0.10.5) ----------------------------------------------
MGBA_CONFIG = Path.home() / ".config/mgba/config.ini"
MGBA_QT = Path.home() / ".config/mgba/qt.ini"
MGBA_PAD = "gba.input.SDLB"                  # Belegung fuer alle Controller ohne eigenes Profil
MGBA_DEFAULTS = {
    "autosave": "1",              # Stand alle 10 s und beim Beenden sichern (Platz 0) ...
    "autoload": "1",              # ... und beim naechsten Start dort weitermachen
    "lockAspectRatio": "1",       # Seitenverhaeltnis behalten
    "lockIntegerScaling": "1",    # ganzzahlig vergroessern: gleich breite, scharfe Pixel (720p/1080p: wenig Rand)
    "resampleVideo": "0",         # nicht weichzeichnen
    "interframeBlending": "0",
    "pauseOnFocusLost": "0",      # Anhalten im Hintergrund macht VoidStation selbst
    "suspendScreensaver": "1",
}


def mgba_pad_map(pad, roles):
    """Belegung fuer mGBA: ○ (rechts) = A, ✕ (unten) = B, L/R, Select/Start, Steuerkreuz und linker Stick.
    GBA-Tasten: A0 B1 Select2 Start3 Rechts4 Links5 Hoch6 Runter7 R8 L9."""
    from evdev import ecodes as E
    btn, ax = sdl_indices(pad)
    b = lambda role: str(btn[roles[role]]) if roles.get(role) in btn else "-1"
    m = {"keyA": b("b"), "keyB": b("a"), "keySelect": b("select"), "keyStart": b("start"),
         "keyL": b("lb"), "keyR": b("rb"), "keyUp": b("up"), "keyDown": b("down"), "keyLeft": b("left"),
         "keyRight": b("right"), "hat0Up": "6", "hat0Right": "4", "hat0Down": "7", "hat0Left": "5"}
    if E.ABS_X in ax:
        m.update({"axisLeftValue": "-16384", "axisLeftAxis": f"-{ax[E.ABS_X]}",
                  "axisRightValue": "16384", "axisRightAxis": f"+{ax[E.ABS_X]}"})
    if E.ABS_Y in ax:
        m.update({"axisUpValue": "-16384", "axisUpAxis": f"-{ax[E.ABS_Y]}",
                  "axisDownValue": "16384", "axisDownAxis": f"+{ax[E.ABS_Y]}"})
    return m


MGBA_AXIS_KEYS = [f"axis{d}{s}" for d in ("Left", "Right", "Up", "Down") for s in ("Value", "Axis")]


def qt_ini_group(name):
    """Gruppenname so maskiert, wie QSettings (IniFormat) ihn schreibt (Leerzeichen -> %20 usw.)."""
    return "".join(c if c.isascii() and (c.isalnum() or c in "_-.") else "".join(f"%{b:02X}" for b in c.encode())
                   if ord(c) <= 0xFF else f"%U{ord(c):04X}" for c in name)


def ini_section_once(app, path, section, values, st, key, remove=()):
    """Ganzen Abschnitt schreiben, solange er fehlt oder noch so aussieht, wie VoidStation ihn zuletzt schrieb."""
    cur = ini_read(path).get(section)
    last = st.get(app, {}).get(key)
    if cur and cur != last:
        return False                               # vom Nutzer in mGBA geaendert: bleibt
    if cur != values:
        ini_update(path, section, values, remove=remove)
    st.setdefault(app, {})[key] = dict(values)
    return True


def mgba_prepare():
    """Vor jedem Start von mGBA: Grundeinstellungen und Controller-Belegung (nur, wo der Nutzer nichts geaendert hat)."""
    with EMU_LOCK:
        st = emu_state_load()
        wanted = dict(MGBA_DEFAULTS)
        if SYS_ARCH != "i686":                 # Zurueckspulen kostet jedes Bild Rechenzeit – auf alten Rechnern nicht
            wanted["rewindEnable"] = "1"
        ini_defaults("mgba", MGBA_CONFIG, "ports.qt", wanted, st)
        # Controller: mGBA kennt von sich aus nur wenige Controller, und sein eingebautes Profil fuer "Wireless
        # Controller" (PS4 und Nachbauten) ist fuer Windows gezaehlt – unter Linux lagen A/B daneben, und ✕ oeffnete
        # das Laden-Fenster. Deshalb: Belegung fuer den ersten Controller (Spieler 1) als allgemeine Belegung UND als
        # Profil unter dem Namen, den mGBA von SDL bekommt (dann greift das eingebaute Profil nicht), dazu dessen
        # Kurzbefehle entschaerft. Savestates machen △/□ ueber VoidStation (emu_quick_state).
        pads = gamepads()
        if pads:
            pad = pads[0]
            probe = sdl_probe()
            roles, src = pad_roles(pad, probe)
            m = mgba_pad_map(pad, roles)
            rm = [k for k in MGBA_AXIS_KEYS if k not in m]
            if ini_section_once("mgba", MGBA_CONFIG, MGBA_PAD, m, st, "pad", rm):
                log(f"mGBA: Controller-Belegung fuer {pad['name']} ({src}):", m)
            else:
                log("mGBA: eigene Controller-Belegung vorhanden, bleibt")
            sdl_name = next((d["name"] for d in probe if d.get("path") == pad["path"]), "") or \
                (probe[0]["name"] if len(probe) == 1 else "")
            if sdl_name:
                ini_section_once("mgba", MGBA_CONFIG, f"gba.input-profile.{sdl_name}", m, st,
                                 f"profile:{sdl_name}", rm)
                ini_section_once("mgba", MGBA_QT, "shortcutProfileButton." + qt_ini_group(sdl_name),
                                 {"loadState": "-1", "saveState": "-1", "holdFastForward": "-1", "holdRewind": "-1"},
                                 st, f"shortcuts:{sdl_name}")
                ini_section_once("mgba", MGBA_QT, "shortcutProfileAxis." + qt_ini_group(sdl_name),
                                 {"loadState": "", "saveState": "", "holdFastForward": "", "holdRewind": ""},
                                 st, f"shortcutaxes:{sdl_name}")
        emu_state_save(st)


def emu_quick_state(load):
    """In mGBA: △ = Savestate speichern (Platz 1, Umschalt+F1), □ = laden (F1). Nur, wenn mGBA wirklich vorn ist."""
    tid = APPS.front()
    if not tid or APPS.kinds.get(tid) != "mgba-qt" or not shutil.which("xdotool"):
        return
    proc = APPS._get(tid)
    act = active_window()
    if not proc or not act or not any(int(w[0], 16) == act for w in APPS._windows_of(tid, proc)):
        return
    run(["xdotool", "key", "--clearmodifiers", "F1" if load else "shift+F1"])
    log("mGBA: Savestate", "geladen" if load else "gespeichert")


# ---- Vollbild ------------------------------------------------------------------------------------------------
# Programm -> (Startoption, Taste zum Umschalten). Beide aus dem Quelltext der Programme: mGBA (commandline.c "-f",
# Window.cpp Strg+F), DuckStation (qthost.cpp "-fullscreen", hotkeys.cpp F11).
EMU_FULLSCREEN = {"mgba-qt": ("-f", "ctrl+f"), "duckstation": ("-fullscreen", "F11")}
# Emulatoren mit einem einzigen Fenster ohne eigene Vollbild-Startoption: Vollbild ueber den Fenstermanager
EMU_WM_FULLSCREEN = {"snes9x", "nestopia", "melonds", "stella", "vice", "retroarch"}
FS_HOLD = 0.8                                # L3 so lange halten -> Vollbild an/aus


def emu_kind(args):
    p = Path(str(args[0]))
    return p.parent.name.lower() if p.name == "AppRun" else p.name


def emu_fullscreen_wanted(tid):
    t = find_tile(tid) or {}
    if isinstance(t.get("fullscreen"), bool):
        return t["fullscreen"]
    return bool(settings_load().get("emu_fullscreen", True))


def emu_prepare(tid, args):
    """Vor dem Start: Vorgaben schreiben, Vollbild-Option einsetzen. -> (args, Umgebung, Vollbild ueber Fenstermanager)"""
    kind = emu_kind(args)
    env, wm_fs = {}, False
    if kind == "mgba-qt":
        try:
            mgba_prepare()
        except Exception as e:  # noqa: BLE001 – Vorgaben duerfen den Start nie verhindern
            log("mGBA-Vorgaben:", e)
        env["SDL_JOYSTICK_HIDAPI"] = "0"
    # Nur mit Spiel (aus der Spieleliste): "Emulator ohne Spiel starten" bleibt im Fenster, dort will man die Menues
    game = len(args) > 1 and Path(str(args[-1])).suffix.lower() in {e for x in ROMS.EXTENSIONS.values() for e in x}
    if game and emu_fullscreen_wanted(tid):
        spec = EMU_FULLSCREEN.get(kind)
        if spec:
            if spec[0] not in args:
                args = [args[0], spec[0]] + list(args[1:])
        elif tid in EMU_WM_FULLSCREEN:
            wm_fs = True
    return args, env, wm_fs


def emu_toggle_fullscreen():
    """L3 lang gedrueckt: Vollbild des Emulators vorn an/aus (zum Beispiel, um an die Menues von mGBA zu kommen).
    Nur, wenn das aktive Fenster wirklich zu einem Emulator gehoert – nie in Firefox, Steam oder der Startseite."""
    tid = APPS.front()
    if not tid or not app_suspendable(tid):
        return
    proc = APPS._get(tid)
    act = active_window()
    if not proc or not act or not any(int(w[0], 16) == act for w in APPS._windows_of(tid, proc)):
        return
    key = EMU_FULLSCREEN.get(APPS.kinds.get(tid, ""), (None, None))[1]
    if key and shutil.which("xdotool"):
        run(["xdotool", "key", "--clearmodifiers", key])
    else:
        run(["wmctrl", "-i", "-r", hex(act), "-b", "toggle,fullscreen"])
    log("Vollbild umgeschaltet:", tid)


# ---- Spielstand-Sicherung -------------------------------------------------------------------------------------
class SaveBackup:
    """Sichert alle 30 Minuten (und kurz nach dem Beenden eines Emulators) die Spielstaende nach
    ~/share/Spielstand-Backups/<Datum_Uhrzeit>/ – vom PC aus ueber die Freigabe erreichbar.
      * nur, wenn sich seit der letzten Sicherung etwas geaendert hat
      * unveraenderte Dateien sind harte Links auf die vorige Sicherung (kostet keinen Platz)
      * behaelt alle Sicherungen der letzten 24 Stunden, danach eine pro Tag fuer 30 Tage
    Gesichert werden Speicherstaende neben den Spielen (share/ROMs: .sav, .srm, Savestates .ss0–.ss9 …) und die
    bekannten Ordner der Emulatoren, soweit vorhanden. Abschalten: "save_backup": false in settings.json."""
    INTERVAL = 1800
    KEEP_ALL = 24 * 3600
    KEEP_DAYS = 30
    MAX_FILE = 512 * 1024 * 1024
    SAVE_EXT = re.compile(r"\.(sav|srm|sra|eep|fla|rtc|mpk|dsv|mcr|mcd|ss\d|st\d|state\d*|oops)$", re.I)
    ROOT = Path.home() / "share" / "Spielstand-Backups"
    H = Path.home()
    # (Name im Backup, Ordner, nur Speicherstaende?) – fehlende Ordner werden uebersprungen
    SOURCES = [
        ("ROMs", H / "share" / "ROMs", True),                                # mGBA, melonDS, Snes9x … neben dem Spiel
        ("DuckStation", H / ".local/share/duckstation/memcards", False),
        ("DuckStation-Savestates", H / ".local/share/duckstation/savestates", False),
        ("PPSSPP", H / ".config/ppsspp/PSP/SAVEDATA", False),
        ("PPSSPP-Savestates", H / ".config/ppsspp/PSP/PPSSPP_STATE", False),
        ("Dolphin-GC", H / ".local/share/dolphin-emu/GC", False),
        ("Dolphin-Savestates", H / ".local/share/dolphin-emu/StateSaves", False),
        ("RetroArch", H / ".config/retroarch/saves", False),
        ("RetroArch-Savestates", H / ".config/retroarch/states", False),
        ("PCSX2", H / ".var/app/net.pcsx2.PCSX2/config/PCSX2/memcards", False),
        ("PCSX2-Savestates", H / ".var/app/net.pcsx2.PCSX2/config/PCSX2/sstates", False),
        ("Flycast", H / ".var/app/org.flycast.Flycast/data/flycast", True),
        ("Mednafen", H / ".mednafen/sav", False),
        ("Mednafen-Savestates", H / ".mednafen/mcs", False),
        ("Nestopia", H / ".nestopia/save", False),
        ("ScummVM", H / ".local/share/scummvm/saves", False),
    ]
    STAMP = "%Y-%m-%d_%H-%M-%S"

    def __init__(self):
        self.lock = threading.Lock()
        self.last_sig = None
        self.last_run = 0.0
        self.last_result = None

    def enabled(self):
        return bool(settings_load().get("save_backup", True))

    def _files(self):
        """[(Pfad im Backup, Datei, Groesse, mtime_ns)] aller zu sichernden Dateien."""
        out = []
        for name, root, saves_only in self.SOURCES:
            if not root.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "Cover"]
                for fn in filenames:
                    if saves_only and not self.SAVE_EXT.search(fn):
                        continue
                    p = Path(dirpath) / fn
                    try:
                        s = p.stat()
                    except OSError:
                        continue
                    if s.st_size > self.MAX_FILE or not p.is_file():
                        continue
                    out.append((f"{name}/{p.relative_to(root)}", p, s.st_size, s.st_mtime_ns))
        out.sort()
        return out

    def snapshots(self):
        try:
            return sorted(d for d in self.ROOT.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d", d.name))
        except OSError:
            return []

    def run_once(self, why=""):
        if not self.enabled():
            return None
        with self.lock:
            self.last_run = time.time()
            files = self._files()
            if not files:
                return None
            sig = hashlib.sha1(json.dumps([(r, sz, mt) for r, _, sz, mt in files]).encode()).hexdigest()
            snaps = self.snapshots()
            if self.last_sig is None:
                try:
                    self.last_sig = (snaps[-1] / ".signatur").read_text().strip() if snaps else ""
                except OSError:
                    self.last_sig = ""
            if sig == self.last_sig:
                return None
            prev = snaps[-1] if snaps else None
            name = datetime.datetime.now().strftime(self.STAMP)
            tmp = self.ROOT / f".{name}.tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            copied = linked = 0
            try:
                for rel, src, size, mtime in files:
                    dst = tmp / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    old = prev / rel if prev else None
                    try:
                        if old and old.is_file():
                            os_ = old.stat()
                            if os_.st_size == size and os_.st_mtime_ns == mtime:
                                os.link(old, dst)
                                linked += 1
                                continue
                    except OSError:
                        pass
                    shutil.copy2(src, dst)
                    copied += 1
                (tmp / ".signatur").write_text(sig)
                tmp.rename(self.ROOT / name)
            except OSError as e:
                log("Spielstand-Sicherung fehlgeschlagen:", e)
                shutil.rmtree(tmp, ignore_errors=True)
                return None
            self.last_sig = sig
            self._readme()
            self._prune()
            self.last_result = {"name": name, "copied": copied, "linked": linked}
            log(f"Spielstaende gesichert ({why}): {name}, {copied} neu, {linked} unveraendert")
            return self.last_result

    def _prune(self):
        now = datetime.datetime.now()
        keep_day = set()
        for d in reversed(self.snapshots()):
            try:
                t = datetime.datetime.strptime(d.name, self.STAMP)
            except ValueError:
                continue
            age = (now - t).total_seconds()
            day = t.date()
            if age <= self.KEEP_ALL:
                keep_day.add(day)
                continue
            if age <= self.KEEP_DAYS * 86400 and day not in keep_day:
                keep_day.add(day)                    # neueste Sicherung dieses Tages behalten
                continue
            shutil.rmtree(d, ignore_errors=True)

    def _readme(self):
        f = self.ROOT / "LIESMICH.txt"
        if f.exists():
            return
        try:
            f.write_text(
                "VoidStation – Spielstand-Sicherung / save backups\n"
                "=================================================\n"
                "Alle 30 Minuten (und kurz nach dem Beenden eines Emulators) landet hier ein Ordner mit Datum und\n"
                "Uhrzeit – aber nur, wenn sich ein Spielstand geaendert hat. Behalten werden alle Sicherungen der\n"
                "letzten 24 Stunden und danach eine pro Tag fuer 30 Tage.\n"
                "Zurueckholen: Emulator beenden, Datei aus dem gewuenschten Ordner an ihren alten Platz kopieren\n"
                "(ROMs/... = Freigabe-Ordner ROMs; mGBA: .sav = Spielstand im Spiel, .ss0 = automatischer Stand).\n\n"
                "Every 30 minutes (and shortly after an emulator closes) a dated folder appears here – only if a save\n"
                "changed. All backups of the last 24 hours are kept, then one per day for 30 days.\n"
                "To restore: close the emulator and copy the file back to where it came from.\n", encoding="utf-8")
        except OSError:
            pass

    def watcher(self):
        """Hintergrund-Thread: alle 30 Minuten, und 10 s nachdem ein Emulator beendet wurde."""
        time.sleep(180)
        emus_before = set()
        due_at = 0.0
        while True:
            try:
                emus = {t for t in APPS.running() if app_suspendable(t)}
                if emus_before - emus:
                    due_at = time.time() + 10
                emus_before = emus
                if due_at and time.time() >= due_at:
                    due_at = 0.0
                    self.run_once("Emulator beendet")
                elif time.time() - self.last_run >= self.INTERVAL:
                    self.run_once("alle 30 Minuten")
            except Exception as e:  # noqa: BLE001 – der Waechter darf nie sterben
                log("Spielstand-Sicherung:", e)
            time.sleep(15)


SAVES = SaveBackup()


# ---- Cover in der Spieleliste ----------------------------------------------------------------------------------
class RomCovers:
    """Bild zu jedem Spiel der Spieleliste. Reihenfolge:
      1. eigenes Bild: ROMs/<system>/Cover/<Name des Spiels>.png|.jpg|.jpeg|.webp (oder gleichnamig neben dem Spiel)
      2. sonst online gesucht und dauerhaft als ROMs/<system>/Cover/<Name>.png gespeichert – Quelle sind die
         Boxbilder von libretro-thumbnails (dieselben wie in RetroArch), Liste ueber GitHub, Rueckfall
         thumbnails.libretro.com
    Gesucht wird nach dem genauen Dateinamen (No-Intro-Namen wie "Pokemon - Crystal Version (USA, Europe)"), dann
    nach dem Titel ohne Klammern (Region der eigenen Sprache bevorzugt), dann aehnlich geschrieben. ROM-Hacks und
    selbst benannte Dateien finden oft nichts – dafuer ist Punkt 1 da. Nicht Gefundenes wird 14 Tage nicht erneut
    gesucht. Abschalten: "rom_covers": false in settings.json."""
    SYSTEMS = {                                  # Ordner unter share/ROMs -> System bei libretro
        "gba": "Nintendo - Game Boy Advance", "gbc": "Nintendo - Game Boy Color", "gb": "Nintendo - Game Boy",
        "snes": "Nintendo - Super Nintendo Entertainment System", "nes": "Nintendo - Nintendo Entertainment System",
        "psx": "Sony - PlayStation", "psp": "Sony - PlayStation Portable", "nds": "Nintendo - Nintendo DS",
        "gamecube": "Nintendo - GameCube", "dreamcast": "Sega - Dreamcast", "n64": "Nintendo - Nintendo 64",
        "megadrive": "Sega - Mega Drive - Genesis", "genesis": "Sega - Mega Drive - Genesis",
        "atari2600": "Atari - 2600", "c64": "Commodore - 64",
    }
    BY_EXT = {".gba": "gba", ".gbc": "gbc", ".gb": "gb"}     # mGBA-Ordner enthalten alle drei
    IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
    LIST_AGE = 30 * 86400
    MISS_AGE = 14 * 86400
    CACHE = BASE / "cache" / "romcovers"
    REGIONS = {"de": ("Germany", "Europe", "World", "USA"), "en": ("USA", "World", "Europe")}

    def __init__(self):
        self.lock = threading.Lock()
        self.list_locks = {}
        self.lists = {}                          # System -> {"names": set, "by_key": {schluessel: [namen]}}
        self.list_fail = {}                      # System -> Zeitpunkt des letzten Fehlschlags
        self.dl = threading.Semaphore(3)
        self.miss = None

    def enabled(self):
        return bool(settings_load().get("rom_covers", True))

    @staticmethod
    def key(name):
        """Vergleichsschluessel: ohne Klammern, Akzente, "The", Satzzeichen."""
        s = re.sub(r"\s*[\(\[][^()\[\]]*[\)\]]", "", name)
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("&", " and ")
        s = re.sub(r"\bthe\b", " ", s)
        return re.sub(r"[^a-z0-9]", "", s)

    @staticmethod
    def thumb_name(stem):
        return re.sub(r'[&*/:`<>?\\|"]', "_", stem)

    def system_of(self, folder, filename):
        return self.SYSTEMS.get(self.BY_EXT.get(Path(filename).suffix.lower(), folder))

    def own_image(self, folder, filename):
        stem = Path(filename).stem
        base = ROMS.rom_dir / folder
        for d in (base / "Cover", base):
            for ext in self.IMG_EXT:
                p = d / (stem + ext)
                if p.is_file():
                    return p
        return None

    def url(self, rom):
        """Adresse fuer die Oberflaeche; ?v= wechselt, sobald ein Bild da ist (sonst haelt Qt das alte Ergebnis)."""
        f = rom.get("folder") or rom.get("system") or ""
        own = self.own_image(f, rom["filename"])
        v = int(own.stat().st_mtime) if own else 0
        return ("/api/roms/cover?folder=" + urllib.parse.quote(f) + "&file=" + urllib.parse.quote(rom["filename"])
                + f"&v={v}")

    # -- Liste der vorhandenen Bilder eines Systems --
    def _repo(self, system):
        return system.replace(" ", "_")

    def _load_list(self, system):
        with self.lock:
            lk = self.list_locks.setdefault(system, threading.Lock())
        with lk:
            if system in self.lists:
                return self.lists[system]
            if time.time() - self.list_fail.get(system, 0) < 600:
                return None
            self.CACHE.mkdir(parents=True, exist_ok=True)
            cf = self.CACHE / (self._repo(system) + ".json")
            names = None
            try:
                if time.time() - cf.stat().st_mtime < self.LIST_AGE:
                    names = json.loads(cf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if names is None:
                names = self._fetch_list(system)
                if names:
                    try:
                        cf.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        pass
                else:
                    try:                            # offline: lieber alte Liste als keine
                        names = json.loads(cf.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        self.list_fail[system] = time.time()
                        return None
            by_key = {}
            for n in names:
                by_key.setdefault(self.key(n), []).append(n)
            self.lists[system] = {"names": set(names), "by_key": by_key}
            return self.lists[system]

    def _fetch_list(self, system):
        repo = self._repo(system)
        try:                                        # GitHub: eine Anfrage je System (ohne Konto 60 pro Stunde)
            req = urllib.request.Request(
                f"https://api.github.com/repos/libretro-thumbnails/{repo}/git/trees/master?recursive=1",
                headers={**UA, "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                tree = json.loads(r.read().decode("utf-8"))
            names = [t["path"][len("Named_Boxarts/"):-4] for t in tree.get("tree", [])
                     if t.get("path", "").startswith("Named_Boxarts/") and t["path"].endswith(".png")]
            if names:
                return names
        except (OSError, ValueError, KeyError) as e:
            log("Cover-Liste (GitHub):", system, e)
        try:                                        # Rueckfall: Verzeichnisliste von thumbnails.libretro.com
            req = urllib.request.Request(
                "https://thumbnails.libretro.com/" + urllib.parse.quote(system) + "/Named_Boxarts/", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", "replace")
            return [urllib.parse.unquote(h)[:-4] for h in re.findall(r'href="([^"?/]+\.png)"', html)]
        except OSError as e:
            log("Cover-Liste (libretro):", system, e)
        return []

    def _pick(self, lst, stem):
        tn = self.thumb_name(stem)
        if tn in lst["names"]:
            return tn
        k = self.key(stem)
        cands = lst["by_key"].get(k)
        if not cands and len(k) >= 6:              # "Pokemon Smaragd" -> "Pokemon - Smaragd-Edition", nur wenn eindeutig
            longer = [x for x in lst["by_key"] if x.startswith(k)]
            if len(longer) == 1:
                cands = lst["by_key"][longer[0]]
        if not cands and len(k) >= 4:
            import difflib
            close = difflib.get_close_matches(k, list(lst["by_key"]), n=1, cutoff=0.88)
            cands = lst["by_key"][close[0]] if close else None
        if not cands:
            return None
        own = set(re.findall(r"\(([^)]*)\)", stem))
        pref = self.REGIONS.get(ui_lang(), self.REGIONS["en"])

        def score(n):
            tags = re.findall(r"\(([^)]*)\)", n)
            regs = [r.strip() for t in tags[:1] for r in t.split(",")]
            s = len(own & set(tags)) * 10
            for i, r in enumerate(pref):
                if r in regs:
                    s += (len(pref) - i)
                    break
            return (s, -len(n))
        return max(cands, key=score)

    def _download(self, system, name, depth=0):
        """PNG-Daten des Boxbilds. libretro-thumbnails enthaelt Verweise (Symlinks): GitHub liefert dann statt des
        Bildes nur den Namen des Zielbilds – dem wird gefolgt (hoechstens zweimal)."""
        repo = self._repo(system)
        for u in (f"https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/Named_Boxarts/"
                  + urllib.parse.quote(name + ".png"),
                  "https://thumbnails.libretro.com/" + urllib.parse.quote(system) + "/Named_Boxarts/"
                  + urllib.parse.quote(name + ".png")):
            try:
                with self.dl:
                    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                        data = r.read(8 * 1024 * 1024)
            except OSError:
                continue
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                return data
            link = data.strip()
            if len(link) < 300 and link.endswith(b".png") and depth < 2:
                return self._download(system, link.decode("utf-8", "replace").split("/")[-1][:-4], depth + 1)
        return None

    def _miss_load(self):
        if self.miss is None:
            try:
                self.miss = json.loads((self.CACHE / "miss.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.miss = {}
        return self.miss

    def _miss_set(self, k, on):
        with self.lock:
            m = self._miss_load()
            if on:
                m[k] = time.time()
            else:
                m.pop(k, None)
            try:
                self.CACHE.mkdir(parents=True, exist_ok=True)
                (self.CACHE / "miss.json").write_text(json.dumps(m), encoding="utf-8")
            except OSError:
                pass

    def get(self, folder, filename):
        """Pfad zum Bild des Spiels oder None (holt es bei Bedarf aus dem Netz – kann einige Sekunden dauern)."""
        if folder not in ROMS.EXTENSIONS or os.path.basename(filename) != filename:
            return None
        rom = (ROMS.rom_dir / folder / filename)
        if not rom.is_file():
            return None
        own = self.own_image(folder, filename)
        if own or not self.enabled():
            return own
        system = self.system_of(folder, filename)
        if not system:
            return None
        mk = f"{folder}/{filename}"
        with self.lock:
            t = self._miss_load().get(mk, 0)
        if time.time() - t < self.MISS_AGE:
            return None
        lst = self._load_list(system)
        if not lst:
            return None                              # offline – naechstes Mal wieder versuchen
        name = self._pick(lst, Path(filename).stem)
        data = self._download(system, name) if name else None
        if not data:
            if not name:                             # nichts Passendes: 14 Tage Ruhe; Downloadfehler: bald wieder
                self._miss_set(mk, True)
            return None
        out = ROMS.rom_dir / folder / "Cover" / (Path(filename).stem + ".png")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(out.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(out)
        except OSError as e:
            log("Cover nicht gespeichert:", out, e)
            return None
        self._miss_set(mk, False)
        log("Cover gespeichert:", out.name, "<-", name)
        return out


ROM_COVERS = RomCovers()


# ---------------------------------------------------------------------------
#  Bluetooth: Kopfhoerer, Controller, Joysticks, Tastaturen – BlueZ ueber D-Bus
# ---------------------------------------------------------------------------
BT_AGENT_XML = """
<node>
  <interface name="org.bluez.Agent1">
    <method name="Release"/>
    <method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
    <method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
    <method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
    <method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
    <method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
    <method name="RequestAuthorization"><arg type="o" direction="in"/></method>
    <method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
    <method name="Cancel"/>
  </interface>
</node>
"""

# Geraeteart aus dem BlueZ-Symbol; was nicht gekoppelt ist und hier "hide" ergibt, erscheint nicht in der Liste
BT_KIND_BY_ICON = (("audio", "audio"), ("input-gaming", "gamepad"), ("input-keyboard", "keyboard"),
                   ("input-mouse", "mouse"), ("input-tablet", "mouse"), ("phone", "hide"),
                   ("computer", "hide"), ("video-display", "hide"), ("printer", "hide"),
                   ("camera", "hide"), ("network", "hide"), ("modem", "hide"))
BT_KIND_ORDER = {"audio": 0, "gamepad": 1, "keyboard": 2, "mouse": 3, "other": 4, "hide": 5}

# BlueZ-Fehler -> Schluessel in i18n (bt.err.*)
BT_ERRORS = (("AuthenticationFailed", "auth"), ("AuthenticationRejected", "auth"), ("AuthenticationCanceled", "auth"),
             ("AuthenticationTimeout", "timeout"), ("ConnectionAttemptFailed", "timeout"), ("Page Timeout", "timeout"),
             ("page-timeout", "timeout"), ("Host is down", "timeout"), ("UnknownObject", "gone"),
             ("DoesNotExist", "gone"), ("does not exist", "gone"), ("NotReady", "off"), ("Blocked", "off"),
             ("InProgress", "busy"), ("profile-unavailable", "profile"), ("NotAvailable", "profile"))


def bt_error_key(msg):
    for needle, key in BT_ERRORS:
        if needle.lower() in (msg or "").lower():
            return "bt.err." + key
    return "bt.err.other"


class BluetoothManager:
    """BlueZ ueber D-Bus (python3-gobject) mit eigenem Kopplungs-Agenten.

    Der Agent beantwortet Kopplungsanfragen selbst, ohne Tastatur am Fernseher:
      * Just Works / Bestaetigung (Kopfhoerer, Controller, AirPods): annehmen
      * alte Geraete mit PIN: nacheinander 0000, 1234, 1111
      * Tastaturen, die einen Code verlangen: Code steht in status()["prompt"] (Oberflaeche zeigt ihn)
    Anfragen, die ein Geraet von sich aus stellt, nimmt er nur im Kopplungsfenster an (Suche + 3 Min.)
    oder fuer bereits gekoppelte Geraete – sonst koennte sich jedes Geraet in Reichweite koppeln.
    Mehrere Adapter (z. B. USB-Stick + eingebauter Chip): der neueste Bluetooth-Standard gewinnt,
    die anderen werden ausgeschaltet. Fest waehlbar ueber /usr/local/share/voidstation/bt-adapter
    (Adresse des Adapters)."""

    MAC_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$", re.I)
    AGENT_PATH = "/org/voidstation/btagent"
    PINS = ("0000", "1234", "1111")
    SCAN_SECONDS = 30
    WINDOW = 180
    ADAPTER_FILE = Path("/usr/local/share/voidstation/bt-adapter")

    def __init__(self):
        self.lock = threading.Lock()
        self.bus = None
        self.Gio = self.GLib = None
        self._agent_ok = False
        self._started = False
        self._scanning = False
        self._scan_until = 0.0
        self._window_until = 0.0
        self._pairing = None          # D-Bus-Pfad des Geraets, das gerade gekoppelt wird
        self._pin = "0000"
        self._pin_asked = False
        self._prompt = None           # {"mac", "code"} fuer Tastaturen
        self._adapter_path = None
        self._last_err = ""

    # ---- Verbindung zu BlueZ ----
    def start(self):
        """Agent-Thread starten (einmal, beim Start des Launchers)."""
        if self._started:
            return
        self._started = True
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib
        except (ImportError, ValueError) as e:
            log("Bluetooth: python3-gobject fehlt, nur bluetoothctl:", e)
            return
        self.Gio, self.GLib = Gio, GLib
        threading.Thread(target=self._agent_thread, daemon=True).start()

    def _connect_bus(self):
        Gio = self.Gio
        addr = os.environ.get("VS_BT_BUS")             # nur fuer Tests (eigener D-Bus mit nachgebautem BlueZ)
        if addr:
            return Gio.DBusConnection.new_for_address_sync(
                addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def _agent_thread(self):
        Gio, GLib = self.Gio, self.GLib
        ctx = GLib.MainContext()
        ctx.push_thread_default()
        while self.bus is None:
            try:
                self.bus = self._connect_bus()
            except GLib.Error as e:
                log("Bluetooth: kein System-D-Bus:", e.message)
                time.sleep(10)
        node = Gio.DBusNodeInfo.new_for_xml(BT_AGENT_XML)
        self.bus.register_object(self.AGENT_PATH, node.interfaces[0], self._agent_call, None, None)
        self.bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                                  "/org/freedesktop/DBus", "org.bluez", Gio.DBusSignalFlags.NONE,
                                  self._owner_changed, None)
        self._register_agent()
        GLib.MainLoop(ctx).run()

    def _owner_changed(self, _conn, _sender, _path, _iface, _sig, params, _data):
        name, _old, new = params.unpack()
        if name != "org.bluez":
            return
        self._agent_ok = False
        self._adapter_path = None
        if new:                                         # bluetoothd (neu) gestartet
            threading.Thread(target=lambda: (time.sleep(1), self._register_agent()), daemon=True).start()

    def _register_agent(self):
        if not self.bus:
            return False
        try:
            self._call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent",
                       self.GLib.Variant("(os)", (self.AGENT_PATH, "KeyboardDisplay")))
        except RuntimeError as e:
            if "AlreadyExists" not in str(e):
                if "ServiceUnknown" not in str(e) and "NameHasNoOwner" not in str(e):
                    log("Bluetooth: Agent nicht angemeldet:", e)
                return False
        try:
            self._call("/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent",
                       self.GLib.Variant("(o)", (self.AGENT_PATH,)))
        except RuntimeError as e:
            log("Bluetooth: Agent nicht Standard:", e)
        if not self._agent_ok:
            log("Bluetooth: Kopplungs-Agent aktiv")
        self._agent_ok = True
        return True

    def _call(self, path, iface, method, params=None, timeout=10):
        """Methode bei BlueZ aufrufen; Fehler -> RuntimeError mit D-Bus-Fehlername und Text."""
        if not self.bus:
            raise RuntimeError("org.bluez.Error.NotReady: kein D-Bus")
        try:
            r = self.bus.call_sync("org.bluez", path, iface, method, params, None,
                                   self.Gio.DBusCallFlags.NONE, int(timeout * 1000), None)
            return r.unpack() if r is not None else ()
        except self.GLib.Error as e:
            name = self.Gio.DBusError.get_remote_error(e) or ""
            msg = re.sub(r"^GDBus\.Error:[\w.]+: ", "", e.message or "")
            raise RuntimeError(f"{name}: {msg}") from None

    def _set_prop(self, path, iface, prop, variant):
        self._call(path, "org.freedesktop.DBus.Properties", "Set", self.GLib.Variant("(ssv)", (iface, prop, variant)))

    def _objects(self):
        try:
            return self._call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")[0]
        except RuntimeError:
            return {}

    def _bluez_running(self):
        if not self.bus:
            return False
        try:
            r = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                   "NameHasOwner", self.GLib.Variant("(s)", ("org.bluez",)), None,
                                   self.Gio.DBusCallFlags.NONE, 3000, None)
            return bool(r.unpack()[0])
        except self.GLib.Error:
            return False

    # ---- Adapter ----
    def _adapter(self, objs=None):
        """Pfad des Adapters, mit dem VoidStation arbeitet (siehe Klassenbeschreibung)."""
        objs = objs if objs is not None else self._objects()
        ads = sorted((p, o["org.bluez.Adapter1"]) for p, o in objs.items() if "org.bluez.Adapter1" in o)
        if not ads:
            self._adapter_path = None
            return None
        try:
            want = self.ADAPTER_FILE.read_text(encoding="utf-8").strip().upper()
        except OSError:
            want = ""
        pick = next((p for p, a in ads if want and str(a.get("Address", "")).upper() == want), None)
        if not pick:
            usable = [(p, a) for p, a in ads if a.get("PowerState") != "off-blocked"] or ads
            pick = max(usable, key=lambda pa: (int(pa[1].get("Version", 0) or 0), -ads.index(pa)))[0]
        if pick != self._adapter_path:
            self._adapter_path = pick
            a = dict(ads)[pick]
            log("Bluetooth-Adapter:", pick, a.get("Address", ""), "Version", a.get("Version", "?"))
            for p, other in ads:                           # zweiter Adapter aus, sonst antworten beide
                if p != pick and other.get("Powered"):
                    try:
                        self._set_prop(p, "org.bluez.Adapter1", "Powered", self.GLib.Variant("b", False))
                        log("Bluetooth: weiterer Adapter ausgeschaltet:", p, other.get("Address", ""))
                    except RuntimeError as e:
                        log("Bluetooth:", p, e)
        return pick

    def _dev_path(self, adapter, mac):
        return f"{adapter}/dev_{mac.upper().replace(':', '_')}"

    @staticmethod
    def _mac_of(path):
        m = re.search(r"dev_([0-9A-F_]{17})$", path or "", re.I)
        return m.group(1).replace("_", ":").upper() if m else ""

    # ---- Agent (laeuft im Agent-Thread) ----
    def _allowed(self, path):
        return path == self._pairing or time.time() < self._window_until

    def _known(self, path):
        d = self._objects().get(path, {}).get("org.bluez.Device1", {})
        return bool(d.get("Paired") or d.get("Trusted"))

    def _agent_call(self, _conn, _sender, _path, _iface, method, params, inv):
        GLib = self.GLib
        args = params.unpack()
        dev = args[0] if args else ""
        mac = self._mac_of(dev)

        def reject(why="Rejected"):
            log("Bluetooth-Agent:", method, mac, "abgelehnt")
            inv.return_dbus_error("org.bluez.Error." + why, "VoidStation: nicht im Kopplungsfenster")

        if method == "Release":
            self._agent_ok = False
            return inv.return_value(None)
        if method == "Cancel":
            self._prompt = None
            return inv.return_value(None)
        if method == "RequestPinCode":
            if not self._allowed(dev):
                return reject()
            self._pin_asked = True
            log("Bluetooth-Agent: PIN", self._pin, "fuer", mac)
            return inv.return_value(GLib.Variant("(s)", (self._pin,)))
        if method == "DisplayPinCode":
            self._prompt = {"mac": mac, "code": args[1]}
            return inv.return_value(None)
        if method == "RequestPasskey":
            if not self._allowed(dev):
                return reject()
            return inv.return_value(GLib.Variant("(u)", (0,)))
        if method == "DisplayPasskey":
            self._prompt = {"mac": mac, "code": f"{args[1]:06d}", "entered": args[2]}
            return inv.return_value(None)
        if method in ("RequestConfirmation", "RequestAuthorization"):
            if not self._allowed(dev):
                return reject()
            return inv.return_value(None)
        if method == "AuthorizeService":
            if self._known(dev) or self._allowed(dev):
                return inv.return_value(None)
            return reject()
        inv.return_dbus_error("org.bluez.Error.Rejected", "unbekannt")

    # ---- Abfragen ----
    def is_available(self):
        return bool(shutil.which("bluetoothctl"))

    def is_service_active(self):
        return os.path.exists("/var/service/bluetoothd") or self._bluez_running()

    @staticmethod
    def _kind(dev):
        icon = str(dev.get("Icon") or "")
        for prefix, kind in BT_KIND_BY_ICON:
            if icon.startswith(prefix):
                return kind
        cls = int(dev.get("Class") or 0)
        major, minor = (cls >> 8) & 0x1F, (cls >> 2) & 0x3F
        if major == 0x04:
            return "audio"
        if major == 0x05:
            if (minor & 0x0F) in (1, 2):                       # Joystick, Gamepad
                return "gamepad"
            return "keyboard" if minor & 0x10 else "mouse" if minor & 0x20 else "gamepad"
        if major in (0x01, 0x02):
            return "hide"
        uuids = " ".join(str(u) for u in dev.get("UUIDs") or [])
        if "0000110b" in uuids or "0000111e" in uuids:
            return "audio"
        if "00001124" in uuids or "00001812" in uuids:      # HID (klassisch / LE)
            return "gamepad"
        return "other"

    def _devices(self, objs, adapter):
        out = []
        for path, o in objs.items():
            d = o.get("org.bluez.Device1")
            if not d or not path.startswith(adapter + "/"):
                continue
            mac = str(d.get("Address") or self._mac_of(path)).upper()
            name = str(d.get("Name") or "")
            alias = str(d.get("Alias") or "")
            if alias.replace("-", ":").upper() == mac:
                alias = ""
            paired = bool(d.get("Paired") or d.get("Bonded"))
            kind = self._kind(d)
            if not paired and (not (name or alias) or kind == "hide"):
                continue
            bat = o.get("org.bluez.Battery1", {}).get("Percentage")
            out.append({"mac": mac, "name": alias or name, "orig": name, "custom": bool(alias) and alias != name,
                        "paired": paired,
                        "connected": bool(d.get("Connected")), "trusted": bool(d.get("Trusted")),
                        "kind": "other" if kind == "hide" else kind,
                        "icon": "audio" if kind == "audio" else "gamepad" if kind == "gamepad" else "bluetooth",
                        "battery": int(bat) if bat is not None else None,
                        "rssi": int(d["RSSI"]) if d.get("RSSI") is not None else None})
        out.sort(key=lambda x: (not x["connected"], not x["paired"], BT_KIND_ORDER.get(x["kind"], 4),
                                -(x["rssi"] if x["rssi"] is not None else -999), x["name"].lower()))
        return out[:30]

    def status(self):
        if not self.bus:
            return self._legacy_status()
        objs = self._objects()
        adapter = self._adapter(objs)
        service = self.is_service_active()
        if adapter and not self._agent_ok:
            self._register_agent()
        a = objs.get(adapter, {}).get("org.bluez.Adapter1", {}) if adapter else {}
        powered = bool(a.get("Powered"))
        prompt = self._prompt if self._pairing else None
        return {
            "available": self.is_available() and (adapter is not None or not self._bluez_running()),
            "service": service,
            "powered": powered,
            "blocked": a.get("PowerState") == "off-blocked",
            "scanning": self._scanning,
            "pairing": self._mac_of(self._pairing) if self._pairing else None,
            "prompt": prompt,
            "adapter": str(a.get("Address", "")),
            "devices": self._devices(objs, adapter) if (adapter and powered) else [],
        }

    # ---- Suche ----
    def start_scan(self, seconds=None):
        if not self.bus:
            return self._legacy_scan()
        seconds = seconds or self.SCAN_SECONDS
        adapter = self._adapter()
        if not adapter:
            return
        self._register_agent()                          # Standard-Agent holen (falls bluetoothctl ihn hatte)
        now = time.time()
        self._window_until = max(self._window_until, now + seconds + self.WINDOW)
        with self.lock:
            self._scan_until = max(self._scan_until, now + seconds)
            if self._scanning:
                return
            self._scanning = True
        try:
            self._call(adapter, "org.bluez.Adapter1", "SetDiscoveryFilter",
                       self.GLib.Variant("(a{sv})", ({"Transport": self.GLib.Variant("s", "auto"),
                                                       "DuplicateData": self.GLib.Variant("b", False)},)))
        except RuntimeError as e:
            log("Bluetooth: Suchfilter:", e)
        try:
            self._call(adapter, "org.bluez.Adapter1", "StartDiscovery")
        except RuntimeError as e:
            if "InProgress" not in str(e):
                log("Bluetooth: Suche:", e)
                with self.lock:
                    self._scanning = False
                return

        def stop_later():
            while time.time() < self._scan_until and self._scanning:
                time.sleep(0.5)
            self._stop_scan(adapter)

        threading.Thread(target=stop_later, daemon=True).start()

    def _stop_scan(self, adapter=None):
        adapter = adapter or self._adapter_path
        with self.lock:
            was, self._scanning = self._scanning, False
        if was and adapter:
            try:
                self._call(adapter, "org.bluez.Adapter1", "StopDiscovery")
            except RuntimeError:
                pass

    # ---- Koppeln / Verbinden ----
    def pair(self, mac):
        """Koppeln, vertrauen, verbinden. Rueckgabe (ok, Fehlerschluessel oder None)."""
        if not self.bus:
            return self._legacy_pair(mac), None
        adapter = self._adapter()
        if not adapter:
            return False, "bt.err.off"
        path = self._dev_path(adapter, mac)
        self._window_until = max(self._window_until, time.time() + self.WINDOW)
        if path not in self._objects():                # BlueZ vergisst ungekoppelte Geraete nach der Suche
            self.start_scan(20)
            t0 = time.time()
            while path not in self._objects() and time.time() - t0 < 15:
                time.sleep(0.5)
            if path not in self._objects():
                return False, "bt.err.gone"
        self._stop_scan(adapter)                        # manche Controller koppeln nicht, solange gesucht wird
        self._register_agent()
        self._pairing, self._prompt = path, None
        try:
            err = None
            for i, pin in enumerate(self.PINS):
                self._pin, self._pin_asked = pin, False
                try:
                    self._call(path, "org.bluez.Device1", "Pair", timeout=60)
                    err = None
                    break
                except RuntimeError as e:
                    err = str(e)
                    if "AlreadyExists" in err:          # war schon gekoppelt
                        err = None
                        break
                    log("Bluetooth: Koppeln", mac, "fehlgeschlagen:", err)
                    if self._pin_asked and bt_error_key(err) == "bt.err.auth" and i + 1 < len(self.PINS):
                        time.sleep(1)
                        continue
                    break
            if err:
                return False, bt_error_key(err)
            log("Bluetooth: gekoppelt", mac)
            try:
                self._set_prop(path, "org.bluez.Device1", "Trusted", self.GLib.Variant("b", True))
            except RuntimeError as e:
                log("Bluetooth: vertrauen", mac, e)
            ok, cerr = self._connect_path(path, mac)
            return ok, cerr
        finally:
            self._pairing, self._prompt = None, None

    def _connect_path(self, path, mac):
        err = ""
        for attempt in range(2):
            try:
                self._call(path, "org.bluez.Device1", "Connect", timeout=30)
                err = ""
                break
            except RuntimeError as e:
                err = str(e)
                if "AlreadyConnected" in err or "InProgress" in err:
                    err = ""
                    break
                log("Bluetooth: verbinden", mac, f"(Versuch {attempt + 1}):", err)
                time.sleep(2)
        d = self._objects().get(path, {}).get("org.bluez.Device1", {})
        if err and not d.get("Connected"):
            return False, bt_error_key(err)
        if self._kind(d) == "audio":
            threading.Thread(target=bt_audio_follow, args=(mac,), daemon=True).start()
        return True, None

    def connect(self, mac):
        if not self.bus:
            return self._legacy_connect(mac), None
        adapter = self._adapter()
        if not adapter:
            return False, "bt.err.off"
        path = self._dev_path(adapter, mac)
        if path not in self._objects():
            return False, "bt.err.gone"
        self._stop_scan(adapter)
        return self._connect_path(path, mac)

    def disconnect(self, mac):
        if not self.bus:
            return self._legacy_simple("disconnect", mac)
        adapter = self._adapter()
        try:
            self._call(self._dev_path(adapter, mac), "org.bluez.Device1", "Disconnect", timeout=15)
            return True
        except (RuntimeError, TypeError) as e:
            log("Bluetooth: trennen", mac, e)
            return False

    def remove(self, mac):
        if not self.bus:
            return self._legacy_simple("remove", mac)
        adapter = self._adapter()
        try:
            self._call(adapter, "org.bluez.Adapter1", "RemoveDevice",
                       self.GLib.Variant("(o)", (self._dev_path(adapter, mac),)), timeout=15)
            return True
        except (RuntimeError, TypeError) as e:
            log("Bluetooth: entfernen", mac, e)
            return False

    # ---- Umbenennen: eigener Name als BlueZ-Alias (bei gekoppelten Geraeten dauerhaft gespeichert,
    #      der vom Geraet gemeldete Name bleibt unberuehrt; leerer Name = wieder der Geraetename) ----
    NAME_MAX = 40

    @classmethod
    def clean_name(cls, name):
        name = re.sub(r"[\x00-\x1f\x7f]+", " ", str(name or ""))
        name = re.sub(r"\s{2,}", " ", name).strip()
        return name[:cls.NAME_MAX].strip()

    def rename(self, mac, name):
        name = self.clean_name(name)
        if not self.bus:
            return self._legacy_rename(mac, name)
        adapter = self._adapter()
        if not adapter:
            return False
        path = self._dev_path(adapter, mac)
        if path not in self._objects():
            return False
        try:
            self._set_prop(path, "org.bluez.Device1", "Alias", self.GLib.Variant("s", name))
            log("Bluetooth: umbenannt", mac, "->", repr(name) if name else "(Geraetename)")
            return True
        except RuntimeError as e:
            log("Bluetooth: umbenennen", mac, e)
            return False

    def power(self, on):
        if not self.bus:
            return self._legacy_simple("power", "on" if on else "off")
        adapter = self._adapter()
        if not adapter:
            return False
        for attempt in range(2):
            try:
                self._set_prop(adapter, "org.bluez.Adapter1", "Powered", self.GLib.Variant("b", bool(on)))
                return True
            except RuntimeError as e:
                log("Bluetooth: Ein/Aus:", e)
                if on and attempt == 0:                 # per Funkschalter (rfkill) gesperrt -> freigeben
                    subprocess.run(["sudo", "-n", PKG_HELPER, "bluetooth", "on"],
                                   capture_output=True, text=True, timeout=30)
                    time.sleep(1)
        return False

    # ---- Rueckfall ohne python3-gobject: bluetoothctl (ohne eigenen Agenten) ----
    def _legacy_status(self):
        available = self.is_available()
        service = os.path.exists("/var/service/bluetoothd")
        powered = False
        if available and service:
            r = run(["bluetoothctl", "show"])
            powered = bool(r and r.returncode == 0 and "Powered: yes" in r.stdout)
        devs = {}
        if powered:
            for args, paired in ((["devices", "Paired"], True), (["devices"], False)):
                r = run(["bluetoothctl", *args])
                for line in (r.stdout.splitlines() if r and r.returncode == 0 else []):
                    p = line.strip().split(None, 2)
                    if len(p) >= 3 and p[0] == "Device" and p[1] not in devs:
                        if paired or p[2].replace("-", ":").upper() != p[1].upper():
                            devs[p[1]] = {"mac": p[1], "name": p[2], "paired": paired, "connected": False,
                                          "icon": "bluetooth", "kind": "other", "battery": None}
            for mac, d in list(devs.items())[:25]:
                info = run(["bluetoothctl", "info", mac])
                for line in (info.stdout.splitlines() if info and info.returncode == 0 else []):
                    line = line.strip()
                    if line.startswith("Connected: yes"):
                        d["connected"] = True
                    elif line.startswith("Icon:"):
                        ic = line.split(":", 1)[1].strip()
                        d["kind"] = self._kind({"Icon": ic})
                        d["icon"] = "audio" if d["kind"] == "audio" else "gamepad" if d["kind"] == "gamepad" else "bluetooth"
        lst = sorted(devs.values(), key=lambda x: (not x["connected"], not x["paired"], x["name"].lower()))
        return {"available": available, "service": service, "powered": powered, "scanning": self._scanning,
                "pairing": None, "prompt": None, "devices": lst}

    def _legacy_scan(self):
        with self.lock:
            if self._scanning:
                return
            self._scanning = True

        def _do():
            try:
                run(["bluetoothctl", "--timeout", str(self.SCAN_SECONDS), "scan", "on"], timeout=self.SCAN_SECONDS + 5)
            finally:
                with self.lock:
                    self._scanning = False

        threading.Thread(target=_do, daemon=True).start()

    def _legacy_pair(self, mac):
        run(["bluetoothctl", "pair", mac], timeout=30)
        run(["bluetoothctl", "trust", mac], timeout=10)
        return self._legacy_connect(mac)

    def _legacy_connect(self, mac):
        r = run(["bluetoothctl", "connect", mac], timeout=20)
        return bool(r and r.returncode == 0)

    def _legacy_simple(self, cmd, arg):
        r = run(["bluetoothctl", cmd, arg], timeout=15)
        return bool(r and r.returncode == 0)

    def _legacy_rename(self, mac, name):
        """bluetoothctl kann den Alias nur fuer das gerade gewaehlte Geraet setzen -> direkt per dbus-send."""
        dev = "dev_" + mac.upper().replace(":", "_")
        hcis = sorted(p.name for p in Path("/sys/class/bluetooth").glob("hci*") if ":" not in p.name) if \
            Path("/sys/class/bluetooth").is_dir() else []
        for hci in hcis:
            r = run(["dbus-send", "--system", "--print-reply", "--dest=org.bluez", f"/org/bluez/{hci}/{dev}",
                     "org.freedesktop.DBus.Properties.Set", "string:org.bluez.Device1", "string:Alias",
                     f"variant:string:{name}"], timeout=10)
            if r and r.returncode == 0:
                return True
        return False


def bt_audio_follow(mac, wait=10):
    """Ton auf den gerade verbundenen Bluetooth-Kopfhoerer legen (PipeWire merkt sich das als Standard:
    verbindet er sich spaeter von selbst, wechselt der Ton wieder dorthin)."""
    key = mac.upper().replace(":", "_")
    t0 = time.time()
    while time.time() - t0 < wait:
        for s in pactl_json("list", "sinks") or []:
            name = s.get("name", "")
            props = s.get("properties") or {}
            if key in name.upper() or str(props.get("api.bluez5.address", "")).upper() == mac.upper():
                if audio_select("bluez_card." + key):    # gemerktes Format/Mikro, sonst A2DP (volle Qualitaet)
                    log("Ton auf Bluetooth:", name)
                    return True
                run(["pactl", "set-default-sink", name])
                run(["pactl", "set-sink-mute", name, "0"])
                log("Ton auf Bluetooth:", name)
                return True
        time.sleep(0.5)
    log("Bluetooth: kein Tonausgang fuer", mac, "(Geraet ohne Audio-Profil oder PipeWire-Bluetooth fehlt)")
    return False


BLUETOOTH = BluetoothManager()


# ---------------------------------------------------------------------------
#  YouTube Light (Player-Modus --yt, Kachel "ytlight"): YouTube ohne Browser und ohne Google-Konto.
#  Suche, Kanaele, Playlists und Stream-Adressen ueber yt-dlp; Abos lokal ueber die RSS-Feeds der Kanaele
#  (Import aus Google Takeout, NewPipe, FreeTube); Verlauf, Weiterschauen und "Spaeter ansehen" lokal.
#  Shorts bleiben draussen (Feed: Playlist-Feed UULF… = nur normale Videos; Suche: /shorts/-Adressen und <= 60 s).
#  Kein Google-Login: die Data-API verbietet Fremd-Player, Cookies aus einem Browser gefaehrden das Konto.
# ---------------------------------------------------------------------------
YT_VID = re.compile(r"[A-Za-z0-9_-]{11}")
YT_CID = re.compile(r"UC[A-Za-z0-9_-]{22}")
YT_PID = re.compile(r"[A-Za-z0-9_-]{10,80}")
YT_QUALITIES = ("auto", "1080", "720", "480", "360")
YT_IMG_HOSTS = re.compile(r"^https://(i\d?\.ytimg\.com|yt3\.ggpht\.com|yt3\.googleusercontent\.com|i\.ytimg\.com)/")
# Fehlermeldungen von yt-dlp -> Grund fuer die Anzeige (yt.err.<grund>)
YT_ERRORS = [
    (re.compile(r"(?i)confirm your age|age-restricted|inappropriate for some users"), "age"),
    (re.compile(r"(?i)not a bot|sign in to confirm"), "bot"),
    (re.compile(r"(?i)private video"), "private"),
    (re.compile(r"(?i)members[- ]only|join this channel"), "members"),
    (re.compile(r"(?i)not available in your country|blocked it in your country|geo"), "geo"),
    (re.compile(r"(?i)premieres? in|live event will begin|upcoming"), "upcoming"),
    (re.compile(r"(?i)video unavailable|has been removed|does not exist|account.*terminated|no longer available"), "gone"),
    (re.compile(r"(?i)requested format is not available|nsig|n challenge|signature|js runtime|javascript|"
                r"some formats may be missing|unable to extract|http error 403"), "outdated"),
    (re.compile(r"(?i)timed out|temporary failure in name resolution|network is unreachable|"
                r"name or service not known|connection (refused|reset)|urlopen error|unable to download|"
                r"unable to connect|proxy"), "offline"),
]


class YtError(Exception):
    def __init__(self, reason, msg=""):
        super().__init__(msg or reason)
        self.reason = reason


def yt_classify(text):
    for rx, reason in YT_ERRORS:
        if rx.search(text or ""):
            return reason
    return "failed"


class YtLight:
    SUBS = BASE / "yt-subs.json"
    HIST = BASE / "yt-history.json"
    LATER = BASE / "yt-later.json"
    LOCAL = BASE / "bin" / "yt-dlp"                     # eigene, aktuelle yt-dlp-Kopie (Knopf "yt-dlp aktualisieren")
    CACHE = Path.home() / ".cache" / "voidstation" / "yt"
    RSS = "https://www.youtube.com/feeds/videos.xml?"
    YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
    NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    # Seiten von youtube.com ohne Zustimmungsdialog (EU): Cookie "Notwendige" wie nach "Alle ablehnen"
    WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
                   "Accept-Language": "en-US,en;q=0.8", "Cookie": "SOCS=CAI; CONSENT=PENDING+999"}
    MAX_HIST = 500
    MAX_LATER = 500

    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}                                  # (art, schluessel) -> (zeit, daten)
        self.feed = {"items": [], "t": 0, "refreshing": False, "errors": 0}
        self.upd = {"state": "idle", "msg": "", "t": 0}
        self.ver = ("", 0.0)
        self.avatar_busy = False

    # ---- Dateien ----
    @staticmethod
    def _load(path, default):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, type(default)) else default
        except (OSError, ValueError):
            return default

    @staticmethod
    def _save(path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(path)
        except OSError as e:
            log("YouTube Light:", path.name, e)

    # ---- Einstellungen und Werkzeuge ----
    @staticmethod
    def weak():
        v = os.environ.get("VS_WEAK", "")
        return v == "1" if v in ("0", "1") else os.uname().machine in ("i386", "i486", "i586", "i686")

    def settings(self):
        d = settings_load().get("yt") or {}
        q = str(d.get("quality") or "auto")
        return {"accepted": bool(d.get("accepted")), "quality": q if q in YT_QUALITIES else "auto"}

    def save_settings(self, body):
        s = settings_load()
        d = dict(s.get("yt") or {})
        if "accepted" in body:
            d["accepted"] = bool(body.get("accepted"))
        if body.get("quality") in YT_QUALITIES:
            d["quality"] = body["quality"]
        s["yt"] = d
        settings_save(s)
        return self.state()

    def tool(self):
        if os.environ.get("VS_YTDLP"):
            return os.environ["VS_YTDLP"]
        if self.LOCAL.is_file() and os.access(self.LOCAL, os.X_OK):
            return str(self.LOCAL)
        return shutil.which("yt-dlp")

    def version(self):
        v, t = self.ver
        if time.time() - t < 600:
            return v
        exe = self.tool()
        r = run([exe, "--version"], timeout=40) if exe else None
        v = r.stdout.strip() if r and r.returncode == 0 else ""
        self.ver = (v, time.time())
        return v

    def base_args(self):
        exe = self.tool()
        if not exe:
            raise YtError("noytdlp", "yt-dlp fehlt")
        args = [exe, "--ignore-config", "--no-warnings", "--no-progress"]
        if shutil.which("node"):                        # JS-Aufgaben von YouTube (yt-dlp-ejs), Node.js >= 22
            args += ["--js-runtimes", "node"]
        return args

    def state(self):
        self._auto_update()
        return dict(self.settings(), weak=self.weak(), subs=len(self._load(self.SUBS, [])),
                    tools={"ytdlp": self.version(), "local": self.LOCAL.is_file(), "node": bool(shutil.which("node"))},
                    update=dict(self.upd))

    def _ytdlp(self, args, timeout=60):
        """yt-dlp mit -J aufrufen und das JSON zurueckgeben; Fehler als YtError mit Grund."""
        full = self.base_args() + args
        t0 = time.monotonic()
        try:
            r = subprocess.run(full, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise YtError("timeout", "yt-dlp antwortet nicht")
        except OSError as e:
            raise YtError("noytdlp", str(e))
        if r.returncode != 0 or not r.stdout.strip():
            err = [ln for ln in (r.stderr or "").splitlines() if "ERROR" in ln] or (r.stderr or "").strip().splitlines()
            msg = (err[-1] if err else "yt-dlp-Fehler").replace("ERROR: ", "")
            log(f"YouTube Light: yt-dlp ({time.monotonic() - t0:.1f} s):", msg[:300])
            raise YtError(yt_classify(r.stderr), msg[:300])
        try:
            d = json.loads(r.stdout)
        except ValueError:
            raise YtError("failed", "Antwort von yt-dlp nicht lesbar")
        if not isinstance(d, dict):
            raise YtError("failed", "Antwort von yt-dlp nicht lesbar")
        # Netzfehler bei Listen: yt-dlp meldet ERROR, liefert aber trotzdem JSON mit leeren Eintraegen ([null])
        ents = d.get("entries")
        if ents is not None:
            d["entries"] = [e for e in ents if isinstance(e, dict)]
            if not d["entries"] and "ERROR" in (r.stderr or ""):
                err = [ln for ln in r.stderr.splitlines() if "ERROR" in ln]
                log("YouTube Light: yt-dlp:", err[-1][:300])
                raise YtError(yt_classify(r.stderr), err[-1].replace("ERROR: ", "")[:300])
        return d

    def _cached(self, kind, key, ttl, fn):
        now = time.time()
        with self.lock:
            hit = self.cache.get((kind, key))
            if hit and now - hit[0] < ttl:
                return hit[1]
        data = fn()
        with self.lock:
            self.cache[(kind, key)] = (now, data)
            if len(self.cache) > 300:
                for k, _ in sorted(self.cache.items(), key=lambda kv: kv[1][0])[:100]:
                    self.cache.pop(k, None)
        return data

    # ---- Eintraege ----
    @staticmethod
    def _thumb_url(thumbs, square=False):
        best, bw = "", 0
        for t in thumbs or []:
            if not isinstance(t, dict) or not t.get("url"):
                continue
            w = int(t.get("width") or 0)
            h = int(t.get("height") or 0)
            if square and w and h and abs(w - h) > 4:
                continue
            if w > 900 or (bw and w < bw):
                continue
            best, bw = t["url"], w
        if best.startswith("//"):
            best = "https:" + best
        return best

    @staticmethod
    def img_url(u):
        return "/api/yt/img?u=" + urllib.parse.quote(u, safe="") if u else ""

    def video(self, e):
        """Eintrag aus yt-dlp (flach) -> Video fuer die Oberflaeche; None fuer Shorts und Unbrauchbares."""
        vid = str(e.get("id") or "")
        url = str(e.get("url") or e.get("webpage_url") or "")
        if not YT_VID.fullmatch(vid) or "/shorts/" in url:
            return None
        live = e.get("live_status") == "is_live" or bool(e.get("is_live"))
        if e.get("live_status") in ("is_upcoming", "post_live") and not live:
            return None
        dur = int(e.get("duration") or 0)
        if 0 < dur <= 60:                                  # Shorts tauchen in der Suche auch als normale Videos auf
            return None
        ts = e.get("timestamp") or e.get("release_timestamp") or 0
        return {"kind": "video", "id": vid, "title": str(e.get("title") or "")[:200],
                "channel": str(e.get("channel") or e.get("uploader") or "")[:100],
                "channel_id": str(e.get("channel_id") or "") if YT_CID.fullmatch(str(e.get("channel_id") or "")) else "",
                "duration": dur, "views": int(e.get("view_count") or 0), "published": int(ts or 0), "live": live,
                "thumb": f"/api/yt/img?v={vid}"}

    def channel_item(self, e):
        cid = str(e.get("channel_id") or e.get("id") or "")
        if not YT_CID.fullmatch(cid):
            m = YT_CID.search(str(e.get("url") or ""))
            cid = m.group(0) if m else ""
        if not cid:
            return None
        return {"kind": "channel", "id": cid, "title": str(e.get("channel") or e.get("title") or "")[:100],
                "followers": int(e.get("channel_follower_count") or 0),
                "thumb": self.img_url(self._thumb_url(e.get("thumbnails"), square=True))}

    def playlist_item(self, e):
        url = str(e.get("url") or "")
        m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
        pid = m.group(1) if m else str(e.get("id") or "")
        if not YT_PID.fullmatch(pid) or YT_VID.fullmatch(pid):
            return None
        thumb = self._thumb_url(e.get("thumbnails"))
        return {"kind": "playlist", "id": pid, "title": str(e.get("title") or "")[:200],
                "channel": str(e.get("channel") or e.get("uploader") or "")[:100],
                "count": int(e.get("playlist_count") or 0), "thumb": self.img_url(thumb)}

    def entry(self, e):
        url = str(e.get("url") or "")
        if "list=" in url and "watch?" not in url:
            return self.playlist_item(e)
        if "/channel/" in url or "/@" in url or YT_CID.fullmatch(str(e.get("id") or "")):
            return self.channel_item(e)
        return self.video(e)

    def annotate(self, items):
        """Fortschritt (Verlauf), Spaeter-Markierung und Abo-Status ergaenzen."""
        hist = {h["id"]: h for h in self._load(self.HIST, []) if isinstance(h, dict) and h.get("id")}
        later = {x.get("id") for x in self._load(self.LATER, []) if isinstance(x, dict)}
        subs = {x.get("id") for x in self._load(self.SUBS, []) if isinstance(x, dict)}
        out = []
        for it in items:
            if not it:
                continue
            it = dict(it)
            if it["kind"] == "video":
                h = hist.get(it["id"])
                if h and not it.get("live"):
                    it["pos"], it["dur"] = h.get("pos", 0), h.get("dur", 0)
                it["later"] = it["id"] in later
            elif it["kind"] == "channel":
                it["sub"] = it["id"] in subs
            out.append(it)
        return out

    # ---- Suche, Kanaele, Playlists ----
    def search(self, q, kind="video"):
        q = " ".join(str(q or "").split())[:200]
        if not q:
            return {"items": []}
        if kind not in ("video", "channel", "playlist"):
            kind = "video"

        def fetch():
            if kind == "video":
                d = self._ytdlp(["-J", "--flat-playlist", f"ytsearch40:{q}"], timeout=90)
                items = [self.video(e) for e in d.get("entries") or []]
            else:
                sp = "EgIQAg==" if kind == "channel" else "EgIQAw=="
                url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q, "sp": sp})
                d = self._ytdlp(["-J", "--flat-playlist", "--playlist-end", "30", url], timeout=90)
                items = [self.entry(e) for e in d.get("entries") or []]
                items = [x for x in items if x and x["kind"] == kind]
            seen, out = set(), []
            for x in items:
                if x and (x["kind"], x["id"]) not in seen:
                    seen.add((x["kind"], x["id"]))
                    out.append(x)
            return out
        return {"items": self.annotate(self._cached("search", (kind, q.lower()), 600, fetch)), "q": q, "kind": kind}

    def channel(self, cid, tab="videos"):
        if not YT_CID.fullmatch(cid or ""):
            raise YtError("gone", "ungueltige Kanal-ID")
        tab = tab if tab in ("videos", "streams", "playlists") else "videos"

        def fetch():
            d = self._ytdlp(["-J", "--flat-playlist", "--playlist-end", "60",
                             f"https://www.youtube.com/channel/{cid}/{tab}"], timeout=90)
            ents = d.get("entries") or []
            items = [self.playlist_item(e) if tab == "playlists" else self.video(e) for e in ents]
            if tab == "streams":                           # vergangene Livestreams sind normale Videos
                items = [x for x in items if x]
            name = str(d.get("channel") or d.get("uploader") or d.get("title") or "")
            name = re.sub(r"\s+-\s+(Videos|Live|Playlists)$", "", name)
            thumb = self._thumb_url([t for t in d.get("thumbnails") or [] if "avatar" in str(t.get("id", ""))]
                                    or d.get("thumbnails"), square=True)
            return {"id": cid, "title": name[:100], "followers": int(d.get("channel_follower_count") or 0),
                    "thumb": self.img_url(thumb), "tab": tab, "items": [x for x in items if x]}
        r = dict(self._cached("channel", (cid, tab), 900, fetch))
        self._sub_touch(cid, r.get("title"), r.get("thumb"))
        r["sub"] = cid in {x.get("id") for x in self._load(self.SUBS, []) if isinstance(x, dict)}
        r["items"] = self.annotate(r["items"])
        return r

    def playlist(self, pid):
        if not YT_PID.fullmatch(pid or ""):
            raise YtError("gone", "ungueltige Playlist-ID")

        def fetch():
            d = self._ytdlp(["-J", "--flat-playlist", "--playlist-end", "300",
                             f"https://www.youtube.com/playlist?list={pid}"], timeout=120)
            items = [self.video(e) for e in d.get("entries") or []]
            return {"id": pid, "title": str(d.get("title") or "")[:200],
                    "channel": str(d.get("channel") or d.get("uploader") or "")[:100],
                    "channel_id": str(d.get("channel_id") or "") if YT_CID.fullmatch(str(d.get("channel_id") or "")) else "",
                    "items": [x for x in items if x]}
        r = dict(self._cached("playlist", pid, 900, fetch))
        r["items"] = self.annotate(r["items"])
        r["count"] = len(r["items"])
        return r

    # ---- Abspielen ----
    def resolve(self, vid, quality="auto", lang="de"):
        """Stream-Adressen fuer mpv: Bild und Ton getrennt (DASH) oder eine Adresse (Livestream: HLS)."""
        if not YT_VID.fullmatch(vid or ""):
            raise YtError("gone", "ungueltige Video-ID")
        if quality not in YT_QUALITIES:
            quality = self.settings()["quality"]
        weak = self.weak()
        h = (480 if weak else 1080) if quality == "auto" else int(quality)
        # H.264 ist am billigsten zu dekodieren (und kann fast jede Grafikkarte); auf schwacher Hardware hoechstens 30 fps
        sort = f"res:{h},vcodec:h264,acodec:aac" + (",fps:30" if weak else "")

        def fetch():
            d = self._ytdlp(["-J", "--no-playlist", "-f", "bv+ba/b", "-S", sort,
                             f"https://www.youtube.com/watch?v={vid}"], timeout=150 if weak else 75)
            rf = d.get("requested_formats") or []
            vf = next((f for f in rf if f.get("vcodec") not in (None, "none")), None)
            af = next((f for f in rf if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")), None)
            main = vf or d
            url = str(main.get("url") or "")
            if not url.startswith("http"):
                raise YtError("failed", "keine Stream-Adresse")
            hdr = main.get("http_headers") or d.get("http_headers") or {}
            heights = sorted({int(f.get("height") or 0) for f in d.get("formats") or []
                              if f.get("vcodec") not in (None, "none") and 144 <= int(f.get("height") or 0) <= 2160},
                             reverse=True)
            subs = []
            for code, tracks in (d.get("subtitles") or {}).items():   # nur echte Untertitel, keine automatischen
                vtt = next((t for t in tracks or [] if t.get("ext") == "vtt" and t.get("url")), None)
                if vtt and code != "live_chat":
                    subs.append({"lang": code, "name": str(vtt.get("name") or code), "url": vtt["url"]})
            want = [lang.split("-")[0], "en", str(d.get("language") or "")]
            subs.sort(key=lambda s: next((i for i, w in enumerate(want) if w and s["lang"].split("-")[0] == w), 9))
            live = bool(d.get("is_live"))
            return {"id": vid, "title": str(d.get("title") or "")[:200],
                    "channel": str(d.get("channel") or d.get("uploader") or "")[:100],
                    "channel_id": str(d.get("channel_id") or "") if YT_CID.fullmatch(str(d.get("channel_id") or "")) else "",
                    "duration": int(d.get("duration") or 0), "live": live,
                    "url": url, "audio": str(af.get("url") or "") if af else "",
                    "ua": str(hdr.get("User-Agent") or ""), "referer": str(hdr.get("Referer") or ""),
                    "height": int(main.get("height") or 0), "vcodec": str(main.get("vcodec") or ""),
                    "heights": heights, "quality": quality, "subs": subs[:3],
                    "thumb": f"/api/yt/img?v={vid}"}
        t0 = time.monotonic()
        key = ("resolve", (vid, quality, lang))
        with self.lock:
            hit = self.cache.get(key)
        # Adressen gelten bei YouTube etwa 6 Stunden; Livestreams nur kurz aufheben
        if hit and time.time() - hit[0] < (600 if hit[1].get("live") else 5400):
            return hit[1]
        r = fetch()
        with self.lock:
            self.cache[key] = (time.time(), r)
        log(f"YouTube Light: {vid} aufgeloest in {time.monotonic() - t0:.1f} s ({r.get('height')}p {r.get('vcodec')})")
        return r

    # ---- Verlauf, Spaeter, Weiterschauen ----
    @staticmethod
    def _meta(body):
        vid = str(body.get("id") or "")
        if not YT_VID.fullmatch(vid):
            raise ValueError("ungueltige Video-ID")
        cid = str(body.get("channel_id") or "")
        return {"kind": "video", "id": vid, "title": str(body.get("title") or "")[:200],
                "channel": str(body.get("channel") or "")[:100], "channel_id": cid if YT_CID.fullmatch(cid) else "",
                "duration": int(float(body.get("duration") or body.get("dur") or 0)), "live": bool(body.get("live")),
                "thumb": f"/api/yt/img?v={vid}"}

    def progress(self, body):
        it = self._meta(body)
        pos, dur = float(body.get("pos") or 0), float(body.get("dur") or 0)
        with self.lock:
            hist = [h for h in self._load(self.HIST, []) if isinstance(h, dict) and h.get("id") != it["id"]]
            it.update({"pos": 0 if it["live"] else round(pos, 1), "dur": round(dur, 1), "t": int(time.time())})
            hist.insert(0, it)
            self._save(self.HIST, hist[:self.MAX_HIST])
        return {"ok": True}

    def history(self):
        return {"items": self.annotate(self._load(self.HIST, []))}

    def history_remove(self, vid):
        with self.lock:
            hist = self._load(self.HIST, [])
            self._save(self.HIST, [h for h in hist if isinstance(h, dict) and h.get("id") != vid] if vid else [])
        return self.history()

    def resume_list(self):
        out = []
        for h in self._load(self.HIST, []):
            if isinstance(h, dict) and not h.get("live") and h.get("dur", 0) > 0 and 30 < h.get("pos", 0) < 0.95 * h["dur"]:
                out.append(h)
        return self.annotate(out[:20])

    def later(self):
        return {"items": self.annotate(self._load(self.LATER, []))}

    def later_set(self, body):
        it = self._meta(body.get("item") or {})
        with self.lock:
            lst = [x for x in self._load(self.LATER, []) if isinstance(x, dict) and x.get("id") != it["id"]]
            if body.get("on"):
                lst.insert(0, it)
            self._save(self.LATER, lst[:self.MAX_LATER])
        return {"on": bool(body.get("on")), "n": len(lst)}

    # ---- Abos ----
    def subs(self):
        lst = [x for x in self._load(self.SUBS, []) if isinstance(x, dict) and YT_CID.fullmatch(str(x.get("id") or ""))]
        lst.sort(key=lambda x: str(x.get("title") or "").lower())
        if any(not x.get("thumb") for x in lst):
            self._fetch_avatars()
        return [{"kind": "channel", "id": x["id"], "title": x.get("title") or x["id"], "thumb": x.get("thumb") or "",
                 "sub": True} for x in lst]

    def sub_set(self, body):
        it = body.get("item") or {}
        cid = str(it.get("id") or it.get("channel_id") or "")
        if not YT_CID.fullmatch(cid):
            raise ValueError("ungueltige Kanal-ID")
        on = bool(body.get("on"))
        with self.lock:
            lst = [x for x in self._load(self.SUBS, []) if isinstance(x, dict) and x.get("id") != cid]
            if on:
                lst.append({"id": cid, "title": str(it.get("title") or it.get("channel") or "")[:100],
                            "thumb": str(it.get("thumb") or ""), "t": int(time.time())})
            self._save(self.SUBS, lst)
            self.feed["t"] = 0                             # Feed beim naechsten Abruf neu holen
        log("YouTube Light: Abo", "an" if on else "aus", cid)
        return {"on": on, "n": len(lst)}

    def _sub_touch(self, cid, title, thumb):
        """Name und Bild eines abonnierten Kanals nachtragen (Import liefert oft nur die ID)."""
        with self.lock:
            lst = self._load(self.SUBS, [])
            changed = False
            for x in lst:
                if isinstance(x, dict) and x.get("id") == cid:
                    if title and not x.get("title"):
                        x["title"], changed = title, True
                    if thumb and not x.get("thumb"):
                        x["thumb"], changed = thumb, True
            if changed:
                self._save(self.SUBS, lst)

    def _fetch_avatars(self):
        """Fehlende Kanalbilder nachladen (og:image der Kanalseite), eins pro Sekunde, im Hintergrund."""
        if self.avatar_busy:
            return
        self.avatar_busy = True

        def work():
            try:
                for x in self._load(self.SUBS, []):
                    if not isinstance(x, dict) or x.get("thumb") or not YT_CID.fullmatch(str(x.get("id") or "")):
                        continue
                    if x.get("nothumb", 0) > time.time() - 86400:
                        continue
                    thumb, title = "", ""
                    try:
                        req = urllib.request.Request(f"https://www.youtube.com/channel/{x['id']}", headers=self.WEB_HEADERS)
                        with urllib.request.urlopen(req, timeout=15) as r:
                            html = r.read(1_500_000).decode("utf-8", "replace")
                        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
                        thumb = self.img_url(m.group(1).replace("&amp;", "&")) if m and YT_IMG_HOSTS.match(m.group(1)) else ""
                        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
                        title = m.group(1) if m else ""
                    except (OSError, ValueError) as e:
                        log("YouTube Light: Kanalbild", x["id"], e)
                    with self.lock:
                        lst = self._load(self.SUBS, [])
                        for y in lst:
                            if isinstance(y, dict) and y.get("id") == x["id"]:
                                if thumb:
                                    y["thumb"] = thumb
                                else:
                                    y["nothumb"] = int(time.time())
                                if title and not y.get("title"):
                                    y["title"] = html_unescape(title)[:100]
                        self._save(self.SUBS, lst)
                    time.sleep(1)
            finally:
                self.avatar_busy = False
        threading.Thread(target=work, daemon=True).start()

    def import_subs(self):
        """Abos aus Dateien uebernehmen: Google Takeout (subscriptions.csv / Abos.csv, auch im ZIP), NewPipe
        (newpipe_subscriptions*.json), FreeTube (profiles.db / *subscriptions*.db). Gesucht wird in ~/share und auf
        USB-Laufwerken; vorhandene Abos bleiben."""
        import zipfile
        found, chans = [], {}

        def take(text, name):
            n0 = len(chans)
            lines = text.splitlines()
            if name.lower().endswith(".csv"):
                for ln in lines[1:]:
                    m = YT_CID.search(ln)
                    if m:
                        cols = next(csv.reader([ln]), [])
                        title = next((c for c in reversed(cols) if c and "youtube.com" not in c and not YT_CID.fullmatch(c)), "")
                        chans.setdefault(m.group(0), title.strip())
            else:
                try:
                    objs = [json.loads(text)]
                except ValueError:
                    objs = []
                    for ln in lines:                       # FreeTube: eine JSON-Zeile pro Profil
                        try:
                            objs.append(json.loads(ln))
                        except ValueError:
                            pass
                for o in objs:
                    for s in (o.get("subscriptions") or []) if isinstance(o, dict) else []:
                        if not isinstance(s, dict):
                            continue
                        m = YT_CID.search(str(s.get("id") or s.get("url") or ""))
                        if m:
                            chans.setdefault(m.group(0), str(s.get("name") or "").strip())
            if len(chans) > n0:
                found.append(name)

        def wanted(p):
            n = p.name.lower()
            return (n.endswith(".csv") and ("subscription" in n or n.startswith("abo"))) or \
                   (n.endswith(".json") and "newpipe" in n and "subscription" in n) or \
                   (n.endswith(".db") and ("profiles" in n or "subscription" in n)) or \
                   (n.endswith(".zip") and n.startswith("takeout"))
        roots = [Path.home() / "share"] + [p for d in ("/run/media", "/media") for p in Path(d).glob("*/*") if p.is_dir()]
        for root in roots:
            base_depth = len(root.parts)
            for dirpath, dirs, files in os.walk(root):
                if len(Path(dirpath).parts) - base_depth >= 4:
                    dirs[:] = []
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    p = Path(dirpath) / fn
                    if not wanted(p):
                        continue
                    try:
                        if p.stat().st_size > 50_000_000:
                            continue
                        if p.suffix.lower() == ".zip":
                            with zipfile.ZipFile(p) as z:
                                for zn in z.namelist():
                                    low = zn.lower().rsplit("/", 1)[-1]
                                    if low.endswith(".csv") and ("subscription" in low or low.startswith("abo")):
                                        take(z.read(zn).decode("utf-8-sig", "replace"), f"{p.name}/{low}")
                        else:
                            take(p.read_text(encoding="utf-8-sig", errors="replace"), p.name)
                    except (OSError, zipfile.BadZipFile, UnicodeError) as e:
                        log("YouTube Light: Import", p, e)
        added = 0
        with self.lock:
            lst = [x for x in self._load(self.SUBS, []) if isinstance(x, dict)]
            have = {x.get("id") for x in lst}
            for cid, title in chans.items():
                if cid not in have:
                    lst.append({"id": cid, "title": title[:100], "thumb": "", "t": int(time.time())})
                    added += 1
            self._save(self.SUBS, lst)
            if added:
                self.feed["t"] = 0
        log(f"YouTube Light: Import aus {', '.join(found) or 'nichts gefunden'} – {added} neue Kanaele")
        if added:
            self._fetch_avatars()
        return {"files": found, "found": len(chans), "added": added, "total": len(lst)}

    # ---- Abo-Feed (RSS) ----
    def _rss(self, cid):
        """Neueste Videos eines Kanals. Zuerst der Playlist-Feed UULF… (nur normale Videos, ohne Shorts und
        Livestreams), sonst der Kanal-Feed ohne /shorts/-Eintraege. Bei Fehlern der letzte gute Stand."""
        cache = self.CACHE / "feeds" / f"{cid}.json"
        old = self._load(cache, {})
        items, err = None, ""
        for q, shorts_filter in ((f"playlist_id=UULF{cid[2:]}", False), (f"channel_id={cid}", True)):
            try:
                req = urllib.request.Request(self.RSS + q, headers=UA)
                with urllib.request.urlopen(req, timeout=15) as r:
                    root = ET.fromstring(r.read(3_000_000))
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code}"
                if e.code == 404:
                    continue
                break
            except (OSError, ET.ParseError) as e:
                err = str(e)
                break
            items = []
            title = (root.findtext("a:title", "", self.NS) or "").strip()
            for en in root.findall("a:entry", self.NS):
                vid = en.findtext("yt:videoId", "", self.NS)
                link = en.find("a:link", self.NS)
                href = link.get("href", "") if link is not None else ""
                if not YT_VID.fullmatch(vid or "") or (shorts_filter and "/shorts/" in href):
                    continue
                stats = en.find("m:group/m:community/m:statistics", self.NS)
                pub = en.findtext("a:published", "", self.NS)
                try:
                    ts = int(datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                except ValueError:
                    ts = 0
                items.append({"kind": "video", "id": vid, "title": (en.findtext("a:title", "", self.NS) or "")[:200],
                              "channel": (en.findtext("a:author/a:name", "", self.NS) or title)[:100], "channel_id": cid,
                              "duration": 0, "views": int(stats.get("views") or 0) if stats is not None else 0,
                              "published": ts, "live": False, "thumb": f"/api/yt/img?v={vid}"})
            break
        if items is None:
            return old.get("items") or [], err or "kein Feed"
        self._save(cache, {"t": int(time.time()), "items": items})
        return items, ""

    def _refresh_feed(self):
        from concurrent.futures import ThreadPoolExecutor
        subs = [x for x in self._load(self.SUBS, []) if isinstance(x, dict) and YT_CID.fullmatch(str(x.get("id") or ""))]
        t0 = time.monotonic()
        errors, allv = 0, []
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for items, err in ex.map(lambda s: self._rss(s["id"]), subs):
                    allv += items
                    errors += 1 if err else 0
            seen, uniq = set(), []
            for v in sorted(allv, key=lambda v: v["published"], reverse=True):
                if v["id"] not in seen:
                    seen.add(v["id"])
                    uniq.append(v)
            with self.lock:
                self.feed.update(items=uniq[:300], t=time.time(), errors=errors)
            log(f"YouTube Light: Feed aus {len(subs)} Kanaelen in {time.monotonic() - t0:.1f} s"
                + (f", {errors} nicht erreichbar" if errors else ""))
        finally:
            with self.lock:
                self.feed["refreshing"] = False

    def feed_get(self, limit=150, force=False):
        has_subs = bool(self._load(self.SUBS, []))
        with self.lock:
            stale = force or time.time() - self.feed["t"] > 900
            if stale and has_subs and not self.feed["refreshing"]:
                self.feed["refreshing"] = True
                threading.Thread(target=self._refresh_feed, daemon=True).start()
            items = list(self.feed["items"][:limit])
            state = {"refreshing": self.feed["refreshing"], "errors": self.feed["errors"], "t": int(self.feed["t"])}
        if not items and not self.feed["t"]:                # gleich nach dem Start: letzter Stand aus den Dateien
            allv = []
            for x in self._load(self.SUBS, []):
                if isinstance(x, dict) and x.get("id"):
                    allv += self._load(self.CACHE / "feeds" / f"{x['id']}.json", {}).get("items") or []
            items = sorted({v["id"]: v for v in allv}.values(), key=lambda v: v["published"], reverse=True)[:limit]
        return dict(state, items=self.annotate(items))

    def home(self):
        f = self.feed_get(60)
        later = self._load(self.LATER, [])
        return {"resume": self.resume_list(), "feed": f["items"], "refreshing": f["refreshing"], "errors": f["errors"],
                "later": self.annotate(later[:30]), "laterCount": len(later), "subs": self.subs(),
                "historyCount": len(self._load(self.HIST, []))}

    # ---- Bilder (Zwischenspeicher, damit alte Rechner nicht alles neu laden) ----
    def img(self, vid="", url=""):
        if vid:
            if not YT_VID.fullmatch(vid):
                return None
            url = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
        if not YT_IMG_HOSTS.match(url or ""):
            return None
        f = self.CACHE / "img" / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".jpg")
        try:
            if f.is_file() and f.stat().st_size:
                return f.read_bytes()
        except OSError:
            pass
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read(2_000_000)
                if not str(r.headers.get("Content-Type", "")).startswith("image/"):
                    return None
        except (OSError, ValueError):
            return None
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            if random.random() < 0.02:                     # ab und zu aufraeumen: hoechstens ~4000 Bilder
                files = sorted(f.parent.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
                for p in files[:max(0, len(files) - 4000)]:
                    p.unlink(missing_ok=True)
        except OSError:
            pass
        return data

    # ---- yt-dlp aktualisieren (eigene Kopie, Prüfsumme von GitHub) ----
    def update_ytdlp(self, quiet=False):
        with self.lock:
            if self.upd["state"] == "running":
                return dict(self.upd)
            self.upd = {"state": "running", "msg": "", "t": int(time.time()), "quiet": quiet}

        def work():
            tmp = self.LOCAL.with_suffix(".new")
            try:
                req = urllib.request.Request(self.YTDLP_URL + "SHA2-256SUMS", headers=UA)
                with urllib.request.urlopen(req, timeout=30) as r:
                    sums = r.read(200_000).decode("utf-8", "replace")
                want = next((ln.split()[0] for ln in sums.splitlines()
                             if len(ln.split()) == 2 and ln.split()[1].lstrip("*") == "yt-dlp"), "")
                if not re.fullmatch(r"[0-9a-f]{64}", want):
                    raise RuntimeError("Pruefsumme nicht gefunden")
                self.LOCAL.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                req = urllib.request.Request(self.YTDLP_URL + "yt-dlp", headers=UA)
                with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as fh:
                    while True:
                        b = r.read(65536)
                        if not b:
                            break
                        h.update(b)
                        fh.write(b)
                if h.hexdigest() != want:
                    raise RuntimeError("Pruefsumme stimmt nicht")
                tmp.chmod(0o755)
                r = run([str(tmp), "--version"], timeout=60)
                if not r or r.returncode != 0:
                    raise RuntimeError("neue Version startet nicht")
                tmp.replace(self.LOCAL)
                self.ver = ("", 0.0)
                with self.lock:
                    self.cache = {k: v for k, v in self.cache.items() if k[0] != "resolve"}
                    self.upd = {"state": "done", "msg": r.stdout.strip(), "t": int(time.time()), "quiet": quiet}
                log("YouTube Light: yt-dlp aktualisiert auf", r.stdout.strip())
            except (OSError, RuntimeError, ValueError) as e:
                tmp.unlink(missing_ok=True)
                with self.lock:
                    self.upd = {"state": "error", "msg": str(e)[:200], "t": int(time.time()), "quiet": quiet}
                log("YouTube Light: yt-dlp-Aktualisierung fehlgeschlagen:", e)
        threading.Thread(target=work, daemon=True).start()
        return dict(self.upd)

    def _auto_update(self):
        """Gibt es schon eine eigene yt-dlp-Kopie, wird sie woechentlich still aktualisiert (YouTube aendert oft etwas)."""
        try:
            age = time.time() - self.LOCAL.stat().st_mtime
        except OSError:
            return
        if age > 7 * 86400 and self.upd["state"] != "running" and time.time() - self.upd.get("t", 0) > 86400:
            self.update_ytdlp(quiet=True)


YT = YtLight()


# ---------------------------------------------------------------------------
#  HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "voidstation"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):     # Oberflaeche hat abgebrochen (z. B. Vorschaubild weggeblaettert)
            pass

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def _host_ok(self):
        return self.headers.get("Host", "") in (f"{HOST}:{PORT}", f"localhost:{PORT}")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 65536:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            return {}

    def _yt_get(self, what, qs):
        """YouTube Light (GET): Zustand, Startseite, Feed, Suche, Kanal, Playlist, Verlauf, Spaeter, Abos, Bilder."""
        g = lambda k: qs.get(k, [""])[0]
        try:
            if what == "img":
                data = YT.img(vid=g("v"), url=g("u"))
                return self._send(200, data, "image/jpeg") if data else self._send(404)
            res = {"state": YT.state, "home": YT.home, "history": YT.history, "later": YT.later,
                   "subs": lambda: {"items": YT.subs()},
                   "feed": lambda: YT.feed_get(300, force=g("force") == "1"),
                   "search": lambda: YT.search(g("q"), g("kind") or "video"),
                   "channel": lambda: YT.channel(g("id"), g("tab") or "videos"),
                   "playlist": lambda: YT.playlist(g("id"))}.get(what)
            if not res:
                return self._send(404)
            return self._json(200, res())
        except YtError as e:
            return self._json(502, {"error": e.reason, "msg": str(e)})
        except (ValueError, OSError) as e:
            log("YouTube Light:", e)
            return self._json(500, {"error": "failed", "msg": str(e)})

    def do_GET(self):
        if not self._host_ok():
            return self._send(403)
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path == "/api/front":                   # heisse Ecke und Controller-Maus der Startseite
            tid = APPS.front()
            return self._json(200, {"id": tid, "mouse": pad_mouse_default(tid),
                                    "padmouse": bool(settings_load().get("padmouse", True))})
        if path == "/api/status":
            running = APPS.running()
            return self._json(200, {"running": running, "starting": APPS.starting(), "radio": RADIO.status(),
                                    "update": updates_badge() if not LIVE else {"available": False},
                                    "tv": TV.now if "tv" in running else None, "tvFailed": TV.failed, "live": LIVE,
                                    "media": (MEDIA_NOW or None) if "media" in running else None,
                                    "install": INSTALL.state.get("state") if INSTALL.state else None})
        if path == "/api/tv/status":
            TV.ensure()
            return self._json(200, TV.status())
        if path in ("/api/tv/list", "/api/tv/search"):
            qs = urllib.parse.parse_qs(url.query)
            g = lambda k: qs.get(k, [""])[0]
            if path == "/api/tv/search":
                return self._json(200, TV.search(g("q"), g("country"), g("cat")))
            num = lambda k, d: int(g(k)) if g(k).isdigit() else d
            return self._json(200, TV.page(g("q"), g("country"), g("cat"), g("letter").upper(),
                                           num("offset", 0), num("limit", TV_PAGE)))
        if path == "/api/tv/favs":
            return self._json(200, [TV.mark(IPTV.public(f)) for f in tvfavs_load()])
        if path == "/api/tv/zap":                    # Player: Liste zum Umschalten, Favoriten, zuletzt gesehen
            TV.ensure()
            return self._json(200, TV.zap())
        if path == "/api/media/roots":
            return self._json(200, MEDIA.roots())
        if path == "/api/media/list":
            try:
                return self._json(200, MEDIA.listdir(urllib.parse.parse_qs(url.query).get("path", [""])[0]))
            except (ValueError, FileNotFoundError, OSError) as e:
                return self._json(404, {"error": str(e)})
        if path == "/api/media/dvd":                 # Startseite der Mediathek: Disc eingelegt/entnommen?
            return self._json(200, {"discs": DVD.discs()})
        if path == "/api/media/nextfolder":
            try:
                return self._json(200, MEDIA.next_folder(urllib.parse.parse_qs(url.query).get("path", [""])[0]) or {})
            except (ValueError, OSError) as e:
                return self._json(404, {"error": str(e)})
        if path == "/api/dl/settings":
            return self._json(200, MUSICDL.payload())
        if path == "/api/dl/status":
            return self._json(200, MUSICDL.status())
        if path.startswith("/api/yt/"):
            return self._yt_get(path[8:], urllib.parse.parse_qs(url.query))
        if path == "/api/media/covers":
            return self._json(200, COVERS.status())
        if path == "/api/media/thumb":
            qs = urllib.parse.parse_qs(url.query)
            cname = qs.get("cover", [""])[0]
            if cname:                                    # heruntergeladenes Cover aus dem Zwischenspeicher
                if not re.fullmatch(r"[0-9a-f]{16}\.jpg", cname) or not (COVERS.CACHE / cname).is_file():
                    return self._send(404)
                return self._send(200, (COVERS.CACHE / cname).read_bytes(), "image/jpeg")
            art = qs.get("art", [""])[0]
            r = MEDIA.art(art) if art else MEDIA.thumb(qs.get("path", [""])[0])
            if not r:
                return self._send(404)
            return self._send(200, r[0], r[1])
        if path == "/api/tv/epg":
            qs = urllib.parse.parse_qs(url.query)
            ch_id = qs.get("id", [""])[0] or qs.get("channel_id", [""])[0]
            ch_name = qs.get("name", [""])[0] or qs.get("channel_name", [""])[0] or ch_id
            return self._json(200, EPG.get_program(ch_id, ch_name) or {})
        if path == "/api/apps":
            return self._json(200, apps_payload())
        if path in ("/api/updates", "/api/selfupdate"):
            force = urllib.parse.parse_qs(url.query).get("force", [""])[0] == "1"
            return self._json(200, updates_state(force))
        if path == "/api/apps/job":
            return self._json(200, JOBS.current() or {})
        if path == "/api/radio/favs":
            return self._json(200, favs_load())
        if path == "/api/radio/search":
            q = urllib.parse.parse_qs(url.query).get("q", [""])[0].strip()
            if not q:
                return self._json(200, [])
            try:
                return self._json(200, radio_search(q))
            except RuntimeError as e:
                return self._json(502, {"error": str(e)})
        if path == "/api/volume":
            return self._json(200, volume_get() or {})
        if path == "/api/settings":
            return self._json(200, settings_payload())
        if path == "/api/install/probe":
            if not LIVE:
                return self._json(404, {"error": "nur im Live-System"})
            try:
                force = urllib.parse.parse_qs(url.query).get("force", [""])[0] == "1"
                return self._json(200, INSTALL.probe(force))
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
                return self._json(502, {"error": str(e)})
        if path == "/api/install/status":
            st = INSTALL.status()
            if INSTALL.autostart:
                st["autostart"] = True
                INSTALL.autostart = False                 # nur beim ersten Aufruf
            return self._json(200, st)
        if path == "/api/install/gparted":
            return self._json(200, {"running": INSTALL.gparted_running()})
        if path == "/api/install/log":
            try:
                return self._json(200, {"log": INSTALL.log_text()})
            except (OSError, subprocess.SubprocessError) as e:
                return self._json(502, {"error": str(e)})
        if path == "/api/wifi/scan":
            try:
                return self._json(200, wifi_scan())
            except RuntimeError as e:
                return self._json(502, {"error": str(e)})
        if path == "/api/roms":
            qs = urllib.parse.parse_qs(url.query)
            system = qs.get("system", [""])[0]
            if not system:
                summary = {}
                for s in ROMS.EXTENSIONS:
                    r = ROMS.list_folder(s)
                    if r:
                        summary[s] = len(r)
                return self._json(200, {"systems": summary})
            roms = ROMS.list_roms(system)
            for r in roms:
                r["cover"] = ROM_COVERS.url(r)
            return self._json(200, {"system": ROMS.canonical_system(system), "folders": ROMS.folders(system),
                                    "count": len(roms), "roms": roms})
        if path == "/api/roms/cover":              # Bild zum Spiel (eigenes oder online gesucht, s. RomCovers)
            qs = urllib.parse.parse_qs(url.query)
            try:
                f = ROM_COVERS.get(qs.get("folder", [""])[0], qs.get("file", [""])[0])
                if f:
                    return self._send(200, f.read_bytes(), MIME.get(f.suffix.lower(), "image/png"))
            except OSError as e:
                log("Cover:", e)
            return self._send(404)
        if path == "/api/bluetooth/status":
            return self._json(200, BLUETOOTH.status())
        if path == "/tiles.json":
            try:
                c = json.loads(CONFIG.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return self._send(404)
            hints = {a["id"]: a["start_hint"] for a in catalog()["apps"] if a.get("start_hint")}
            for g in c.get("groups", []):
                for t in g.get("tiles", []):
                    if t.get("id") in hints and not t.get("start_hint"):
                        t["start_hint"] = hints[t["id"]]
            return self._json(200, c)
        if path == "/":
            path = "/index.html"
        target = (WEB / path.lstrip("/")).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._send(404)
        self._send(200, target.read_bytes(), MIME.get(target.suffix, "application/octet-stream"))

    def do_POST(self):
        # Eigener Header erzwingt bei fremden Webseiten einen CORS-Preflight,
        # den wir nie beantworten -> nur die eigene Startseite darf Aktionen ausloesen.
        if not self._host_ok() or self.headers.get("X-TV") != "1":
            return self._send(403)
        parts = self.path.strip("/").split("/")
        try:
            if parts[:2] == ["api", "launch"] and len(parts) == 3:
                tile = find_tile(parts[2])
                if not tile:
                    return self._json(404, {"error": "unbekannte Kachel"})
                return self._json(200, {"result": APPS.launch(tile), "running": APPS.running()})
            if parts[:2] == ["api", "close"] and len(parts) == 3:
                APPS.close(parts[2])
                raise_home()
                return self._json(200, {"running": APPS.running()})
            if parts == ["api", "home"]:
                raise_home()
                return self._json(200, {"running": APPS.running()})
            if parts == ["api", "radio", "play"]:
                RADIO.play(self._body())
                return self._json(200, RADIO.status())
            if parts == ["api", "radio", "stop"]:
                RADIO.stop()
                return self._json(200, RADIO.status())
            if parts == ["api", "radio", "fav"]:
                st = self._body()
                favs = [f for f in favs_load() if f.get("url") != st.get("url")]
                if st.get("url"):
                    favs.append({k: st.get(k, "") for k in ("name", "url", "favicon", "country", "tags")})
                favs_save(favs)
                return self._json(200, favs)
            if parts == ["api", "radio", "unfav"]:
                url = self._body().get("url")
                favs = [f for f in favs_load() if f.get("url") != url]
                favs_save(favs)
                return self._json(200, favs)
            if parts == ["api", "tv", "play"]:
                b = self._body()
                return self._json(200, TV.play(str(b.get("key", "")), b.get("ctx")))
            if parts == ["api", "tv", "tune"]:              # Player schaltet um
                return self._json(200, TV.tune(str(self._body().get("key", ""))))
            if parts == ["api", "tv", "broken"]:
                b = self._body()
                TV.mark_broken(str(b.get("key", "")), str(b.get("reason", ""))[:40])
                return self._json(200, {"ok": True})
            if parts == ["api", "dl", "settings"]:
                return self._json(200, MUSICDL.save_settings(self._body().get("sources")))
            if parts[:2] == ["api", "yt"]:                        # YouTube Light
                b = self._body()
                act = "/".join(parts[2:])
                res = {"settings": lambda: YT.save_settings(b),
                       "resolve": lambda: YT.resolve(str(b.get("id") or ""), str(b.get("quality") or ""),
                                                     str(b.get("lang") or "de")),
                       "progress": lambda: YT.progress(b), "later": lambda: YT.later_set(b),
                       "sub": lambda: YT.sub_set(b), "import": YT.import_subs,
                       "history/remove": lambda: YT.history_remove(str(b.get("id") or "") or "-"),
                       "history/clear": lambda: YT.history_remove(""),
                       "update": lambda: YT.update_ytdlp()}.get(act)
                if not res:
                    return self._send(404)
                return self._json(200, res())
            if parts == ["api", "dl", "search"]:
                return self._json(200, MUSICDL.search(self._body().get("q")))
            if parts == ["api", "dl", "get"]:
                return self._json(200, MUSICDL.get(self._body().get("key")))
            if parts == ["api", "media", "covers", "scan"]:     # alle Ordner ohne Bild (Standard: share/Musik)
                root = MEDIA.resolve(str(self._body().get("path") or MEDIA.share() / "Musik"))
                if not root or not root.is_dir():
                    return self._json(404, {"error": "Ordner nicht gefunden"})
                COVERS.scan(root)
                return self._json(200, COVERS.status())
            if parts == ["api", "media", "covers", "auto"]:
                s = settings_load(); s["covers_auto"] = bool(self._body().get("on")); settings_save(s)
                return self._json(200, COVERS.status())
            if parts == ["api", "media", "covers", "refresh"]:  # Cover eines Titels neu suchen
                p = MEDIA.resolve(str(self._body().get("path") or ""))
                if not p or not p.is_file():
                    return self._json(404, {"error": "Datei nicht gefunden"})
                COVERS.refresh_track(p)
                return self._json(200, {"ok": True})
            if parts == ["api", "media", "covers", "embed"]:   # Cover + fehlende Tags in die Dateien schreiben
                s = settings_load(); s["covers_embed"] = bool(self._body().get("on")); settings_save(s)
                if s["covers_embed"]:
                    MEDIA.art_done.clear()               # beim naechsten Oeffnen der Ordner alle Titel einmal pruefen
                return self._json(200, COVERS.status())
            if parts == ["api", "media", "eject"]:
                return self._json(200, {"ok": DVD.eject(str(self._body().get("dev") or ""))})
            if parts == ["api", "media", "now"]:
                b = self._body()
                MEDIA_NOW.clear()
                if b.get("title"):
                    MEDIA_NOW.update({k: str(b.get(k) or "")[:120] for k in ("title", "sub", "kind")})
                return self._json(200, {"ok": True})
            if parts == ["api", "media", "resume"]:
                b = self._body()
                MEDIA.resume_set(str(b.get("path", "")), b.get("pos"), b.get("dur"))
                return self._json(200, {"ok": True})
            if parts == ["api", "tv", "stop"]:
                APPS.close("tv")
                TV.now = None
                return self._json(200, TV.status())
            if parts[:2] == ["api", "tv"] and parts[2:] in (["fav"], ["unfav"]):
                key = str(self._body().get("key", ""))
                favs = [f for f in tvfavs_load() if f.get("key") != key]
                if parts[2] == "fav":
                    e = TV.entry(key)
                    if not e:
                        return self._json(404, {"error": "Sender unbekannt"})
                    favs.append(e)
                tvfavs_save(favs)
                return self._json(200, [IPTV.public(f) for f in favs])
            if parts[:2] == ["api", "install"] and len(parts) == 3:
                if not LIVE:
                    return self._json(404, {"error": "nur im Live-System"})
                b = self._body()
                try:
                    if parts[2] == "start":
                        return self._json(200, INSTALL.start(b.get("config") or {}))
                    if parts[2] == "retry":
                        return self._json(200, INSTALL.start(resume=True, alt=bool(b.get("alt"))))
                    if parts[2] == "gparted":
                        INSTALL.gparted()
                        return self._json(200, {"running": True})
                    if parts[2] == "savelog":
                        return self._json(200, INSTALL.savelog())
                    if parts[2] == "keymap":
                        km = str(b.get("keymap", ""))
                        if km not in KEYMAPS:
                            return self._json(400, {"error": "unbekannte Tastatur"})
                        subprocess.run(["setxkbmap"] + KEYMAPS[km], capture_output=True, timeout=10)
                        return self._json(200, {"keymap": km})
                except RuntimeError as e:
                    return self._json(409, {"error": str(e)})
                return self._send(404)
            if parts == ["api", "settings", "ssh"]:
                on = bool(self._body().get("on"))
                r = subprocess.run(["sudo", "-n", PKG_HELPER, "ssh", "on" if on else "off"],
                                   capture_output=True, text=True, timeout=180)
                if r.returncode != 0:
                    return self._json(500, {"error": (r.stdout + r.stderr).strip()[-300:] or "fehlgeschlagen"})
                log("Fernzugriff (SSH):", "an" if on else "aus")
                return self._json(200, {"ssh": ssh_state()})
            if parts == ["api", "selfupdate", "channel"]:
                ch = str(self._body().get("channel", ""))
                if ch not in CHANNELS:
                    return self._json(400, {"error": "unbekannter Kanal"})
                r = subprocess.run(["sudo", "-n", PKG_HELPER, "channel", ch], capture_output=True, text=True, timeout=20)
                if r.returncode != 0:
                    return self._json(500, {"error": (r.stdout + r.stderr).strip() or "fehlgeschlagen"})
                vs_update_status(force=True)
                return self._json(200, updates_state())
            if parts == ["api", "apps", "localtile"]:
                b = self._body()
                try:
                    local_tile(str(b.get("id", "")), bool(b.get("on")))
                except RuntimeError as e:
                    return self._json(404, {"error": str(e)})
                return self._json(200, apps_payload())
            if parts[:2] == ["api", "apps"] and len(parts) == 3:
                act = parts[2]
                try:
                    if act in ("install", "remove"):
                        a = catalog_app(str(self._body().get("id", "")))
                        if not a:
                            return self._json(404, {"error": "unbekannte App"})
                        if act == "install" and not app_supported(a):
                            return self._json(409, {"error": f"{a['name']} gibt es nicht für {SYS_ARCH}"})
                        JOBS.start(act, a)
                    elif act == "update":               # alle Updates (Einstellungen → Updates, vsctl update)
                        if LIVE:
                            return self._json(409, {"error": "im Live-System gibt es keine Updates"})
                        JOBS.start(act)
                    else:
                        return self._send(404)
                except RuntimeError as e:
                    return self._json(409, {"error": str(e)})
                return self._json(200, JOBS.current())
            if parts == ["api", "settings", "sysupd"]:
                days = self._body().get("days")
                if days not in SYSUPD_DAYS:
                    return self._json(400, {"error": "ungueltige Frist"})
                s = settings_load(); s["sysupd_days"] = days; settings_save(s)
                log("Systemupdate-Erinnerung nach", days, "Tagen")
                return self._json(200, updates_state())
            if parts == ["api", "settings", "lang"]:
                lang = str(self._body().get("lang", ""))
                if lang not in {l["id"] for l in LANGS}:
                    return self._json(400, {"error": "unbekannte Sprache"})
                s = settings_load(); s["lang"] = lang; settings_save(s)
                log("Sprache:", lang)
                return self._json(200, {"lang": lang})
            if parts == ["api", "settings", "scale"]:
                val = float(self._body().get("scale", 1.75))
                if val not in SCALES:
                    return self._json(400, {"error": "ungueltige Skalierung"})
                s = settings_load(); s["scale"] = val; settings_save(s)
                apply_appearance(s)
                return self._json(200, settings_payload())
            if parts == ["api", "settings", "theme"]:
                th = str(self._body().get("theme", "")).strip()
                if th not in available_themes():
                    return self._json(400, {"error": "unbekanntes Theme"})
                s = settings_load(); s["theme"] = th; settings_save(s)
                apply_appearance(s)                    # Programme folgen hell/dunkel
                return self._json(200, settings_payload())
            if parts == ["api", "settings", "padmouse"]:
                on = bool(self._body().get("on"))
                s = settings_load(); s["padmouse"] = on; settings_save(s)
                log("Controller-Maus:", "an" if on else "aus")
                return self._json(200, settings_payload())
            if parts == ["api", "settings", "frontend"]:
                fe = str(self._body().get("frontend", ""))
                if fe not in frontends():
                    return self._json(400, {"error": "unbekannte Oberflaeche"})
                FRONTEND_FILE.write_text(fe + "\n", encoding="utf-8")
                log("Oberflaeche:", fe)
                restart_home_later(0.6)
                return self._json(200, settings_payload())
            if parts == ["api", "settings", "cursor"]:
                b = self._body()
                s = settings_load()
                if b.get("theme") in cursor_themes():
                    s["cursor_theme"] = b["theme"]
                if int(b.get("size") or 0) in CURSOR_SIZES:
                    s["cursor_size"] = int(b["size"])
                settings_save(s)
                apply_appearance(s)
                restart_home_later()
                return self._json(200, settings_payload())
            if parts == ["api", "settings", "resolution"]:
                res = str(self._body().get("mode", ""))
                if not any(res in o["modes"] for o in xrandr_info()):
                    return self._json(400, {"error": "Aufloesung nicht verfuegbar"})
                apply_resolution(res)
                s = settings_load(); s["resolution"] = res; settings_save(s)
                return self._json(200, settings_payload())
            if parts[:2] == ["api", "audio"] and len(parts) == 3 and parts[2] in ("device", "format", "mic"):
                b = self._body()
                key = str(b.get("key") or "")
                fmt = str(b["format"]) if parts[2] == "format" and b.get("format") is not None else None
                mic = bool(b.get("on")) if parts[2] == "mic" else None
                if parts[2] == "format" and fmt is None:
                    return self._json(400, {"error": "kein Format gewaehlt"})
                if not audio_select(key, fmt=fmt, mic=mic):
                    return self._json(400, {"error": "unbekannter Ausgang"})
                return self._json(200, settings_payload())
            if parts == ["api", "audio", "auto"]:
                s = settings_load(); s["audio_auto"] = bool(self._body().get("on")); settings_save(s)
                return self._json(200, settings_payload())
            if parts == ["api", "wifi", "connect"]:
                b = self._body()
                if not b.get("ssid"):
                    return self._json(400, {"error": "kein Netz gewaehlt"})
                try:
                    wifi_connect(str(b["ssid"]), str(b.get("password") or ""))
                except RuntimeError as e:
                    return self._json(502, {"error": str(e)})
                return self._json(200, settings_payload())
            if parts == ["api", "roms", "launch"]:
                b = self._body()
                sys_id = str(b.get("system", ""))
                filename = str(b.get("file") or b.get("filename") or b.get("path") or "")
                folder = str(b.get("folder") or "") or None
                try:
                    res = ROMS.launch(sys_id, filename, folder)
                    return self._json(200, {"result": res, "running": APPS.running()})
                except OSError as e:          # Emulator nicht installiert
                    return self._json(400, {"error": f"Emulator nicht gefunden: {e.filename or e}"})
                except (ValueError, RuntimeError) as e:
                    return self._json(400, {"error": str(e)})
            if parts == ["api", "bluetooth", "scan"]:
                BLUETOOTH.start_scan()
                return self._json(200, BLUETOOTH.status())
            if parts == ["api", "bluetooth", "pair"]:
                mac = str(self._body().get("mac", ""))
                if not BLUETOOTH.MAC_RE.match(mac):
                    return self._json(400, {"error": "ungueltige Geraeteadresse"})
                ok, err = BLUETOOTH.pair(mac)
                return self._json(200, {"ok": ok, "error": err, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "connect"]:
                mac = str(self._body().get("mac", ""))
                if not BLUETOOTH.MAC_RE.match(mac):
                    return self._json(400, {"error": "ungueltige Geraeteadresse"})
                ok, err = BLUETOOTH.connect(mac)
                return self._json(200, {"ok": ok, "error": err, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "disconnect"]:
                mac = str(self._body().get("mac", ""))
                if not BLUETOOTH.MAC_RE.match(mac):
                    return self._json(400, {"error": "ungueltige Geraeteadresse"})
                ok = BLUETOOTH.disconnect(mac)
                return self._json(200, {"ok": ok, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "remove"]:
                mac = str(self._body().get("mac", ""))
                if not BLUETOOTH.MAC_RE.match(mac):
                    return self._json(400, {"error": "ungueltige Geraeteadresse"})
                ok = BLUETOOTH.remove(mac)
                return self._json(200, {"ok": ok, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "rename"]:
                b = self._body()
                mac = str(b.get("mac", ""))
                if not BLUETOOTH.MAC_RE.match(mac):
                    return self._json(400, {"error": "ungueltige Geraeteadresse"})
                ok = BLUETOOTH.rename(mac, b.get("name", ""))
                return self._json(200, {"ok": ok, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "power"]:
                b = self._body()
                on = b.get("powered") if "powered" in b else b.get("on")
                ok = BLUETOOTH.power(bool(on))
                return self._json(200, {"ok": ok, "status": BLUETOOTH.status()})
            if parts == ["api", "bluetooth", "service"]:
                b = self._body()
                on = (b.get("action") == "start") if "action" in b else bool(b.get("on"))
                subprocess.run(["sudo", "-n", PKG_HELPER, "bluetooth", "on" if on else "off"],
                               capture_output=True, text=True, timeout=30)
                return self._json(200, BLUETOOTH.status())
            if parts[:2] == ["api", "volume"] and len(parts) == 3:
                return self._json(200, volume_set(parts[2]) or {})
            if parts == ["api", "power", "suspend"]:
                if not can_suspend():
                    return self._json(400, {"error": "Standby wird hier nicht unterstuetzt"})
                RADIO.stop()                           # wie beim Fernseher: Ton aus; Programme bleiben offen
                log("Standby")
                # kurz warten, damit die Antwort noch rausgeht und die Oberflaeche den Dialog schliesst
                threading.Timer(0.8, lambda: subprocess.Popen(POWER["suspend"])).start()
                return self._json(200, {"ok": True})
            if parts[:2] == ["api", "power"] and len(parts) == 3 and parts[2] in POWER:
                RADIO.stop()
                APPS.close_all()
                subprocess.Popen(POWER[parts[2]])
                return self._json(200, {"ok": True})
        except YtError as e:
            return self._json(502, {"error": e.reason, "msg": str(e)})
        except Exception as e:  # noqa: BLE001
            log("Fehler:", e)
            return self._json(500, {"error": str(e)})
        self._send(404)

    def do_OPTIONS(self):
        self._send(403)


# ---------------------------------------------------------------------------
#  Gamepad: Guide-Taste -> Startseite nach vorn
# ---------------------------------------------------------------------------
def gamepad_watcher():
    """Controller-Tasten, die VoidStation selbst auswertet (auch wenn ein Programm vorn ist):
      * Guide/Home: Startseite nach vorn
      * L3 lang halten: Vollbild des Emulators vorn an/aus (emu_toggle_fullscreen)
      * in mGBA: △ = Savestate speichern, □ = Savestate laden (emu_quick_state)
    Welche Taste L3, △ und □ ist, kommt aus pad_roles (eigene Belegung, SDL, Linux-Codes)."""
    try:
        import evdev  # type: ignore
        from evdev import ecodes
        import selectors
    except ImportError:
        log("python3-evdev fehlt, Gamepad-Home-Taste deaktiviert")
        return
    sel = selectors.DefaultSelector()
    known = {}                                     # Pfad -> Geraet
    roles = {}                                     # Pfad -> {evdev-Code: "l3" | "y" | "x"}

    def rescan():
        pads = {p["path"]: p for p in gamepads()}
        new = [p for p in pads if p not in known]
        probe = sdl_probe() if new else []
        for path in evdev.list_devices():
            if path in known:
                continue
            try:
                dev = evdev.InputDevice(path)
                if path in pads or ecodes.BTN_MODE in dev.capabilities().get(ecodes.EV_KEY, []):
                    known[path] = dev
                    sel.register(dev, selectors.EVENT_READ)
                    r = {}
                    if path in pads:
                        found, src = pad_roles(pads[path], probe)
                        r = {found[k]: k for k in ("l3", "y", "x") if k in found}
                        log("Gamepad erkannt:", dev.name, f"[{pads[path].get('id')}] (Belegung: {src}, Rollen:",
                            ", ".join(f"{k}={v}" for k, v in sorted(found.items())) + ")")
                    else:
                        log("Gamepad erkannt:", dev.name)
                    roles[path] = r or {ecodes.BTN_THUMBL: "l3"}
                else:
                    dev.close()
            except OSError:
                pass

    def drop(path):
        known.pop(path, None)
        roles.pop(path, None)
        for k in [k for k in held if k[0] == path]:
            held.pop(k, None)
            fired.discard(k)

    last_scan = 0.0
    held = {}                                      # (Pfad, Rolle) -> seit wann gedrueckt
    fired = set()                                  # (Pfad, Rolle): langes Halten hat schon ausgeloest
    while True:
        if time.time() - last_scan > 5:
            rescan()
            last_scan = time.time()
        for key, _ in sel.select(timeout=0.1 if held else 1):
            dev = key.fileobj
            try:
                for ev in dev.read():
                    if ev.type != ecodes.EV_KEY:
                        continue
                    if ev.code == ecodes.BTN_MODE and ev.value == 1:
                        raise_home()
                        continue
                    role = roles.get(dev.path, {}).get(ev.code)
                    if not role:
                        continue
                    if role in ("y", "x"):                             # △ speichern, □ laden
                        if ev.value == 1:
                            threading.Thread(target=emu_quick_state, args=(role == "x",), daemon=True).start()
                        continue
                    k = (dev.path, role)
                    if ev.value == 1:
                        held[k] = time.monotonic()
                    elif ev.value == 0 and k in held:
                        held.pop(k)
                        fired.discard(k)
            except OSError:
                sel.unregister(dev)
                drop(dev.path)
        for k, t in list(held.items()):
            if k not in fired and time.monotonic() - t >= FS_HOLD:
                fired.add(k)
                threading.Thread(target=emu_toggle_fullscreen, daemon=True).start()


def app_prefs():
    """Voreinstellungen fuer mitgelieferte Programme (nur Werte, die VoidStation vorgibt)."""
    conf = Path.home() / ".config/gpicview/gpicview.conf"            # Bildbetrachter: schwarzer Hintergrund
    try:
        txt = conf.read_text(encoding="utf-8") if conf.exists() else "[General]\n"
        for k in ("bg", "bg_full"):
            if re.search(rf"^{k}=", txt, re.M):
                txt = re.sub(rf"^{k}=.*$", f"{k}=#000000", txt, flags=re.M)
            else:
                txt = txt.replace("[General]\n", f"[General]\n{k}=#000000\n", 1)
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(txt, encoding="utf-8")
    except OSError as e:
        log("gpicview.conf:", e)


def resume_leftovers():
    """Vom vorigen Launcher im Hintergrund angehaltene Programme weiterlaufen lassen (z. B. nach einem Update,
    das den Launcher neu startet) – sonst hingen sie unsichtbar und unerreichbar herum."""
    try:
        pids = json.loads(PAUSED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    AppManager._kill_all([p for p in pids if isinstance(p, int) and p > 1], signal.SIGCONT)
    log("vom vorigen Start angehalten, laeuft weiter:", pids)
    PAUSED_FILE.unlink(missing_ok=True)


def on_term(sig, _frame):
    """SIGTERM: angehaltene Programme fortsetzen, sonst wie bisher sofort beenden (Radio & Co. laufen weiter)."""
    try:
        APPS.resume_all()
    finally:
        signal.signal(sig, signal.SIG_DFL)
        os.kill(os.getpid(), sig)


def main():
    global BOOT_BUILD
    BOOT_BUILD = vs_version().get("build")
    resume_leftovers()
    signal.signal(signal.SIGTERM, on_term)
    app_prefs()
    s = settings_load()
    apply_appearance(s)
    apply_resolution(s.get("resolution"))
    threading.Thread(target=gamepad_watcher, daemon=True).start()
    threading.Thread(target=resume_watcher, daemon=True).start()
    BLUETOOTH.start()                               # Kopplungs-Agent (BlueZ ueber D-Bus)
    threading.Thread(target=AUDIO_WATCH.run, daemon=True).start()   # neue Kopfhoerer, HDMI-Vorgabe Stereo
    if not LIVE:                                    # im Live-System gibt es keine Updates
        threading.Thread(target=updates_background_check, daemon=True).start()
        threading.Thread(target=kernel_autopurge, daemon=True).start()
        threading.Thread(target=SAVES.watcher, daemon=True).start()   # Spielstaende alle 30 Minuten sichern
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"laeuft auf http://{HOST}:{PORT}/")
    try:
        httpd.serve_forever()
    finally:
        APPS.resume_all()
        RADIO.stop()


if __name__ == "__main__":
    main()
