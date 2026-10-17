// SPDX-License-Identifier: GPL-3.0-or-later
// Knoepfe oben rechts fuer die Maus – erscheinen, sobald sie bewegt wird, und verschwinden nach 3 s Ruhe
import QtQuick
import VS

Row {
    id: mb
    property var buttons: []                     // [{icon, tip, act: function}]
    property bool hovered: false
    z: 46
    anchors.right: parent.right; anchors.rightMargin: Ui.padX
    y: 30 * Ui.f
    spacing: 10 * Ui.f
    opacity: 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 200 } }
    function poke() { opacity = 1; hideT.restart() }
    Timer { id: hideT; interval: 3000; onTriggered: if (!mb.hovered) mb.opacity = 0; else restart() }
    Repeater {
        model: mb.buttons
        Rectangle {
            id: btn
            width: 50 * Ui.f; height: width; radius: width / 2
            color: ma.containsMouse ? Ui.c.surfaceCardHover : Ui.alpha(Ui.c.surfaceDialog, 0.88)
            border.width: ma.containsMouse ? 2 : 1
            border.color: ma.containsMouse ? Ui.c.borderFocus : Ui.c.borderMuted
            Glyph { anchors.centerIn: parent; name: modelData.icon; width: parent.width * 0.44; height: width }
            Rectangle {                              // Beschriftung unter dem Knopf
                visible: ma.containsMouse && !!modelData.tip
                anchors.top: parent.bottom; anchors.topMargin: 8 * Ui.f
                anchors.horizontalCenter: parent.horizontalCenter
                width: tipTxt.implicitWidth + 18 * Ui.f
                height: tipTxt.implicitHeight + 10 * Ui.f
                color: Ui.alpha(Ui.c.surfaceDialog, 0.95)
                Txt { id: tipTxt; anchors.centerIn: parent; text: modelData.tip || ""; font.pixelSize: 13 * Ui.f; elide: Text.ElideNone }
            }
            MouseArea {
                id: ma
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onContainsMouseChanged: { mb.hovered = containsMouse; mb.poke() }
                onClicked: modelData.act()
            }
        }
    }
}
