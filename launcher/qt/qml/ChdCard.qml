// SPDX-License-Identifier: GPL-3.0-or-later
// Karte ueber der Spieleliste: bin/cue-Spiele in CHD umwandeln (launcher.py ChdConvert).
// Ablauf: Frage (ask) -> "Alte Dateien loeschen?" (delete) -> Fortschritt (run) -> Ergebnis (done).
// Die Umwandlung laeuft im Launcher weiter, wenn die Karte zu ist ("Im Hintergrund weiter") – die Spieleliste
// zeigt dann einen Knopf, der die Karte wieder holt.
import QtQuick
import VS

Rectangle {
    id: cc
    property string scope: "chd"
    property bool open: false
    property var tile: null
    property string mode: "ask"                 // ask | delete | run | done
    property var st: null                       // Antwort von /api/roms/chd
    readonly property var job: st && st.job ? st.job : ({})
    readonly property color tint: tile && tile.color ? tile.color : Ui.c.surfaceActive
    signal finished()                           // Spiele haben sich geaendert: Liste neu laden
    z: 28
    color: Ui.c.surfaceOverlay
    visible: open
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function (w) { w.accepted = true } }

    function openFor(t, status) {
        tile = t
        st = status || null
        mode = job.state === "running" ? "run" : "ask"
        open = true
        app.updateLayer()
        refocus()
        refresh()
    }
    function close() {
        if (!open) return
        open = false
        app.updateLayer()
        var m = Nav.remembered(app.layerName, app.layerRoot)
        if (m) app.setFocus(m, true)
        else { var it = Nav.collect(app.layerRoot); if (it.length) app.setFocus(it[0], true) }
    }
    // Zurueck (B, Esc, Rechtsklick): Frage = Nein, Loeschfrage = einen Schritt zurueck, sonst Karte zu
    function handleBack() {
        if (mode === "delete") setMode("ask")
        else if (mode === "ask") decline()
        else if (mode === "done") { close(); finished() }
        else close()
        return true
    }
    function setMode(m) { mode = m; refocus() }
    // Fokus auf den Knopf, der nichts kaputt macht: Frage -> Umwandeln, Loeschfrage -> Behalten
    function refocus() { Qt.callLater(function () { var b = Nav.collect(btns); if (cc.open && b.length) app.setFocus(b[0], true) }) }
    function refresh() {
        var t = tile
        if (!t) return
        Api.get("/api/roms/chd?system=" + encodeURIComponent(t.id), function (j) {
            if (!cc.tile || cc.tile.id !== t.id) return
            var was = cc.job.state
            cc.st = j
            if (cc.mode === "run" && j.job && j.job.state !== "running") { cc.setMode("done"); if (was === "running") cc.finished() }
        }, function () {})
    }
    function decline() {
        Api.post("/api/roms/chd/decline", { system: tile.id }, function () {}, function () {})
        close()
    }
    function start(del) {
        Api.post("/api/roms/chd/start", { system: tile.id, "delete": del }, function (j) {
            var s = Object.assign({}, cc.st || {}); s.job = j.job; cc.st = s
            cc.setMode("run")
        }, function () { app.toast(Ui.t("common.failed"), true); cc.close() })
    }
    function cancel() { Api.post("/api/roms/chd/cancel", { system: tile.id }, function () { cc.refresh() }, function () {}) }

    function sizeText(b) {
        var gb = b / 1073741824
        return gb >= 1 ? Ui.num(Math.round(gb * 10) / 10, 1) + " GB" : Ui.num(Math.max(1, Math.round(b / 1048576)), 0) + " MB"
    }
    function gamesText(n) { return n === 1 ? Ui.t("chd.game1") : Ui.t("chd.games", { n: Ui.num(n) }) }
    readonly property real progress: {
        if (!job.n) return 0
        var part = job.step === "verify" ? 0.8 + (job.pct || 0) * 0.002 : (job.pct || 0) * 0.008
        return Math.max(0, Math.min(1, (Math.max(1, job.i || 1) - 1 + part) / job.n))
    }
    Timer { interval: 1000; repeat: true; running: cc.open && cc.mode === "run"; onTriggered: cc.refresh() }

    Rectangle {
        id: card
        width: Math.min(760 * Ui.f, cc.width - 2 * Ui.padX)
        height: head.height + body.implicitHeight + 2 * pad
        anchors.centerIn: parent
        readonly property real pad: 28 * Ui.f
        color: Ui.c.surfaceDialog
        border.width: 1
        border.color: Ui.c.borderSubtle
        clip: true
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }

        // Kopf in der Farbe der Kachel: viele Dateien -> eine Datei
        Rectangle {
            id: head
            width: parent.width
            height: 132 * Ui.f
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.lighter(cc.tint, 1.25) }
                GradientStop { position: 1; color: Qt.darker(cc.tint, 1.35) }
            }
            Row {
                anchors.centerIn: parent
                spacing: 22 * Ui.f
                // links: ein Blatt (.cue) und seine Spuren (.bin)
                Row {
                    spacing: 6 * Ui.f
                    anchors.verticalCenter: parent.verticalCenter
                    Repeater {
                        model: [".cue", ".bin", ".bin"]
                        Rectangle {
                            width: 64 * Ui.f; height: 76 * Ui.f; radius: 4 * Ui.f
                            color: Ui.alpha("#000000", cc.mode === "done" ? 0.14 : 0.3)
                            border.width: 1; border.color: Ui.alpha("#ffffff", cc.mode === "done" ? 0.16 : 0.42)
                            Txt {
                                anchors.centerIn: parent; text: modelData
                                font.pixelSize: 16 * Ui.f; font.weight: Font.Medium
                                color: "#ffffff"; opacity: cc.mode === "done" ? 0.35 : 0.9
                            }
                        }
                    }
                }
                Glyph { name: "chevright"; color: "#ffffff"; opacity: 0.85; width: 34 * Ui.f; height: width; anchors.verticalCenter: parent.verticalCenter }
                // rechts: eine .chd
                Rectangle {
                    width: 118 * Ui.f; height: 76 * Ui.f; radius: 4 * Ui.f
                    anchors.verticalCenter: parent.verticalCenter
                    color: Ui.alpha("#ffffff", cc.mode === "done" ? 0.95 : 0.16)
                    border.width: 2; border.color: "#ffffff"
                    Row {
                        anchors.centerIn: parent
                        spacing: 8 * Ui.f
                        Glyph { name: "disc"; width: 26 * Ui.f; height: width; anchors.verticalCenter: parent.verticalCenter
                                color: cc.mode === "done" ? Qt.darker(cc.tint, 1.4) : "#ffffff" }
                        Txt { text: ".chd"; font.pixelSize: 20 * Ui.f; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                              color: cc.mode === "done" ? Qt.darker(cc.tint, 1.4) : "#ffffff" }
                    }
                }
            }
        }

        Column {
            id: body
            x: card.pad
            y: head.height + card.pad
            width: card.width - 2 * card.pad
            spacing: 14 * Ui.f

            Txt {
                width: parent.width
                wrapMode: Text.Wrap; elide: Text.ElideNone
                font.pixelSize: 30 * Ui.f; font.weight: Font.Light
                text: cc.mode === "ask" ? Ui.t("chd.askTitle")
                    : cc.mode === "delete" ? Ui.t("chd.delTitle")
                    : cc.mode === "run" ? Ui.t("chd.runTitle")
                    : cc.job.state === "cancelled" ? Ui.t("chd.cancelledTitle")
                    : cc.job.state === "error" ? Ui.t("chd.errorTitle") : Ui.t("chd.doneTitle")
            }
            // Kennzahlen: Frage/Loeschfrage = wie viele Spiele und wie gross, Ergebnis = umgewandelt und gespart
            Row {
                spacing: 10 * Ui.f
                visible: cc.mode !== "run"
                Repeater {
                    model: cc.mode === "done" ? [cc.gamesText(cc.job.ok || 0), Ui.t("chd.saved", { size: cc.sizeText(cc.job.saved || 0) })]
                         : cc.st ? [cc.gamesText(cc.st.count || 0), cc.sizeText(cc.st.bytes || 0)] : []
                    Rectangle {
                        width: chip.implicitWidth + 24 * Ui.f; height: chip.implicitHeight + 12 * Ui.f
                        radius: height / 2
                        color: cc.mode === "done" && index === 1 ? Ui.c.statusOkBg : Ui.c.surfaceCard
                        Txt { id: chip; anchors.centerIn: parent; text: modelData; font.pixelSize: 15 * Ui.f; font.weight: Font.Medium }
                    }
                }
            }
            Txt {
                width: parent.width
                visible: text !== ""
                wrapMode: Text.Wrap; elide: Text.ElideNone
                color: Ui.c.textDim; font.pixelSize: 16 * Ui.f; lineHeight: 1.3
                text: cc.mode === "ask" ? Ui.t("chd.askText")
                    : cc.mode === "delete" ? Ui.t("chd.delText")
                    : cc.mode === "done" ? [cc.job.error === "space" ? Ui.t("chd.space") : "",
                                            cc.job.failed && cc.job.failed.length ? Ui.t("chd.failed", { names: cc.job.failed.join(", ") }) : "",
                                            cc.job.ok && !cc.job["delete"] ? Ui.t("chd.kept") : ""].filter(Boolean).join("\n")
                    : ""
            }
            // Fortschritt: Name des Spiels, Balken ueber alle Spiele, "Spiel 3 von 12 · prueft"
            Column {
                width: parent.width
                visible: cc.mode === "run"
                spacing: 10 * Ui.f
                Txt { width: parent.width; text: cc.job.name || " "; font.pixelSize: 20 * Ui.f; font.weight: Font.Medium }
                Rectangle {
                    width: parent.width; height: 8 * Ui.f; radius: height / 2
                    color: Ui.c.borderSubtle; clip: true
                    Rectangle {
                        height: parent.height; radius: parent.radius
                        color: Ui.c.textPrimary
                        width: parent.width * cc.progress
                        Behavior on width { NumberAnimation { duration: 600 } }
                    }
                }
                Txt {
                    width: parent.width
                    color: Ui.c.textDim; font.pixelSize: 14 * Ui.f
                    text: Ui.t("chd.runOf", { i: Ui.num(Math.max(1, cc.job.i || 1)), n: Ui.num(cc.job.n || 1) }) + "  ·  "
                          + Ui.t(cc.job.step === "verify" ? "chd.stepVerify" : "chd.stepConvert") + "  ·  " + Ui.pct(Math.round(cc.progress * 100))
                }
            }
            Item { width: 1; height: 4 * Ui.f }
            Item {
                id: btns
                width: parent.width
                height: Math.max(askRow.height, delRow.height, runRow.height, doneRow.height)
                Flow {
                    id: askRow; width: parent.width; spacing: 12 * Ui.f; visible: cc.mode === "ask"
                    Btn { text: Ui.t("chd.yes"); onTriggered: cc.setMode("delete") }
                    Btn { text: Ui.t("chd.no"); onTriggered: cc.decline() }
                }
                Flow {
                    id: delRow; width: parent.width; spacing: 12 * Ui.f; visible: cc.mode === "delete"
                    Btn { text: Ui.t("chd.keep"); onTriggered: cc.start(false) }
                    Btn { text: Ui.t("chd.delete"); danger: true; onTriggered: cc.start(true) }
                    Btn { text: Ui.t("common.back"); onTriggered: cc.setMode("ask") }
                }
                Flow {
                    id: runRow; width: parent.width; spacing: 12 * Ui.f; visible: cc.mode === "run"
                    Btn { text: Ui.t("chd.background"); onTriggered: cc.close() }
                    Btn { text: Ui.t("common.cancel"); onTriggered: cc.cancel() }
                }
                Flow {
                    id: doneRow; width: parent.width; spacing: 12 * Ui.f; visible: cc.mode === "done"
                    Btn { text: Ui.t("common.ok"); onTriggered: { cc.close(); cc.finished() } }
                }
            }
        }
    }
}
