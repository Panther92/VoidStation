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

**Controller als Maus:** In Programmen wie Firefox/YouTube, FreeTube oder Discord bewegt der rechte Stick den Mauszeiger (je weiter, desto schneller), <kbd>R2</kbd> klickt (halten zieht), <kbd>L2</kbd> ist Rechtsklick, der linke Stick scrollt. In Spielen und Emulatoren ist das von selbst aus, weil Stick und Schultertasten dort zum Spiel gehören. <kbd>R3</kbd> (rechten Stick drücken) schaltet in jedem Programm um, ein kurzer Hinweis unten rechts zeigt den Stand. Ganz abschalten: **Einstellungen → System → Controller als Maus**.

## Fernsehen {#fernsehen}

Die Kachel *Fernsehen* öffnet die Senderliste mit Suche, Filtern nach Land und Thema und einer A–Z-Leiste. <kbd>A</kbd> schaltet einen Sender ein, danach bleibst du im Bild:

| | Controller | Tastatur / Fernbedienung | Maus |
|---|---|---|---|
| Sender weiter / zurück | ▲ / ▼ | ↑ / ↓, Bild ↑ / Bild ↓, CH+ / CH− | Pfeile oben rechts |
| Leiser / lauter | ◀ / ▶ | ← / →, <kbd>−</kbd> / <kbd>+</kbd> | Mausrad, − / + oben rechts |
| Info (Sender, Sendung jetzt und danach) | <kbd>A</kbd> | <kbd>Enter</kbd> | Klick |
| Senderliste (Liste, Favoriten, Zuletzt) | <kbd>X</kbd> | <kbd>L</kbd> | Doppelklick |
| Favorit an / aus | <kbd>Y</kbd> | <kbd>F</kbd> | ☆ oben rechts |
| Voriger Sender | <kbd>LB</kbd> / <kbd>RB</kbd> | | |
| Ton & Bild (Tonspur, Untertitel, Bildformat, Qualität) | <kbd>Start</kbd> | <kbd>M</kbd> | Menü oben rechts |
| Technik (Auflösung, Decoder, Darstellungsstufe) | <kbd>Select</kbd> | <kbd>I</kbd> | |
| Zur Startseite, Fernsehen läuft weiter | <kbd>Guide</kbd> | <kbd>Win</kbd> | ⊞ oben rechts |
| Fernsehen beenden | zweimal <kbd>B</kbd> | zweimal <kbd>Esc</kbd> | ✕ oben rechts |

Ist ein Sender nicht erreichbar, steht der Grund im Bild (gesperrt, Zeitüberschreitung, Stream gibt es nicht mehr, kein Internet). ▲ springt gleich zum nächsten, <kbd>A</kbd> versucht es noch einmal. In der Senderliste ist so ein Sender danach 24 Stunden lang mit ⚠ markiert. Startet das Fernsehen, geht das Radio aus.

## Videos & Musik {#medien}

Die Kachel *Videos & Musik* zeigt, was in der Freigabe unter `share/Videos` und `share/Musik` liegt, dazu eingesteckte USB-Laufwerke – mit Vorschaubildern und Album-Covern. Ganze Ordner spielst du mit *Alle abspielen*.

**Videos:**

| | Controller | Tastatur |
|---|---|---|
| Pause / weiter | <kbd>A</kbd> | <kbd>Enter</kbd>, Leertaste |
| 10 Sekunden zurück / vor | ◀ / ▶ | ← / → |
| 1 Minute zurück / vor | <kbd>LB</kbd> / <kbd>RB</kbd> | Bild ↓ / Bild ↑ |
| Leiser / lauter | ▼ / ▲ | ↓ / ↑, <kbd>−</kbd> / <kbd>+</kbd> |
| Ton & Untertitel | <kbd>Start</kbd> | <kbd>M</kbd> |
| Stopp – die Stelle wird gemerkt | <kbd>B</kbd> | <kbd>Esc</kbd> |

Unter *Weiterschauen* stehen angefangene Videos; beim nächsten Öffnen fragt VoidStation, ob es an der Stelle weitergehen soll.

**Musik:**

| | Controller | Tastatur |
|---|---|---|
| Pause / weiter | <kbd>A</kbd> | <kbd>Enter</kbd>, Leertaste |
| Voriger / nächster Titel | ◀ / ▶ | ← / → |
| 10 Sekunden zurück / vor | <kbd>LB</kbd> / <kbd>RB</kbd> | Bild ↓ / Bild ↑ |
| Leiser / lauter | ▼ / ▲ | ↓ / ↑ |
| Wiederholen umschalten | <kbd>Y</kbd> | <kbd>F</kbd> |
| Zufällige Reihenfolge | <kbd>X</kbd> | <kbd>L</kbd> |
| Menü *Wiedergabe* (Wiederholen, Reihenfolge, Ton, „Cover neu suchen“) | <kbd>Start</kbd> | <kbd>M</kbd> |
| Stopp | <kbd>B</kbd> | <kbd>Esc</kbd> |

*Wiederholen* funktioniert wie beim MP3-Player: **Weiter mit nächstem Ordner** (Standard – am Ende eines Albums geht es mit dem nächsten weiter, auch über Interpreten-Ordner hinweg), **Ordner wiederholen**, **Ordner, dann Stopp** und **Titel wiederholen**. Wahl und Reihenfolge bleiben gespeichert.

Mit <kbd>Guide</kbd> / <kbd>Win</kbd> oder *Start → Zur Startseite* (für Controller ohne Guide-Taste) geht es zur Startseite, ohne zu beenden: Musik spielt weiter, ein Video hält an. Die Kachel zeigt, was gerade läuft. Startet das Radio, hält die Musik an.

**Album-Cover** kommen von selbst: zuerst das in den Dateien eingebettete Bild, sonst sucht VoidStation Interpret und Album bei [MusicBrainz](https://musicbrainz.org) und lädt das Cover aus dem [Cover Art Archive](https://coverartarchive.org). Auf der Startseite der Mediathek:

- **Cover automatisch laden** (an/aus) – für die Ordner, die du gerade ansiehst.
- **Alle Cover laden** – geht die ganze Sammlung durch, mit Fortschritt.
- **Cover in Dateien speichern** (Standard aus) – schreibt gefundene Cover und fehlende Tags (Interpret, Titel, Album, Jahr, Titelnummer) in MP3-, M4A- und FLAC-Dateien, damit auch andere Player und das Handy sie sehen. Vorhandene Tags bleiben unangetastet.

### Musik suchen {#musik-suchen}

Unter *Herunterladen → Musik suchen* findest und lädst du Musik. Beim ersten Öffnen kreuzt du selbst an, wo gesucht wird – nichts ist vorausgewählt:

- **Freie Musik (Internet Archive):** Netlabels, Live-Mitschnitte und Alben unter Creative-Commons-Lizenz oder gemeinfrei, ganze Alben auf einmal.
- **YouTube** und **SoundCloud:** einzelne Titel als MP3. Bitte nur laden, was du laden darfst – die Nutzung erfolgt auf eigene Verantwortung, es gelten die Bedingungen der Plattform.

<kbd>Y</kbd> springt ins Suchfeld (mit Bildschirmtastatur), <kbd>A</kbd> lädt einen Treffer, <kbd>X</kbd> ändert die Quellen. Downloads laufen nacheinander, der Fortschritt steht am Treffer. Einzelne Titel bekommen Interpret, Album, Titelnummer, Jahr, Genre und Cover und landen unter `share/Musik/<Interpret>/<Album>/` (ohne Album unter `<Interpret>/Singles/`).

## Updates {#updates}

**Einstellungen → Updates → Aktualisieren** ist der einzige Update-Knopf. Er prüft und installiert alles in einem Durchgang: Void-Pakete (samt Kernel), Flatpaks, AppImages, Proton-GE und VoidStation selbst. Eigene Kacheln, Favoriten und Einstellungen bleiben erhalten.

- Die Geräte schauen kurz nach dem Start und dann alle sechs Stunden selbst nach. Eine neue VoidStation-Version meldet ein gelber Hinweis unten rechts sofort.
- Reine Systemupdates meldet der Hinweis erst, wenn das System seit 30, 60 oder 90 Tagen nicht aktualisiert wurde (Einstellungen → Updates, Standard 90).
- **Update-Kanal:** Alle Geräte bekommen *Stable*. Wer Fehler melden möchte, wechselt im Terminal mit `vsctl channel testing` auf den Entwicklerstand *Testing* (neue Versionen zuerst, ungeprüft); zurück mit `vsctl channel stable` – Updates kommen dann wieder, sobald Stable neuer ist.
- Im Terminal macht `vsctl update` dasselbe wie der Knopf. `sudo xbps-install -Su` aktualisiert nur die Void-Pakete – VoidStation erkennt das.

## Freigabe: Dateien vom PC {#freigabe}

Jede VoidStation hat eine Windows-Freigabe. Am PC im Explorer `\\<rechnername>\share` eingeben (z. B. `\\wohnzimmer\share`) und mit Benutzername und Passwort aus der Installation anmelden. Dort hinein gehören Filme, Musik, Bilder und Spiele: Videos nach `share/Videos` und Musik nach `share/Musik` (beides zeigt die Kachel *Videos & Musik*), Spiele nach `share/ROMs/<System>`.

## Spiele und Emulatoren {#spiele}

Emulatoren gibt es im AppCenter unter *Emulatoren*. ROMs kommen in die Freigabe unter `share/ROMs/<System>`, zum Beispiel `gba`, `gbc`, `snes`, `nes`, `psx`, `psp`, `nds`, `gamecube` oder `dreamcast`. Die Emulator-Kachel zeigt dann eine Spieleliste; ohne Spiele startet der Emulator direkt. Game-Boy-Color-Spiele (`gbc`) zeigt die mGBA-Kachel zusammen mit `gba`; DOSBox Staging startet fertig eingerichtet mit `share/ROMs/dos` als Laufwerk C.

Ein laufendes Spiel gehört zur Kachel: Nach <kbd>Guide</kbd> / <kbd>Win</kbd> holt die Kachel es mit <kbd>A</kbd> zurück, <kbd>Y</kbd> oder *App schließen* in der Ecke beenden es. Solange die Startseite oder ein anderes Programm vorn ist, hält der Emulator an und läuft danach genau an der Stelle weiter (gilt nicht für Steam und Netzwerkspiele).

## Programmvorschau beim Fernsehen {#epg}

Laufende und nächste Sendung erscheinen beim Umschalten und mit <kbd>A</kbd> im Bild. Standardmäßig aus. Zum Einschalten die Adresse einer XMLTV-Datei (`.xml` oder `.xml.gz`) eintragen – sie wird täglich geladen:

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

### Wo ist VLC hin?

„Videos & Musik“ ersetzt VLC; das Update entfernt VLC samt Kachel. Wer VLC für DVD-Menüs, Umwandeln oder exotische Formate braucht, holt es mit einem Klick zurück: **AppCenter → Medien → VLC**. Wer VLC schon selbst über das AppCenter installiert hatte, behält es.

### Cover fehlen oder sind falsch

Auf der Startseite der Mediathek **Alle Cover laden** wählen. Ist ein Cover falsch, im Musikbildschirm **Start → Wiedergabe → Weiteres → Cover neu suchen**: VoidStation nimmt heraus, was es selbst geschrieben hat (eigene Cover und Tags bleiben), und sucht neu. Am zuverlässigsten klappt die Suche mit Tags oder Dateinamen wie `Interpret - Titel.mp3`.

### Das Bild bleibt schwarz oder ruckelt

<kbd>Select</kbd> (bzw. <kbd>I</kbd>) im Player zeigt Auflösung, Decoder und Darstellungsstufe – bitte in jeden Fehlerbericht. Klappt die Darstellung auf einer Grafikkarte nicht, stuft VoidStation von selbst zurück, beim Fernsehen zuletzt bis zum einfachen Vollbild.

### Welche Sprachen gibt es?

Dreizehn: Deutsch, English, Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский und Українська – **Einstellungen → Sprache**. Außer Deutsch und Englisch sind die Übersetzungen maschinell erstellt; Korrekturen gern als [Pull Request](seite:contribute#uebersetzen). Installer und Startmenü des Sticks gibt es vorerst nur auf Deutsch und Englisch.

### Die Oberfläche startet nicht – was nun?

Nach zwei Fehlstarts installiert VoidStation den Grafik-Server XLibre einmal neu. Klappt es dann immer noch nicht, erscheint eine Rettungskonsole. Dort hilft `sudo /usr/local/sbin/voidstation-pkg xserver status`.

### Wo finde ich Protokolle?

Unter `~/.local/share/voidstation/logs/`. Das Protokoll des Installers liegt während der Installation unter `/run/voidstation-installer/install.log` und lässt sich direkt auf einen USB-Stick speichern.

### Ist VoidStation ein offizielles Void-Linux-Projekt?

Nein. VoidStation ist ein eigenständiges Projekt, das auf Void Linux aufbaut. Fragen zu VoidStation bitte nicht an das Void-Team, sondern [in die Discussions](https://github.com/Panther92/VoidStation/discussions).
