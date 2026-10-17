// SPDX-License-Identifier: GPL-3.0-or-later
// Lautstaerke oben rechts (kurz nach jeder Aenderung)
import QtQuick
import VS

Rectangle {
    id: v
    property real level: 0
    property bool muted: false
    z: 60
    x: parent.width - width - Ui.padX
    y: 34 * Ui.f
    width: row.width + 36 * Ui.f
    height: row.height + 22 * Ui.f
    color: Ui.alpha(Ui.c.surfaceDialog, 0.92)
    border.width: 1
    border.color: Ui.c.borderSubtle
    opacity: 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 200 } }
    function show(lvl, m) {
        level = lvl || 0
        muted = !!m
        opacity = 1
        hideT.restart()
        if (app.player && !app.embedded) app.player.osdText(Ui.t("player.volume") + " " + Ui.pct(Math.round(level)), "1500")
    }
    Timer { id: hideT; interval: 1600; onTriggered: v.opacity = 0 }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 12 * Ui.f
        Glyph { name: "speaker"; width: 22 * Ui.f; height: width; opacity: v.muted ? 0.4 : 1; anchors.verticalCenter: parent.verticalCenter }
        Rectangle {
            width: 150 * Ui.f; height: 6 * Ui.f; radius: height / 2; color: Ui.c.surfaceActive
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                height: parent.height; radius: parent.radius; color: v.muted ? Ui.c.textFaint : Ui.c.textPrimary
                width: parent.width * Math.min(100, Math.max(0, v.level)) / 100
                Behavior on width { NumberAnimation { duration: 150 } }
            }
        }
        Txt {
            text: v.muted ? Ui.t("player.muted") : Ui.pct(Math.round(v.level))
            width: Math.max(implicitWidth, 52 * Ui.f)
            font.pixelSize: 16 * Ui.f
            color: Ui.c.textSecondary
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
