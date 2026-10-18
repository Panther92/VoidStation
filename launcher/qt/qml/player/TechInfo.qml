// SPDX-License-Identifier: GPL-3.0-or-later
// Technik-Anzeige oben links (Select / I): Aufloesung, Codec, Decoder, verworfene Bilder, Puffer – hilft bei Fehlerberichten.
// Bei Musik stattdessen Format, Bitrate, Abtastrate, Kanaele und Tonausgabe.
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
    // Musik (keine Videospur ausser dem Cover): Ton-Angaben statt Aufloesung und verworfener Bilder
    readonly property bool audioOnly: !(st.tracks || []).some(function (t) { return t.type === "video" && !t.albumart })
    function audioFmt() {                        // "MP3 · 320 kbit/s"
        if (!st.acodec) return "–"
        var c = String(st.acodec).toUpperCase()
        return st.abitrate > 0 ? c + " · " + Ui.num(Math.round(st.abitrate / 1000), 0) + " kbit/s" : c
    }
    function chans(n) {
        if (n === 1) return Ui.t("player.info.mono")
        if (n === 2) return Ui.t("player.info.stereo")
        if (n === 6) return "5.1"
        if (n === 8) return "7.1"
        return n > 0 ? Ui.t("player.info.channels", { n: n }) : ""
    }
    function sampling() {                        // "44,1 kHz · Stereo"
        if (!st.asr) return "–"
        var k = Ui.num(Math.round(st.asr / 100) / 10, st.asr % 1000 ? 1 : 0) + " kHz"
        var c = chans(st.ach || 0)
        return c ? k + " · " + c : k
    }
    function output() {
        var a = String(st.ao || "")
        return { pipewire: "PipeWire", pulse: "PulseAudio", alsa: "ALSA", jack: "JACK", "null": "–" }[a] || (a || "–")
    }
    readonly property var lines: audioOnly ? [
        [Ui.t("player.info.codec"), audioFmt()],
        [Ui.t("player.info.samplerate"), sampling()],
        [Ui.t("player.info.decoder"), Ui.t("player.info.sw")],
        [Ui.t("player.info.output"), output()],
        [Ui.t("player.info.cache"), Ui.t("player.info.secs", { n: Ui.num(Math.round((st.cache || 0) * 10) / 10, 1) })]
    ] : [
        [Ui.t("player.info.res"), res()],
        [Ui.t("player.info.codec"), codec()],
        [Ui.t("player.info.decoder"), hw()],
        [Ui.t("player.info.audio"), [audioFmt(), sampling()].filter(function (x) { return x !== "–" }).join(" · ") || "–"],
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
