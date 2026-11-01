// SPDX-License-Identifier: GPL-3.0-or-later
// Tastenbelegung eines Emulators (aus dessen Spieleliste): Skizze der Konsole, deren Tasten nacheinander abgefragt
// werden – man drueckt jeweils die Controllertaste, die dafuer gelten soll. Daneben die aktuelle Belegung; eine Taste
// waehlen: neu belegen oder frei lassen. Gilt nur fuer den Emulator, die Startseite bedient sich weiter wie bisher.
// Daten: /api/keymap (launcher.py, ~/.config/voidstation/emu-pads.json). Waehrend einer Abfrage haelt der Launcher
// den Controller exklusiv: die Druecke bedienen dann nicht die Oberflaeche. Abbrechen: PS-/Guide-Taste, Esc, Maus.
import QtQuick
import VS

Layer {
    id: km
    scope: "keymap"
    track: trk
    title: Ui.t("keymap.title")
    property var tile: null
    property var kd: null                        // Antwort von /api/keymap
    property string padPath: ""
    property string mode: ""                     // "" | "learn"
    property var queue: []                       // noch abzufragende Tasten dieses Durchgangs
    property int total: 0
    property string cur: ""
    property var session: ({})                   // in diesem Durchgang belegt: Taste -> Bindung
    property int secs: 0
    property int token: 0                        // veraltete Antworten nach Abbrechen ignorieren
    property string lastKey: ""
    property string edit: ""                     // in der Liste gewaehlte Taste: neu belegen oder frei lassen?
    readonly property var keys: kd ? kd.buttons.filter(function (b) { return !b.action }) : []
    readonly property var extras: kd ? kd.buttons.filter(function (b) { return b.action }) : []
    // Viele Tasten (PlayStation-Pad …): drei Spalten und eine etwas kleinere Skizze
    readonly property bool many: keys.length > 12
    readonly property int cols: many ? 3 : 2
    readonly property real cellW: Ui.screenW * (many ? 0.17 : 0.23)
    readonly property real listW: cols * cellW + (cols - 1) * 8 * Ui.f
    // Linke Spalte: mindestens so breit, dass die Erklaerung in wenigen Zeilen unter die Skizze passt
    readonly property real leftW: Math.max(picW, Ui.screenW * 0.3)
    // Skizze so gross, dass darunter Knopf und Erklaerung (mit Hinweisen des Emulators mehr) Platz haben
    readonly property real picW: Math.min(Ui.screenW * (many ? 0.3 : 0.36),
                                          Math.max(Ui.screenW * 0.22, (stage.height - (kd && kd.notes && kd.notes.length > 1 ? 300 : 250) * Ui.f) / pic.aspect))
    // Tasten, die ueberall gleich heissen, als Zeichen (Rest: Texte keymap.btn.*, sonst die Kennung)
    readonly property var symbols: ({ Cross: "✕", Circle: "○", Square: "□", Triangle: "△" })

    function openFor(t) {
        tile = t
        kd = null
        mode = ""
        edit = ""
        app.openLayer(km)
        load("kmall")
    }
    // Die Spieleliste darunter ausblenden: die Ebenen sind leicht durchscheinend
    onOpened: if (roms.open) roms.opacity = 0
    onClosed: { if (mode) stop(false); if (roms.open) roms.opacity = 1 }
    onOpenChanged: if (!open && roms.open) roms.opacity = 1
    function firstFocus() { return Nav.collect(trk)[0] || null }
    function load(focusKey) {
        if (!tile) return
        Api.get("/api/keymap?emu=" + encodeURIComponent(tile.id) + "&path=" + encodeURIComponent(padPath), function (j) {
            kd = j
            padPath = j.pad ? j.pad.path : ""
            Qt.callLater(function () { refocus(focusKey) })
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }
    function refocus(k) {
        if (!km.open) return
        var it = Nav.collect(trk)
        for (var i = 0; i < it.length; i++) if (k && it[i].key === k) return app.setFocus(it[i], true)
        var inTrack = false
        for (var p = Nav.current; p; p = p.parent) if (p === trk) inTrack = true
        if (!inTrack && it.length) app.setFocus(it[0], true)
    }
    function btnText(id) { return Ui.t("keymap.btn." + id, null, symbols[id] || id) }
    function infoText() {
        if (!kd) return ""
        var t = Ui.t("keymap.info", { name: kd.name })
        for (var i = 0; i < (kd.notes || []).length; i++) t += " " + Ui.t("keymap.note." + kd.notes[i])
        return t
    }
    function ctrlText(b) {
        if (!b || !b.label) return Ui.t("keymap.unset")
        return b.label                           // Steuerkreuz: nur der Pfeil (die Konsolentaste nennt "Kreuz" schon)
    }
    function btn(id) { return kd ? (kd.buttons.filter(function (b) { return b.id === id })[0] || null) : null }
    function handleBack() {
        if (mode) { stop(false); return true }
        if (edit) { closeEdit(); return true }
        return false
    }

    // ---- Taste aus der Liste gewaehlt: neu belegen, frei lassen oder zurueck
    function openEdit(id) {
        edit = id
        Qt.callLater(function () { refocus("kmrebind") })
    }
    function closeEdit() {
        var id = edit
        edit = ""
        Qt.callLater(function () { refocus("kmb" + id) })
    }
    function clearOne(id) {
        Api.post("/api/keymap/set", { emu: tile.id, path: padPath, button: id, bind: null }, function (j) {
            kd = j
            app.toast(Ui.t("keymap.cleared", { btn: btnText(id) }))
            closeEdit()
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }

    // ---- Abfrage: eine Taste nach der anderen, je bis zu 10 s; nichts gedrueckt = bleibt, wie sie ist
    function learnAll() { start(kd.buttons.map(function (b) { return b.id }), "kmall") }
    function learnOne(id) { edit = ""; start([id], "kmb" + id) }
    function start(ids, back) {
        if (!kd || !kd.pad) return
        lastKey = back
        queue = ids; total = ids.length; session = ({}); mode = "learn"
        Qt.callLater(function () { refocus("kmcancel") })
        next()
    }
    function next() {
        if (mode !== "learn") return
        if (!queue.length) return finish()
        cur = queue[0]
        var t = ++token
        secs = 10
        tick.restart()
        Api.post("/api/keymap/capture", { path: padPath, timeout: 10, rstick: !!(kd && kd.rstick) }, function (r) {
            if (t !== token || mode !== "learn") return
            if (!r || r.cancelled) return
            if (r.cancel) return stop(true)
            if (r.timeout || !r.bind) { queue = queue.slice(1); return next() }
            var dup = ""
            for (var k in session) if (k !== cur && JSON.stringify(session[k]) === JSON.stringify(r.bind)) dup = k
            if (dup) { app.toast(Ui.t("keymap.dup", { btn: btnText(dup) }), true); return next() }
            var id = cur
            Api.post("/api/keymap/set", { emu: tile.id, path: padPath, button: id, bind: r.bind }, function (j) {
                if (t !== token || mode !== "learn") return
                kd = j
                var s = Object.assign({}, session); s[id] = r.bind; session = s       // neues Objekt: Bild aktualisiert
                if (total === 1 && j.swapped && j.swapped.length) {
                    var o = btn(j.swapped[0])
                    app.toast(Ui.t("keymap.swapped", { btn: btnText(j.swapped[0]), key: ctrlText(o) }))
                }
                queue = queue.slice(1)
                next()
            }, function (e) { stop(false); app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
        }, function (e) {
            if (t !== token) return
            stop(false)
            app.toast(Ui.t("common.failedMsg", { msg: e }), true)
        })
    }
    function finish() {
        token++
        tick.stop()
        mode = ""
        cur = ""
        session = ({})
        if (total > 1) app.toast(Ui.t("keymap.saved", { name: kd ? kd.name : "" }))
        Qt.callLater(function () { refocus(lastKey) })
    }
    function stop(byPad) {
        token++
        tick.stop()
        var was = mode
        mode = ""
        cur = ""
        session = ({})
        if (!byPad) Api.post("/api/keymap/cancel", null)
        if (was && km.open) Qt.callLater(function () { refocus(lastKey) })
    }
    function reset() {
        Api.post("/api/keymap/reset", { emu: tile.id, path: padPath }, function (j) {
            kd = j
            app.toast(Ui.t("keymap.resetDone"))
            Qt.callLater(function () { refocus("kmall") })
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }
    Timer { id: tick; interval: 1000; repeat: true; onTriggered: if (km.secs > 0) km.secs-- }

    headRight: NowLine {
        main: km.kd ? km.kd.name : ""
        sub: km.kd ? (km.kd.pad ? km.kd.pad.name : Ui.t("keymap.noPadShort")) : ""
    }

    Track {
        id: trk
        anchors.fill: parent
        // Konsole: Skizze, Abfrage, alle nacheinander / Standard
        SetGroup {
            availH: km.stage.height
            maxW: km.leftW
            title: km.kd ? km.kd.sub : ""
            ConsolePic {
                id: pic
                width: km.picW
                kind: km.kd ? km.kd.console : "gba"
                cur: km.cur || km.edit
                done: Object.keys(km.session)
                screenText: km.mode === "learn" ? km.btnText(km.cur) : ""
            }
            Txt {
                visible: km.mode === "learn"
                width: km.leftW
                text: km.mode === "learn" ? Ui.t("keymap.press", { btn: km.btnText(km.cur) }) : ""
                font.pixelSize: 22 * Ui.f
                wrapMode: Text.Wrap
                elide: Text.ElideNone
            }
            Txt {
                visible: km.mode === "learn"
                width: km.leftW
                color: Ui.c.textDim
                text: km.total > 1 ? Ui.t("keymap.step", { n: km.total - km.queue.length + 1, total: km.total, s: km.secs })
                                   : Ui.t("keymap.stepOne", { s: km.secs })
                wrapMode: Text.Wrap
                elide: Text.ElideNone
            }
            Info { visible: !!km.kd && !km.kd.pad; width: km.leftW; html: Ui.esc(Ui.t("keymap.noPad")) }
            SetRow {                                 // gewaehlte Taste: neu belegen / frei lassen
                width: km.leftW
                visible: km.edit !== "" && !km.mode
                label: km.edit ? Ui.t("keymap.editLabel", { btn: km.btnText(km.edit), key: km.ctrlText(km.btn(km.edit)) }) : ""
                Pill { property string key: "kmrebind"; text: Ui.t("keymap.rebind"); onTriggered: km.learnOne(km.edit) }
                Pill { property string key: "kmclear"; text: Ui.t("keymap.clear"); enabled: !!km.btn(km.edit) && !!km.btn(km.edit).bind; onTriggered: km.clearOne(km.edit) }
                Pill { property string key: "kmeditback"; text: Ui.t("common.back"); onTriggered: km.closeEdit() }
            }
            SetRow {
                width: km.leftW
                visible: !!km.kd && !!km.kd.pad && km.edit === ""
                Pill { property string key: "kmall"; visible: !km.mode; text: Ui.t("keymap.all"); onTriggered: km.learnAll() }
                Pill { property string key: "kmreset"; visible: !km.mode && !!km.kd && km.kd.custom; text: Ui.t("keymap.reset"); onTriggered: km.reset() }
                Pill { property string key: "kmcancel"; visible: km.mode !== ""; text: Ui.t("common.cancel"); onTriggered: km.stop(false) }
            }
            Info { visible: km.mode === "learn"; width: km.leftW; html: Ui.t("keymap.learnHint") }
            // Erklaerung und Hinweise des Emulators: etwas kleiner, damit sie unter die Skizze passen
            Info {
                visible: !km.mode && !km.edit && !!km.kd && !!km.kd.pad
                width: km.leftW
                html: km.infoText()
                font.pixelSize: 14 * Ui.f
                lineHeight: 1.35
            }
        }
        // Belegung: Konsolentaste -> Controllertaste; waehlen = nur diese Taste neu
        SetGroup {
            visible: !!km.kd && !!km.kd.pad
            availH: km.stage.height
            maxW: km.listW
            title: Ui.t("keymap.mapping")
            Grid {
                columns: km.cols
                spacing: 8 * Ui.f
                Repeater {
                    model: km.keys
                    Pill {
                        property string key: "kmb" + modelData.id
                        width: km.cellW
                        maxWidth: km.cellW
                        text: km.btnText(modelData.id) + "   →   " + km.ctrlText(modelData)
                        on: km.cur === modelData.id || km.edit === modelData.id
                        dim: !modelData.bind
                        enabled: !km.mode
                        onTriggered: km.edit === modelData.id ? km.closeEdit() : km.openEdit(modelData.id)
                    }
                }
            }
            Txt { visible: km.extras.length > 0; text: Ui.t("keymap.extras"); color: Ui.c.textFaint; font.pixelSize: 14 * Ui.f; topPadding: 6 * Ui.f }
            Grid {
                columns: 2
                spacing: 8 * Ui.f
                Repeater {
                    model: km.extras
                    Pill {
                        property string key: "kmb" + modelData.id
                        width: (km.listW - 8 * Ui.f) / 2
                        maxWidth: (km.listW - 8 * Ui.f) / 2
                        text: km.btnText(modelData.id) + "   →   " + km.ctrlText(modelData)
                        on: km.cur === modelData.id || km.edit === modelData.id
                        dim: !modelData.bind
                        enabled: !km.mode
                        onTriggered: km.edit === modelData.id ? km.closeEdit() : km.openEdit(modelData.id)
                    }
                }
            }
            SetRow {
                width: km.listW
                visible: !!km.kd && km.kd.pads.length > 1
                label: Ui.t("keymap.pads")
                Repeater {
                    model: km.kd ? km.kd.pads : []
                    Pill {
                        property string key: "kmpad" + index
                        text: modelData.name
                        on: modelData.path === km.padPath
                        enabled: !km.mode
                        onTriggered: { km.padPath = modelData.path; km.load("kmpad" + index) }
                    }
                }
            }
        }
    }
}
