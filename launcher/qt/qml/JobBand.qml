// SPDX-License-Identifier: GPL-3.0-or-later
// Laufender Auftrag (Installieren, Entfernen, Updates): Band unten mit den letzten Zeilen des Protokolls
import QtQuick
import VS

Rectangle {
    id: jb
    property bool shown: false
    property bool upd: false                    // Update-Auftrag: laufender Schritt statt Protokollzeilen
    z: 35
    width: parent.width
    height: col.implicitHeight + 28 * Ui.f
    y: parent.height - height
    visible: shown && !updScreen.shown          // Updates: erst im Hintergrund (Esc / B im Vollbild)
    color: Ui.c.surfaceBase
    Rectangle { width: parent.width; height: 1; color: Ui.c.divider }
    Column {
        id: col
        x: Ui.padX; y: 14 * Ui.f
        width: parent.width - 2 * Ui.padX
        spacing: 6
        Row {
            spacing: 12
            Spinner { id: spin; size: 14 * Ui.f; line: 2; anchors.verticalCenter: parent.verticalCenter }
            Txt { id: title; font.pixelSize: 17 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
        }
        Text {
            id: logText
            width: parent.width
            font.family: jb.upd ? Ui.font : "DejaVu Sans Mono"
            font.pixelSize: (jb.upd ? 14 : 12.5) * Ui.f
            color: Ui.c.textDim
            wrapMode: Text.WrapAnywhere
            maximumLineCount: 6
            elide: Text.ElideRight
            height: Math.min(implicitHeight, 110 * Ui.f)
            clip: true
        }
    }
    Timer { id: poll; interval: 1000; repeat: true; onTriggered: jb.tick() }
    Timer { id: hideLater; onTriggered: jb.shown = false }
    function watch() {
        hideLater.stop()
        shown = true
        tick()
        poll.start()
    }
    function tick() {
        Api.get("/api/apps/job", function (js) {
            if (!js || !js.state) return
            app.jobState = js
            var name = Ui.l(js.name)
            var what = js.action === "update" ? Ui.t("job.update")
                     : (js.action === "install" || js.action === "remove") ? Ui.t("job." + js.action, { name: name }) : name
            title.text = what + Ui.t(js.state === "running" ? "job.running" : js.state === "done" ? "job.done" : "job.failed")
            spin.visible = js.state === "running"
            var upd = js.action === "update", r = js.result
            jb.upd = upd
            // Updates: statt Protokollzeilen nur der laufende Schritt (das Protokoll steht in logs/update.log)
            logText.text = upd ? (js.state === "running" ? updScreen.current() : "") : (js.log || []).slice(-6).join("\n")
            if (js.state === "running") return
            poll.stop()
            app.load()
            if (apps.open) apps.load()
            if (settings.open) { settings.refreshVs(false); settings.load() }
            if (upd) {
                hideLater.interval = 300
                hideLater.restart()
                updScreen.finish(function () { jb.updateDone(js) })
                return
            }
            app.toast(js.state === "done" ? Ui.t("job.toastDone", { name: name }) + (r && typeof r === "string" ? " – " + r : "")
                                         : Ui.t("job.toastFailed", { name: name }), js.state !== "done")
            hideLater.interval = js.state === "done" ? 2500 : 9000
            hideLater.restart()
            if (js.reboot) {
                var rb = { kernel: !!(r && r.kernel) }
                Qt.callLater(function () { app.rebootPrompt(rb) })
            } else if (js.state === "done" && js.action === "install" && typeof js.result === "string")
                app.dialog(Ui.t("apps.isInstalled", { name: name }), Ui.t("app." + js.app + ".note", null, js.result), [[Ui.t("common.ok")]])
        })
    }
    // Ende des Update-Auftrags (nach dem Vollbild): Neustart-Frage, Fehler mit Protokoll oder kurzer Hinweis
    function updateDone(js) {
        var r = js.result
        if (r && r.busy) return app.toast(Ui.t("upd.xbpsBusy"), true)
        if (js.state !== "done") {
            var step = updScreen.failedStep()
            var btns = [[Ui.t("upd.showLog"), function () { Qt.callLater(function () { jb.showLog(js) }) }]]
            if (js.reboot) btns.push([Ui.t("upd.rebootNow"), function () { app.power("reboot") }])   // ein Teil kam trotzdem an
            btns.push([Ui.t("common.close")])
            app.dialog(Ui.t("upd.failTitle"), step ? Ui.t("upd.failText", { step: step }) : Ui.t("upd.toastFailed"), btns)
        } else if (js.reboot) {
            app.rebootPrompt({ kernel: !!(r && r.kernel) })
        } else {
            app.toast(Ui.t(js.steps && js.steps.length ? "upd.toastDone" : "upd.upToDate"))
        }
    }
    function showLog(js) {
        var lines = (js.log || []).slice(-40).join("\n")
        app.dialog(Ui.t("upd.logTitle"), lines + "\n\n" + Ui.t("upd.logFile", { path: "~/.local/share/voidstation/logs/update.log" }),
                   [[Ui.t("common.close")]])
    }
}
