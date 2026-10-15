// SPDX-License-Identifier: GPL-3.0-or-later
// Heisse Ecke unten rechts: Ist ein Programm vorn und bleibt die Maus kurz ganz in der Ecke,
// klappt hier ein kleines Feld auf – Startseite (Programm laeuft weiter, wie Win / Guide) oder App schliessen
// (das Programm im Vordergrund). Ausgeloest wird erst per Klick, eine Maus, die zufaellig in der Ecke parkt, stoert nicht.
// Eigenes Fenster ohne Fensterverwaltung (X11 override-redirect): liegt so auch ueber Vollbild-Programmen
// und nimmt ihnen den Tastaturfokus nicht weg.
import QtQuick
import QtQuick.Window
import VS

Window {
    id: cw
    flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.BypassWindowManagerHint
           | Qt.WindowDoesNotAcceptFocus
    transientParent: null
    color: Ui.c.surfaceDialog
    visible: false
    width: box.width + 2 * pad
    height: box.height + 2 * pad

    property real pad: 10 * Ui.f
    property real tileS: 128 * Ui.f
    property var front: null              // Kachel des Programms im Vordergrund (null: unbekannt -> nur Startseite)
    property real rightX: 0
    property real bottomY: 0
    property int awayMs: 0
    property bool asking: false

    signal goHome()
    signal closeFront(var t)

    // right / bottom: rechte und untere Kante (letztes Pixel) des Bildschirms, auf dem der Zeiger steht
    property real askT0: 0
    function openAt(right, bottom) {
        if (asking && Date.now() - askT0 < 3000) return    // Antwort steht noch aus (nach 3 s neu fragen)
        asking = true
        askT0 = Date.now()
        awayMs = 0
        vs.log("Ecke: getroffen bei " + right + "," + bottom + " – frage, welches Programm vorn ist")
        Api.get("/api/front", function (r) { place(right, bottom, r && r.id ? Ui.app.tileById(r.id) : null) },
                function (e) { vs.log("Ecke: /api/front fehlgeschlagen: " + e); place(right, bottom, null) })
    }
    function place(right, bottom, t) {
        asking = false
        front = t
        rightX = right
        bottomY = bottom
        cw.x = right - cw.width + 1
        cw.y = bottom - cw.height + 1
        visible = true
        raise()
        vs.log("Ecke: Feld offen " + cw.width + "x" + cw.height + " bei " + cw.x + "," + cw.y
               + ", sichtbar: " + cw.visible + ", vorn: " + (t ? t.id : "unbekannt"))
    }
    function close(why) {                               // front bleibt bis zum naechsten Oeffnen (place)
        if (visible) vs.log("Ecke: Feld zu (" + (why || "Startseite vorn") + ")")
        visible = false
        awayMs = 0
    }
    onWidthChanged: if (visible) cw.x = rightX - cw.width + 1
    onHeightChanged: if (visible) cw.y = bottomY - cw.height + 1

    Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1; border.color: Ui.c.borderMuted }
    HoverHandler { id: hov }

    Row {
        id: box
        x: cw.pad
        y: cw.pad
        spacing: 8 * Ui.f
        Repeater {
            model: cw.front ? ["home", "close"] : ["home"]     // Startseite zuerst, daneben (an der Ecke) App schliessen
            Rectangle {
                width: cw.tileS
                height: cw.tileS
                color: ma.containsMouse ? Ui.c.surfaceCardHover : Ui.c.surfaceCard
                border.width: ma.containsMouse ? 2 : 0
                border.color: Ui.c.borderFocus
                Glyph {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: parent.height * 0.18
                    width: parent.width * 0.34
                    height: width
                    name: modelData === "home" ? "home" : "bad"
                    color: Ui.c.textPrimary
                }
                Txt {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 10 * Ui.f
                    text: Ui.t(modelData === "home" ? "corner.home" : "corner.close")
                    font.pixelSize: 15 * Ui.f
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    // erst ausloesen, dann zu: Schliessen baut sonst diese Kachel ab, solange der Klick noch laeuft
                    onClicked: {
                        if (modelData === "home") cw.goHome()
                        else cw.closeFront(cw.front)
                        cw.close(modelData === "home" ? "Startseite gewaehlt" : "App schliessen gewaehlt")
                    }
                }
            }
        }
    }

    // Wieder zu, sobald die Maus eine Sekunde lang weder ueber dem Feld noch in der Ecke ist
    Timer {
        interval: 200
        repeat: true
        running: cw.visible
        onTriggered: {
            if (hov.hovered || vs.cornerHit().length) { cw.awayMs = 0; return }
            cw.awayMs += interval
            if (cw.awayMs >= 1000) cw.close("Maus weg")
        }
    }
}
