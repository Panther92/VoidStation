# Hilfe

Bedienung, Updates, Freigabe und die häufigsten Fragen. Fehlt etwas? Dann [frag in den Discussions](https://github.com/Panther92/VoidStation/discussions).

## Hilfe bekommen {#support}

- **Fragen, Ideen, Erfahrungen:** in den [Discussions auf GitHub](https://github.com/Panther92/VoidStation/discussions). Unter *Q&A* lassen sich Antworten als Lösung markieren, so finden andere sie später wieder.
- **Etwas funktioniert nicht:** als [Issue auf GitHub](https://github.com/Panther92/VoidStation/issues). Was dabei hilft, steht unter [Fehler melden](seite:contribute#fehler).

Zum Lesen brauchst du kein Konto, zum Schreiben ein kostenloses GitHub-Konto.

## Bedienung {#bedienung}

| | Controller | Tastatur | Maus |
|---|---|---|---|
| Bewegen | Steuerkreuz / linker Stick | Pfeiltasten | zeigen, Mausrad blättert |
| Öffnen / Auswählen | <kbd>A</kbd> | <kbd>Enter</kbd> | Klick |
| Zurück | <kbd>B</kbd> | <kbd>Esc</kbd> / Rücktaste | Rechtsklick |
| Programm schließen, Favorit | <kbd>X</kbd> / <kbd>Y</kbd> | <kbd>Entf</kbd>, <kbd>F</kbd>, <kbd>Y</kbd> | ✕ auf der Kachel |
| Gruppe vor / zurück | <kbd>RT</kbd> / <kbd>LT</kbd> | Bild ↓ / Bild ↑ | Pfeile oben rechts |
| Leiser / lauter | <kbd>LB</kbd> / <kbd>RB</kbd> | <kbd>−</kbd> / <kbd>+</kbd> | |
| Update öffnen (wenn unten rechts angezeigt) | <kbd>Select</kbd> | <kbd>U</kbd> | Klick auf den Hinweis |
| Ausschalten, Standby | <kbd>Start</kbd> | | ⏻ oben rechts |
| Zurück zur Startseite (aus jedem Programm) | <kbd>Guide</kbd> / Home | <kbd>Win</kbd> | Ecke unten rechts, dann **Startseite** |
| Programm schließen (aus dem Programm heraus) | | | Ecke unten rechts, dann **App schließen** |

**Standby** (⏻ → Standby, oder Einstellungen → System): Programme bleiben offen, das Radio geht aus. Aufwecken mit einer USB-Tastatur, -Maus oder einer Fernbedienung mit USB-Empfänger (Air-Mouse). Bluetooth weckt bewusst nicht – ein Controller verliert beim Einschlafen die Verbindung, und der Adapter hielt das für einen Weckruf. Nach dem Aufwachen verbindet sich der Controller von selbst wieder. Klappt das Wecken nicht, im BIOS/UEFI nach „Wake on USB“ o. Ä. schauen; wodurch das Gerät aufgewacht ist oder warum ein Standby abgebrochen wurde, steht in `~/.local/share/voidstation/launcher.log`.

Die Pfeile oben rechts erscheinen, sobald eine Seite breiter als der Bildschirm ist; der helle Punkt zeigt die aktuelle Gruppe. Gamepads per Bluetooth koppelst du unter **Einstellungen → Bluetooth**.

## Updates {#updates}

**Einstellungen → Updates → Aktualisieren** ist der einzige Update-Knopf. Er prüft und installiert alles in einem Durchgang: Void-Pakete (samt Kernel), Flatpaks, AppImages, Proton-GE und VoidStation selbst. Eigene Kacheln, Favoriten und Einstellungen bleiben erhalten.

- Die Geräte schauen kurz nach dem Start und dann alle sechs Stunden selbst nach. Eine neue VoidStation-Version meldet ein gelber Hinweis unten rechts sofort.
- Reine Systemupdates meldet der Hinweis erst, wenn das System seit 30, 60 oder 90 Tagen nicht aktualisiert wurde (Einstellungen → Updates, Standard 90).
- **Update-Kanal:** *Stable* für alle oder *Testing*, wenn du neue Versionen zuerst haben möchtest.
- Im Terminal macht `vsctl update` dasselbe wie der Knopf. `sudo xbps-install -Su` aktualisiert nur die Void-Pakete – VoidStation erkennt das.

## Freigabe: Dateien vom PC {#freigabe}

Jede VoidStation hat eine Windows-Freigabe. Am PC im Explorer `\\<rechnername>\share` eingeben (z. B. `\\wohnzimmer\share`) und mit Benutzername und Passwort aus der Installation anmelden. Dort hinein gehören Filme, Musik, Bilder und Spiele.

## Spiele und Emulatoren {#spiele}

Emulatoren gibt es im AppCenter unter *Emulatoren*. ROMs kommen in die Freigabe unter `share/ROMs/<System>`, zum Beispiel `gba`, `gbc`, `snes`, `nes`, `psx`, `psp`, `nds`, `gamecube` oder `dreamcast`. Die Emulator-Kachel zeigt dann eine Spieleliste; ohne Spiele startet der Emulator direkt.

## Programmvorschau beim Fernsehen {#epg}

Standardmäßig aus. Zum Einschalten die Adresse einer XMLTV-Datei (`.xml` oder `.xml.gz`) eintragen – sie wird täglich geladen:

```
echo 'https://…/epg.xml.gz' | sudo tee /usr/local/share/voidstation/epg-url
```

## Häufige Fragen {#faq}

### Brauche ich ein Konto?

Nein. VoidStation kennt keine Anmeldung bei irgendeinem Dienst. Nur Streaming-Apps wie Netflix wollen natürlich ihr eigenes Konto.

### Läuft das auf einem Raspberry Pi?

Nein, nur auf 64-Bit-PCs (x86_64). Ein gebrauchter Mini-PC oder Büro-PC ist ideal.

### Kann ich Windows behalten?

Ja: Die Live-ISO installiert neben Windows (im UEFI-Modus). Vorher in Windows den Schnellstart ausschalten und Windows herunterfahren statt in den Ruhezustand zu schicken. Beim Start erscheint dann ein kurzes Auswahlmenü.

### Eigene Programme als Kachel {#eigene-programme}

Programme, die du selbst installiert hast, erscheinen im AppCenter unter **Installiert → Auf diesem Gerät**. Dort legt **Kachel anlegen** eine Kachel an – Spiele landen in der Gruppe *Spiele*, alles andere unter *Programme*. Void-Pakete und Flatpaks bringen den nötigen Starteintrag (eine `.desktop`-Datei) selbst mit und tauchen dort von allein auf.

Ein **AppImage** braucht diesen Eintrag noch. Datei in die Freigabe legen, dann im Terminal (Name, Kurzname `ID` ohne Leerzeichen und Dateiname anpassen):

```
NAME="Mein Programm"; ID=meinprogramm
FILE=~/share/MeinProgramm-x86_64.AppImage

mkdir -p ~/Apps ~/.local/bin ~/.local/share/applications && cd ~/Apps
chmod +x "$FILE" && "$FILE" --appimage-extract
rm -rf "$ID" && mv squashfs-root "$ID"
printf '#!/bin/sh\nexec "%s" "$@"\n' "$HOME/Apps/$ID/AppRun" > ~/.local/bin/$ID
chmod +x ~/.local/bin/$ID
printf '[Desktop Entry]\nType=Application\nName=%s\nExec=%s\nCategories=Utility;\n' \
  "$NAME" "$HOME/.local/bin/$ID" > ~/.local/share/applications/$ID.desktop
```

Für ein Spiel `Categories=Game;` statt `Utility;` eintragen. Durch das Entpacken braucht das AppImage kein FUSE. Updates bekommen solche Programme nicht über VoidStation: neue Datei holen und die Befehle noch einmal ausführen.

### Die Oberfläche startet nicht – was nun?

Nach zwei Fehlstarts installiert VoidStation den Grafik-Server XLibre einmal neu. Klappt es dann immer noch nicht, erscheint eine Rettungskonsole. Dort hilft `sudo /usr/local/sbin/voidstation-pkg xserver status`.

### Wo finde ich Protokolle?

Unter `~/.local/share/voidstation/logs/`. Das Protokoll des Installers liegt während der Installation unter `/run/voidstation-installer/install.log` und lässt sich direkt auf einen USB-Stick speichern.

### 4K-Fernseher: nur 30 Hz oder kleinere Auflösung

Viele Fernseher stellen ihre HDMI-Anschlüsse ab Werk auf eine schmale Bandbreite. 4K gibt es dann höchstens mit 30 Hz, flüssig läuft es nur in kleinerer Auflösung. Abhilfe schafft eine Einstellung im Fernseher – für genau den Anschluss, an dem der VoidStation-PC hängt:

- **Samsung:** *Eingangssignal Plus*, bei Modellen ab 2025 *Externe Geräteverwaltung → Erweitertes Eingangssignal*, bis 2018 *HDMI UHD Color*
- **LG:** *HDMI ULTRA HD Deep Colour*
- **Sony:** *HDMI-Signalformat → Erweitertes Format*
- **Philips:** *HDMI Ultra HD → Optimal*

Bei anderen Marken heißt sie ähnlich (*HDMI 2.0*, *Erweitert*, *Enhanced*). Danach unter **Einstellungen → Anzeige** die volle Auflösung wählen. Klappt es trotzdem nicht, liegt es meist am Kabel: 4K mit 60 Hz braucht eines für 18 Gbit/s (*Premium High Speed*). Ob es geklappt hat, zeigt `xrandr` im Terminal – hinter `3840x2160` muss `60.00` stehen.

### Ist VoidStation ein offizielles Void-Linux-Projekt?

Nein. VoidStation ist ein eigenständiges Projekt, das auf Void Linux aufbaut. Fragen zu VoidStation bitte nicht an das Void-Team, sondern [in die Discussions](https://github.com/Panther92/VoidStation/discussions).
