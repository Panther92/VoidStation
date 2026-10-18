#!/usr/bin/env python3
"""
Qt-Startseite ohne Void-Geraet ausprobieren: Beispieldaten wie tools/screenshots.py, eigener Port 8766.
Benoetigt: pip install PySide6-Essentials (gleiche Version wie python3-pyside6 in Void)
Aufruf:    python3 tools/qt-preview.py                         -> Fenster 1280×720 auf dem Bildschirm
           python3 tools/qt-preview.py --size 1920x1080
           python3 tools/qt-preview.py --shot out.png --keys "right,a,shot:radio.png,b"   (ohne Bildschirm)
           VS_LANG=en …                                        -> englische Oberflaeche
           python3 tools/qt-preview.py --player tv             -> Fernseh-Player (Teststream von mpv: Testbild)
           python3 tools/qt-preview.py --player media --home DIR   -> Videos & Musik, DIR wie ein Home (DIR/share/Videos …)
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import screenshots as S  # noqa: E402  (Beispieldaten und Web-Auslieferung)

PORT = 8766
BT = {"pairing": None, "prompt": None, "names": {}}   # Bluetooth-Kopplung, eigene Geraetenamen (Vorschau)
BT_DEVICES = [{"mac": "11:22:33:44:55:66", "name": "Wireless Controller", "paired": True, "connected": True,
               "kind": "gamepad", "battery": 80},
              {"mac": "AA:BB:CC:DD:EE:01", "name": "AirPods", "paired": False, "kind": "audio", "battery": None},
              {"mac": "AA:BB:CC:DD:EE:FF", "name": "JBL Flip 5", "paired": True, "kind": "audio", "battery": None}]


def bt_devices():
    out = []
    for d in BT_DEVICES:
        alias = BT["names"].get(d["mac"], "")
        out.append(dict(d, name=alias or d["name"], orig=d["name"], custom=bool(alias) and alias != d["name"]))
    return out


def bt_status():
    return {"available": True, "service": True, "powered": STATE["bt_powered"], "scanning": False,
            "pairing": BT["pairing"], "prompt": BT["prompt"], "blocked": False, "devices": bt_devices()}
STATE = {"running": ["youtube"], "radio": S.RADIO_NOW, "tv": None, "favs": list(S.RADIO_FAVS), "tvfavs": list(S.TV_FAVS),
         "volume": dict(S.SETTINGS["volume"]), "bt_powered": True, "update": {"available": True, "version": "0.13.0"}}
STATIONS = [{"name": f"Testsender {i}", "url": f"https://example.invalid/s{i}", "favicon": ""} for i in range(1, 15)]
ROMS = [{"title": n, "name": n, "filename": n.lower().replace(" ", "-") + ".gba", "size": "8 MB"} for n in
        ("Advance Wars", "Golden Sun", "Metroid Fusion", "Pokémon Smaragd", "Mario Kart", "Zelda Minish Cap", "F-Zero")]


TILES = json.loads(json.dumps(S.TILES))
TILES["groups"].insert(1, {"name": "Spiele", "tiles": [
    {"id": "gba", "label": "Game Boy Advance", "sub": "mGBA", "size": "wide", "color": "#2d3763", "icon": "handheld", "cmd": ["mgba-qt"]}]})


JOB = {}
# Player (--player): Teststream, zuletzt gesehen, Mediathek ueber den echten Launcher-Code (MediaLib) in --home
PLAYER = {"stream": "av://lavfi:testsrc2=size=1280x720:rate=25", "recent": [], "media": None, "tmp": None}


def media():
    """MediaLib aus launcher.py mit HOME = --home; Weiterschauen und Vorschaubilder in einem Wegwerf-Ordner."""
    if PLAYER["media"] is None:
        import tempfile
        sys.path.insert(0, str(REPO / "launcher"))
        import launcher as L  # noqa: E402
        tmp = Path(tempfile.mkdtemp(prefix="vs-preview-"))
        L.RESUME = tmp / "resume.json"
        L.MediaLib.THUMBS = tmp / "thumbs"
        L.CoverFetcher.CACHE = tmp / "covers"                   # Cover-Suche: Zwischenspeicher im Wegwerf-Ordner,
        L.CoverFetcher.MISSES = tmp / "covers" / "misses.json"  # Schalter nur im Speicher (VS_MB_URL/VS_CAA_URL: Testserver)
        L.CoverFetcher.auto = staticmethod(lambda: PLAYER.get("covers_auto", True))
        L.SETTINGS = tmp / "settings.json"                     # Einstellungen (Musik suchen) nicht ins Repo schreiben
        PLAYER["L"] = L
        PLAYER["media"], PLAYER["tmp"] = L.MediaLib(), tmp
    return PLAYER["media"]


def media_list(q):
    try:
        return media().listdir(q.get("path", [""])[0])
    except (ValueError, OSError) as e:
        return {"error": str(e)}
# VS_TVDATA=<Ordner mit channels.json, streams.json, logos.json von iptv-org>: echte Senderliste statt Beispieldaten
TVREAL = {}


def tv_list(q):
    d = os.environ.get("VS_TVDATA")
    if not d:
        return S.tv_list(q)
    if "index" not in TVREAL:
        sys.path.insert(0, str(REPO / "launcher"))
        import launcher as L  # noqa: E402
        rd = lambda n: json.loads((Path(d) / n).read_text(encoding="utf-8")) if (Path(d) / n).exists() else []
        TVREAL["L"] = L
        TVREAL["index"] = L.IPTV.build_index(rd("channels.json"), rd("streams.json"), rd("logos.json"))[0]
    g = lambda k: q.get(k, [""])[0]
    num = lambda k, dflt: int(g(k)) if g(k).isdigit() else dflt
    return TVREAL["L"].IPTV.page_of(TVREAL["index"], g("q"), g("country"), g("cat"), g("letter").upper(), num("offset", 0), num("limit", 200))


def job():
    if JOB.get("state") == "running":
        JOB["n"] = JOB.get("n", 0) + 1
        JOB["log"].append(f"Schritt {JOB['n']} …")
        if JOB["n"] >= 4:
            JOB["state"] = "done"
    return JOB


def settings():
    return dict(S.SETTINGS, volume=STATE["volume"], version={"version": "0.12.1", "build": "abc123"}, ssh=True, live=LIVE["on"],
                standby=not LIVE["on"],
                sysupd_days=90, sysupd_choices=[30, 60, 90], frontend=STATE.get("frontend", "qt"), frontends=["qt", "web"],
                padmouse=STATE.get("padmouse", True))


# Installer (--live): Geraet wie im Web-Installer (DEMO_PROBE), Installation laeuft simuliert in ~20 s durch
GiB = 1024 ** 3
PROBE = {"uefi": True, "secureboot": False, "arch": "x86_64", "ram": 3.7 * GiB, "cpu": "Intel Core i3-6100T", "gpu": ["Intel HD Graphics 530"],
         "net": "lan", "screen": {"mode": "1280x720", "rate": 60}, "favs": {"radio": 2, "tv": 1}, "wifi_saved": ["Zuhause-5G"],
         "windows": False, "lang": "de", "users": [],
         "disks": [
             {"path": "/dev/sda", "size": 128e9, "model": "Samsung SSD MZ7TE128", "tran": "sata", "label": "gpt", "esp": "/dev/sda1",
              "systems": ["Ubuntu 24.04 LTS"],
              "parts": [{"path": "/dev/sda1", "start": 2048, "sectors": 1048576, "size": 536870912, "fstype": "vfat", "role": "esp"},
                        {"path": "/dev/sda2", "start": 1050624, "sectors": 243000000, "size": 124416000000, "fstype": "ext4", "role": "os",
                         "os": "Ubuntu 24.04 LTS"},
                        {"path": "/dev/sda3", "start": 244050624, "sectors": 4000000, "size": 2048000000, "fstype": "swap", "role": "swap"}],
              "free": [], "options": {"whole": True, "beside": [{"part": "/dev/sda2", "os": "Ubuntu 24.04 LTS", "fstype": "ext4",
                                                               "size": 124416000000, "used": 41e9, "min": 40e9, "max_new": 78e9,
                                                               "default": 59 * GiB}]}},
             {"path": "/dev/nvme0n1", "size": 500e9, "model": "Crucial P3", "tran": "nvme", "label": "gpt", "esp": "/dev/nvme0n1p1",
              "systems": ["FreeBSD"],
              "parts": [{"path": "/dev/nvme0n1p1", "start": 2048, "sectors": 532480, "size": 272629760, "fstype": "vfat", "role": "esp"},
                        {"path": "/dev/nvme0n1p2", "start": 534528, "sectors": 777000000, "size": 397824000000, "fstype": "zfs_member",
                         "role": "os", "os": "FreeBSD", "locked": True}],
              "free": [{"start": 777534528, "sectors": 199000000, "bytes": 101888000000}],
              "options": {"whole": True, "free": [{"start": 777534528, "sectors": 199000000, "bytes": 101888000000}]}}]}
INST = {"state": "idle"}
LIVE = {"on": False, "fail": False}


def inst_status():
    st = INST
    if st.get("state") == "running":
        t = time.time() - st["t0"]
        order = ["check", "partition", "format", "copy", "configure", "boot", "cleanup"]
        dur = [1, 1, 1, 10, 3, 2, 1]
        acc, cur = 0, None
        for ph, d in zip(order, dur):
            if t >= acc + d:
                st["phases"][ph] = "done"
            elif cur is None:
                st["phases"][ph] = "running"
                cur = ph
                st["phase"], st["phase_pct"] = ph, (t - acc) / d * 100
                if ph == "copy":
                    st["copy"] = {"done": 1.4e9 * (t - acc) / d, "total": 1.4e9, "eta": int((d - (t - acc)) * 20)}
                if LIVE["fail"] and ph == "boot":
                    st.update(state="error", error={"phase": "boot", "code": "efi_nvram", "msg": "efibootmgr: Could not prepare Boot variable",
                                                    "done": [p for p in order if st["phases"].get(p) == "done"], "alt": True})
                    st["phases"][ph] = "error"
                    return st
            acc += d
        st["pct"] = min(100, t / sum(dur) * 100)
        if cur is None:
            st.update(state="done", pct=100, result={"user": st["cfg"]["user"]["name"], "login": st["cfg"]["user"]["login"],
                                                    "hostname": st["cfg"]["hostname"], "seconds": int(t)})
    return st


class H(S.H):
    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        st = STATE
        routes = {
            "/tiles.json": lambda: TILES,
            "/api/status": lambda: {"running": st["running"], "starting": [], "radio": st["radio"], "tv": st["tv"],
                                    "update": st["update"] if not LIVE["on"] else {"available": False}, "live": LIVE["on"]},
            "/api/front": lambda: {"id": st["running"][0] if st["running"] else None, "mouse": True,
                                   "padmouse": STATE.get("padmouse", True)},
            "/api/volume": lambda: st["volume"],
            "/api/settings": settings,
            "/api/radio/favs": lambda: st["favs"],
            "/api/radio/search": lambda: STATIONS,
            "/api/tv/status": lambda: {"state": "ready", "error": None, "count": 10432, "countries": S.COUNTRIES, "now": st["tv"]},
            "/api/tv/favs": lambda: st["tvfavs"],
            "/api/tv/search": lambda: [c for c in S.TV if not q.get("cat", [""])[0] or q["cat"][0] in c["cats"]],
            "/api/tv/list": lambda: tv_list(q),
            "/api/tv/epg": lambda: {"current": {"title": "Tagesschau", "start": "20:00", "stop": "20:15", "progress": 60},
                                    "next": {"title": "Wetter"}},
            "/api/apps": S.apps,
            "/api/apps/job": job,
            "/api/updates": lambda: {"local": "0.12.1", "remote": "0.13.0", "available": True, "any": True, "channel": "stable",
                                     "channel_label": "Stable", "changes": [{"version": "0.13.0", "changes": ["Neue Qt-Startseite"],
                                                                              "changes_en": ["New Qt start page"]}],
                                     "system": {"count": 12, "pkgs": ["linux6.18", "mesa"], "kernel": "6.18.45_1", "flatpak": 0,
                                                "appimage": [], "proton": None, "checked": True, "due": False, "due_at": 0},
                                     "reboot": {}},
            "/api/bluetooth/status": bt_status,
            "/api/wifi/scan": lambda: [{"ssid": "FRITZ!Box 7530", "signal": 72, "secure": True, "active": True},
                                       {"ssid": "Nachbar", "signal": 31, "secure": True, "active": False}],
            "/api/roms": lambda: {"system": q.get("system", ["gba"])[0], "count": len(ROMS), "roms": ROMS},
            "/api/install/probe": lambda: PROBE,
            "/api/install/status": lambda: dict(inst_status(), autostart=LIVE["on"] and INST.get("state") == "idle" and not INST.get("seen")),
            "/api/install/gparted": lambda: {"running": False},
            "/api/install/log": lambda: {"log": "[check] ok\n[partition] sgdisk …\n[boot] efibootmgr: Could not prepare Boot variable"},
            "/api/tv/zap": lambda: {"items": S.TV, "favs": st["tvfavs"], "recent": PLAYER["recent"], "key": (st["tv"] or {}).get("key")},
            "/api/media/roots": lambda: media().roots(),
            "/api/media/list": lambda: media_list(q),
            "/api/media/nextfolder": lambda: media().next_folder(q.get("path", [""])[0]) or {},
            "/api/media/covers": lambda: (media(), PLAYER["L"].COVERS.status())[1],
            "/api/dl/settings": lambda: (media(), PLAYER["L"].MUSICDL.payload())[1],
            "/api/dl/status": lambda: (media(), PLAYER["L"].MUSICDL.status())[1],
        }
        if p == "/api/media/thumb":
            art = q.get("art", [""])[0]
            r = media().art(art) if art else media().thumb(q.get("path", [""])[0])
            if not r:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", r[1])
            self.send_header("Content-Length", str(len(r[0])))
            self.end_headers()
            self.wfile.write(r[0])
            return
        if p in routes:
            return self.j(routes[p]())
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        st = STATE
        if p.startswith("/api/volume/"):
            a = p.rsplit("/", 1)[1]
            v = st["volume"]
            v["level"] = max(0, min(100, v["level"] + (5 if a == "up" else -5 if a == "down" else 0)))
            if a == "mute":
                v["muted"] = not v.get("muted")
            return self.j(v)
        if p == "/api/radio/play":
            st["radio"] = {"station": body, "title": None}
            return self.j(st["radio"])
        if p == "/api/radio/stop":
            st["radio"] = {}
            return self.j({})
        if p in ("/api/radio/fav", "/api/radio/unfav"):
            st["favs"] = [f for f in st["favs"] if f["url"] != body.get("url")] + ([body] if p.endswith("/fav") else [])
            return self.j(st["favs"])
        if p == "/api/tv/play":
            ch = next((c for c in S.TV if c["key"] == body.get("key")), None)
            st["tv"] = ch
            return self.j({"now": ch})
        if p == "/api/tv/tune":                  # Player: Teststream; Sender mit "Fehler" im Namen scheitern
            ch = next((c for c in S.TV if c["key"] == body.get("key")), None) or S.TV[0]
            st["tv"] = ch
            PLAYER["recent"] = [ch] + [r for r in PLAYER["recent"] if r["key"] != ch["key"]][:14]
            url = "https://example.invalid/fehler.m3u8" if "Fehler" in ch["name"] else PLAYER["stream"]
            return self.j({"entry": ch, "url": url, "ref": "", "ua": "", "recent": PLAYER["recent"]})
        if p in ("/api/tv/fav", "/api/tv/unfav"):
            ch = next((c for c in S.TV if c["key"] == body.get("key")), None)
            st["tvfavs"] = [f for f in st["tvfavs"] if f["key"] != body.get("key")] + ([ch] if ch and p.endswith("/fav") else [])
            return self.j(st["tvfavs"])
        if p.startswith("/api/dl/"):                # Musik suchen: echter Launcher-Code (VS_IA_URL/VS_ITUNES_URL/VS_YTDLP: Testserver)
            media()
            D = PLAYER["L"].MUSICDL
            try:
                if p == "/api/dl/settings":
                    return self.j(D.save_settings(body.get("sources")))
                if p == "/api/dl/search":
                    return self.j(D.search(body.get("q")))
                if p == "/api/dl/get":
                    return self.j(D.get(body.get("key")))
            except ValueError as e:
                self.send_response(404); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode()); return
        if p == "/api/media/covers/scan":
            media()
            L = PLAYER["L"]
            L.COVERS.scan(Path(os.environ["HOME"]) / "share" / "Musik")
            return self.j(L.COVERS.status())
        if p == "/api/media/covers/auto":
            media()
            PLAYER["covers_auto"] = bool(body.get("on"))
            return self.j(PLAYER["L"].COVERS.status())
        if p == "/api/media/resume":
            media().resume_set(body.get("path", ""), body.get("pos"), body.get("dur"))
            return self.j({"ok": True})
        if p in ("/api/apps/install", "/api/apps/remove", "/api/apps/update"):
            JOB.clear()
            JOB.update({"state": "running", "action": p.rsplit("/", 1)[1], "name": body.get("id", ""), "app": body.get("id"),
                        "log": ["xbps-install -Sy …"], "n": 0})
            return self.j(JOB)
        if p == "/api/install/start":
            INST.clear()
            INST.update({"state": "running", "pct": 0, "phases": {}, "mode": body["config"]["mode"], "t0": time.time(), "cfg": body["config"]})
            print("Installer-Konfiguration:", json.dumps(body["config"], ensure_ascii=False), flush=True)
            return self.j(inst_status())
        if p == "/api/install/retry":
            LIVE["fail"] = False
            INST.update(state="running", error=None, t0=time.time() - 15)
            return self.j(inst_status())
        if p in ("/api/install/keymap", "/api/install/gparted"):
            return self.j({"keymap": body.get("keymap"), "running": True})
        if p == "/api/install/savelog":
            return self.j({"ok": False, "code": "no_usb"})
        if p == "/api/bluetooth/rename":         # eigener Name (leer = Geraetename)
            BT["names"][body.get("mac", "")] = " ".join(str(body.get("name", "")).split())[:40]
            return self.j({"ok": True, "status": bt_status()})
        if p == "/api/bluetooth/pair":           # Koppeln: Tastatur-Code 3 s anzeigen, dann je nach Geraet Erfolg/Fehler
            BT.update(pairing=body.get("mac"), prompt={"mac": body.get("mac"), "code": "482913"})
            time.sleep(3)
            BT.update(pairing=None, prompt=None)
            ok = not body.get("mac", "").endswith("01")
            return self.j({"ok": ok, "error": None if ok else "bt.err.timeout", "status": {}})
        if p.startswith("/api/launch/"):
            tid = p.rsplit("/", 1)[1]
            if tid not in st["running"]:
                st["running"].append(tid)
            return self.j({"running": st["running"]})
        if p.startswith("/api/close/"):
            tid = p.rsplit("/", 1)[1]
            st["running"] = [t for t in st["running"] if t != tid]
            return self.j({"running": st["running"]})
        if p.startswith("/api/settings/") or p in ("/api/audio/output", "/api/wifi/connect"):
            if p.endswith("/theme"):
                S.SETTINGS["theme"] = body.get("theme")
            if p.endswith("/scale"):
                S.SETTINGS["scale"] = body.get("scale")
            if p.endswith("/lang"):
                S.SETTINGS["lang"] = body.get("lang")
                return self.j({"lang": body.get("lang")})
            if p.endswith("/padmouse"):
                STATE["padmouse"] = bool(body.get("on"))
            if p.endswith("/frontend"):
                STATE["frontend"] = body.get("frontend")
            return self.j(settings())
        return self.j({})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--shot")
    ap.add_argument("--keys", default="")
    ap.add_argument("--theme")
    ap.add_argument("--live", action="store_true", help="Live-System mit Installer-Kachel")
    ap.add_argument("--fail", action="store_true", help="Installation scheitert beim Startmanager (Fehlerseite)")
    ap.add_argument("--bios", action="store_true", help="Geraet im BIOS-Modus")
    ap.add_argument("--clean", action="store_true", help="fuer Screenshots: kein Update-Hinweis, keine laufende App")
    ap.add_argument("--scale", type=float, help="Skalierung der Oberflaeche (Standard 1.25)")
    ap.add_argument("--player", choices=["tv", "media"], help="Player statt Startseite: Fernsehen bzw. Videos & Musik")
    ap.add_argument("--stream", help="Stream/Datei fuer den Fernseh-Player (Standard: Testbild von mpv)")
    ap.add_argument("--home", help="Ordner, der fuer die Mediathek als Home gilt (darin share/Videos, share/Musik)")
    ap.add_argument("--arg", default="", help="Startargument des Players (Sender bzw. Datei/Ordner)")
    a = ap.parse_args()
    if a.stream:
        PLAYER["stream"] = a.stream
    if a.home:
        os.environ["HOME"] = str(Path(a.home).resolve())
    if a.clean:
        STATE["running"] = []
        STATE["update"] = {"available": False}
    if a.scale:
        S.SETTINGS["scale"] = a.scale
    if a.theme:
        S.SETTINGS["theme"] = a.theme
    if a.live:
        LIVE["on"] = True
        TILES["groups"].insert(0, {"name": {"de": "Installieren", "en": "Install"}, "tiles": [{
            "id": "install", "type": "install", "size": "large", "color": "#2f6d4f", "icon": "install",
            "label": {"de": "VoidStation installieren", "en": "Install VoidStation"}, "sub": {"de": "auf diesen PC", "en": "on this PC"}}]})
        TILES["user"] = {"de": "Gast", "en": "Guest"}
    LIVE["fail"] = a.fail
    if a.bios:
        PROBE["uefi"] = False
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, VS_API=f"http://127.0.0.1:{PORT}", VS_SIZE=a.size, VS_DEMO="1")
    if a.shot or a.keys:
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env.setdefault("QT_QUICK_BACKEND", "software")
        env["VS_KEYS"] = a.keys
        if a.shot:
            env["VS_SCREENSHOT"] = a.shot
    t0 = time.monotonic()
    if a.player:
        prog = [sys.executable, str(REPO / "launcher" / "qt" / "voidstation-player.py"), "--" + a.player]
        prog += [a.arg or (S.TV[0]["key"] if a.player == "tv" else "")]
        env["VS_BASE"] = str(PLAYER["tmp"] or Path("/tmp"))      # Steuer-Socket nicht im Repo
        if a.shot or a.keys:
            env.pop("QT_QPA_PLATFORM", None) if os.environ.get("DISPLAY") else None
            env.pop("QT_QUICK_BACKEND", None)
        r = subprocess.run([x for x in prog if x != ""], env=env)
    else:
        r = subprocess.run([sys.executable, str(REPO / "launcher" / "qt" / "voidstation-home.py")], env=env)
    print(f"beendet nach {time.monotonic() - t0:.1f} s, Code {r.returncode}")
    srv.shutdown()


if __name__ == "__main__":
    main()
