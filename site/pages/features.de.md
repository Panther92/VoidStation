# Funktionen

Alles, was man vom Sofa aus braucht – auf einem kleinen PC am Fernseher, ohne Konto und ohne Werbung im System.

## Screenshots {#screenshots}

{{screens}}

## Oberfläche {#oberflaeche}

- Kacheln im Stil von Windows 8, in Gruppen sortiert – eigene Kacheln lassen sich ergänzen
- Bedienung mit Gamepad, Fernbedienung, Maus oder Tastatur; Controller von Xbox, PlayStation, Nintendo, 8BitDo & Co., einfache USB-Pads und Joysticks – auch per Bluetooth, Kopplung ohne Tastatur
- Bildschirmtastatur für jedes Eingabefeld – auch in Firefox und auf YouTube
- Designs: Dunkel, Hell, Hoher Kontrast und Nord; eigene Designs als einzelne CSS-Datei
- Skalierung und Auflösung einstellbar, 60 Hz werden bevorzugt
- 13 Sprachen: Deutsch und Englisch von Hand gepflegt, dazu Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский und Українська (maschinell übersetzt) – Datum, Uhrzeit und Zahlen im Format der Sprache, gestartete Programme folgen
- Mehrere Programme gleichzeitig – mit <kbd>Guide</kbd> bzw. <kbd>Win</kbd> geht es aus jedem Programm zurück zur Startseite, mit der Maus über die Ecke unten rechts
- Controller als Maus in Programmen wie Firefox, FreeTube oder Discord – in Spielen schaltet sich das von selbst ab
- Standby mit Aufwecken per USB-Tastatur, -Maus oder Fernbedienung
- Ton: Geräte wie „Fernseher · HDMI“ oder „Kopfhörer · Bluetooth“ statt kryptischer Profile, Format und Mikrofon je Gerät; neue Kopfhörer übernehmen auf Wunsch den Ton

<div class="screens">
<figure><a href="/assets/screens/11-ton.webp"><img src="/assets/screens/11-ton.webp" alt="Ton: Geräte statt Profile" loading="lazy" width="1600" height="900"></a><figcaption>Ton: Geräte statt Profile</figcaption></figure>
</div>

## Fernsehen {#fernsehen}

- Frei empfangbare Sender aus aller Welt (Senderliste von [iptv-org](https://github.com/iptv-org/iptv)), mit Suche, Filtern nach Land und Thema, A–Z-Leiste und Favoriten
- Eigener Player: umschalten mit ▲▼ direkt im Bild, Senderliste am Bildrand (Liste, Favoriten, Zuletzt), „Ton & Bild“ für Tonspur, Untertitel, Bildformat und Qualität
- Beim Umschalten Logo, Sendername und – sobald eine XMLTV-Quelle eingetragen ist – laufende und nächste Sendung
- Ist ein Sender nicht erreichbar, sagt VoidStation, warum; kurze Netzaussetzer überbrückt der Player
- Die Grafikkarte dekodiert (VA-API, bei NVIDIA NVDEC) – weniger Last, leisere Lüfter
- Mediatheken von ARD, ZDF und ARTE sowie Pluto TV im AppCenter

<div class="screens">
<figure><a href="/assets/screens/7-tv-player.webp"><img src="/assets/screens/7-tv-player.webp" alt="Fernseh-Player mit Senderinfo über einer Szene aus Big Buck Bunny" loading="lazy" width="1600" height="900"></a><figcaption>Fernsehen: umschalten direkt im Bild, mit Programminfo. Bild: „Big Buck Bunny“ © Blender Foundation | <a href="https://peach.blender.org">peach.blender.org</a>, <a href="https://creativecommons.org/licenses/by/3.0/deed.de">CC BY 3.0</a></figcaption></figure>
</div>

## Radio {#radio}

- Zehntausende Sender über [radio-browser.info](https://www.radio-browser.info), mit Suche und Favoriten
- Die Radio-Kachel zeigt Sender und laufenden Titel – das Radio spielt weiter, während du andere Kacheln benutzt

## Videos & Musik {#medien}

- Mediathek für die Freigabe (`share/Videos`, `share/Musik`) und USB-Laufwerke, mit Vorschaubildern und „Weiterschauen“ an der letzten Stelle
- Videos mit Ton- und Untertitelwahl, Musik mit Cover, Titelliste und „Alle abspielen“
- Wiederholen wie beim MP3-Player (auch „Weiter mit nächstem Ordner“) und zufällige Reihenfolge
- Album-Cover kommen von selbst (MusicBrainz, Cover Art Archive), auf Wunsch samt fehlender Tags direkt in die Dateien
- Musik und Fernsehen laufen weiter, während du auf der Startseite oder in einem anderen Programm bist
- **Musik suchen:** freie Musik aus dem Internet Archive, auf Wunsch auch YouTube und SoundCloud – als MP3 mit Interpret, Album, Titelnummer und Cover, sortiert in `share/Musik`

<div class="screens">
<figure><a href="/assets/screens/12-video.webp"><img src="/assets/screens/12-video.webp" alt="Video-Wiedergabe mit Fortschrittsleiste über einer Szene aus Big Buck Bunny" loading="lazy" width="1600" height="900"></a><figcaption>Videos mit Ton- und Untertitelwahl. Bild: „Big Buck Bunny“ © Blender Foundation | <a href="https://peach.blender.org">peach.blender.org</a>, <a href="https://creativecommons.org/licenses/by/3.0/deed.de">CC BY 3.0</a></figcaption></figure>
<figure><a href="/assets/screens/8-mediathek.webp"><img src="/assets/screens/8-mediathek.webp" alt="Die Mediathek mit Album-Covern" loading="lazy" width="1600" height="900"></a><figcaption>Die Mediathek mit Album-Covern</figcaption></figure>
<figure><a href="/assets/screens/9-musik.webp"><img src="/assets/screens/9-musik.webp" alt="Musik mit Cover, Wiederholen und Zufall" loading="lazy" width="1600" height="900"></a><figcaption>Musik mit Cover, Wiederholen und Zufall</figcaption></figure>
<figure><a href="/assets/screens/10-musik-suchen.webp"><img src="/assets/screens/10-musik-suchen.webp" alt="„Musik suchen“: Quellen wählst du selbst" loading="lazy" width="1600" height="900"></a><figcaption>„Musik suchen“: Quellen wählst du selbst</figcaption></figure>
</div>

## YouTube und Streaming {#streaming}

- YouTube im Vollbild (Firefox im Kioskmodus)
- Netflix, Prime Video, Disney+, Joyn, RTL+ und Twitch aus dem AppCenter – Kopierschutz (Widevine) wird dafür eingeschaltet
- Kodi, Jellyfin, Plex HTPC, Spotify und FreeTube aus dem AppCenter; VLC gibt es dort weiterhin mit einem Klick

## AppCenter {#appcenter}

61 ausgesuchte Apps in sieben Bereichen – installieren und entfernen mit einem Klick:

- **Gaming:** Steam mit Proton-GE, Heroic Games Launcher, Lutris, itch, Prism Launcher (Minecraft), Moonlight, Steam Link, Discord
- **Emulatoren:** DuckStation, PCSX2, PPSSPP, Dolphin, Cemu, Flycast, mGBA, melonDS, Azahar, Snes9x, Nestopia, Rosalie's Mupen GUI, MAME, DOSBox Staging, ScummVM, VICE, Stella, RetroArch
- **Spiele:** SuperTuxKart, SuperTux, Neverball, Luanti, Xonotic, Hedgewars, Battle for Wesnoth, OpenTTD
- **Medien, Streaming, Browser und Werkzeuge:** von Kodi bis LocalSend (Dateien vom Handy schicken)

Native Void-Pakete haben Vorrang; Flatpak oder AppImage gibt es nur, wo kein Void-Paket existiert. „Installiert“ zeigt alles auf dem Gerät – auch Programme aus dem Terminal.

## Spiele {#spiele}

- Steam nativ aus den Void-Paketquellen, Proton-GE wird automatisch aktuell gehalten
- Emulator-Kacheln zeigen die Spiele aus der Freigabe (`share/ROMs/<System>`) und starten sie direkt; im Hintergrund hält das Spiel an und läuft danach an derselben Stelle weiter
- DOSBox Staging fertig eingerichtet, Game Boy Color in der mGBA-Kachel
- Spiele vom Gaming-PC streamen mit Moonlight oder Steam Link

## Updates {#updates}

- Ein Knopf für alles: Void-Pakete samt Kernel, Flatpaks, AppImages, Proton-GE und VoidStation selbst
- Updates von VoidStation sind signiert – Geräte installieren nur, was der Herausgeber unterschrieben hat
- Kanäle **Stable** (für alle) und **Testing** (neue Versionen zuerst)
- Kein tägliches Nachfragen: reine Systemupdates meldet VoidStation erst nach 30, 60 oder 90 Tagen; ein Neustart wird nur verlangt, wenn er nötig ist

## Unter der Haube {#technik}

- [Void Linux](https://voidlinux.org) (glibc, Rolling Release) mit runit, Openbox und PipeWire
- Grafik-Server [XLibre](https://github.com/X11Libre/xserver); startet die Oberfläche zweimal nicht, repariert VoidStation sich selbst, danach gibt es eine Rettungskonsole
- Startseite und Player als eigene Programme in Python + Qt 6, die direkt auf der Grafikkarte zeichnen; abgespielt wird mit [mpv](https://mpv.io). Die Web-Oberfläche (WebKitGTK) bleibt als Rückfall
- Windows-Freigabe `\\<rechner>\share` für Filme, Musik und ROMs; Fernzugriff per SSH auf Wunsch
- Live-ISO mit Installer im selben Kacheldesign: ganze SSD, neben Windows oder Linux, in freien Platz oder selbst einteilen
