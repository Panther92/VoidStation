// SPDX-License-Identifier: GPL-3.0-or-later
// Schmale senkrechte Leiste links neben einer scrollenden Liste: zeigt, dass es weitergeht und wo man gerade ist.
// Nur sichtbar, wenn die Liste laenger ist als ihr Platz. Klick oder Ziehen auf der Leiste scrollt mit.
//   ScrollBar { flick: meineListe; x: meineListe.x - width - 8 * Ui.f; y: meineListe.y; height: meineListe.height }
import QtQuick

Item {
    id: sb
    property Flickable flick: null
    readonly property real total: flick ? flick.contentHeight : 0
    readonly property real view: flick ? flick.height : 0
    readonly property real range: Math.max(1, total - view)
    visible: !!flick && total > view + 2
    width: 5 * Ui.f
    Rectangle {                                   // Schiene
        anchors.fill: parent
        radius: width / 2
        color: Ui.alpha(Ui.c.textPrimary, 0.10)
    }
    Rectangle {                                   // Griff: Groesse = sichtbarer Anteil, Lage = Position
        id: thumb
        width: parent.width
        radius: width / 2
        height: Math.max(28 * Ui.f, sb.height * sb.view / Math.max(1, sb.total))
        y: (sb.height - height) * Math.max(0, Math.min(1, (sb.flick ? sb.flick.contentY : 0) / sb.range))
        color: Ui.c.textDim
    }
    MouseArea {
        anchors.fill: parent
        anchors.margins: -8 * Ui.f                // etwas breiter greifen als die Leiste
        function jump(my) {
            var f = Math.max(0, Math.min(1, (my - thumb.height / 2) / Math.max(1, sb.height - thumb.height)))
            sb.flick.contentY = f * sb.range
        }
        onPressed: function (m) { jump(m.y - 8 * Ui.f) }
        onPositionChanged: function (m) { if (pressed) jump(m.y - 8 * Ui.f) }
    }
}
