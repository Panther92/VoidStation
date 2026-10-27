#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  VoidStation: Systemkorrekturen – als root, beliebig oft ausfuehrbar.
#  Aufgerufen von install.sh (auch im chroot des Installers / beim ISO-Bau) und update.sh.
#
#   1. elogind: eigener Dienst voidstation-elogind statt /etc/sv/elogind. Startet D-Bus elogind
#      beim Hochfahren schon selbst (NetworkManager, automatische Anmeldung), lief /etc/sv/elogind
#      in eine Schleife ("elogind is already running", jede Sekunde, sichtbar auf der Konsole).
#      Umgestellt wird beim naechsten Start (core-service), damit kein laufender Dienst stoppt.
#   2. WLAN: Funkregeln des Landes (sonst Kanaele 12/13 und viele 5-GHz-Kanaele nur passiv),
#      USB-Sticks: keine Zufalls-MAC beim Suchen, kein Stromsparmodus.
#   3. GRUB-Start ohne Meldungsflut (quiet), wie beim EFISTUB-Start.
#   4. Bluetooth & Controller: BlueZ fuer Kopfhoerer/Controller eingestellt, Zugriff auf Controller
#      (hidraw, uinput) fuer Steam, Emulatoren und SDL, uinput beim Start laden.
#   6. Standby: USB-Tastaturen, -Maeuse, Fernbedienungen mit USB-Empfaenger und der Bluetooth-Adapter duerfen
#      wecken (Kernel-Vorgabe ist oft "aus"); dazu der USB-Controller selbst.
#   5. Flatpak-Programme: Dateidialog ueber xdg-desktop-portal (GTK-Oberflaeche). Ohne Portal sehen
#      Flatpaks ohne Dateirechte (z. B. FreeTube beim Abo-Import) nur ein leeres Homeverzeichnis.
#      Unter Openbox ist XDG_CURRENT_DESKTOP leer, darum legt portals.conf das GTK-Backend fest.
#   7. Systemname: /etc/os-release meldet "VoidStation <Version>" (ID_LIKE=void), xbps laesst sie stehen.
#   8. Terminal: bash-Komfort (/etc/bash/bashrc.d), fastfetch mit VoidStation-Logo, nano mit Syntaxfarben.
# =====================================================================
CHROOT="${VOIDSTATION_CHROOT:-0}"
say() { printf '%s\n' "$*"; }

# ---------------------------------------------------------------------
# 1. elogind
mkdir -p /etc/sv/voidstation-elogind /etc/runit/core-services
cat > /etc/sv/voidstation-elogind/run <<'EOF'
#!/bin/sh
# VoidStation: elogind wie /etc/sv/elogind, aber ohne Doppelstart. Hat D-Bus elogind beim
# Hochfahren schon selbst gestartet, wird diese Kopie nur ueberwacht; endet sie, startet runit
# elogind wieder regulaer (ueber den Wrapper des Pakets).
exec 2>&1
sv check dbus >/dev/null || exit 1
pid="$(pgrep -xo 'elogind|elogind-daemon')"
if [ -n "$pid" ]; then
  echo "elogind laeuft schon (PID $pid) – ueberwache nur"
  while kill -0 "$pid" 2>/dev/null; do sleep 15; done
  exit 0
fi
exec /usr/libexec/elogind/elogind.wrapper
EOF
chmod 755 /etc/sv/voidstation-elogind/run
cat > /etc/runit/core-services/91-voidstation-elogind.sh <<'EOF'
# SPDX-License-Identifier: GPL-3.0-or-later
# VoidStation (runit core-service): elogind ueber /etc/sv/voidstation-elogind statt /etc/sv/elogind
# (dort Neustart-Schleife, wenn D-Bus elogind schon gestartet hat). Laeuft vor allen Diensten.
if [ -x /etc/sv/voidstation-elogind/run ] && [ -d /etc/runit/runsvdir/default ]; then
  rm -f /etc/runit/runsvdir/default/elogind
  [ -e /etc/runit/runsvdir/default/voidstation-elogind ] || ln -s /etc/sv/voidstation-elogind /etc/runit/runsvdir/default/
fi
EOF
chmod 644 /etc/runit/core-services/91-voidstation-elogind.sh
say "elogind: voidstation-elogind (aktiv ab dem naechsten Start)"

# ---------------------------------------------------------------------
# 2. WLAN
mkdir -p /etc/NetworkManager/conf.d /etc/modprobe.d
cat > /etc/NetworkManager/conf.d/90-voidstation-wifi.conf <<'EOF'
# VoidStation: WLAN robuster, vor allem mit USB-Sticks
[device]
# viele Sticks (Realtek u. a.) verbinden nicht, wenn beim Suchen eine Zufalls-MAC benutzt wird
wifi.scan-rand-mac-address=no

[connection]
# Stromsparen fuehrt bei USB-Sticks zu Zeitueberschreitungen und Abbruechen (2 = aus)
wifi.powersave=2
EOF
# Land fuer die Funkregeln: aus der Zeitzone, sonst aus der Sprache, sonst Deutschland
cc=""
tz="$(readlink /etc/localtime 2>/dev/null | sed 's|.*zoneinfo/||')"
if [ -n "$tz" ] && [ -r /usr/share/zoneinfo/zone.tab ]; then
  cc="$(awk -v z="$tz" '$3 == z { print $1; exit }' /usr/share/zoneinfo/zone.tab)"
fi
if [ -z "$cc" ] && [ -r /etc/locale.conf ]; then
  cc="$(sed -n 's/^LANG=[a-z]*_\([A-Z][A-Z]\).*/\1/p' /etc/locale.conf | head -1)"
fi
[ -n "$cc" ] || cc=DE
printf '# VoidStation: Funkregeln fuer WLAN (Land %s, aus Zeitzone/Sprache)\noptions cfg80211 ieee80211_regdom=%s\n' "$cc" "$cc" \
  > /etc/modprobe.d/voidstation-wlan.conf
if [ "$CHROOT" != 1 ] && command -v iw >/dev/null 2>&1; then
  iw reg set "$cc" 2>/dev/null || true
fi
[ -f /usr/lib/firmware/regulatory.db ] || say "Hinweis: wireless-regdb fehlt (Funkregeln wirken erst damit)"
say "WLAN: Funkregeln $cc, ohne Zufalls-MAC und Stromsparen"

# ---------------------------------------------------------------------
# 3. GRUB: still starten (Void-Standard ist "loglevel=4" ohne quiet)
if [ -f /etc/default/grub ] && ! grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=.*quiet' /etc/default/grub; then
  if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT="' /etc/default/grub; then
    sed -i -e '/^GRUB_CMDLINE_LINUX_DEFAULT="/s/loglevel=[0-9]*/loglevel=3/' \
           -e '/^GRUB_CMDLINE_LINUX_DEFAULT="/s/"$/ quiet"/' /etc/default/grub
  else
    echo 'GRUB_CMDLINE_LINUX_DEFAULT="loglevel=3 quiet"' >> /etc/default/grub
  fi
  grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=.*loglevel=' /etc/default/grub \
    || sed -i '/^GRUB_CMDLINE_LINUX_DEFAULT="/s/ quiet"$/ loglevel=3 quiet"/' /etc/default/grub
  say "GRUB: $(grep '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub)"
  if [ "$CHROOT" != 1 ] && [ -f /boot/grub/grub.cfg ]; then
    update-grub >/dev/null 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg >/dev/null 2>&1 || say "GRUB-Menue nicht erneuert"
  fi
fi

# ---------------------------------------------------------------------
# 4. Bluetooth & Controller
# Setzt "Schluessel = Wert" im Abschnitt einer ini-Datei (ersetzt auch auskommentierte Vorgaben)
ini_set() {
  [ -f "$1" ] || return 0
  awk -v sec="[$2]" -v key="$3" -v val="$4" '
    function put() { if (!done) { print key " = " val; done = 1 } }
    /^[ \t]*\[.*\][ \t]*$/ { if (insec) put(); insec = ($0 == sec); if (insec) seen = 1; print; next }
    insec && $0 ~ ("^[ \t]*" key "[ \t]*=") { put(); next }
    insec && $0 ~ ("^[#;][ \t]*" key "[ \t]*=") { if (!done) put(); else print; next }
    { print }
    END { if (insec) put(); else if (!seen) { print ""; print sec; print key " = " val } }' "$1" > "$1.vs-new" \
    && cat "$1.vs-new" > "$1"
  rm -f "$1.vs-new"
}
# BlueZ (wirkt ab dem naechsten Start von bluetoothd):
#  - Controller, die ihre Kopplung vergessen haben (anderes Geraet, Reset), koppeln neu ohne "Entkoppeln"
#  - Kopfhoerer verbinden sich schneller wieder, Adapter ist nach dem Start an
#  - gefundene Geraete bleiben 3 Minuten waehlbar (Standard 30 s – zu knapp fuer die Fernbedienung)
#  - PlayStation-Controller drahtlos (ClassicBondedOnly=false), Controller ueber die Kernel-Treiber (UserspaceHID)
ini_set /etc/bluetooth/main.conf General JustWorksRepairing always
ini_set /etc/bluetooth/main.conf General FastConnectable true
ini_set /etc/bluetooth/main.conf General TemporaryTimeout 180
ini_set /etc/bluetooth/main.conf Policy AutoEnable true
ini_set /etc/bluetooth/input.conf General UserspaceHID true
ini_set /etc/bluetooth/input.conf General ClassicBondedOnly false
[ -f /etc/bluetooth/main.conf ] && say "Bluetooth: Neukopplung, schnelles Wiederverbinden, Controller drahtlos"

# Controller-Zugriff: Steam, Emulatoren und SDL lesen Controller direkt (hidraw) und legen virtuelle an (uinput).
# USB ueber die Herstellerkennung, Bluetooth ueber die HID-Kennung (0005:<Hersteller>:<Produkt>).
mkdir -p /etc/udev/rules.d /etc/modules-load.d
{
  echo "# VoidStation: Controller, Lenkraeder und Joysticks fuer den angemeldeten Benutzer (wird bei Updates neu geschrieben)"
  # Sony, Microsoft, Nintendo, Valve, 8BitDo, Logitech, Hori, PDP, PowerA, Nacon/BigBen, Mad Catz, Razer,
  # Thrustmaster, GameSir, ShanWan, DragonRise, Betop, Google (Stadia), SteelSeries, Saitek, VKB, Virpil, Nacon (neu)
  for v in 054c 045e 057e 28de 2dc8 046d 0f0d 0e6f 20d6 24c6 146b 0738 1532 044f 3537 2563 0079 11c0 11c1 18d1 1038 06a3 231d 3344 3285; do
    V="$(printf '%s' "$v" | tr 'a-f' 'A-F')"
    printf 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="%s", MODE="0660", GROUP="input", TAG+="uaccess"\n' "$v"
    printf 'SUBSYSTEM=="hidraw", KERNELS=="*:%s:*", MODE="0660", GROUP="input", TAG+="uaccess"\n' "$V"
  done
  echo '# alle Joysticks/Gamepads als Eingabegeraet'
  echo 'SUBSYSTEM=="input", ENV{ID_INPUT_JOYSTICK}=="1", MODE="0660", GROUP="input", TAG+="uaccess"'
  echo '# virtuelle Controller (Steam Input, AntiMicroX)'
  echo 'KERNEL=="uinput", SUBSYSTEM=="misc", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput", TAG+="uaccess"'
} > /etc/udev/rules.d/70-gamepad.rules
echo uinput > /etc/modules-load.d/voidstation-gamepad.conf
if [ "$CHROOT" != 1 ]; then
  modprobe uinput 2>/dev/null || true
  if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --subsystem-match=hidraw --subsystem-match=input --subsystem-match=misc 2>/dev/null || true
  fi
fi
say "Controller: Zugriff fuer Steam/Emulatoren (hidraw, uinput)"

# ---------------------------------------------------------------------
# 5. Flatpak: Dateidialog ueber xdg-desktop-portal
mkdir -p /etc/xdg-desktop-portal
cat > /etc/xdg-desktop-portal/portals.conf <<'EOF'
# VoidStation: Openbox hat kein eigenes Portal-Backend – alles ueber xdg-desktop-portal-gtk
# (Dateidialog fuer Flatpak-Programme wie FreeTube, Flycast, Moonlight)
[preferred]
default=gtk
EOF
chmod 644 /etc/xdg-desktop-portal/portals.conf
say "Flatpak: Dateidialog ueber xdg-desktop-portal (GTK)"

# ---------------------------------------------------------------------
# 6. Standby: Weckquellen
#    Wecken duerfen USB-Tastaturen, -Maeuse und Fernbedienungen mit USB-Empfaenger (HID, Klasse 03).
#    Der Bluetooth-Adapter (Klasse e0, Unterklasse 01, Protokoll 01) ausdruecklich NICHT: Ein verbundener
#    BT-Controller verliert beim Einschlafen die Verbindung, der Adapter meldet das und bricht den Standby
#    sofort ab (NiPoGi, 20.10.2026). Wecken per Controller-Home-Taste klappt ohnehin nicht.
mkdir -p /etc/udev/rules.d
cat > /etc/udev/rules.d/71-voidstation-wakeup.rules <<'EOF'
# VoidStation: aus dem Standby wecken per USB-Tastatur, -Maus und Fernbedienung mit USB-Empfaenger (HID, Klasse 03)
ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_interface", ATTR{bInterfaceClass}=="03", RUN+="/bin/sh -c 'echo enabled > /sys%p/../power/wakeup'"
# Bluetooth-Adapter weckt nicht (ein verbundener Controller wuerde den Standby sonst sofort abbrechen)
ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_interface", ATTR{bInterfaceClass}=="e0", ATTR{bInterfaceSubClass}=="01", ATTR{bInterfaceProtocol}=="01", RUN+="/bin/sh -c 'echo disabled > /sys%p/../power/wakeup'"
# USB-Controller (xHCI)
ACTION=="add", SUBSYSTEM=="pci", ATTR{class}=="0x0c0330", ATTR{power/wakeup}="enabled"
EOF
chmod 644 /etc/udev/rules.d/71-voidstation-wakeup.rules
if [ "$CHROOT" != 1 ]; then                       # schon angeschlossene Geraete gleich umstellen
  for i in /sys/bus/usb/devices/*:*; do
    case "$(cat "$i/bInterfaceClass" 2>/dev/null)/$(cat "$i/bInterfaceSubClass" 2>/dev/null)/$(cat "$i/bInterfaceProtocol" 2>/dev/null)" in
      03/*) echo enabled > "$i/../power/wakeup" 2>/dev/null ;;
      e0/01/01) echo disabled > "$i/../power/wakeup" 2>/dev/null ;;
    esac
  done
  for d in /sys/bus/pci/devices/*; do
    [ "$(cat "$d/class" 2>/dev/null)" = 0x0c0330 ] && echo enabled > "$d/power/wakeup" 2>/dev/null
  done
fi
# elogind: nur Suspend-to-RAM ("mem" – nimmt automatisch deep bzw. s2idle laut /sys/power/mem_sleep).
# Standard waere "mem standby freeze": bricht "mem" ab (Weckereignis beim Einschlafen), versucht elogind
# sofort "freeze" – auf Geraeten ohne s2idle-Unterstuetzung im BIOS scheitert das (amdgpu: -22) nur laut.
mkdir -p /etc/elogind/sleep.conf.d
cat > /etc/elogind/sleep.conf.d/voidstation.conf <<'EOF'
# VoidStation: Standby nur als Suspend-to-RAM, kein Ausweichen auf "freeze" nach einem Abbruch
[Sleep]
SuspendState=mem
EOF
chmod 644 /etc/elogind/sleep.conf.d/voidstation.conf
say "Standby: wecken per USB-Tastatur/-Maus/Fernbedienung (nicht per Bluetooth), nur Suspend-to-RAM"

# ---------------------------------------------------------------------
# 7. Name des Systems: /etc/os-release ("VoidStation <Version>" statt "Void Linux")
#    Lesen u. a. fastfetch und der Installer (Kachel "Neben …"). Void liefert /etc/os-release als Verweis auf
#    /usr/lib/os-release (Paket base-files); das Original bleibt dort unveraendert, /etc geht laut Spezifikation
#    vor. noextract haelt xbps davon ab, den Verweis bei einem Update von base-files zurueckzuschreiben.
#    ID_LIKE=void: Werkzeuge, die Abkoemmlinge kennen, behandeln VoidStation wie Void (fastfetch: Void-Farben).
VSDIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /etc/xbps.d
cat > /etc/xbps.d/voidstation-os-release.conf <<'EOF'
# VoidStation: eigene /etc/os-release behalten (das Void-Original liegt unveraendert in /usr/lib/os-release)
noextract=/etc/os-release
EOF
chmod 644 /etc/xbps.d/voidstation-os-release.conf
if python3 - "$VSDIR/version.json" > /etc/os-release.vs-tmp <<'PYEOF'
import json, re, sys
try:
    v = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError):
    v = {}
ver = str(v.get("version") or "")
build = str(v.get("build") or "")
ver = ver if re.fullmatch(r"[0-9A-Za-z.+_-]+", ver) else ""
build = build if re.fullmatch(r"[0-9a-f]+", build) else ""
m = re.match(r"\d{4}\.\d{2}(?:\.\d+)?|0\.\d+\.\d+", ver)
out = ['NAME="VoidStation"', 'ID="voidstation"', 'ID_LIKE="void"',
       f'PRETTY_NAME="VoidStation {ver}"' if ver else 'PRETTY_NAME="VoidStation"']
if ver:
    out.append(f'VERSION="{ver}"')                     # z. B. 2026.11 oder 2026.11+testing.20261120
if m:
    out.append(f'VERSION_ID="{m.group(0)}"')           # nur Ziffern und Punkte (Spezifikation: kein "+")
if build:
    out.append(f'BUILD_ID="{build}"')
out += ['HOME_URL="https://voidstation.de/"',
        'DOCUMENTATION_URL="https://github.com/Panther92/VoidStation#readme"',
        'BUG_REPORT_URL="https://github.com/Panther92/VoidStation/issues"',
        'ANSI_COLOR="0;38;2;95;168;184"']
print("\n".join(out))
PYEOF
then
  chmod 644 /etc/os-release.vs-tmp && mv -f /etc/os-release.vs-tmp /etc/os-release
  say "Systemname: $(sed -n 's/^PRETTY_NAME="\(.*\)"/\1/p' /etc/os-release)"
else
  rm -f /etc/os-release.vs-tmp
  say "Systemname: /etc/os-release nicht geschrieben (bleibt Void)"
fi
# Begruessung der Textkonsole (Strg+Alt+F2 …, /etc/issue): ersetzt nur Voids Vorgabe und fruehere VoidStation-Zeilen
# (auch "VoidStation – Void Linux" vom Installer); eigene Texte und die des Live-Sticks bleiben
case "$(head -n1 /etc/issue 2>/dev/null)" in
  'Void \r (\n) (\l)'|VoidStation*)
    printf '%s \\r (\\n) (\\l)\n\n' "$(sed -n 's/^PRETTY_NAME="\(.*\)"/\1/p' /etc/os-release 2>/dev/null | grep . || echo VoidStation)" \
      > /etc/issue ;;
esac

# ---------------------------------------------------------------------
# 8. Terminal: Shell-Komfort (Verlauf, Vervollstaendigung, Eingabeaufforderung, Aliase – fuer alle Benutzer,
#    eigene ~/.bashrc geht vor), fastfetch mit VoidStation-Logo, nano mit Syntaxfarben und Zeilennummern.
#    xterm selbst (Farben nach Theme, Schriftgroesse, 256 Farben) stellt der Launcher ueber ~/.Xresources ein.
mkdir -p /etc/bash/bashrc.d /etc/xdg/fastfetch /usr/local/share/voidstation
install -m 644 "$VSDIR/shell/bashrc.sh" /etc/bash/bashrc.d/voidstation.sh
install -m 644 "$VSDIR/shell/fastfetch-logo.ansi" /usr/local/share/voidstation/fastfetch-logo.ansi
install -m 644 "$VSDIR/shell/fastfetch.jsonc" /etc/xdg/fastfetch/config.jsonc
# Void legt keine /etc/nanorc an (nur ein Beispiel unter /usr/share/examples/nano) – Block einmalig anhaengen
if ! grep -q 'VoidStation' /etc/nanorc 2>/dev/null; then
  cat >> /etc/nanorc <<'EOF'
## VoidStation: Syntaxfarben und Zeilennummern (eigene Einstellungen in ~/.nanorc gehen vor)
include "/usr/share/nano/*.nanorc"
set linenumbers
EOF
  chmod 644 /etc/nanorc
fi
say "Terminal: Vervollstaendigung, Verlauf, Eingabeaufforderung, fastfetch-Logo, nano mit Farben"
exit 0
