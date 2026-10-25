// SPDX-License-Identifier: GPL-3.0-or-later
// Skizze einer Konsole fuer die Tastenbelegung (KeymapLayer): Gehaeuse, Bildschirm, Tasten an ihrer Lage.
// Schlichte Umrisse ohne Logos und Schriftzuege. Je Konsole ein Eintrag in `specs` (Einheiten w × h);
// die Kennungen der Tasten sind die aus EMU_LAYOUTS im Launcher.
// cur = Taste, die gerade abgefragt wird (pulsiert), done = in diesem Durchgang schon belegt (dezent gruen),
// screenText = Text im Bildschirm (die gefragte Taste – auch Extras wie "Savestate speichern", die es auf der
// Konsole nicht gibt).
import QtQuick
import VS

Item {
    id: pic
    property string kind: "gba"
    property string cur: ""
    property var done: []
    property string screenText: ""
    readonly property var specs: ({
        // Game Boy Advance: quer, Bildschirm in der Mitte, Kreuz links, A/B rechts, L/R oben, Start/Select links unten
        gba: {
            w: 100, h: 62,
            body: "M14 6H86C95 6 99 14 99 26V40C99 52 92 58 82 58C74 58 70 54 64 54H36C30 54 26 58 18 58"
                + "C8 58 1 52 1 40V26C1 14 5 6 14 6Z",
            screen: { x: 29, y: 11, w: 42, h: 34, r: 2 },
            keys: [
                { id: "L", t: "L", x: 18, y: 5, w: 18, h: 4.2, r: 2.1 },
                { id: "R", t: "R", x: 82, y: 5, w: 18, h: 4.2, r: 2.1 },
                { id: "Up", t: "▲", x: 16, y: 20.4, w: 4.6, h: 4.8, r: 0.6 },
                { id: "Down", t: "▼", x: 16, y: 29.6, w: 4.6, h: 4.8, r: 0.6 },
                { id: "Left", t: "◀", x: 11.4, y: 25, w: 4.8, h: 4.6, r: 0.6 },
                { id: "Right", t: "▶", x: 20.6, y: 25, w: 4.8, h: 4.6, r: 0.6 },
                { id: "A", t: "A", x: 88.5, y: 22, w: 8.4, h: 8.4, r: 4.2 },
                { id: "B", t: "B", x: 79, y: 28.5, w: 8.4, h: 8.4, r: 4.2 },
                { id: "Start", t: "Start", x: 16, y: 40.5, w: 11, h: 3.8, r: 1.9 },
                { id: "Select", t: "Select", x: 16, y: 46.5, w: 11, h: 3.8, r: 1.9 }
            ]
        }
    })
    readonly property var spec: specs[kind] || specs.gba
    readonly property real k: width / spec.w
    height: width * spec.h / spec.w

    function fill(id) {
        if (id === cur) return Ui.c.borderFocus
        if (done.indexOf(id) >= 0) return Ui.alpha(Ui.c.statusOkBg, 0.6)
        return Ui.c.surfaceCard
    }

    Canvas {
        id: body
        anchors.fill: parent
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.scale(pic.k, pic.k)
            c.path = pic.spec.body
            c.fillStyle = String(Ui.c.surfaceRaised)
            c.fill()
            c.lineWidth = 0.5
            c.strokeStyle = String(Ui.c.borderMuted)
            c.stroke()
        }
        onWidthChanged: requestPaint()
        Connections { target: vs; function onThemeChanged() { body.requestPaint() } }
        Connections { target: pic; function onKindChanged() { body.requestPaint() } }
    }
    // Bildschirm (zeigt die gefragte Taste)
    Rectangle {
        visible: !!pic.spec.screen
        x: pic.spec.screen.x * pic.k; y: pic.spec.screen.y * pic.k
        width: pic.spec.screen.w * pic.k; height: pic.spec.screen.h * pic.k
        radius: pic.spec.screen.r * pic.k
        color: Ui.c.bgMain
        border.width: Math.max(1, 0.4 * pic.k)
        border.color: Ui.c.borderMuted
        Txt {
            anchors.centerIn: parent
            width: parent.width - 4 * pic.k
            horizontalAlignment: Text.AlignHCenter
            text: pic.screenText
            color: Ui.c.textPrimary
            font.pixelSize: Math.max(12, (text.length > 3 ? 4.2 : 9) * pic.k)
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            elide: Text.ElideNone
        }
    }
    Repeater {
        model: pic.spec.keys
        Rectangle {
            readonly property var kd: modelData
            x: (kd.x - kd.w / 2) * pic.k
            y: (kd.y - kd.h / 2) * pic.k
            width: kd.w * pic.k
            height: kd.h * pic.k
            radius: kd.r * pic.k
            color: pic.fill(kd.id)
            border.width: Math.max(1, 0.25 * pic.k)
            border.color: kd.id === pic.cur ? Ui.c.borderFocus : pic.done.indexOf(kd.id) >= 0 ? Ui.c.statusOkText : Ui.c.borderMuted
            SequentialAnimation on opacity {
                running: kd.id === pic.cur
                loops: Animation.Infinite
                alwaysRunToEnd: true
                NumberAnimation { to: 0.45; duration: 450; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 1; duration: 450; easing.type: Easing.InOutQuad }
            }
            Txt {
                anchors.centerIn: parent
                text: kd.t
                color: kd.id === pic.cur ? Ui.c.bgMain : Ui.c.textPrimary
                font.pixelSize: Math.max(8, Math.min(parent.height * 0.55, 2.6 * pic.k))
                font.weight: Font.DemiBold
                elide: Text.ElideNone
            }
        }
    }
}
