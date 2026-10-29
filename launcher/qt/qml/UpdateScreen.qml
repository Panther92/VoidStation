// SPDX-License-Identifier: GPL-3.0-or-later
// Updates im Vollbild (wie der Startbildschirm der Kacheln): statt des Protokolls nur die Schritte
//   "VoidStation 2026.10.1 → 2026.11" · ✓ Programme aktualisiert (12 Pakete) · ✓ Neue Version geladen und
//   geprueft · ✓ Eingerichtet
// Der Stand kommt aus /api/apps/job (JobBand fragt ab und setzt app.jobState). Esc / B: im Hintergrund weiter,
// dann zeigt das Band unten den aktuellen Schritt. Das ganze Protokoll steht in logs/update.log.
import QtQuick
import VS

Rectangle {
    id: us
    property bool shown: false                 // Vollbild sichtbar (false = laeuft im Hintergrund weiter)
    property bool finished: false              // Ergebnis steht kurz da, bevor das Bild schliesst
    readonly property var js: app.jobState && app.jobState.action === "update" ? app.jobState : null
    readonly property var steps: js && js.steps ? js.steps : []
    z: 41
    color: "#3a3f46"                           // Grau der Kachel "Einstellungen" (ruhig, Rot wirkte zu alarmierend)
    opacity: shown ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 250 } }
    MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: us.toBackground() }

    function open() { finished = false; shown = true }
    function toBackground() { if (!finished) shown = false }
    // Ergebnis kurz zeigen, dann schliessen; then() laeuft danach (Neustart-Frage, Fehlerdialog, Hinweis)
    function finish(then) {
        if (!shown) { then(); return }
        finished = true
        closeLater.then = then
        closeLater.restart()
    }
    Timer {
        id: closeLater
        interval: 1600
        property var then: null
        onTriggered: { us.shown = false; us.finished = false; var f = then; then = null; if (f) f() }
    }

    function pkgs(n) { return n === 1 ? Ui.t("upd.onePkg") : Ui.t("upd.nPkgs", { n: Ui.num(n) }) }
    // Text eines Schritts: laufend/wartend in der Verlaufsform, fertig in der Vergangenheit
    function label(st) {
        var past = st.state === "done"
        var base = st.id === "apps" ? Ui.t(past ? "upd.stepApps" : "upd.stepAppsRun")
                 : st.id === "load" ? Ui.t(past ? "upd.stepLoad" : "upd.stepLoadRun")
                 : Ui.t(past ? "upd.stepSetup" : "upd.stepSetupRun")
        return st.id === "apps" && st.n ? base + " (" + pkgs(st.n) + ")" : base
    }
    function current() {                       // laufender Schritt, fuer das Band im Hintergrund
        for (var i = 0; i < steps.length; i++) if (steps[i].state === "run") return label(steps[i])
        return Ui.t("upd.checking")
    }
    function failedStep() {
        for (var i = 0; i < steps.length; i++) if (steps[i].state === "fail") return label(steps[i])
        return ""
    }
    // Breite der Schrittliste fest nach dem laengsten Text (laufend und fertig), damit sie nicht springt
    function allLabels() {
        var out = []
        for (var i = 0; i < steps.length; i++) {
            out.push(label({ id: steps[i].id, n: steps[i].n, state: "run" }))
            out.push(label({ id: steps[i].id, n: steps[i].n, state: "done" }))
        }
        return out
    }
    Item {
        visible: false
        Repeater { id: meas; model: us.allLabels(); Txt { text: modelData; font.pixelSize: 19 * Ui.f } }
    }
    readonly property real labelW: {
        var w = 0
        for (var i = 0; i < meas.count; i++) { var it = meas.itemAt(i); if (it) w = Math.max(w, it.implicitWidth) }
        return w
    }
    readonly property string phase: !js ? "check" : js.state === "running" ? (steps.length ? "run" : "check")
                                    : js.state === "done" ? "done" : "fail"

    Column {
        anchors.centerIn: parent
        spacing: 0
        Glyph {
            anchors.horizontalCenter: parent.horizontalCenter
            width: us.height * 0.13; height: width
            name: us.phase === "fail" ? "warn" : "update"
            color: Ui.c.tileText
        }
        Item { width: 1; height: us.height * 0.03 }
        Txt {
            anchors.horizontalCenter: parent.horizontalCenter
            text: us.phase === "done" ? (us.steps.length ? Ui.t("upd.doneTitle") : Ui.t("upd.upToDate"))
                : us.phase === "fail" ? Ui.t("upd.failTitle")
                : us.js && us.js.to ? Ui.t("upd.screenTitle") : Ui.t("job.update")
            font.pixelSize: 30 * Ui.f; font.weight: Font.Light; color: Ui.c.tileText
        }
        Item { width: 1; height: us.height * 0.012 }
        Txt {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !!(us.js && us.js.to)
            text: us.js && us.js.to ? "VoidStation " + (us.js.from || "–") + "  →  " + us.js.to : ""
            font.pixelSize: 17 * Ui.f; color: Ui.c.tileSub
        }
        Item { width: 1; height: us.height * 0.055 }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            width: us.phase === "check" ? implicitWidth : 38 * Ui.f + us.labelW
            spacing: 16 * Ui.f
            Row {                              // noch keine Schritte: die Pruefung laeuft
                visible: us.phase === "check"
                spacing: 16 * Ui.f
                Spinner { size: 22 * Ui.f; line: 2.5 * Ui.f; anchors.verticalCenter: parent.verticalCenter; visible: parent.visible }
                Txt { text: Ui.t("upd.checking"); font.pixelSize: 19 * Ui.f; color: Ui.c.tileText; anchors.verticalCenter: parent.verticalCenter }
            }
            Repeater {
                model: us.steps
                Row {
                    spacing: 16 * Ui.f
                    Item {
                        width: 22 * Ui.f; height: width
                        anchors.verticalCenter: parent.verticalCenter
                        Spinner { anchors.fill: parent; size: parent.width; line: 2.5 * Ui.f; visible: modelData.state === "run" && us.visible }
                        Glyph { anchors.fill: parent; visible: modelData.state === "done" || modelData.state === "fail"
                                name: modelData.state === "fail" ? "bad" : "ok"; color: Ui.c.tileText }
                        Rectangle {                    // wartet noch
                            visible: modelData.state === "wait"
                            anchors.centerIn: parent; width: parent.width * 0.42; height: width; radius: width / 2
                            color: "transparent"; border.color: Ui.c.tileSub; border.width: 2 * Ui.f
                        }
                    }
                    Txt {
                        anchors.verticalCenter: parent.verticalCenter
                        text: us.label(modelData)
                        font.pixelSize: 19 * Ui.f
                        color: modelData.state === "wait" ? Ui.c.tileSub : Ui.c.tileText
                        opacity: modelData.state === "wait" ? 0.75 : 1
                    }
                }
            }
        }
        Item { width: 1; height: us.height * 0.06 }
        Txt {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: us.phase === "run" || us.phase === "check"
            text: Ui.t("upd.dontTurnOff")
            font.pixelSize: 15 * Ui.f; color: Ui.c.tileSub
        }
    }
    Txt {
        anchors.bottom: parent.bottom; anchors.bottomMargin: us.height * 0.06
        anchors.horizontalCenter: parent.horizontalCenter
        visible: !us.finished
        text: Ui.keys(Ui.t("upd.bgKey"), Ui.c.tileText, 12 * Ui.f)
        textFormat: Text.StyledText
        color: Ui.c.tileSub
        font.pixelSize: 12 * Ui.f
    }
}
