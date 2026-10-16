# Neue Versionsnummern: VoidStation geht nach dem Kalender

Die nächste VoidStation heißt nicht 0.16.0, sondern **2026.11**. Ab jetzt sagt die Versionsnummer, *wann* eine Version erschienen ist – Jahr und Monat. Dazu kommt ein fester Rhythmus: jeden Monat ein Update für alle, alle drei Monate eine neue Live-ISO.

> Nachtrag vom 16. Oktober 2026: Die erste Kalendernummer kam einen Monat früher als angekündigt. Drei Fehlerkorrekturen – Abo-Import in FreeTube, das Farbschema der Programme und die Blätter-Pfeile auf der Startseite – sollten nicht bis November warten. Weil es auf Stable noch keine Kalendernummer gab, an die ein Hotfix wie „.1“ hätte anschließen können, heißt diese Korrektur **2026.10**. Am Plan ändert sich nichts: Das erste reguläre Monats-Update mit neuen Funktionen ist 2026.11 Anfang November, Hotfixes heißen ab jetzt wie beschrieben 2026.10.1, 2026.11.1 usw.

## Warum? {#warum}

**VoidStation steht auf einem Rolling Release.** Void Linux bekommt laufend neue Pakete, es gibt kein „Void 5“ und kein „Void 6“. Eine VoidStation-ISO ist deshalb immer ein Schnappschuss: VoidStation plus alle Void-Pakete vom Tag des Baus. Bei so einem Schnappschuss ist das Datum die ehrlichste Angabe – genau so machen es auch Arch Linux bei seinen ISOs oder Ubuntu mit Nummern wie 24.04.

**Die alten Nummern haben mehr versprochen, als sie sagen.** Bei 0.15.0 fragt man sich: Ist das noch eine Beta? Was kommt mit 1.0? Ist 0.16 ein großer Schritt oder ein kleiner? Bei VoidStation kommen Neuerungen Stück für Stück, nicht in großen Sprüngen – eine Zahl, die Meilensteine andeutet, passt dazu nicht.

**Du siehst sofort, wie aktuell etwas ist.** 2026.11 und 2027.05 – da ist ohne Nachschlagen klar, was neuer ist und wie viel Zeit dazwischen liegt. Das gilt für dein Gerät genauso wie für die ISO auf der [Downloadseite](seite:download).

**Ein fester Rhythmus macht VoidStation verlässlicher.** Mit den neuen Nummern kommt eine feste Reihenfolge, wie Neues zu dir gelangt – dazu gleich mehr.

## So läuft es ab jetzt {#ablauf}

- **Testing zuerst:** Jede Neuerung landet zuerst im Kanal *Testing* und bleibt dort mindestens 14 Tage, auf mehreren Geräten im täglichen Einsatz.
- **Einmal im Monat für alle:** Was sich in Testing bewährt hat, geht Anfang des Monats als Update an alle Geräte im Kanal *Stable* – das ist dann z. B. Version 2026.11. Ist in einem Monat nichts reif, gibt es eben kein Update; leere Versionen nur fürs Datum gibt es nicht.
- **Fehler werden nicht aufgeschoben:** Ein Fehler in Stable wartet nicht bis zum nächsten Monat. Die Korrektur kommt nach kurzer Probe sofort als Hotfix, z. B. 2026.11.1.
- **Alle drei Monate eine neue Live-ISO:** im Februar, Mai, August und November, jeweils kurz nach dem Update des Monats. Die ISO trägt dieselbe Nummer wie die Version, die sie enthält – in `voidstation-2026.11-20261108.iso` steht vorn die Version und hinten der Tag, an dem sie gebaut wurde.

## Was ändert sich für dich? {#fuer-dich}

**Nichts, was du tun musst.** Deine VoidStation aktualisiert sich wie bisher über Einstellungen → Updates, und nach 0.15.0 kommt einfach 2026.11. Alte Versionsnummern bleiben im Verlauf stehen, wie sie sind.

Wenn du den Kanal *Testing* nutzt, siehst du dort Nummern wie `2026.11+testing.20261120` – das heißt: Stand nach 2026.11, letzte Änderung am 20. November. Wechselst du von Testing zurück auf Stable, wartet dein Gerät wie bisher, bis Stable aufgeholt hat, statt auf eine ältere Version zurückzuspringen.

Die erste Version nach dem neuen Schema ist für Anfang November geplant, die erste Live-ISO dazu kurz danach. Wer genau wissen will, wie Versionen entstehen, findet alles in [RELEASING.md auf GitHub](https://github.com/Panther92/VoidStation/blob/main/RELEASING.md).
