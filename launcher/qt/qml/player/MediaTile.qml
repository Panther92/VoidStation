// SPDX-License-Identifier: GPL-3.0-or-later
// Kachel der Mediathek: Ordner, Laufwerk, Video (Vorschaubild), Musik (Cover des Ordners); unten der Name,
// bei angefangenen Videos ein Balken, wie weit man gekommen ist
import QtQuick
import VS

Tile {
    id: mt
    property var it: ({})
    property string coverOverride: ""                 // nachgeladenes Cover (Cover-Suche im Hintergrund)
    readonly property string kind: it.kind || "dir"
    readonly property string thumb: coverOverride ? Ui.url(coverOverride) : it.thumb ? Ui.url(it.thumb) : ""
    readonly property real progress: it.resume && it.resume.dur > 0 ? Math.min(1, it.resume.pos / it.resume.dur) : 0
    tileColor: kind === "videos" ? "#2c3f57" : kind === "music" ? "#4a2f45" : kind === "resume" ? Ui.c.accentTv
             : kind === "drive" ? "#33433a" : kind === "playall" ? Ui.c.surfaceActive : kind === "dl" ? "#3d3566" : Ui.c.surfaceCard
    enterDelay: Math.min(index * 18, 500)

    function glyph() {
        return { dir: "folder", videos: "film", music: "music", drive: "usb", video: "film", audio: "music",
                 playall: "playfill", resume: "play", dl: "download" }[kind] || "folder"
    }
    Image {
        id: img
        anchors.fill: parent
        source: mt.thumb
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize: Qt.size(Math.ceil(width), Math.ceil(height))
        visible: status === Image.Ready
        opacity: 0.92
    }
    Glyph {
        visible: img.status !== Image.Ready
        x: (parent.width - width) / 2
        y: parent.height * 0.38 - height / 2
        width: Math.min(parent.width, parent.height) * 0.34; height: width
        name: mt.glyph()
        color: Ui.c.tileText
        opacity: 0.75
    }
    Rectangle {                                    // Lesbarkeit ueber Vorschaubildern
        visible: img.status === Image.Ready
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: parent.height * 0.55
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: "#d9000000" }
        }
    }
    Column {
        x: parent.width * 0.06
        width: parent.width * 0.88
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.07 + (mt.progress > 0 ? 8 * Ui.f : 0)
        Txt {
            width: parent.width
            text: mt.it.title || mt.it.name || ""
            font.pixelSize: Math.min(mt.height * 0.13, 17 * Ui.f)
            font.weight: Font.Medium
            color: img.status === Image.Ready ? "#ffffff" : Ui.c.tileText
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            lineHeight: 1.05
            elide: Text.ElideRight
        }
        Txt {
            width: parent.width
            visible: text !== ""
            text: mt.it.sub || ""
            font.pixelSize: Math.min(mt.height * 0.1, 13 * Ui.f)
            color: img.status === Image.Ready ? "#c8ffffff" : Ui.c.tileSub
        }
    }
    Bar {
        visible: mt.progress > 0
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 8 * Ui.f
        height: 4 * Ui.f
        value: mt.progress
        fill: Ui.c.statusOkText
    }
}
