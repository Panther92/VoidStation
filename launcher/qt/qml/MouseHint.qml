// SPDX-License-Identifier: GPL-3.0-or-later
// Kurzer Hinweis, wenn die Controller-Maus per R3 an- oder ausgeht. Kommt nur vor, waehrend ein Programm vorn ist,
// darum wie die heisse Ecke ein eigenes Fenster ohne Fensterverwaltung (X11 override-redirect): liegt auch ueber
// Vollbild-Programmen und nimmt ihnen den Fokus nicht weg. Steht unten rechts wie die Meldungen der Startseite.
import QtQuick
import QtQuick.Window
import VS

Window {
    id: mh
    flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.BypassWindowManagerHint
           | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    transientParent: null
    color: Ui.c.surfaceCard
    visible: false
    width: row.width + 2 * 16 * Ui.f
    height: row.height + 2 * 12 * Ui.f
    property bool on: false

    function show(isOn) {
        on = isOn
        var g = vs.cursorScreen()                       // [x, y, Breite, Hoehe]
        mh.x = g[0] + g[2] - mh.width - 48 * Ui.f
        mh.y = g[1] + g[3] - mh.height - 52 * Ui.f
        visible = true
        raise()
        hideTimer.restart()
    }
    onWidthChanged: if (visible) { var g = vs.cursorScreen(); mh.x = g[0] + g[2] - mh.width - 48 * Ui.f }
    Timer { id: hideTimer; interval: 2200; onTriggered: mh.visible = false }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 1
        border.color: Ui.c.borderSubtle
    }
    Row {
        id: row
        x: 16 * Ui.f
        y: 12 * Ui.f
        spacing: 10 * Ui.f
        Glyph {
            anchors.verticalCenter: parent.verticalCenter
            width: 20 * Ui.f
            height: width
            name: "gamepad"
            color: mh.on ? Ui.c.textPrimary : Ui.c.textFaint
        }
        Txt {
            anchors.verticalCenter: parent.verticalCenter
            text: Ui.t(mh.on ? "pad.mouseOn" : "pad.mouseOff")
            font.pixelSize: 16 * Ui.f
            elide: Text.ElideNone
        }
    }
}
