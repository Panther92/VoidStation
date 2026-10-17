// SPDX-License-Identifier: GPL-3.0-or-later
// Fortschrittsbalken (Sendung, Film, Titel); mit seekable: Klick springt an die Stelle
import QtQuick
import VS

Rectangle {
    id: b
    property real value: 0                       // 0 … 1
    property real buffered: 0                    // 0 … 1, heller Bereich dahinter (Puffer)
    property color fill: Ui.c.textPrimary
    property bool seekable: false
    signal seek(real frac)
    height: 6 * Ui.f
    radius: height / 2
    color: Ui.alpha(Ui.c.textPrimary, 0.18)
    Rectangle {
        visible: b.buffered > b.value
        height: parent.height; radius: parent.radius
        color: Ui.alpha(Ui.c.textPrimary, 0.3)
        width: parent.width * Math.min(1, Math.max(0, b.buffered))
    }
    Rectangle {
        height: parent.height; radius: parent.radius
        color: b.fill
        width: parent.width * Math.min(1, Math.max(0, b.value))
    }
    MouseArea {
        enabled: b.seekable
        anchors.fill: parent
        anchors.margins: -10 * Ui.f
        cursorShape: b.seekable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: function (m) { b.seek(Math.min(1, Math.max(0, (m.x - 10 * Ui.f) / b.width))) }
    }
}
