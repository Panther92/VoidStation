# Änderungen

Neueste Version oben. Die erste Überschrift bestimmt die Versionsnummer, die Geräte im Update-Dialog anzeigen.
Jede Änderung steht auch in `CHANGELOG.en.md` (englisch) – sonst bricht `build.sh` ab.

Versionen nach Kalender (seit 2026.11): `## 2026.11 – 2026-11-07` (Release-Zug im November),
Hotfixes dazu `## 2026.11.1 – …`. Neues kommt zuerst unter `## Testing – <Datum der letzten Änderung>`
ganz oben; die Nummer vergibt `vspub --release` bzw. `vspub --hotfix` beim Freigeben (siehe `RELEASING.md`).
Ältere Versionen (bis 0.15.0) tragen noch Nummern nach dem alten Schema.

## Testing – 2026-10-25
- Terminal: Einfügen aus der Zwischenablage geht jetzt – mit Strg+Umschalt+V, Umschalt+Einfg oder Rechtsklick (am Controller L2). Bisher fügte das Terminal nur markierten Text ein, nicht das mit Strg+C Kopierte (etwa aus Firefox). Markieren im Terminal kopiert zugleich in die Zwischenablage, Strg+Umschalt+C ebenso
- mGBA: Controller-Belegung korrigiert – bei PS4-Controllern und Nachbauten lagen A und B daneben, und ✕ öffnete das Laden-Fenster (mGBAs eingebautes Profil für „Wireless Controller“ zählt die Tasten wie unter Windows). Jetzt fragt VoidStation SDL, welche Taste wo sitzt – dieselbe Bibliothek und Controller-Datenbank, die mGBA nutzt –, und belegt danach: ○ = A, ✕ = B, Share/Options = Select/Start. Die alte, falsche Belegung von VoidStation wird beim nächsten Start von selbst ersetzt; was man in mGBA selbst belegt hat, bleibt. Für Controller, die SDL nicht kennt, gilt die eigene Belegung aus `~/.config/voidstation/pads.json` (wie für die Startseite) auch in mGBA
- mGBA: **△ kurz** speichert einen Savestate (Platz 1), **△ lang** (knapp eine Sekunde) lädt ihn – die Meldung erscheint unten im Bild
- Spiele aus der Spieleliste starten im Vollbild (der Emulator ohne Spiel bleibt im Fenster): mGBA und DuckStation mit ihrer eigenen Vollbild-Option, Snes9x, Nestopia, melonDS, Stella, VICE und RetroArch über den Fenstermanager. **L3 lang drücken** (linken Stick knapp eine Sekunde gedrückt halten) schaltet das Vollbild des Emulators vorn aus und wieder an – etwa um an die Menüs von mGBA zu kommen (dann R3 für den Controller als Maus). Wirkt nur, wenn wirklich ein Emulator vorn ist. Abschaltbar mit `"emu_fullscreen": false` in `settings.json`, je Kachel mit `"fullscreen": false` in `tiles.json`. Neu installiert: xdotool
- mGBA mit sinnvollen Grundeinstellungen: Controller funktionieren jetzt von selbst – bisher kannte mGBA nur alte Xbox-360-Pads, bei allen anderen (Xbox Series, DualSense, DualShock 4, Switch Pro, 8BitDo …) waren A, B, Start und Select nicht belegt. Belegt wird wie auf dem Game Boy angeordnet (rechte Taste = A, untere = B), dazu L/R, Steuerkreuz und linker Stick. Außerdem: Spielstand alle 10 Sekunden und beim Beenden automatisch gesichert und beim nächsten Start dort weiter, Zurückspulen an, scharfe Pixel (ganzzahlig vergrößert, ohne Weichzeichnen). VoidStation fasst nur an, was man in mGBA nicht selbst umgestellt hat – eigene Einstellungen und eine eigene Controller-Belegung bleiben
- Spielstand-Sicherung: Alle 30 Minuten und kurz nach dem Beenden eines Emulators landen die Spielstände in der Freigabe unter `Spielstand-Backups/<Datum_Uhrzeit>` – aber nur, wenn sich etwas geändert hat. Gesichert werden Speicherstände neben den Spielen in `ROMs` (z. B. `.sav`, Savestates `.ss0`–`.ss9`) und die Ordner von DuckStation, PPSSPP, Dolphin, RetroArch, PCSX2, Flycast, Mednafen, Nestopia und ScummVM. Unveränderte Dateien kosten keinen Platz (harte Links). Behalten werden alle Sicherungen der letzten 24 Stunden, danach eine pro Tag für 30 Tage. Zurückholen vom PC aus: Datei an ihren alten Platz kopieren (`LIESMICH.txt` im Ordner). Abschaltbar mit `"save_backup": false` in `settings.json`
- Spieleliste mit Bildern: Zu jedem Spiel sucht VoidStation das Boxbild online (libretro-thumbnails, dieselben Bilder wie in RetroArch) und speichert es dauerhaft unter `ROMs/<System>/Cover/<Name des Spiels>.png`. Am besten klappt das mit den üblichen Dateinamen wie „Pokemon - Crystal Version (USA, Europe)“; ROM-Hacks und selbst benannte Dateien finden oft nichts – dafür ein eigenes Bild mit dem Namen des Spiels in den Ordner `Cover` legen (`.png`, `.jpg` oder `.webp`), das hat immer Vorrang. Nicht Gefundenes wird erst nach 14 Tagen wieder gesucht. Abschaltbar mit `"rom_covers": false` in `settings.json`
- Videos & Musik spielt DVDs: Liegt eine Video-DVD im Laufwerk, erscheint auf der Startseite der Mediathek eine Kachel „DVD“ mit dem Namen der Disc. Darin stehen die Titel der DVD mit Länge und Kapiteln – bei Serien-DVDs meist ein Titel je Folge; kurze Vorspanne und Warnhinweise sind ausgeblendet, „Alle Titel abspielen“ spielt der Reihe nach. Ab dem gewählten Titel geht es automatisch weiter, X/Y springt zum nächsten/vorigen Titel. Tonspuren, Untertitel und Bildformat (4:3 bleibt 4:3) wie bei Videos; im Menü lässt sich der Zeilensprung entfernen (gegen Kammmuster bei Serien-DVDs, kostet Rechenzeit). DVD-Menüs selbst gehen nicht (kann mpv nicht). Kachel „Auswerfen“ öffnet das Laufwerk. Neu installiert: lsdvd; der Benutzer kommt in die Gruppe des Laufwerks (wirkt nach dem nächsten Neustart)
- AppCenter auf 32-Bit-Rechnern (experimentell): Apps, die es dort nicht gibt, werden nicht mehr angeboten – alles aus Flathub (baut kein 32 Bit mehr, z. B. FreeTube, Spotify, Discord, Heroic), Netflix, Prime Video, Disney+, Joyn und RTL+ (Kopierschutz Widevine nur für 64 Bit), DuckStation, Steam und Prism Launcher. Übrig bleiben 36 Apps, darunter Kodi, Jellyfin, VLC, RetroArch, die Emulatoren aus Void, die Spiele und die Mediatheken. Auf 64 Bit ändert sich nichts
- Neu: **YouTube Light** – YouTube ohne Browser und ohne Google-Konto, eingebaut in den VoidStation-Player und ganz mit dem Controller bedienbar. Startseite mit Weiterschauen, neuen Videos aus den eigenen Abos, „Später ansehen“ und den abonnierten Kanälen; Suche nach Videos, Kanälen und Playlists; Kanalseiten (Videos, Live, Playlists), Playlists mit „Alle abspielen“, Verlauf. Abspielen über yt-dlp und mpv (H.264 bevorzugt, Qualität wählbar bis 1080p, Untertitel des Videos). Abos, Verlauf und Listen bleiben auf dem Gerät; Abos lassen sich aus Google Takeout (auch als ZIP), NewPipe und FreeTube übernehmen – Datei in die Freigabe oder auf einen USB-Stick legen. Shorts bleiben draußen. Beim ersten Start erscheint ein Hinweis (YouTube erlaubt fremde Player nicht ausdrücklich), den man bestätigen muss. Schlägt ein Video fehl, weil YouTube etwas geändert hat, lädt ein Knopf die neueste yt-dlp-Fassung direkt vom yt-dlp-Projekt (mit Prüfsumme) und hält sie danach wöchentlich aktuell; „Musik suchen“ nutzt sie mit. Im AppCenter unter Medien; auf 32-Bit-Rechnern ersetzt YouTube Light die YouTube-Kachel (Firefox), die dort zu schwer wäre – bei neuen Installationen und einmalig beim Update, an derselben Stelle und in derselben Größe (auch wenn YouTube Light schon aus dem AppCenter installiert war). Auf 64 Bit bleibt die YouTube-Kachel
- Fernsehen und Videos auf 32-Bit-Rechnern (experimentell): Der Player gibt das Bild dort über Xv aus – die Grafikkarte skaliert dann selbst, auch alte Chips ohne 3D-Treiber (z. B. Radeon 7500/9000 im ThinkPad T41). Dazu installiert VoidStation auf 32 Bit den passenden Grafiktreiber (ATI, Intel, NVIDIA oder VIA) und dekodiert mit Abkürzungen, die auf alten Prozessoren spürbar Rechenzeit sparen. Fernsehen startet dort mit der Qualität „Sparsam“
- Fernsehen: Die gewählte Qualität (Beste/Sparsam) bleibt jetzt gespeichert. Die Technik-Anzeige (Select / I) nennt bei der Stufe auch die Bildausgabe (z. B. „Stufe 2 · xv“)
- Fernsehen: Viele Sender (z. B. 3sat, ZDF und andere HLS-Streams) kamen seit dem neuen Player nicht hinterher – der Puffer lief leer, das Bild stockte oder kam gar nicht. Schuld war eine Einstellung zum automatischen Wiederverbinden, die bei diesen Streams jedes Teilstück einzeln betraf. Sie ist raus; Abbrüche fängt der Player weiterhin selbst ab
- Updates und Installation schreiben am Ende alles auf die Platte, bevor „Fertig“ erscheint. Ging der Rechner direkt nach einem Update hart aus (Netzschalter, Stromausfall), konnten Dateien von VoidStation leer zurückbleiben – die Startseite kam dann nicht mehr hoch
- Fernsehen und Videos auf Grafikkarten ohne Videobeschleunigung (z. B. alte Notebooks; der Player zeigt das Bild dann in einem eigenen mpv-Fenster): Das Bild lag hinter dem Player, man hörte nur den Ton, bis man die Kachel ein zweites Mal wählte. Jetzt kommt das Bild von selbst nach vorn
- Ton: Auf langsamen Rechnern und im Live-System blieb es manchmal stumm – Radio verband sich, aber ohne Ton, Fernsehsender meldeten „nicht erreichbar“ (Zeitüberschreitung) und die Lautstärke zeigte „kein Audiodienst“. Ursache: WirePlumber, der den Ton verwaltet, lief doppelt, und einer davon blieb beim Start hängen. Jetzt startet PipeWire ihn genau einmal selbst; die Startseite verbindet sich außerdem auch dann noch mit dem Ton, wenn der erst später bereit ist (Hinweis aus der Community)
- Live-ISO: Experimentell lässt sich jetzt auch eine 32-Bit-Fassung bauen (`sudo bash build-iso.sh --arch i686`) – für alte Rechner wie ThinkPads mit Pentium M. Sie kommt ohne NVIDIA-Treiber und Startbild aus und startet mit dem Kernel-Parameter `forcepae`, den Pentium-M-Prozessoren brauchen (sie können PAE, melden es aber nicht); der Installer übernimmt ihn ins installierte System und lässt die 32-Bit-Fassung schon ab 1 GB Arbeitsspeicher zu (64 Bit: weiter 4 GB). Das Live-System legt seine Schreibschicht dort per OverlayFS an – über den bisherigen Weg (Device-Mapper) blieb der 32-Bit-Start hängen. Startet in QEMU bis zur Startseite; eine 32-Bit-ISO zum Herunterladen gibt es noch nicht
- AppCenter: Die „YouTube TV-Oberfläche“ ist weg. Sie gaukelte YouTube einen Smart-TV vor, damit youtube.com/tv überhaupt lädt – Google lässt die Oberfläche aber nur noch auf echten Fernsehern zu und meldet sonst, das Gerät werde nicht erkannt. Wer sie installiert hatte, verliert mit diesem Update Kachel und Browser-Profil dazu. Die normale YouTube-Kachel bleibt, ebenso FreeTube im AppCenter
- Emulatoren: Ein Spiel aus der Spieleliste (z. B. mGBA) war nach Home/Guide nicht mehr erreichbar – die Kachel öffnete wieder die Liste, jedes weitere Spiel und „Emulator ohne Spiel starten“ starteten eine neue Instanz, und Y bzw. „App schließen“ in der Ecke griffen nicht. Jetzt gilt das Spiel als laufendes Programm der Kachel: Die Kachel zeigt es als laufend und holt es mit A zurück, Y oder die Ecke beenden es (Spielstand-Abfrage wie bei Alt+F4). Außerdem halten Emulatoren an, solange die Startseite oder ein anderes Programm vorn ist – bisher spielte das Spiel im Hintergrund jeden Tastendruck auf dem Controller mit. Zurück im Spiel läuft es genau an der Stelle weiter. Gilt für alle Emulatoren aus dem AppCenter (mGBA, DuckStation, PPSSPP, Dolphin, DOSBox …), nicht für Steam und Netzwerkspiele; abschaltbar je Kachel mit `"suspend": false` in `tiles.json`
- Standby: Mit verbundenem Bluetooth-Controller wachte VoidStation sofort wieder auf – der Controller verliert beim Einschlafen die Verbindung, und der Bluetooth-Adapter hat das als Weckruf gemeldet. Bluetooth weckt deshalb nicht mehr (die Home-Taste eines Controllers kann einen PC ohnehin nicht wecken); aufwecken per USB-Tastatur, -Maus oder Fernbedienung mit USB-Empfänger. Der Controller verbindet sich nach dem Aufwachen von selbst wieder. Wodurch das Gerät geweckt wurde bzw. warum ein Standby abgebrochen ist, steht jetzt im Protokoll (`launcher.log`)
- Videos & Musik: Die Technik-Anzeige (Select / I) zeigt bei Musik Format und Bitrate (z. B. „MP3 · 320 kbit/s“), Abtastrate, Kanäle und die Tonausgabe statt Auflösung und verworfener Bilder; bei Videos steht zusätzlich eine Zeile „Ton“
- Einstellungen → Ton zeigt jetzt Geräte statt PipeWire-Profile: oben „Fernseher · HDMI“, „MCHOSE X9 · USB“, „JBL … · Bluetooth“ usw., das aktive ist markiert – bisher standen die Profile aller Soundkarten ohne Gerätenamen in einer langen Liste, mit einem Haken je Karte. Darunter für das gewählte Gerät nur noch, was es wirklich gibt: Format (Stereo, Surround 5.1/7.1; bei Bluetooth der Codec, z. B. AAC) und Mikrofon an/aus. Format und Mikro merkt sich VoidStation je Gerät. Bluetooth-Kopfhörer laufen von selbst in voller Qualität (A2DP); das Mikrofon schaltet auf Sprachqualität und ist deshalb aus, bis man es braucht. Neu: „Neue Geräte automatisch verwenden“ (Standard an) – ein eingesteckter USB- oder eingeschalteter Bluetooth-Kopfhörer übernimmt den Ton; Controller mit Kopfhörerbuchse (z. B. DualSense per USB) und Webcams nicht, ebenso wenig beim Hochfahren und direkt nach dem Standby. HDMI steht beim ersten Start einmalig auf Stereo statt 7.1, wenn noch niemand ein Format gewählt hat: Fernseher haben zwei Lautsprecher, und bei 7.1 gingen dort leicht die Dialoge unter. Mit AV-Receiver oder Soundbar: Einstellungen → Ton → Format
- VLC wird mit diesem Update entfernt, samt Kachel – „Videos & Musik“ übernimmt. Wer VLC für DVD-Menüs, Umwandeln oder exotische Formate braucht, holt es mit einem Klick zurück: AppCenter → Medien → VLC. Wer VLC schon selbst über das AppCenter installiert hat, behält es
- Videos & Musik: Die Cover-Suche über Interpret und Titel nahm manchmal einen Sampler statt des Originalalbums (z. B. „25 Jahre Spex“ statt „Mellow Gold“ bei Beck – Loser). Jetzt zählen alle Treffer gemeinsam: offizielles Studioalbum vor Single vor EP, Zusammenstellungen, Live-Alben und „Various Artists“ zuletzt. Neu im Menü (Start → Wiedergabe → Weiteres): „Cover neu suchen“ – nimmt heraus, was VoidStation selbst in die Datei geschrieben hat (Cover und ergänzte Tags, eigene bleiben), und sucht neu. Funktioniert auch für Dateien, die die erste Fassung von heute schon beschrieben hat. Von VoidStation geschriebene Angaben sind jetzt in der Datei gekennzeichnet (Tag VOIDSTATION). Außerdem konnte ein Download oder eine Cover-Suche liegen bleiben, wenn sie genau in dem Moment angestoßen wurde, in dem die vorige fertig wurde
- Videos & Musik: Ein Titel aus einem Ordner startet jetzt auch wirklich dieser Titel – bisher begann die Wiedergabe immer beim ersten Titel des Ordners. Cover-Suche für Dateien ganz ohne Tags und ohne „Interpret - Titel“ im Namen (z. B. „Beck loser.mp3“): VoidStation probiert die möglichen Aufteilungen in Interpret und Titel durch und nimmt nur einen Treffer, bei dem beides passt. Ordner, in denen getaggte und ungetaggte Dateien gemischt liegen, gelten als lose Sammlung
- Videos & Musik: Neuer Schalter „Cover in Dateien speichern“ auf der Startseite der Mediathek (Standard aus). Eingeschaltet schreibt VoidStation gefundene Cover und fehlende Tags direkt in die Musikdateien (MP3, M4A, FLAC), sodass sie auch in anderen Playern und auf dem Handy zu sehen sind. Vorhandene Tags bleiben unangetastet; ergänzt werden nur fehlende – Interpret, Titel, Album, Jahr und Titelnummer aus MusicBrainz, sonst Interpret und Titel aus dem Dateinamen. Geschrieben wird über eine geprüfte Kopie (Ton und Länge müssen stimmen), Änderungsdatum und Rechte bleiben; Dateien auf schreibgeschützten Laufwerken werden übersprungen. „Alle Cover laden“ geht dann die ganze Sammlung durch
- Videos & Musik: Jeder Titel zeigt sein eigenes Cover, auch in der Kachel – das in die Datei eingebettete, sonst das des Ordners. Hat ein Titel keins (z. B. in einer losen Sammlung), sucht VoidStation es im Hintergrund zu Interpret und Album bei MusicBrainz/Cover Art Archive, ohne Album-Tag über Interpret und Titel (notfalls aus dem Dateinamen „Interpret - Titel“). Gespeichert wird im Zwischenspeicher, nicht in deinen Dateien; ein Album wird nur einmal gesucht. „Alle Cover laden“ erfasst auch lose Sammlungen. Liegen in einem Ordner Titel aus verschiedenen Alben – z. B. alles lose in share/Musik –, sucht VoidStation kein gemeinsames Ordner-Cover mehr; ein so entstandenes falsches cover.jpg wird beim nächsten Öffnen entfernt (nur wenn es genau das Bild des ersten Titels ist, eigene Cover bleiben). Die Liste „Danach“ im Musikbildschirm zeigt nur so viele Titel, wie bis zur Hinweiszeile passen, statt sie zu überdecken
- Videos & Musik → „Musik suchen“: Musik suchen und herunterladen, ähnlich wie ytmdl. Beim ersten Öffnen kreuzt du selbst an, wo gesucht wird – nichts ist vorausgewählt: „Freie Musik (Internet Archive)“ (Netlabels, Live-Mitschnitte und Alben unter Creative-Commons-Lizenz oder gemeinfrei, ganze Alben auf einmal), YouTube und SoundCloud (mit Hinweis: nur laden, was man laden darf). Einzelne Titel werden zu MP3 und bekommen Interpret, Album, Titelnummer, Jahr, Genre und Cover (über die iTunes-Suche), gespeichert unter `share/Musik/Interpret/Album/` bzw. `Interpret/Singles/`. Mehrere Downloads laufen nacheinander, der Fortschritt steht an jedem Treffer. Quellen ändern: X oder „Quellen“. Neue Pakete: yt-dlp, Node.js (für YouTube), ffmpeg
- Videos & Musik: Zufällige Reihenfolge mit X oder im Menü (Start → Wiedergabe → Reihenfolge). Der laufende Titel spielt weiter, danach kommt der Rest des Ordners gemischt; mit „Weiter mit nächstem Ordner“ wird jeder neue Ordner ebenfalls gemischt. Die Einstellung bleibt gespeichert
- Videos & Musik: Album-Cover kommen von selbst, ähnlich wie beim Scraper in Batocera. Für Ordner ohne Bild nimmt VoidStation zuerst das in den Dateien eingebettete Cover, sonst sucht es Interpret und Album (aus den Tags oder den Ordnernamen) bei MusicBrainz und lädt das Cover aus dem Cover Art Archive. Gespeichert wird es als cover.jpg im Ordner, sodass es auch andere Player sehen; bei schreibgeschützten Ordnern (z. B. USB-Stick) im Zwischenspeicher. Die Kacheln aktualisieren sich, sobald ein Cover da ist. Auf der Startseite der Mediathek: „Cover automatisch laden“ (an/aus) und „Alle Cover laden“ für die ganze Sammlung, mit Fortschritt. Interpreten-Ordner ohne eigenes Bild zeigen das Cover ihres ersten Albums
- Videos & Musik: Wiederholen wie beim MP3-Player – „Weiter mit nächstem Ordner“ (am Ende eines Albums geht es mit dem nächsten weiter, auch über Interpreten-Ordner hinweg), „Ordner wiederholen“, „Ordner, dann Stopp“ und „Titel wiederholen“. Umschalten mit Y oder im Menü (Start); die Wahl bleibt gespeichert. Der Musikbildschirm zeigt Ordner und Modus, ▶ am letzten Titel springt gleich in den nächsten Ordner
- Videos & Musik und Fernsehen: Zur Startseite, ohne zu beenden – mit Guide/Win oder über Start → „Zur Startseite“ (auch für Controller ohne Guide-Taste). Musik und Fernsehen laufen weiter, ein Video hält an; daneben lassen sich andere Programme öffnen, z. B. ein Emulator. Die Kachel „Videos & Musik“ zeigt, was gerade läuft, die Hinweiszeile nennt Start und Guide jetzt überall. Startet das Radio, hält die Musik im Player an
- Eigener Player für Fernsehen: Umschalten mit ▲▼ direkt im Bild, ohne Umweg über die Startseite. Beim Umschalten erscheinen Logo, Sendername, Platz in der Liste sowie laufende und nächste Sendung (EPG). X öffnet die Senderliste am Bildrand (Liste, Favoriten, Zuletzt), Y merkt den Sender als Favorit, Start öffnet „Ton & Bild“ (Tonspur, Untertitel, Bildformat, Qualität), ◀▶ ändern die Lautstärke, LB/RB springen zum vorigen Sender. Zweimal B beendet das Fernsehen. Bedienbar mit Controller, Tastatur, Fernbedienung oder Maus – im VoidStation-Look und in allen Sprachen
- Fernsehen: Ein Sender, der nicht erreichbar ist, meldet sich jetzt mit Grund (gesperrt, Zeitüberschreitung, Stream gibt es nicht mehr, kein Internet) statt einfach nichts zu tun; ▲ springt gleich zum nächsten. In der Senderliste ist er danach 24 Stunden lang abgedunkelt und mit ⚠ markiert. Kurze Netzaussetzer überbrückt der Player, statt abzubrechen
- Fernsehen und Videos dekodiert jetzt die Grafikkarte (VA-API, bei NVIDIA NVDEC) statt des Prozessors – weniger Last, weniger Wärme, leisere Lüfter
- Neue Kachel „Videos & Musik“ statt VLC: Mediathek für die Freigabe (share/Videos, share/Musik) und USB-Laufwerke, mit Vorschaubildern und „Weiterschauen“ an der Stelle, an der man aufgehört hat. Videos mit Ton- und Untertitelwahl (◀▶ 10 Sekunden, LB/RB 1 Minute), Musik mit Cover und Titelliste – ganze Ordner auf einmal abspielen. VLC steht weiter im AppCenter
- Das Radio geht aus, sobald Fernsehen oder ein Video startet
- Klappt die Darstellung im Player auf einer Grafikkarte nicht, stuft VoidStation von selbst zurück – zuletzt bis zum bisherigen mpv-Vollbild beim Fernsehen. Select (oder I) zeigt im Player Auflösung, Decoder und Darstellungsstufe für Fehlerberichte
- Controller als Maus: In Programmen wie Firefox/YouTube, FreeTube, Discord, VLC oder mGBA bewegt der rechte Stick den Mauszeiger (je weiter, desto schneller), R2 klickt (halten zieht), L2 ist Rechtsklick, der linke Stick scrollt. In Spielen und Emulatoren ist das von selbst aus, weil dort rechter Stick und Schultertasten zum Spiel gehören – R3 (rechten Stick drücken) schaltet in jedem Programm um, ein kurzer Hinweis unten rechts zeigt den Stand. Ganz abschalten: Einstellungen → System → Controller als Maus. Ohne Zusatzprogramm: die Startseite legt dafür eine virtuelle Maus an
- Bluetooth: Gekoppelte Geräte lassen sich umbenennen – „Umbenennen“ neben „Entkoppeln“, z. B. „PS4-Controller“ statt „Wireless Controller“. Der Name bleibt gespeichert, bis das Gerät entkoppelt wird; „Originalname“ (oder ein leeres Feld) holt den Namen zurück, den das Gerät selbst meldet
- Game Boy Color: Neuer Freigabe-Ordner `share/ROMs/gbc`. Die mGBA-Kachel zeigt die Spiele aus `gba` und `gbc` zusammen in einer Liste (Game-Boy-Spiele `.gb` gehen in beide Ordner)
- DOSBox Staging startet fertig eingerichtet: im Vollbild, als 386er mit 4000 Zyklen (Strg+F11/F12 ändern die Geschwindigkeit), Laufwerk C ist die Freigabe `share/ROMs/dos`, Sprache und Tastatur wie in VoidStation eingestellt. Die Grundeinstellung (`~/.config/dosbox/dosbox-staging.conf`) wird nur angelegt, wenn es noch keine gibt – eigene Einstellungen bleiben
- Fernsehen: Die Senderliste brach nach 80 Sendern ab – in Deutschland etwa bei „F“, ZDF & Co. fand nur die Suche. Jetzt sind alle Sender erreichbar: neben der Liste eine A–Z-Leiste zum direkten Springen, am Ende eines Buchstabens geht es mit „Weiter mit …“ zum nächsten. Große Listen kommen in Seiten zu 200 Sendern (z. B. alle Länder unter „T“: rund 1.450) mit „Weitere Sender“ am Ende und „Zurück“ am Anfang. Die Suche findet Namen jetzt auch ohne Akzente (Hinweis aus der Community)
- Standby: ⏻ → Standby (auch unter Einstellungen → System). Programme bleiben offen, das Radio geht aus. Aufwecken per USB-Tastatur, -Maus oder Fernbedienung mit USB-Empfänger. WLAN und Bluetooth melden sich danach von selbst wieder (Wunsch aus der Community)
- Mit der Maus zurück zur Startseite: Maus nach unten rechts schieben – genau ins Eck muss sie nicht, es reicht der untere oder rechte Rand kurz vor der Ecke (bis gut ein Zehntel der Bildhöhe davor). Solange ein Programm läuft, schwebt dort eine kleine Karte in der Farbe seiner Kachel mit „Startseite“ (Programm läuft weiter) und „App schließen“. Gilt für jedes Programm aus einer Kachel, auch im Vollbild (Wunsch aus der Community)
- Flatpak-Programme (z. B. FreeTube, Brave): Lief das Programm schon, holte die Kachel es nicht wieder nach vorn, und die Startseite hielt es dauerhaft für „startet noch“. Ihre Fenster werden jetzt beim Start erkannt
- Elf neue Sprachen für die Oberfläche: Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский, Українська – Einstellungen → Sprache. Datum, Uhrzeit und Zahlen im Format der Sprache; Programme wie VLC und YouTube folgen beim nächsten Start. Die Übersetzungen sind maschinell erstellt – Korrekturen gern als Pull Request. Installer und Startmenü des Sticks bleiben vorerst Deutsch/Englisch
- Versionsnummern nach Kalender: Jahr und Monat der Freigabe, z. B. 2026.11. Hotfixes dazu heißen 2026.11.1, 2026.11.2 usw.; die Live-ISO trägt dieselbe Nummer wie die Version, die sie enthält
- Kanal Testing zeigt den Stand als z. B. „2026.11+testing.20261120“ (nach 2026.11, letzte Änderung am 20.11.). Wer von Testing auf Stable wechselt, bekommt weiterhin kein älteres Update angeboten

## 2026.10 – 2026-10-16
- FreeTube und andere Flatpak-Programme: Der Dateidialog zeigte nur ein leeres Homeverzeichnis – z. B. ließen sich keine Abos importieren. Jetzt öffnet sich ein Dialog mit Zugriff auf alle eigenen Ordner; das Programm bekommt nur die gewählte Datei. Gilt für Programme, die nach dem Update gestartet werden
- Programme und Browser folgen dem VoidStation-Theme: Steht in FreeTube & Co. „Systemvorgabe“ als Farbschema, war das bisher immer hell, YouTube und die Mediatheken waren dagegen immer dunkel. Jetzt alles dunkel bei dunklen Themes und hell bei „Default Light“ – Firefox-Kacheln, Chromium, Brave, LibreWolf, GTK- und Qt-Programme. Wirkt beim nächsten Start des Programms, manche wechseln sofort
- Blätter-Pfeile oben rechts auf der Startseite: Sie bewegten oft nur den Fokusrahmen in die nächste Gruppe, ohne zu blättern. Jetzt rückt die nächste bzw. vorige Gruppe an den linken Rand; LT/RT und Bild auf/ab blättern genauso
- Änderungen an der Oberfläche kamen nach einem Update teils nicht an: Die Startseite lief mit einer zwischengespeicherten älteren Fassung weiter, bis Void das nächste Mal Qt aktualisierte. Jetzt erkennt sie geänderte Dateien selbst

## 0.15.0 – 2026-10-07
- Bluetooth neu gebaut: VoidStation koppelt jetzt selbst, ohne Tastatur – Kopfhörer, Controller und Joysticks mit „Just Works“ werden bestätigt, ältere Geräte mit PIN-Kopplung bekommen automatisch 0000, 1234 oder 1111. Bisher scheiterten solche Geräte stumm
- Tastaturen, die beim Koppeln einen Code verlangen: der Code steht unten rechts, bis die Kopplung durch ist
- Fremde Geräte können sich nicht von selbst koppeln – Anfragen werden nur während und bis 3 Minuten nach der Suche angenommen
- Suche dauert 30 statt 10 Sekunden; gefundene Geräte bleiben 3 Minuten wählbar. Ist ein Gerät inzwischen verschwunden, wird vor dem Koppeln kurz neu gesucht
- Liste aufgeräumt: Handys, PCs und Fernseher in der Nachbarschaft sowie Geräte ohne Namen erscheinen nicht mehr. Dafür steht dabei, was es ist (Audio, Controller, Tastatur, Maus) und – wo das Gerät es meldet – der Akkustand
- Fehlermeldungen mit Ursache („Gerät antwortet nicht – ist es im Kopplungsmodus?“ statt nur „Koppeln fehlgeschlagen“) und ein Hinweis, wie gängige Geräte in den Kopplungsmodus kommen (AirPods, PlayStation, Xbox, Switch)
- Kopfhörer: nach dem Verbinden läuft der Ton sofort über sie
- Zwei Bluetooth-Adapter (z. B. USB-Stick zusätzlich zum eingebauten Chip): der neuere wird benutzt, der andere ausgeschaltet. Fest wählen: Adresse in `/usr/local/share/voidstation/bt-adapter`
- Bluetooth per Funkschalter gesperrt: „Einschalten“ hebt die Sperre auf
- Controller, die ihre Kopplung vergessen haben (Reset, anderes Gerät), koppeln neu, ohne vorher „Entkoppeln“; Kopfhörer verbinden sich schneller wieder
- Startseite: auch einfache USB-Pads ohne eigenen Treiber, Joysticks und Arcade-Sticks steuern die Oberfläche. Eigene Belegung möglich über `~/.config/voidstation/pads.json`
- Steam, Emulatoren und SDL-Spiele dürfen Controller aller gängigen Hersteller direkt ansprechen (Sony, Microsoft, Nintendo, Valve, 8BitDo, Logitech, Hori, PDP, PowerA, Thrustmaster, GameSir u. a., per USB und Bluetooth) – bisher nur PlayStation

## 0.14.3 – 2026-10-05
- Alte Kernel werden automatisch entfernt, sobald das System mit dem neuesten Kernel fehlerfrei läuft (Oberfläche seit 10 Minuten oben) – spart pro Kernel rund 300 MB
- Direktstart (EFISTUB): Stellt die Firmware die Startreihenfolge selbst um (z. B. GRUB immer zuerst), bleibt das so, statt bei jedem Kernel-Update dagegen anzuschreiben – GRUB startet ebenfalls den neuesten Kernel. Erzwingen: `sudo voidstation-efistub --order`

## 0.14.2 – 2026-10-05
- Kernel-Updates: Die gelbe Meldung „Neustart nötig“ verschwand nach dem Neustart nicht, weil der Rechner weiter den alten Kernel startete. Der Direktstart (EFISTUB) nutzt jetzt einen festen Starteintrag „VoidStation EFISTUB“, der bei Kernel-Updates gleich bleibt – der neue Kernel liegt unter festem Namen auf der EFI-Partition
- Das Initramfs enthält keine Grafiktreiber mehr (die laden ohnehin später) – rund 200 MB kleiner je Kernel; die EFI-Partition lief damit fast voll. Alte Kernel-Dateien werden von dort entfernt
- Passt ein Kernel nicht auf die EFI-Partition, startet automatisch GRUB mit dem neuesten Kernel
- Bestehende Geräte werden beim Update umgestellt (Initramfs wird einmal neu gebaut, danach einmal neu starten)
- Startet ein neuer Kernel trotz Neustart nicht, erscheint statt der Dauermeldung ein Hinweis in Einstellungen → Updates
- Updates: statt „Update-Server nicht erreichbar“ direkt nach dem Start wird jetzt sofort geprüft; ohne Netz steht dort „offline – keine Internetverbindung“, die Server-Meldung kommt nur noch, wenn das Netz da ist und der Server wirklich nicht antwortet

## 0.14.1 – 2026-10-04
- Englische Oberfläche: Die Uhr zeigt nachmittags wieder „2:53 PM“ statt „14:53 PM“

## 0.14.0 – 2026-10-04
- Installer jetzt auch als Qt-Programm: Live-System und Installation laufen ohne WebKit – flüssig auch mit NVIDIA-Treiber in 4K, Maus inklusive
- Alle Wege wie gewohnt: ganze SSD, neben einem anderen System (Grenze per Steuerkreuz oder Maus ziehen), freier Bereich, selbst einteilen mit GParted; Konto und Rechnername über die Bildschirmtastatur oder die echte Tastatur; „A halten“ zum Installieren; Fortschritt, Fehlerseite mit „Anders versuchen“ und Protokoll
- „WLAN“ im Installer öffnet direkt die WLAN-Einstellungen
- Startmenü des Sticks: zuerst die Sprache (Deutsch / English), darunter die beiden Starteinträge in dieser Sprache – Oberfläche, Installer und Tastatur starten gleich passend (English mit US-Tastatur)
- Die Blätter-Pfeile oben rechts funktionieren wieder (mit der Qt-Startseite ohne Wirkung)
- Die Web-Oberfläche bleibt als Rückfall: startet die Qt-Oberfläche dreimal nicht, übernimmt sie – auch im Live-System

## 0.13.3 – 2026-10-03
- WLAN: Falsches Passwort meldet jetzt „Passwort falsch? Bitte nochmal eingeben.“ statt der nmcli-Rohmeldung, das Feld wird geleert und die Bildschirmtastatur geht wieder auf; auch „Netz nicht gefunden“, „antwortet nicht“ und „kein WLAN-Adapter“ im Klartext
- WLAN: Ein altes, gespeichertes Profil für dasselbe Netz wird beim Verbinden mit Passwort ersetzt, ein fehlgeschlagener Versuch hinterlässt kein halbes Profil mehr (das blockierte bisher den nächsten Versuch)

## 0.13.2 – 2026-10-03
- Tastatur und Gamepad springen nicht mehr auf die Kachel unter dem Mauszeiger zurück – die Maus setzt den Fokus nur noch, wenn sie bewegt wird

## 0.13.1 – 2026-10-03
- WLAN: Suche mit genug Zeit für USB-Sticks (statt „nmcli nicht verfügbar“), Verbinden mit bis zu 90 s; Funkregeln des Landes (Paket wireless-regdb, Land aus der Zeitzone), keine Zufalls-MAC beim Suchen und kein Stromsparmodus – hilft vielen USB-Sticks
- Tastatur: Die Oberfläche übernimmt das Layout aus dem Installer (vorher immer Deutsch, z. B. falsch mit US-Tastatur)
- Kein Dauer-Neustart von elogind mehr („elogind is already running“ jede Sekunde auf der Konsole); Start über GRUB ohne Meldungsflut
- Web-Oberfläche (Live-System, Installer, „Klassisch“) mit NVIDIA-Treiber: läuft mit Firefox statt WebKit – flüssig auch in 4K
- Live-ISO: Startmenü nie mehr in 4K (reagierte an manchen NVIDIA-Karten kaum auf Tasten), Countdown 15 s; der normale Eintrag sperrt den NVIDIA-Treiber zuverlässig, der Installer übernimmt ihn nur, wenn die Karte wirklich daran hängt

## 0.13.0 – 2026-10-03
- Neue Startseite als eigenes Programm (Python + Qt 6) statt Webseite in WebKit: zeichnet direkt auf der Grafikkarte – auch mit dem NVIDIA-Treiber und in 4K – und braucht weniger Arbeitsspeicher
- Alles wie gewohnt: Kacheln, Radio, Fernsehen mit Programmanzeige, Spiele, AppCenter, Einstellungen, Bildschirmtastatur und Themes, bedienbar mit Gamepad, Tastatur und Maus
- Einstellungen → System → Oberfläche: zwischen „Neu (Qt)“ und „Klassisch (Web)“ wechseln. Startet die neue Oberfläche dreimal nicht, geht es automatisch mit der klassischen weiter
- Live-System und Installer bleiben vorerst bei der Web-Oberfläche

## 0.12.1 – 2026-10-02
- Kein dunkler Bildschirm mehr beim Start: Bis die Startseite steht, zeigt sie das Logo mit Lade-Punkten – nahtlos nach dem Startbild beim Hochfahren
- Die Startseite startet früher (wartet nicht mehr auf Ton und Launcher), der Hintergrund ist von Anfang an dunkelgrau statt schwarz
- Live-ISO: Startbild mit Logo auch im BIOS-Modus (Legacy/CSM) statt Textmeldungen

## 0.12.0 – 2026-10-02
- Startseite mit NVIDIA-Karten: die Oberfläche wählt die passende Darstellung selbst (ohne DMA-BUF bei NVIDIA, ganz ohne GPU, wenn keine da ist) und schaltet nach wiederholten Abstürzen eine Stufe robuster – statt schwarzem Bild mit Mauszeiger
- Live-ISO: neues Startmenü mit Logo im Kacheldesign, nur noch „Start VoidStation Live“, „Start VoidStation Live (NVIDIA only)“ und „Reboot“ (UEFI und BIOS)
- Live-ISO: NVIDIA-Treiber an Bord (GeForce GTX 16xx, RTX 20xx und neuer) – lädt nur über „NVIDIA only“; der normale Eintrag nutzt nouveau mit GSP-Firmware
- Live-ISO: Startbild mit Logo beim Hochfahren
- Installer: wer über „NVIDIA only“ installiert, behält den NVIDIA-Treiber; sonst wird er samt DKMS und Compiler entfernt. Startbild und GParted bleiben auf dem Stick

## 0.11.1 – 2026-10-01
- Bildschirmtastatur öffnet sich bei jedem Eingabefeld, auch per Mausklick – und jetzt auch in Firefox/YouTube (Erweiterung „FX OSK“, funktioniert offline)
- PlayStation-Controller (DualSense/DualShock) per Bluetooth; Steuerkreuz funktioniert auch bei Controllern, die es als Achse melden
- Logos und Kacheln lassen sich nicht mehr versehentlich ziehen, kein Markieren von Text beim Bedienen
- Installer: Größenaufteilung neben einem anderen System lässt sich mit der Maus ziehen
- Danke an DevSpeX!

## 0.11.0 – 2026-10-01
- Installation auch im BIOS-Modus (Legacy/CSM): ältere PCs und virtuelle Maschinen mit Standardeinstellungen (VirtualBox, QEMU) brauchen kein UEFI mehr. Im BIOS-Modus gibt es den Weg „Ganze SSD“; neben anderen Systemen und „Selbst einteilen“ bleiben dem UEFI-Modus vorbehalten
- Eine im BIOS-Modus installierte SSD startet auch, wenn die Firmware später auf UEFI umgestellt wird (GRUB für beide Modi)
- Startmenü des Sticks auch im BIOS-Modus mit „VoidStation installieren“ und den englischen Einträgen
- Der Installer verlangt nur noch, dass Secure Boot aus ist; die Anleitung dazu ist kürzer

## 0.10.1 – 2026-10-01
- AppCenter: sichtbare Scrollbalken neben Kategorien und Apps – so sieht man, dass es weitergeht; die Kategorienliste blendet unten weich aus, wenn noch mehr kommt

## 0.10.0 – 2026-10-01
- AppCenter neu aufgebaut: links „Installiert“ und die Kategorien, rechts die Apps als Kacheln – die Liste scrollt nach unten statt zur Seite, die Spaltenzahl passt sich Auflösung und Skalierung an
- „Installiert“ zeigt alles auf dem Gerät auf einen Blick, nach Kategorien gegliedert – auch Programme, die außerhalb des AppCenters installiert wurden
- Bedienung: hoch / runter wechselt die Kategorie und zeigt sie gleich an, rechts geht in die Apps, links zurück; LT / RT (Bild ↑↓) springt von überall zur vorigen / nächsten Kategorie; Mausrad scrollt die Liste
- Viel mehr Auswahl (60 statt 22 Apps), weiterhin kuratiert:
  - Gaming: Heroic Games Launcher, Lutris, itch, Prism Launcher (Minecraft), Steam Link, Discord
  - Emulatoren: PCSX2 (PS2), Rosalie's Mupen GUI (N64), Azahar (3DS), Cemu (Wii U), MAME (Arcade)
  - Spiele: SuperTuxKart, SuperTux, Neverball, Luanti, Xonotic, Hedgewars, Battle for Wesnoth, OpenTTD
  - Medien: Jellyfin, Plex HTPC, Spotify, FreeTube, Strawberry; Kodi bringt jetzt Controller-Unterstützung und Streaming-Add-ons mit
  - Streaming: Netflix, Prime Video, Disney+, Joyn, RTL+, Pluto TV, Twitch
  - Browser: Firefox (normal mit Adressleiste), Chromium, Brave, LibreWolf
  - Werkzeuge: Mission Center, LocalSend (Dateien vom Handy schicken), AntiMicroX (Controller-Belegung)
- Streaming-Apps mit Kopierschutz (Netflix & Co.) schalten in ihrem Firefox-Profil Widevine ein
- AppCenter öffnet schneller: der Installationsstand wird mit je einem Aufruf für alle Apps geprüft statt einzeln

## 0.9.0 – 2026-10-01
- Updates an einer Stelle: Einstellungen → Updates → „Aktualisieren“ prüft und installiert alles in einem Durchgang – Void-Pakete (inkl. Kernel), Flatpaks, AppImages, Proton-GE und VoidStation selbst; was aktuell ist, wird übersprungen
- Das AppCenter hat keine Update-Knöpfe mehr, es ist nur noch fürs Installieren und Entfernen da
- Die Geräte prüfen jetzt auch Systemupdates (alle 6 Stunden). Neue VoidStation-Versionen melden sich sofort und bringen wartende Systemupdates mit; reine Systemupdates meldet der Hinweis unten rechts erst nach 30, 60 oder 90 Tagen (Standard 90, Einstellungen → Updates) – kein tägliches Nachfragen beim Rolling Release. Die Bestätigung listet alle Pakete
- Updates im Terminal (`sudo xbps-install -Su`) werden erkannt: erledigte Updates verschwinden aus der Anzeige, nach einem neuen Kernel erscheint „Neustart nötig“
- Neustart wird nur noch verlangt, wenn er wirklich nötig ist (neuer Kernel oder neue VoidStation-Version)
- Neu im Terminal: `vsctl update` macht dasselbe wie der Knopf in den Einstellungen, mit mitlaufendem Protokoll

## 0.8.3 – 2026-10-01
- Einstellungen passen sich jeder Auflösung und Skalierung an: lange Listen (WLAN, Bluetooth) scrollen mit, statt unter der Hinweiszeile zu verschwinden; lange Namen brechen um
- Seitentitel werden bei wenig Platz kleiner, statt sich mit den Blätter-Pfeilen zu überlappen
- Behoben: bei großer Skalierung (z. B. 2,25× bei 720p) konnte sich die Oberfläche beim Öffnen von Radio aufhängen (Endlosschleife beim Einpassen)

## 0.8.2 – 2026-10-01
- Einstellungen: die obere Kachelreihe wird nicht mehr abgeschnitten, der Fokusrahmen der unteren Reihe überdeckt nicht mehr die Hinweiszeile

## 0.8.1 – 2026-10-01
- Einstellungen übersichtlicher: eine Kachel je Bereich (Sprache, Anzeige, Design, Ton, Netzwerk, Bluetooth, Freigabe, Updates, System) – jede Kachel zeigt den aktuellen Stand, Esc / B führt zurück zur Übersicht
- Wartet ein Update, ist das auf der Kachel „Updates“ zu sehen; U / Select springt direkt dorthin

## 0.8.0 – 2026-09-30
- Designs: Dunkel, Hell, Hoher Kontrast und Nord – unter Einstellungen → Anzeige
- Bildschirmtastatur für Suchfelder und WLAN-Passwort – bedienbar mit Controller, Fernbedienung oder Tastatur
- Bluetooth: Kopfhörer und Controller in den Einstellungen suchen, koppeln, verbinden und entkoppeln (nach dem Update einmal neu starten)
- Spiele: Emulator-Kacheln zeigen die Spiele aus der Freigabe (share/ROMs/<System>) und starten sie direkt
- Fernsehen: Programmvorschau (EPG) mit laufender und nächster Sendung – sobald eine EPG-Quelle eingetragen ist
- Danke an DevSpeX für diese Version!

## 0.7.8 – 2026-09-29
- Installer: Benutzer- und Root-Passwort werden jetzt wirklich gesetzt – bisher blieben beide Konten ohne Passwort, sudo und su schlugen fehl; der Installer prüft das jetzt und bricht sonst ab
- Installiertes System: keine Begrüßung des Live-Sticks („root:voidlinux …“) mehr auf der Textkonsole

## 0.7.7 – 2026-09-29
- Installer: das Passwort für die Windows-Freigabe „share“ wird jetzt wirklich gesetzt – vorher blieb die Freigabe gesperrt (Fehler 0x80004005)
- Dialoge mit langem Text (z. B. „Was ist neu“): Text scrollt mit ↑ ↓, Mausrad oder Steuerkreuz, die Knöpfe bleiben immer sichtbar

## 0.7.6 – 2026-09-29
- Intel-PCs bekommen beim Start den aktuellen CPU-Microcode (intel-ucode) – behebt Hänger älterer Skylake-Geräte mit altem BIOS; auch in der Live-ISO

## 0.7.5 – 2026-09-29
- Installer: nach dem Halten erscheint sofort der Fortschritt (große Kachel mit Prozent, Schritten und Erklärung) – zurück geht es erst nach dem Neustart
- Installer fertig: nur noch „Jetzt neu starten“

## 0.7.4 – 2026-09-29
- Installer: „Löschen und installieren“ blieb hängen – behoben
- mGBA ist nicht mehr vorinstalliert, sondern im AppCenter (Spiele); vorhandene Installationen bleiben
- AppCenter: neuer Bereich „Auf diesem Gerät“ – im Terminal installierte Programme bekommen auf Wunsch eine Kachel
- Bildbetrachter (GPicView) mit schwarzem Hintergrund

## 0.7.3 – 2026-09-29
- Kein „Update“ mehr auf eine ältere Version (z. B. wenn Stable noch hinter dem installierten Stand liegt)
- Live-System: keine Update-Anzeige in den Einstellungen

## 0.7.2 – 2026-09-29
- ISO-Bau: das Einrichtungsskript des Live-Systems ist jetzt ausführbar (Abbruch bei Schritt 7/13 behoben)

## 0.7.1 – 2026-09-29
- ISO-Bau: Pakete, die es in den Void-Quellen nicht mehr gibt (z. B. mesa-vdpau), werden weggelassen statt den Bau abzubrechen

## 0.7.0 – 2026-09-29
- Grafik-Server ist nur noch XLibre – X.Org wird beim Update entfernt, die Auswahl in den Einstellungen entfällt
- Startet die Oberfläche zweimal nicht, wird XLibre einmal neu installiert; danach folgt eine Rettungskonsole
- Fernzugriff (SSH) lässt sich unter Einstellungen → System ein- und ausschalten
- Update-Kanäle heißen jetzt in beiden Sprachen „Stable“ und „Testing“
- htop, nano, fastfetch und der Editor Mousepad sind jetzt immer dabei
- Neu: Live-ISO mit Installer im Kacheldesign – ganze SSD, neben Windows oder Linux, in freien Platz oder selbst einteilen mit GParted

## 0.6.1 – 2026-09-28
- Programme wie VLC, Dateimanager und YouTube starten in der gewählten Sprache
- Pfeile oben rechts zeigen, dass es links oder rechts weitergeht; ein Punkt je Gruppe
- Gruppenweise blättern: LT / RT am Controller, Bild ↑ / Bild ↓ auf der Tastatur
- Update-Hinweis unten rechts mit gelbem Warndreieck – öffnen mit U oder Select am Controller

## 0.6.0 – 2026-09-28
- Sprache: Deutsch oder Englisch, umschaltbar unter Einstellungen → Sprache · Language
- „Was ist neu“ erscheint in der gewählten Sprache
- Uhrzeit, Datum und Zahlen im Format der gewählten Sprache
- Standard-Kacheln werden mitübersetzt, eigene Kachelnamen bleiben unverändert

## 0.5.1 – 2026-09-28
- Umzug nach GitHub (github.com/Panther92/VoidStation) – Geräte beziehen Updates ab jetzt von dort
- Kurzbefehl zur Neuinstallation: xbps-fetch https://panther92.github.io/VoidStation/vs

## 0.5.0 – 2026-09-28
- Grafik-Server: XLibre statt X.Org (Paketquelle xlibre-void, Schlüssel fest hinterlegt)
- Sicherheitsnetz: startet die Oberfläche zweimal nicht, schaltet VoidStation automatisch auf X.Org zurück
- Wahl zwischen XLibre und X.Org unter Einstellungen → System → Grafik-Server

## 0.4.0 – 2026-09-28
- Update-Kanäle: „Stabil“ für alle, „Test“ zum Ausprobieren neuer Versionen
- Updates sind signiert – Geräte installieren nur Updates mit gültiger Signatur
- Automatische Update-Prüfung mit Hinweis auf der Startseite
- Versionsnummern und „Was ist neu“ im Update-Dialog
- Lizenz: GPL-3.0

## 0.3.0 – 2026-09-28
- Update-Knopf: VoidStation aktualisiert sich über die Einstellungen selbst
- Steam nativ aus dem Void-Repo (nonfree + multilib) mit aktuellem Proton-GE
- Startbildschirm bleibt stehen, bis ein Programm wirklich ein Fenster zeigt
- Auflösung: 60 Hz bevorzugt, Halbbild-Modi (1080i) werden vermieden
- Auslagerungsdatei auf Rechnern mit weniger als 8 GB RAM

## 0.2.0 – 2026-09-27
- Neuer Name: VoidStation
- Neuinstallation einer ganzen SSD mit einem Befehl von der offiziellen Void-ISO
- Screenshots, Raster passen sich dem Platz über der Hinweiszeile an

## 0.1.0 – 2026-09-27
- Kacheloberfläche mit WebKit-Startseite, Radio, Fernsehen, AppCenter, Einstellungen
- Samba-Freigabe, dunkles Theme, großer Mauszeiger, EFISTUB
