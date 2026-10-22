// SPDX-License-Identifier: GPL-3.0-or-later
// Kachel in YouTube Light: Video (Vorschaubild, Dauer bzw. LIVE, Fortschritt, Spaeter-Marke), Kanal (Bild, Abo-Haken),
// Playlist (Bild, Anzahl) und Aktionen (Symbol + Text)
import QtQuick
import VS

Tile {
    id: yt
    property var it: ({})
    readonly property string kind: it.kind || "action"
    readonly property string thumb: it.thumb ? Ui.url(it.thumb) : ""
    readonly property real progress: it.dur > 0 && it.pos > 0 ? Math.min(1, it.pos / it.dur) : 0
    tileColor: kind === "action" ? (it.color || Ui.c.surfaceActive) : kind === "channel" ? "#3a2f2f" : Ui.c.surfaceCard
    enterDelay: Math.min(index * 14, 400)

    function fmtCount(n) {
        if (!n) return ""
        if (n >= 1e9) return Ui.num(Math.round(n / 1e8) / 10, 1) + " " + Ui.t("yt.unit.bn")
        if (n >= 1e6) return Ui.num(Math.round(n / 1e5) / 10, 1) + " " + Ui.t("yt.unit.mn")
        if (n >= 1e4) return Ui.num(Math.round(n / 1e3), 0) + " " + Ui.t("yt.unit.k")
        return Ui.num(n, 0)
    }
    function ago(ts) {
        if (!ts) return ""
        var d = Date.now() / 1000 - ts
        if (d < 3600) return Ui.t("yt.ago.min", { n: Math.max(1, Math.round(d / 60)) })
        if (d < 86400) return Ui.t("yt.ago.h", { n: Math.round(d / 3600) })
        if (d < 86400 * 14) return Ui.t("yt.ago.d", { n: Math.round(d / 86400) })
        if (d < 86400 * 60) return Ui.t("yt.ago.w", { n: Math.round(d / 86400 / 7) })
        if (d < 86400 * 365) return Ui.t("yt.ago.mo", { n: Math.round(d / 86400 / 30) })
        return Ui.t("yt.ago.y", { n: Math.round(d / 86400 / 365) })
    }
    function sub() {
        if (it.sub && kind === "action") return it.sub
        if (kind === "video") {
            var p = [it.channel || ""]
            if (it.views) p.push(Ui.t("yt.views", { n: fmtCount(it.views) }))
            if (it.published) p.push(ago(it.published))
            return p.filter(function (x) { return x }).join(" · ")
        }
        if (kind === "channel") return it.followers ? Ui.t("yt.followers", { n: fmtCount(it.followers) }) : (it.sub ? Ui.t("yt.subscribed") : "")
        if (kind === "playlist") return [it.channel || "", it.count ? Ui.t("yt.videos", { n: it.count }) : ""].filter(function (x) { return x }).join(" · ")
        return ""
    }

    Image {
        id: img
        anchors.fill: parent
        source: yt.thumb
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize: Qt.size(Math.ceil(width), Math.ceil(height))
        visible: status === Image.Ready
        opacity: yt.progress >= 0.95 ? 0.55 : 0.94           // schon gesehen: blasser
    }
    Glyph {
        visible: img.status !== Image.Ready
        x: (parent.width - width) / 2
        y: parent.height * 0.36 - height / 2
        width: Math.min(parent.width, parent.height) * 0.3; height: width
        name: yt.it.icon || ({ video: "playfill", channel: "user", playlist: "list" })[yt.kind] || "play"
        color: Ui.c.tileText
        opacity: 0.75
    }
    Rectangle {                                    // Lesbarkeit ueber Vorschaubildern
        visible: img.status === Image.Ready
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: parent.height * 0.6
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: "#e0000000" }
        }
    }
    Rectangle {                                    // Dauer bzw. LIVE oben rechts
        visible: yt.kind === "video" && (yt.it.live || yt.it.duration > 0)
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8 * Ui.f
        width: durTxt.implicitWidth + 12 * Ui.f; height: durTxt.implicitHeight + 4 * Ui.f
        color: yt.it.live ? "#c62828" : "#cc000000"
        Txt { id: durTxt; anchors.centerIn: parent; elide: Text.ElideNone; color: "#ffffff"; font.pixelSize: 12 * Ui.f
              font.weight: Font.DemiBold; text: yt.it.live ? "LIVE" : vs.fmtTime(yt.it.duration || 0, "") }
    }
    Rectangle {                                    // Playlist: Anzahl
        visible: yt.kind === "playlist" && yt.it.count > 0
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8 * Ui.f
        width: plRow.width + 12 * Ui.f; height: plRow.height + 4 * Ui.f
        color: "#cc000000"
        Row { id: plRow; anchors.centerIn: parent; spacing: 4 * Ui.f
              Glyph { name: "list"; width: 13 * Ui.f; height: width; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
              Txt { text: String(yt.it.count || ""); color: "#ffffff"; font.pixelSize: 12 * Ui.f; elide: Text.ElideNone } }
    }
    Rectangle {                                    // Spaeter ansehen / abonniert
        visible: (yt.kind === "video" && !!yt.it.later) || (yt.kind === "channel" && !!yt.it.sub)
        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 8 * Ui.f
        width: 24 * Ui.f; height: width; radius: width / 2
        color: "#cc000000"
        Glyph { anchors.centerIn: parent; name: yt.kind === "channel" ? "ok" : "clock"; width: 15 * Ui.f; height: width; color: "#ffffff" }
    }
    Column {
        x: parent.width * 0.05
        width: parent.width * 0.9
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.06 + (yt.progress > 0 ? 7 * Ui.f : 0)
        Txt {
            width: parent.width
            text: yt.it.title || ""
            font.pixelSize: Math.min(yt.height * 0.12, 16 * Ui.f)
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
            text: yt.sub()
            font.pixelSize: Math.min(yt.height * 0.09, 12.5 * Ui.f)
            color: img.status === Image.Ready ? "#c8ffffff" : Ui.c.tileSub
        }
    }
    Bar {
        visible: yt.progress > 0
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 7 * Ui.f
        height: 4 * Ui.f
        value: yt.progress
        fill: "#e53935"
    }
}
