<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# VoidStation Architecture Map

Kompakte Architektur-Referenz für Entwicklungs-Sessions. Zielsystem: Void Linux (runit, XLibre, Openbox, PipeWire, Qt 6/PySide6).

---

## 1. Systemübersicht & Datenfluss

### Boot- & Sitzungskette
```text
Boot (EFISTUB / GRUB + Plymouth)
  → tty1 Autologin (~/.bash_profile, XDG_RUNTIME_DIR=/tmp/voidstation-runtime-$UID)
  → launcher/xstart (XLibre; 2. Fehlstart: voidstation-pkg xserver repair; 4.: Rettungs-Bash)
  → ~/.xinitrc (dbus-run-session openbox-session)
  → openbox/autostart:
      ├─ env.sh / im.sh / xrdb ~/.Xresources / unclutter
      ├─ launcher-start.py → launcher.py (Backend-HTTP-API auf 127.0.0.1:8765)
      ├─ home.sh → qt/voidstation-home.py (Qt 6/QML Vollbild-UI, Neustart-Backoff)
      └─ pipewire (+ wireplumber, pipewire-pulse nur falls nicht via /etc/pipewire/pipewire.conf.d)
```

> **Hinweis zu `launcher/web/`:** Die frühere Web-UI (WebKitGTK/`voidstation-shell.py`/`web/index.html`) wurde in **2026.12 entfernt**. Es gibt keinen Web-Fallback mehr. `launcher/web/` enthält ausschließlich gemeinsame Assets (`i18n/*.json`, `themes/*.css`, `logo.png`), die von Qt-UI, Player, Launcher und `vsctl` genutzt werden.

### Laufzeit-Datenfluss
```text
┌─────────────────────────── UI-Prozesse (Qt 6 / QML) ───────────────────────────┐
│ voidstation-home.py (Main.qml)          voidstation-player.py (Player.qml)     │
│  • Kacheln, Ebenen, Installer, OSK       • Modi: --tv | --media | --yt         │
│  • Gamepad (evdev) + PadMouse (uinput)   • Video: libmpv GL (Stufe 0/1)        │
│  • KbdOverlay (XTest via vsx11)            oder mpv IPC-Fenster (Stufe 2/i686) │
└───────────────────┬───────────────────────────────────────┬────────────────────┘
        VS/Api.qml (HTTP + X-TV: 1)              Unix-Socket player-<mode>.sock
                    ▼                                       ▲
┌──────────────────── Backend: launcher/launcher.py (127.0.0.1:8765) ────────────┐
│ ThreadingHTTPServer (Host-Check; POST erfordert Header "X-TV: 1"; OPTIONS 403) │
│ AppManager · PlayerManager · Radio (mpv.sock) · IPTV/EPG (SQLite) · MediaLib   │
│ CoverFetcher · MusicDL · YtLight · ROMManager/Emulatoren/CHD · AppCenter/Jobs  │
│ Settings/DisplayRate/AudioWatch · Bluetooth (BlueZ D-Bus) · Vpn · Installer    │
│ OskField (Long-Poll /api/osk/wait) · gamepad_watcher (Guide=Home, Start+Sel=SS)│
└───┬───────────────────────────┬──────────────────────────────┬─────────────────┘
    │                           │                              │
    ▼                           ▼                              ▼
Browser-OSK-Brücke         System / Prozesse              Nutzer- & Systemdaten
firefox/keyboard/*.js      • vsx11.py (libX11/XTest)      • ~/.local/share/voidstation/
(XPI + CRX3 via /ext/*)    • PipeWire (wpctl, pactl)      • ~/.config/voidstation/
  POST /api/osk/field →    • NetworkManager (nmcli)       • ~/share/ (Samba [share])
  OskField → FieldWatch    • BlueZ (D-Bus), XRandR        • ~/.cache/voidstation/
  → KbdOverlay → XTest     • sudo -n Root-Helfer          • /usr/local/share/voidstation/
```

---

## 2. Modul- & Verzeichnis-Map

### Backend & Laufzeit-Skripte (`launcher/`)
| Pfad | Verantwortlichkeit |
|---|---|
| `launcher.py` (~16,6k Z.) | Zentraler HTTP-Dienst (`127.0.0.1:8765`) & gesamte Geschäftslogik: App-Lifecycle (`AppManager`), `PlayerManager`, `Radio`, `IPTV`/`EPGManager`, `MediaLib`/`DvdDrive`/`CoverFetcher`/`MusicDL`, `YtLight`, `ROMManager`/Emulator-Konfig/Keymap/`SaveBackup`/`RomCovers`/`ChdConvert`, `Jobs` (AppCenter & Updates), `DisplayRate`, `AudioWatch`, `BluetoothManager`, `Vpn`, `Installer`, `OskField`, `PerfMode`, Screenshots, `gamepad_watcher`. |
| `launcher-start.py` | Entrypoint: setzt `mallopt(M_ARENA_MAX)` und importiert `launcher` (nutzt `__pycache__` mit checked-hash). |
| `vsx11.py` | `libX11`/`libXtst` via `ctypes` (Fallback `wmctrl`/`xprop`/`xdotool`): EWMH-Fenstersteuerung, Key-Grab für heiße Ecken, XTest-Tippen (`_Typer`), schneller X11-Screenshot (`grab_screen`). |
| `tvindex.py` | Baut SQLite-Senderindex (`tv.sqlite`) aus iptv-org-JSONs in kurzem Subprozess (schont Launcher-RAM). |
| `discid.py` | Liest PlayStation-Seriennummer/CRC aus ISO/BIN/CUE/CHD (`/dev/sr0` oder Dateien) für Per-Game-Settings. |
| `gameprofiles.py` + `gamedb/*.csv` | Auto-Spielprofile (PSX Texturfilter/FXAA, DOSBox CPU-Tempo); Nutzerwerte haben immer Vorrang. |
| `vsreport.py` | Erzeugt bereinigte Fehlerberichte (scrubbt Passwörter, SSIDs, MAC-Hälften, globale IPs, Home-Pfad) nach `~/share/vs-reports/`. |
| `crxpack.py` | Packt `firefox/keyboard/` als signierte CRX3 + `keyboard.xml` + Managed-Policies für Chromium/Brave (ausgeliefert unter `/ext/*`). |
| `tiles.json` / `catalog.json` | Standard-Startkacheln (Benutzerdatei) / Kuratierter AppCenter-Katalog (Quelle für `allowed-packages`). |
| `xstart` / `home.sh` | XLibre-Start mit Auto-Repair/Rettungskonsole / Watchdog-Schleife für `qt/voidstation-home.py`. |
| `vsctl` / `vsshot` | CLI-Steuerung (`home`, `launch`, `status`, `update`, `version`, `channel`, `report`) / Screenshot-CLI (`F12`, `Start+Select`). |
| `sysfix.sh` | Idempotente Root-Systemkonfiguration (aufgerufen von `install.sh` & `update.sh`): `voidstation-elogind`, TTY3–6 aus, zram-Hook, WLAN-Regdom/Powersave, GRUB `quiet`, BlueZ, Controller-udev (`hidraw`/`uinput`), xdg-desktop-portal GTK, USB-Wakeup/Suspend, `/etc/os-release`, Shell/fastfetch/nano, `voidstation-tune`. |
| `shaders/` | Kuratierte Emulator-Shader (`mgba/`, etc.) + generierte Vorschau-JPGs (`previews/<emu>/`). |

### Qt/QML-Oberfläche (`launcher/qt/`)
| Pfad | Verantwortlichkeit |
|---|---|
| `voidstation-home.py` | PySide6-Host der Startseite: `Vs(VsBase)`, `PadMouse` (virtuelle Maus `/dev/uinput`, R3 Toggle, L2/L3 OSK), `FieldWatch` (Long-Poll `/api/osk/wait`), heiße Ecken, XTest-OSK-Bridge. |
| `voidstation-player.py` | PySide6-Host für `--tv`, `--media`, `--yt`: `EmbeddedEngine`+`Video` (libmpv OpenGL, Stufe 0 EGL / Stufe 1 GLX), `IpcEngine` (mpv-Fenster, Stufe 2 / `i686`), Unix-Socket-Server `player-<mode>.sock`. |
| `vscommon.py` + `icons.py` | Gemeinsame Basis: CSS-Theme-Parser (`theme_tokens`), `Gamepad` (evdev + `pads.json`), `PadPump`, Controller-Glyph-SVGs (Xbox/PS/Nintendo), `VsBase` (HTTP-Threads, i18n-Fallback, Tastatur-Erkennung, QML-Cache-Invalidierung). |
| `qml/Main.qml` | Startseiten-Root, Skalierungs-Layout (`Ui.f`, `Ui.u`), Fokus-/Layer-Stack (`layerOrder`), Polling. |
| `qml/*Layer.qml`, `*Dialog.qml`, `Osk.qml`, `KbdOverlay.qml`, `Corner.qml`, `MusicCorner.qml`, `UpdateScreen.qml`, `ChdCard.qml` | Vollbild-Ebenen & Overlays: `RadioLayer`, `TvLayer`, `RomsLayer`, `EmuOptsLayer`, `KeymapLayer`, `AppsLayer`, `SettingsLayer`, `VpnLayer` (`VpnMap` + `vpn/worldmap.json`), `InstallLayer` (`DiskBar`/`IPanel`/`ITile`), Dialoge, On-Screen-Keyboard, heiße Ecken. |
| `qml/VS/` | Wiederverwendbares Design-System (`qmldir`): Singletons `Ui`, `Nav`, `Api`; Widgets (`Focusable`, `Tile`, `HomeTile`, `TileGrid`, `Track`, `Layer`, `Group`, `Pill`, `Btn`, `Field`, `KeyPad`, `VolBar`, `Glyph`, `OskLayouts.js`, `Hangul.js`, …). |
| `qml/Player.qml` + `qml/player/` | Player-UI: `TvView`, `MediaView`, `YtView`, `DownloadView`, `ChannelPanel`, `Bar`, `MouseBar`, `TrackMenu`, `TechInfo`, `VolumeOsd`, `Hints`. |

### Desktop, Browser, Shell & Assets (`launcher/{web,openbox,firefox,shell}/`)
| Pfad | Verantwortlichkeit |
|---|---|
| `launcher/web/` | `i18n/*.json` (34 Sprachen), `themes/*.css` (`default-dark`, `default-light`, `high-contrast`, `nord`), `logo.png`. **Kein HTML/Web-Frontend.** |
| `launcher/openbox/` | `autostart`, `rc.xml` (rahmenlos maximiert, Theme `VoidStation`, Hotkeys `Super`/`XF86HomePage` → `vsctl home`, `F12` → `vsshot`, `A-F4`, `C-A-t`, Lautstärke via `wpctl`), `menu.xml`. |
| `launcher/firefox/` | `policies.json` (`/etc/firefox/policies/`, erzwingt uBlock Origin, sperrt FX OSK), `user-common.js`, `user-youtube.js`, `keyboard/` (`focus.js` + `background.js`, MV2 für Firefox/LibreWolf & MV3 `manifest.chromium.json` für Chromium/Brave). |
| `launcher/shell/` | `bashrc.sh` (`/etc/bash/bashrc.d/voidstation.sh`, History, Prompt, `vsctl`-Completion), `fastfetch.jsonc`, `fastfetch-logo.ansi`. |

### Root-Helfer (`launcher/voidstation-*` → installiert unter `/usr/local/sbin/`)
| Skript | Aufgabe |
|---|---|
| `voidstation-pkg` | Einziger `sudo -n`-Allzweck-Helfer im installierten System: `install`/`remove`/`markauto` (nur `allowed-packages`), `sync`/`update`/`check`, `mirror`, `selfupdate` (HTTPS + SSH-Signaturprüfung), `netmode`, `repo` (`repo.voidstation.de`), `xserver`, `ssh`, `bluetooth`, `suspend`, `gpu32`, `kernelpurge`, `syslog`, `perf`, `mullvad`, `channel`. |
| `voidstation-installer` | Nur im Live-System (`iso/sudoers-installer`): `probe`, `run` (`check→shrink→partition→format→copy→configure→boot→cleanup`), `--resume`, `gparted`, `savelog`, `status`, `log`, `text`. |
| `voidstation-efistub` | Kernel-Hook: kopiert neuesten Kernel/Initramfs unter festen Namen auf ESP, verwaltet EFISTUB-Eintrag mit GRUB-Fallback. |
| `voidstation-splash` | Richtet Plymouth-Theme (`iso/art/plymouth`) + `dracut-voidstation.conf` + Boot-Quit ein. |
| `voidstation-zram` | Auto-zram bei < 8 GB RAM (`93-voidstation-zram.sh`), manuell `on`/`off`/`status`. |
| `voidstation-tune` | Kernel/System-Feintuning: PipeWire RT-Limits, `earlyoom`, `PREEMPT_DYNAMIC=full`, wöchentliches `fstrim`, CPU-Governor `perf on|off`. |
| `voidstation-mullvad` | Install/Update/Remove/Status für Paket `mullvad-vpn` aus `repo.voidstation.de` (ohne Electron-GUI). |
| `voidstation-issue` | Schreibt ASCII-Logo + Version nach `/etc/issue` (normal oder `--live`). |

### Build-, Update-, ISO- & Release-Pipeline
| Pfad | Verantwortlichkeit |
|---|---|
| `build.sh` | Packt deterministisches `payload.tgz` (`--mtime='2026-01-01'`), prüft i18n (`de`↔`en`↔`LANG_TABLE`↔32 Extras) und `CHANGELOG*.md`, erzeugt `dist/{install.sh,update.sh,build-iso.sh,version.json,version.txt}` (unsigniert). |
| `install-head.sh` / `update-head.sh` | Selbstentpackende Skript-Header (`__PAYLOAD_BELOW__`); `update-head.sh` schützt Nutzerdaten und führt einmalige Migrationen mit Stamp-Dateien unter `/usr/local/share/voidstation/` aus. |
| `update-url` / `keys/` | HTTPS-Update-Template (`.../{channel}/dist`) / Public Keys `voidstation-release.pub` (+ optional `voidstation-notfall.pub`). |
| `iso/` | Live-ISO-Bau (`build-iso-head.sh`, `postsetup.sh`, `99-voidstation-live.sh`, `grub-entries.py`, `sudoers-installer`, `art/{grub,isolinux,plymouth}`). |
| `dist/` | Generierte & signierte Artefakte (`install.sh[.sig]`, `update.sh[.sig]`, `build-iso.sh`, `version.{json,txt}`). **Nur von `tools/publish.sh` pflegen.** |
| `tools/` | `publish.sh` (`vspub`: bauen, signieren, Testing/Release-Train/Hotfix/ISO), `check.sh` (CI-Checks), `qt-preview.py` + `sampledata.py` + `yt-dlp-mock.py`, `qt-screenshots.py`, `gamedb-check.py`, `changelog.py`, `mkbundle.sh`, `vsget.sh`, `build-site.py`, `boot-art.py`, `look-previews.py`, `vpn-map.py`, `gh-release.py`. |
| `.github/workflows/` | `checks.yml` (`tools/check.sh` + PR-Sperre für `dist/` & `keys/`), `release.yml` (Tags/GitHub-Releases bei Push auf `stable`), `pages.yml` (`voidstation.de` aus `site/`). |

### Laufzeit-Dateipfade (Nutzer vs. System)
- **User-App & Zustand (`~/.local/share/voidstation/`):** Entpackter Code + erhaltene Nutzerdateien `tiles.json`, `settings.json`, `radio.json`, `tvfavs.json`; Laufzeitdaten `tvrecent.json`, `resume.json`, `yt-{subs,history,later}.json`, `vpn.json`, `chd.json`, `emu-defaults.json`, `emu-own.ini`, `sysupdate.json`, `paused.json`, `env.sh`, `im.sh`, `VERSION`, `version.json`, `profiles/*`, `apps/*`, `logs/*`, Sockets `mpv.sock`, `player-*.sock`.
- **User-Overrides (`~/.config/voidstation/`):** `pads.json` (Controller-Mapping/Stil), `emu-pads.json` (Emulator-Keymaps), `emu-games.json` (Per-Game-Optionen), `vkBasalt.conf`.
- **Samba-Freigabe (`~/share/`):** `ROMs/<system>` (+ `/bios`), `Musik`, `Videos`, `Bilder`, `Screenshots`, `Spielstand-Backups`, `vs-reports`.
- **Caches (`~/.cache/voidstation/`):** `thumbs/`, `covers/`, `yt/`, `disc-ids.json`, `tv.sqlite` (unter `cache/`).
- **Root-Vertrauensanker (`/usr/local/share/voidstation/`):** `allowed-packages`, `allowed_signers`, `update-url`, `channel`, `testing-optin`, `keyboard.xpi`, `chromium/keyboard.{crx,xml,key,json}`, `dracut-voidstation.conf`, Migrations-Stamps (`vlc-removed`, `zram-on`, …).

---

## 3. Verbindliche Projekt-Konventionen

1. **i18n-Pflicht (`build.sh`-Gate):**
   - Jeder neue UI-Text gehört **immer** in `launcher/web/i18n/de.json` **und** `en.json` mit identischen `{platzhaltern}` (`build.sh` bricht sonst ab).
   - Weitere 32 Sprachen dürfen unvollständig sein (Fallback `lang → en → de`), aber **keine unbekannten Schlüssel** enthalten (Ausnahme: `labels` und `region.XX`) und müssen dieselben `{platzhalter}` nutzen.
   - Dateinamen in `launcher/web/i18n/*.json` müssen 1:1 mit `LANG_TABLE` in `launcher/launcher.py` übereinstimmen (neue Sprache zusätzlich in `install-head.sh` Locales und `voidstation-installer` `LOCALES`).
   - Im QML immer `Ui.t("key", {vars})` bzw. `Ui.l(label)` verwenden; Tastatur-/Pad-Hinweise als `<b>…</b>` für automatische Controller-Glyph-Ersetzung (`Ui.keys()`).
2. **Themes (`launcher/web/themes/*.css`):**
   - Reine CSS-Variablen in `:root { --token-name: #hex|rgba(...); }` (Basis `default-dark.css`).
   - `vscommon.theme_tokens()` wandelt `--foo-bar` in `Ui.c.fooBar` um und leitet `light`, `tileText`, `tileSub`, `pillOnText` ab; `launcher.py` synchronisiert GTK/Openbox/xterm/Firefox anhand von `theme_is_dark()`.
3. **Nutzer-Overrides & Update-Sicherheit:**
   - `update-head.sh` bewahrt `tiles.json`, `radio.json`, `tvfavs.json`, `settings.json` und berührt `~/.config/voidstation/*` sowie `~/share/*` nicht.
   - Kachel-Optionen in `tiles.json` überschreiben `catalog.json`-Defaults (`mouse`, `maximize`, `perf`, `start_hint`).
   - Einmalige Migrationen in `update-head.sh` über Stamp-Dateien in `/usr/local/share/voidstation/` absichern.
   - Wegen festem `tar --mtime='2026-01-01'` nutzt `install.sh`/`update.sh` `compileall --invalidation-mode checked-hash`; Qt-Module laufen mit `sys.dont_write_bytecode = True` und `drop_stale_qml_cache()`.
4. **Sicherheits- & Rechtegrenze:**
   - API lauscht nur auf `127.0.0.1:8765`, prüft `Host` und erzwingt `X-TV: 1` auf allen `POST`s (`OPTIONS` → 403).
   - `AppManager` startet nur Kacheln aus `tiles.json` (keine freien Shell-Kommandos).
   - Root-Operationen ausschließlich über `sudo -n /usr/local/sbin/voidstation-pkg` (Paket-Allowlist aus `catalog.json`), `poweroff`, `reboot`, `nmcli` (Live-ISO zusätzlich `voidstation-installer`).
5. **AppCenter-Paketregel:**
   - Native Void-Pakete (`xbps`) bevorzugen; sonst direkter Hersteller-Download (`source.type = "appimage"`, entpackt nach `apps/<id>`). Keine neuen Flatpaks in `catalog.json`.
6. **Build-, Changelog- & Signatur-Regeln:**
   - **`dist/` und `keys/` niemals manuell oder in PRs ändern** (CI-Check schlägt fehl). Nur `tools/publish.sh` (`vspub`) baut und signiert (`ssh-keygen -Y sign -n voidstation`) auf dem Herausgeber-Rechner.
   - Nur `keys/voidstation-release.pub` und `keys/voidstation-notfall.pub` werden von `build.sh` in `allowed_signers` aufgenommen.
   - `CHANGELOG.md` (DE) und `CHANGELOG.en.md` (EN) synchron halten; neue Einträge unter `## Testing – YYYY-MM-DD` (ganz oben). Versionsnummern (`YYYY.MM[.N]`) vergibt nur `vspub --release` / `--hotfix`.
   - Neue Dateien beginnen mit SPDX-Header (`# SPDX-License-Identifier: GPL-3.0-or-later` bzw. `// ...`). Code-Prüfungen (`ruff`, `mypy`, `shellcheck`) richten sich nach `pyproject.toml`.

---

## 4. „Wo gehört was hin?“ & Lokale Tests

### Feature-Zuordnung
| Neues Feature / Änderung | Zielorte |
|---|---|
| Neue Startseiten-Ebene / Dialog | `launcher/qt/qml/<Name>Layer.qml` (+ in `Main.qml` `layerOrder`/`updateLayer`), UI-Bausteine in `qml/VS/`, Texte in `web/i18n/{de,en}.json`, ggf. Preview-Route in `tools/qt-preview.py`. |
| Neuer Backend-Endpunkt | Logik + Route in `launcher/launcher.py` (`Handler.do_GET` / `do_POST` mit `X-TV: 1`), Aufruf über `Api.get`/`Api.post`, Mock in `tools/qt-preview.py` (oder `tools/sampledata.py`). |
| Neue Einstellung | Persistenz in `settings.json` + `settings_payload()` + `POST /api/settings/<key>` in `launcher.py`, Zeile in `SettingsLayer.qml`, i18n `{de,en}.json`. |
| Neue App im AppCenter | Eintrag in `launcher/catalog.json` (daraus generieren `install-head.sh`/`update-head.sh` automatisch `allowed-packages`); ggf. Start-/Konfig-Logik in `launcher.py`. |
| Neuer Emulator / Spielprofil / Shader | `catalog.json`, `ROMManager`/`EMU_LAYOUTS`/`EMU_OPTS` in `launcher.py`, Spielprofile in `launcher/gamedb/<sys>.csv` + `gameprofiles.py`, Shader in `launcher/shaders/`. |
| Neue Player-Funktion (`tv`/`media`/`yt`) | `launcher/qt/voidstation-player.py` + `qml/Player.qml` / `qml/player/<View>.qml` + Backend-Routen in `launcher.py`. |
| Neue Root-/System-Funktion | Unterbefehl in `launcher/voidstation-pkg` (oder eigener Helfer in `launcher/voidstation-*`, eingebunden in `build.sh`, `install-head.sh`, `update-head.sh`, `sysfix.sh`). |
| Neues Theme / neue Übersetzung | `launcher/web/themes/<id>.css` / `launcher/web/i18n/<lang>.json` (+ `LANG_TABLE` in `launcher.py`, `LOCALES` in `voidstation-installer`, Locales in `install-head.sh`). |
| Live-ISO / Installer-Änderung | `launcher/voidstation-installer`, `qml/InstallLayer.qml`, `iso/{build-iso-head.sh,postsetup.sh,99-voidstation-live.sh,grub-entries.py}`. |
| Neuer CLI-Befehl | `launcher/vsctl` + Bash-Completion in `launcher/shell/bashrc.sh`. |

### Lokale Test- & Preview-Befehle
```sh
# 1. Gesamte Schnellprüfung (wie CI: shellcheck, Python-Syntax, ruff, mypy, JSON, gamedb, build.sh, Webseite)
tools/check.sh
VS_CHECK_INSTALL=1 tools/check.sh          # lädt gepinnte ruff/mypy in Wegwerf-venv

# 2. Build testen, ohne dist/ im Repo zu verändern (prüft i18n, Changelogs, Payload, ISO-Skript)
OUT=/tmp/vs ./build.sh

# 3. Qt-Startseite lokal testen (braucht PySide6-Essentials; Mock-API auf Port 8766)
python3 tools/qt-preview.py                                # 1280x720 Fenster
python3 tools/qt-preview.py --size 1920x1080               # Full-HD
VS_LANG=en python3 tools/qt-preview.py                     # englische UI
python3 tools/qt-preview.py --live [--fail] [--bios]       # Installer-Vorschau
python3 tools/qt-preview.py --player tv                    # TV-Player (Testbild)
python3 tools/qt-preview.py --player media --home /tmp/h   # Videos & Musik
python3 tools/qt-preview.py --player yt --yt-demo          # YouTube Light (mit yt-dlp-mock.py)
VS_VPN=on python3 tools/qt-preview.py                      # VPN-UI (login|off|on|locked|nodaemon)
VS_CHD=ask VS_LOOK=duckstation python3 tools/qt-preview.py # Spieleliste: CHD / Bildstil
python3 tools/qt-preview.py --shot /tmp/out.png --keys "right,a,b"  # Headless-Screenshot

# 4. Weitere Einzelprüfungen
python3 tools/gamedb-check.py                              # Spielprofile prüfen
python3 tools/qt-screenshots.py                            # Doku-Screenshots erzeugen
python3 tools/build-site.py --preview --out /tmp/site      # Webseite lokal bauen
```
