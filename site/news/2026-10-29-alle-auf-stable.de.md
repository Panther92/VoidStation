# Ab 2026.11 laufen alle Geräte auf Stable

Mit VoidStation 2026.11 am 6. November ändert sich etwas Grundsätzliches: Die Wahl zwischen *Stable* und *Testing* verschwindet aus dem Installer und aus den Einstellungen. Alle VoidStations laufen dann auf Stable – auch die, auf denen bisher Testing eingestellt war. Testing gibt es weiter, aber nur noch für Tester, und die schalten es im Terminal ein.

## Warum? {#warum}

**Testing ist der Entwicklerstand.** Was neu gebaut wird, landet dort sofort und ungeprüft. Das ist gut zum Ausprobieren, aber nichts für ein Gerät, das abends einfach laufen soll, wenn man nach der Arbeit YouTube oder Fernsehen schauen will.

**Die Frage im Installer war falsch gestellt.** Wer VoidStation einrichtet, kann kaum einschätzen, was hinter „Testing“ steckt – „neue Versionen zuerst“ klingt nach „besser“. Ein Klick, und auf dem Wohnzimmer-PC läuft Code, den noch niemand richtig ausprobiert hat. So eine Entscheidung sollte man nicht nebenbei treffen müssen.

**Testing hilft nur, wenn jemand Fehler meldet.** Die Zeit in Testing soll Fehler finden, bevor sie bei allen ankommen. Das klappt aber nur, wenn die Geräte dort Rückmeldung geben – und genau für diese Leute gibt es Testing jetzt: für unsere eigenen Testgeräte und für alle, die beim Testen mithelfen wollen.

## Was ändert sich für dich? {#fuer-dich}

**Du nutzt Stable** (das ist die Voreinstellung): Es ändert sich nichts.

**Du hattest Testing gewählt:** Dein Gerät wechselt mit 2026.11 von selbst auf Stable. Weil 2026.11 diesmal alles enthält, was bis dahin in Testing lag, verlierst du dabei nichts und musst nichts tun. Bis dahin steht unter Einstellungen → Updates „Kanal Testing“, mit einem Knopf „Zu Stable wechseln“, falls du nicht warten willst.

**Du willst testen:** Im Terminal schaltet `vsctl channel testing` den Entwicklerstand ein (VoidStation fragt vorher nach), `vsctl channel stable` wieder zurück. Fehler bitte als [Issue auf GitHub](https://github.com/Panther92/VoidStation/issues) melden – was dabei hilft, steht unter [Fehler melden](seite:contribute#fehler).

## Diesmal ausnahmsweise alles auf einmal {#ausnahme}

Normalerweise kommt nur in ein Monats-Update, was mindestens 14 Tage in Testing lag (so wie im [Beitrag zu den Kalenderversionen](/news/versionen-nach-kalender/) beschrieben). Damit am 6. November alle Geräte auf demselben Stand landen, nimmt 2026.11 einmalig alles mit, was bis dahin fertig ist. Ab Dienstag, 3. November, kommt nichts Neues mehr dazu, nur noch Fehlerkorrekturen. Ab 2026.12 gelten wieder die 14 Tage.

## Fahrplan {#fahrplan}

- **Freitag, 6. November – VoidStation 2026.11** für alle, das erste große Monats-Update. Was alles drinsteckt, steht wie immer in den News, sobald es da ist. Eine Neuerung gleich vorweg: Updates zeigen kein Protokoll mehr, sondern einen ruhigen Bildschirm mit drei Schritten – Programme aktualisiert, neue Version geladen und geprüft, eingerichtet.
- **Etwa eine Woche später – die Live-ISO 2026.11.** Neu ist vor allem der Installer: Er spricht jetzt alle 13 Sprachen der Oberfläche statt nur Deutsch und Englisch – Deutsch, Englisch, Spanisch, Französisch, Italienisch, Niederländisch, Polnisch, Portugiesisch (Brasilien), Griechisch, Lettisch, Ungarisch, Russisch und Ukrainisch. Neue Installationen laufen immer auf Stable.

Die Übersetzungen sind maschinell entstanden. Wenn dir in deiner Sprache etwas komisch vorkommt, sind Korrekturen auf [GitHub](https://github.com/Panther92/VoidStation) sehr willkommen.
