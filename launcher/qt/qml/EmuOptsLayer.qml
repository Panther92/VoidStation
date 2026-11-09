// SPDX-License-Identifier: GPL-3.0-or-later
// Optionen eines Emulators bzw. eines einzelnen Spiels (aus der Spieleliste): die wichtigsten Schalter, alles Weitere
// bleibt im Fenster des Emulators. Daten: /api/emuopts (launcher.py EMU_OPTS). Pro Option eine Zeile Knoepfe; "values"
// getrennt von der Liste, damit beim Umschalten nichts neu aufgebaut wird und der Fokus bleibt, wo er ist.
import QtQuick
import VS

Layer {
    id: eo
    scope: "emuopts"
    track: trk
    title: rom ? Ui.t("emuopt.gameTitle", { game: rom.title || rom.name || rom.filename }) : Ui.t("emuopt.title")
    property var tile: null
    property var rom: null                       // gesetzt: Optionen nur fuer dieses Spiel
    property var od: null                        // Antwort von /api/emuopts
    property var values: ({})
    readonly property real colW: Ui.screenW * 0.4

    function openFor(t, r) {
        tile = t
        rom = r || null
        od = null
        values = ({})
        app.openLayer(eo)
        var q = "/api/emuopts?emu=" + encodeURIComponent(t.id) + (rom ? "&game=" + encodeURIComponent(rom.filename) : "")
        Api.get(q, function (j) {
            od = j
            values = j.values
            Qt.callLater(focusFirst)
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true); app.closeLayer(eo) })
    }
    // Die Spieleliste darunter ausblenden: die Ebenen sind leicht durchscheinend
    onOpened: if (roms.open) roms.opacity = 0
    onClosed: if (roms.open) roms.opacity = 1
    onOpenChanged: if (!open && roms.open) roms.opacity = 1
    function firstFocus() { return Nav.collect(trk)[0] || null }
    function focusFirst() { var it = Nav.collect(trk); if (eo.open && it.length) app.setFocus(it[0], true) }
    function choose(oid, v) {
        var body = { emu: tile.id, id: oid, value: v }
        if (rom) body.game = rom.filename
        Api.post("/api/emuopts/set", body, function (j) { values = j.values },
                 function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }
    // Fuer ein Spiel steht vorn "Wie ueberall" (keine eigene Wahl)
    function choicesOf(o) {
        return rom ? [{ v: null, k: "emuopt.v.inherit" }].concat(o.choices) : o.choices
    }
    function isOn(oid, v) {
        var cur = values[oid]
        return (cur === undefined ? null : cur) === v
    }

    headRight: NowLine { main: eo.od ? eo.od.name : ""; sub: "" }

    Track {
        id: trk
        anchors.fill: parent
        Repeater {
            model: eo.od ? eo.od.groups : []
            SetGroup {
                id: grp
                property var g: modelData
                property int gi: index
                availH: eo.stage.height
                maxW: eo.colW
                title: Ui.t("emuopt.g." + g.id)
                Repeater {
                    model: grp.g.opts
                    SetRow {
                        id: row
                        property var o: modelData
                        width: eo.colW
                        label: Ui.t("emuopt." + o.id)
                        Repeater {
                            model: eo.choicesOf(row.o)
                            Pill {
                                property string key: "eo" + row.o.id + index
                                text: modelData.t || Ui.t(modelData.k)
                                on: eo.isOn(row.o.id, modelData.v)
                                maxWidth: eo.colW
                                onTriggered: eo.choose(row.o.id, modelData.v)
                            }
                        }
                    }
                }
                Info {
                    visible: grp.gi === 0
                    width: eo.colW
                    html: Ui.esc(eo.rom ? Ui.t("emuopt.gameInfo") : Ui.t("emuopt.info", { name: eo.od ? eo.od.name : "" }))
                    font.pixelSize: 14 * Ui.f
                    lineHeight: 1.35
                }
            }
        }
    }
}
