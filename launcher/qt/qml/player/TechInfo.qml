// SPDX-License-Identifier: GPL-3.0-or-later
// Technik-Anzeige oben links (Select / I): Aufloesung, Codec, Decoder, verworfene Bilder, Puffer – hilft bei Fehlerberichten
import QtQuick
import VS

Rectangle {
    id: ti
    property bool open: false
    readonly property var st: app.st || {}
    z: 44
    x: Ui.padX
    y: 34 * Ui.f
    width: grid.width + 40 * Ui.f
    height: grid.height + 32 * Ui.f
    color: Ui.alpha(Ui.c.surfaceDialog, 0.9)
    border.width: 1
    border.color: Ui.c.borderSubtle
    opacity: open ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    function hw() {
        var h = st.hwdec || ""
        if (!h || h === "no") return Ui.t("player.info.sw")
        return Ui.t("player.info.hw", { api: h })
    }
    function codec() {                           // kurzer Name aus der Spurliste (h264, hevc …), sonst die Beschreibung
        var tr = st.tracks || []
        for (var i = 0; i < tr.length; i++) if (tr[i].type === "video" && tr[i].selected && tr[i].codec) return String(tr[i].codec).toUpperCase()
        return st.codec ? String(st.codec) : "–"
    }
    function res() {
        if (!st.vw) return "–"
        var fps = st.fps ? " · " + Ui.num(Math.round(st.fps * 100) / 100, 2) + " fps" : ""
        return st.vw + " × " + st.vh + fps
    }
    readonly property var lines: [
        [Ui.t("player.info.res"), res()],
        [Ui.t("player.info.codec"), codec()],
        [Ui.t("player.info.decoder"), hw()],
        [Ui.t("player.info.dropped"), String(st.dropped || 0)],
        [Ui.t("player.info.cache"), Ui.t("player.info.secs", { n: Ui.num(Math.round((st.cache || 0) * 10) / 10, 1) })],
        [Ui.t("player.info.level"), Ui.t("player.info.levelN", { n: st.level === undefined ? "–" : st.level })]
    ]
    Grid {
        id: grid
        x: 20 * Ui.f; y: 16 * Ui.f
        columns: 2
        columnSpacing: 22 * Ui.f
        rowSpacing: 6 * Ui.f
        Repeater {
            model: ti.lines.length * 2
            Txt {
                text: ti.lines[Math.floor(index / 2)][index % 2]
                color: index % 2 ? Ui.c.textPrimary : Ui.c.textDim
                font.pixelSize: 14 * Ui.f
                elide: Text.ElideNone
            }
        }
    }
}
