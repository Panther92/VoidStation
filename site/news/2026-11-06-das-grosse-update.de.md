# Das steckt in VoidStation 2026.11

VoidStation 2026.11 ist da, das erste große Monats-Update. Fernsehen und Medien laufen jetzt in einem eigenen Player, YouTube geht auch ohne Browser, und die Emulatoren lassen sich viel einfacher einrichten. Hier stehen die wichtigsten Neuerungen und was sich für dich ändert. Alles im Detail findest du in den [Änderungen zu 2026.11](/news/v2026.11/).

<div class="screens">
<figure><a href="/assets/screens/7-tv-player.webp"><img src="/assets/screens/7-tv-player.webp" alt="Fernseh-Player mit Senderanzeige und laufender Sendung" loading="lazy" width="1600" height="900"></a><figcaption>Fernsehen: Umschalten direkt im Bild (Szene: Big Buck Bunny, © Blender Foundation, CC BY 3.0)</figcaption></figure>
<figure><a href="/assets/screens/8-mediathek.webp"><img src="/assets/screens/8-mediathek.webp" alt="Musik-Mediathek mit Album-Covern als Kacheln" loading="lazy" width="1600" height="900"></a><figcaption>Videos &amp; Musik: die Mediathek mit Covern</figcaption></figure>
<figure><a href="/assets/screens/9-musik.webp"><img src="/assets/screens/9-musik.webp" alt="Musik-Player mit Cover, Fortschritt und Titelliste" loading="lazy" width="1600" height="900"></a><figcaption>Musik mit Cover, Wiederholen und Zufall</figcaption></figure>
<figure><a href="/assets/screens/11-ton.webp"><img src="/assets/screens/11-ton.webp" alt="Ton-Einstellungen mit Fernseher, USB-Headset und Bluetooth-Lautsprecher" loading="lazy" width="1600" height="900"></a><figcaption>Ton: Geräte statt kryptischer Profile</figcaption></figure>
</div>

## Fernsehen, Videos und Musik im eigenen Player {#player}

**„Videos & Musik“ ersetzt VLC.** Die neue Mediathek zeigt die Freigabe und USB-Laufwerke mit Vorschaubildern, merkt sich, wo du aufgehört hast, und lässt sich ganz mit dem Controller bedienen. Video-DVDs spielt sie auch ab, nur die DVD-Menüs nicht.

**Musik** bekommt ihre Cover von selbst und kennt Wiederholen und Zufallswiedergabe. Mit „Musik suchen“ findest du Titel im Internet Archive, auf YouTube und auf SoundCloud und lädst sie mit Tags und Cover herunter. Welche Quellen du nutzt, entscheidest du selbst, vorausgewählt ist nichts.

**Fernsehen** schaltest du jetzt mit ▲▼ direkt im Bild um, mit Senderlogo, laufender und nächster Sendung. Dazu kommen eine Senderliste mit Favoriten und A–Z-Leiste und die Wahl von Tonspur und Untertiteln. Ist ein Sender nicht erreichbar, sagt VoidStation dir, warum. Wo es geht, übernimmt die Grafikkarte das Dekodieren, das entlastet den Prozessor.

## YouTube Light {#youtube-light}

YouTube Light ist YouTube ohne Browser und ohne Google-Konto, eingebaut in den VoidStation-Player. Abos, Verlauf und Listen bleiben auf deinem Gerät, und deine Abos kannst du aus Google Takeout, NewPipe oder FreeTube übernehmen. Du findest es im AppCenter unter Medien, auf 64 Bit bleibt die normale YouTube-Kachel. YouTube erlaubt fremde Player nicht ausdrücklich, deshalb musst du beim ersten Start einen Hinweis bestätigen.

## Emulatoren {#emulatoren}

- **Tastenbelegung:** Der Knopf in der Spieleliste zeigt eine Skizze der jeweiligen Konsole und fragt die Tasten nacheinander ab.
- **Spieleliste:** Sie zeigt jetzt Bilder zu den Spielen und ist bei fast allen Emulatoren dabei.
- **Einrichtung:** PCSX2, DuckStation und Cemu starten ohne Einrichtungsassistent, die nötigen Einstellungen trägt VoidStation selbst ein.
- **Spielen:** Spiele starten im Vollbild und halten an, solange du auf der Startseite oder in einem anderen Programm bist.
- **Spielstände:** VoidStation sichert sie regelmäßig in die Freigabe.
- **Neu dabei:** xemu für die Original-Xbox.

## Und sonst {#sonst}

- **Updates:** ein ruhiger Vollbild-Bildschirm mit drei Schritten statt eines Protokolls.
- **Startbild:** das Logo statt Textmeldungen beim Hochfahren, jetzt auch auf installierten Geräten.
- **AppCenter:** Programme wie FreeTube, Brave oder Heroic kommen direkt vom Hersteller statt als Flatpak.
- **Netzwerk:** WLAN trennen und wechseln, bekannte Netze ohne neue Passwortabfrage, Kabel oder WLAN fürs Internet bevorzugen.
- **Ton:** Einstellungen → Ton zeigt Geräte statt Profile, neue Kopfhörer können den Ton automatisch übernehmen.
- **Standby:** zu finden unter ⏻. Aufwecken geht per USB-Tastatur, -Maus oder Fernbedienung mit USB-Empfänger.
- **Maus und Controller:** Die heiße Ecke unten rechts führt zur Startseite oder schließt das Programm. Der Controller steuert in Programmen die Maus, und die Hinweise zeigen die Tasten deines Controllers als Symbole.
- **Anzeige:** Der Bildschirm kann sich an die Bildrate des Videos anpassen, etwa auf 50 Hz bei europäischen Sendern. Das ist eine Einstellung und von Haus aus aus.
- **Sprachen:** Die Oberfläche spricht jetzt 15 Sprachen. Die Übersetzungen sind maschinell entstanden, Korrekturen sind sehr willkommen.
- **Terminal:** bessere Tab-Vervollständigung und Suche im Verlauf, Farben passend zum Theme und `vsctl version`.

## Was sich für dich ändert {#fuer-dich}

Du musst nichts von Hand umziehen, aber diese Punkte solltest du kennen:

- **VLC wird samt Kachel entfernt.** Wer VLC für DVD-Menüs oder zum Umwandeln braucht, holt es mit einem Klick zurück: AppCenter → Medien → VLC. Hast du es selbst über das AppCenter installiert, bleibt es.
- **Apps aus dem AppCenter wechseln vom Flatpak zur Herstellerfassung.** Das passiert beim nächsten Aktualisieren. Einstellungen, Logins, Abos und Spielebibliotheken werden übernommen, dabei verschoben und nicht kopiert. Das Flatpak selbst wird entfernt. Bei den Emulatoren werden die Daten kopiert, das Original bleibt als Reserve unter `~/.var/app`.
- **Steam Link und Plex HTPC gibt es nicht mehr im AppCenter,** weil es sie nur als Flatpak gibt. Hast du sie installiert, kannst du sie weiter nutzen. Als Ersatz gibt es Moonlight bzw. Jellyfin oder Kodi.
- **Die „YouTube TV-Oberfläche“ ist weg,** weil Google sie nur noch auf echten Fernsehern zulässt. Kachel und Browser-Profil verschwinden mit dem Update.
- **BIOS-Dateien liegen jetzt je System in `share/ROMs/<system>/bios`.** Dateien aus `share/BIOS` verschiebt VoidStation einmalig selbst. Neue Dateien legst du künftig dort ab.
- **Die Controller-Maus klickt jetzt mit A/B (✕/○)** statt mit R2/L2.
- **Testing-Geräte wechseln von selbst zu Stable.** Die Gründe stehen im [Beitrag vom 29. Oktober](/news/alle-auf-stable/).

## Update und neue ISO {#update}

Installierte Geräte holen sich das Update über **Einstellungen → Updates → Aktualisieren**. Das Startbild wird beim Update eingerichtet, das dauert einmalig etwa eine Minute, und du siehst es ab dem nächsten Neustart.

Am Montag, 9. November, folgt die neue Live-ISO. Ihr Installer und das Startmenü des Sticks sprechen dann ebenfalls alle 15 Sprachen. Für ältere Rechner gibt es außerdem eine experimentelle 32-Bit-ISO, du findest sie auf der [Download-Seite](seite:download).

## Noch nicht dabei {#noch-nicht}

Im [Beitrag zu den 1.000 Downloads](/news/1000-downloads/) hatten wir drei weitere Dinge angekündigt, die noch ausstehen: die Installation auf externe Laufwerke, eigene Layouts der Bildschirmtastatur für Griechisch, Russisch und Ukrainisch sowie Steam mit NVIDIA-Treiber direkt aus dem AppCenter.

## Mitmachen {#mitmachen}

Viele dieser Neuerungen gehen auf Wünsche und Hinweise aus der Community zurück, danke dafür! Fehler und Wünsche nehmen wir weiter gern auf [GitHub](https://github.com/Panther92/VoidStation/issues) entgegen. Und wenn du VoidStation unterstützen möchtest, kannst du uns [einen Kaffee ausgeben](https://buymeacoffee.com/paulvolz92n).
