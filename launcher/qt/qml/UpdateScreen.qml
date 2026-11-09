// SPDX-License-Identifier: GPL-3.0-or-later
// Updates im Vollbild: Eine grosse Kachel in der Farbe des Programms, das gerade dran ist, fuellt sich von unten
// mit dem Download. Darunter die Reihe aller Programme. Grau wie die Kachel "Einstellungen" (Rot wirkte zu alarmierend).
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
    readonly property var items: js && js.items ? js.items : []
    z: 41
    color: "#3a3f46"
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
                 : st.id === "check" ? Ui.t(past ? "upd.stepCheck" : "upd.stepCheckRun")
                 : Ui.t(past ? "upd.stepSetup" : "upd.stepSetupRun")
        return st.id === "apps" && st.n ? base + " (" + pkgs(st.n) + ")" : base
    }
    function runningStep() {
        for (var i = 0; i < steps.length; i++) if (steps[i].state === "run") return steps[i]
        return null
    }
    function current() {                       // laufender Schritt, fuer das Band im Hintergrund
        var st = runningStep()
        return st ? label(st) : Ui.t("upd.checking")
    }
    function failedStep() {
        for (var i = 0; i < steps.length; i++) if (steps[i].state === "fail") return label(steps[i])
        return ""
    }
    function itemName(it) {
        return it.name ? it.name : it.id === "system" ? Ui.t("upd.itemSystem")
             : it.id === "flatpak" ? Ui.t("upd.itemFlatpak") : Ui.t("upd.itemCheck")
    }
    function speedText(bps) {
        return bps >= 1024 * 1024 ? Ui.num(Math.round(bps / 104857.6) / 10, 1) + " MB/s" : Math.round(bps / 1024) + " KB/s"
    }
    function etaText(s) {
        return s < 60 ? Ui.t("upd.sec", { n: Math.max(1, Math.round(s / 5) * 5) })
                      : Ui.t("upd.min", { n: Ui.num(Math.ceil(s / 60)) })
    }

    readonly property string phase: !js ? "check" : js.state === "running" ? (items.length ? "run" : "check")
                                    : js.state === "done" ? "done" : "fail"
    readonly property int curIndex: {
        for (var i = 0; i < items.length; i++) if (items[i].state === "run") return i
        return -1
    }
    readonly property var cur: curIndex >= 0 ? items[curIndex] : null
    readonly property var prog: js && js.progress ? js.progress : null
    readonly property bool hasPct: !!(prog && prog.pct !== null && prog.pct !== undefined)
    readonly property color heroColor: phase === "fail" ? "#7a2f2f" : cur ? cur.color : "#1f6470"
    // Zeilen neben der grossen Kachel
    readonly property string line1: {
        if (phase === "check") return Ui.t("upd.checking")
        if (phase === "fail") {
            for (var i = 0; i < items.length; i++) if (items[i].state === "fail") return itemName(items[i])
            return failedStep()
        }
        if (phase === "done" || !cur) return ""
        return itemName(cur)
    }
    readonly property string line2: {
        if (!cur || phase !== "run") return ""
        if (js.detail === "unpack") return Ui.t("upd.unpack")
        if (prog) return prog.total_mb ? Ui.t("upd.dlOf", { done: Math.round(prog.mb), total: Math.round(prog.total_mb) })
                                       : Math.round(prog.mb) + " MB"
        if (cur.id === "system" || cur.id === "flatpak") return pkgs(cur.n)
        var st = runningStep()
        return cur.id === "vs" && st ? label(st) : ""
    }
    readonly property string line3: {
        if (!cur || phase !== "run" || !prog || !prog.speed) return ""
        return prog.eta !== null && prog.eta !== undefined
            ? Ui.t("upd.dlEta", { speed: speedText(prog.speed), eta: etaText(prog.eta) }) : speedText(prog.speed)
    }
    readonly property real margin: width * 0.09
    // Alles untereinander muss auch bei grosser Skalierung und 4:3 passen: die Kachel nimmt, was uebrig bleibt
    readonly property real topH: title.height + 26 * Ui.f
    readonly property real labelH: 2 * 16 * Ui.f + 6 * Ui.f
    // Reicht der Platz nicht (sehr grosse Skalierung auf kleinem Bildschirm), entfaellt die Reihe unten
    readonly property bool rowFits: (height * 0.7 - topH - labelH - foot.height) / 1.3 >= height * 0.15
    readonly property real heroSize: Math.max(height * 0.12, Math.min(height * 0.36, width * 0.26,
                                     rowFits ? (height * 0.7 - topH - labelH - foot.height) / 1.3
                                             : height * 0.78 - topH - foot.height))
    readonly property real smallSize: heroSize * 0.3
    readonly property real cellW: Math.max(smallSize * 1.5, 100 * Ui.f)     // Breite je Programm samt Name
    readonly property real cellInset: (cellW - smallSize) / 2                // erste kleine Kachel steht buendig am Rand
    // Schrift neben der Kachel waechst nicht ueber deren Hoehe hinaus (grosse Skalierung auf kleinem Bildschirm)
    readonly property real textK: Math.min(1, heroSize / (125 * Ui.f))

    Txt {
        id: title
        x: us.margin
        y: us.height * 0.1
        text: us.phase === "done" ? (us.items.length ? Ui.t("upd.doneTitle") : Ui.t("upd.upToDate"))
            : us.phase === "fail" ? Ui.t("upd.failTitle")
            : us.js && us.js.to ? Ui.t("upd.screenTitle") : Ui.t("job.update")
        font.pixelSize: 30 * Ui.f; font.weight: Font.Light; color: Ui.c.tileText
        width: us.width - 2 * us.margin
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: 12
        elide: Text.ElideNone
    }
    Txt {
        x: us.margin
        anchors.top: title.bottom
        anchors.topMargin: 4 * Ui.f
        visible: !!(us.js && us.js.to)
        text: us.js && us.js.to ? "VoidStation " + (us.js.from || "–") + "  →  " + us.js.to : ""
        font.pixelSize: 16 * Ui.f; color: Ui.c.tileSub
    }

    // ------------------------------------------------------------ Die grosse Kachel
    Rectangle {
        id: hero
        x: us.margin
        y: title.y + us.topH + us.height * 0.06
        width: us.heroSize
        height: us.heroSize
        color: Qt.darker(us.heroColor, us.phase === "run" || us.phase === "check" ? 1.25 : 1)
        clip: true
        Behavior on color { ColorAnimation { duration: 300 } }

        Rectangle {                            // Fuellstand des Downloads
            id: level
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: us.phase === "run" && us.hasPct
            height: visible ? parent.height * us.prog.pct / 100 : 0
            color: Qt.lighter(us.heroColor, 1.55)
            Behavior on height { NumberAnimation { duration: 500; easing.type: Easing.Linear } }
        }
        Rectangle {                            // ohne Prozentangabe (Pakete, Pruefung, Entpacken): ein Band wandert nach oben
            id: sweep
            anchors.left: parent.left
            anchors.right: parent.right
            visible: !us.hasPct && (us.phase === "run" || us.phase === "check") && us.visible
            height: parent.height * 0.22
            color: Qt.lighter(us.heroColor, 1.45)
            NumberAnimation on y {
                running: sweep.visible
                loops: Animation.Infinite
                from: hero.height
                to: -sweep.height
                duration: 1900
            }
        }
        Glyph {
            anchors.centerIn: parent
            width: parent.width * 0.42
            height: width
            name: us.phase === "done" ? "ok" : us.phase === "fail" ? "warn" : us.cur ? us.cur.icon : "update"
            color: Ui.c.tileText
        }
        Txt {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: us.heroSize * 0.05
            visible: us.phase === "run" && us.hasPct
            text: Ui.num(us.hasPct ? us.prog.pct : 0, 0) + " %"
            font.pixelSize: Math.min(18 * Ui.f, us.heroSize * 0.1)
            color: Ui.c.tileText
        }
    }
    Column {
        anchors.left: hero.right
        anchors.leftMargin: us.heroSize * 0.14
        anchors.right: parent.right
        anchors.rightMargin: us.margin
        anchors.verticalCenter: hero.verticalCenter
        spacing: 8 * Ui.f
        Txt {
            width: parent.width
            text: us.line1
            visible: text !== ""
            font.pixelSize: 40 * Ui.f * us.textK; font.weight: Font.Light; color: Ui.c.tileText
            elide: Text.ElideRight
        }
        Txt {
            width: parent.width
            text: us.line2
            visible: text !== ""
            font.pixelSize: 20 * Ui.f * us.textK; color: Ui.c.tileText
            elide: Text.ElideRight
        }
        Txt {
            width: parent.width
            text: us.line3
            visible: text !== ""
            font.pixelSize: 17 * Ui.f * us.textK; color: Ui.c.tileSub
            elide: Text.ElideRight
        }
    }

    // ------------------------------------------------------------ Alle Programme der Reihe nach
    ListView {
        id: row
        x: us.margin - us.cellInset
        y: hero.y + hero.height + us.height * 0.05
        width: Math.min(contentWidth, us.width - 2 * us.margin + 2 * us.cellInset)
        height: us.smallSize + us.labelH
        orientation: ListView.Horizontal
        interactive: false
        spacing: 18 * Ui.f
        model: us.items
        visible: us.items.length > 0 && us.rowFits
        onCountChanged: positionViewAtIndex(Math.max(0, us.curIndex), ListView.Contain)
        Connections {
            target: us
            function onCurIndexChanged() { if (us.curIndex >= 0) row.positionViewAtIndex(us.curIndex, ListView.Contain) }
        }
        delegate: Column {
            required property var modelData
            required property int index
            width: us.cellW
            spacing: 6 * Ui.f
            readonly property bool waiting: modelData.state === "wait"
            Rectangle {
                width: us.smallSize
                height: width
                anchors.horizontalCenter: parent.horizontalCenter
                color: waiting ? "transparent" : modelData.state === "fail" ? "#7a2f2f" : modelData.color
                border.width: modelData.state === "run" ? Math.max(2, Math.round(2 * Ui.f)) : waiting ? 1 : 0
                border.color: modelData.state === "run" ? Ui.c.tileText : Qt.rgba(1, 1, 1, 0.28)
                Glyph {
                    anchors.centerIn: parent
                    width: parent.width * 0.5
                    height: width
                    name: modelData.state === "done" ? "ok" : modelData.state === "fail" ? "bad" : modelData.icon
                    color: Ui.c.tileText
                    opacity: waiting ? 0.5 : 1
                }
            }
            Txt {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: us.itemName(modelData)
                font.pixelSize: 12 * Ui.f
                color: waiting ? Ui.c.tileSub : Ui.c.tileText
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }

    Grid {                                     // passt beides nicht nebeneinander, steht es untereinander
        id: foot
        x: us.margin
        anchors.bottom: parent.bottom
        anchors.bottomMargin: us.height * 0.05
        columns: dont.implicitWidth + bg.implicitWidth + columnSpacing <= us.width - 2 * us.margin ? 2 : 1
        columnSpacing: 36 * Ui.f
        rowSpacing: 4 * Ui.f
        Txt {
            id: dont
            width: Math.min(implicitWidth, us.width - 2 * us.margin)
            elide: Text.ElideRight
            visible: us.phase === "run" || us.phase === "check"
            text: Ui.t("upd.dontTurnOff")
            font.pixelSize: 14 * Ui.f; color: Ui.c.tileSub
        }
        Txt {
            id: bg
            visible: !us.finished
            text: Ui.keys(Ui.t("upd.bgKey"), Ui.c.tileText, 14 * Ui.f)
            textFormat: Text.StyledText
            color: Ui.c.tileSub
            font.pixelSize: 14 * Ui.f
        }
    }
}
