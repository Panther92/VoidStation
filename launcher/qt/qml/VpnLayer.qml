// SPDX-License-Identifier: GPL-3.0-or-later
// Mullvad VPN (AppCenter-Eintrag "mullvad"): Anmelden mit Kontonummer, Hauptseite mit Karte, Ort waehlen, Optionen.
// Daten: /api/vpn (Konto, Optionen, zuletzt verbunden), /api/vpn/relays (Laender, Staedte), /api/vpn/map (Karte);
// der Tunnel-Zustand kommt mit /api/status (app.vpn) alle 1,5 s. Aktionen: POST /api/vpn/<login|logout|connect|
// disconnect|set>. Alles laeuft ueber die mullvad-CLI im Launcher, Mullvad selbst zeigt keine eigene Oberflaeche.
import QtQuick
import VS

Layer {
    id: vp
    scope: "vpn"
    track: view === "opts" ? optTrack : null
    title: Ui.t("vpn.title") + (view === "places" ? " · " + Ui.t("vpn.places") : view === "opts" ? " · " + Ui.t("vpn.opts") : "")
    property string view: "main"                // login | main | places | opts | nodaemon
    property var pg: null                        // /api/vpn
    property var st: app.vpn || ({})             // Tunnel (aus /api/status)
    property var relays: null                    // [{cc, name, cities: [{code, name, lat, lon, n}]}]
    property string nearestCC: ""
    property var mapData: null
    property string digits: ""
    property string loginErr: ""
    property bool loggingIn: false
    property string selCC: ""
    property string selCity: ""
    // Kompakt bei grosser Skalierung (Bildschirmhoehe in Einheiten von Ui.f = 768 / Skalierung, also ab etwa 2,0):
    // breitere linke Spalte, weniger Angaben, Ziffernblock neben der Nummer, Karte kleiner
    readonly property bool compact: Ui.screenH / Ui.f < 400
    readonly property real colW: compact ? Ui.screenW * 0.46 : Math.min(Ui.screenW * 0.34, 560 * Ui.f)
    // Optionen: drei Spalten nebeneinander, solange sie mindestens ein Viertel der Breite haben (sonst blaettern)
    readonly property real optW: Math.max(Ui.screenW * 0.25, Math.min(colW, (Ui.screenW - 2 * Ui.padX - 2 * Ui.u * 0.4) / 3))
    readonly property bool connected: st.state === "connected"
    readonly property bool active: st.state === "connected" || st.state === "connecting"
    readonly property var acct: pg && pg.account ? pg.account : ({})
    readonly property var opt: pg && pg.settings ? pg.settings : null

    // ---------------------------------------------------------------- oeffnen, laden
    function openVpn() {
        view = st.state === "nodaemon" ? "nodaemon" : "main"
        app.openLayer(vp)
        refresh(true)
        if (!mapData) Api.get("/api/vpn/map", function (j) { mapData = j })
    }
    onPgChanged: if (pg && pg.account && pg.account.loggedIn && !relays) loadRelays()
    function refresh(pickView) {
        Api.get("/api/vpn", function (j) {
            pg = j
            if (!j || !j.installed) { app.closeLayer(vp); return }
            if (!pickView) return
            var v = j.status && j.status.state === "nodaemon" ? "nodaemon" : (j.account && j.account.loggedIn ? "main" : "login")
            if (v !== view || pickView === true) { view = v; focusView() }
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }
    function loadRelays(then) {
        Api.get("/api/vpn/relays", function (j) {
            var list = (j.countries || []).slice()
            list.sort(function (a, b) { return cname(a.cc, a.name).localeCompare(cname(b.cc, b.name), Ui.loc.name) })
            relays = list
            nearestCC = j.nearest || ""
            if (then) then()
        }, function (e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) })
    }
    // Daemon wieder da (Update, Neustart) oder gerade weg: Seite passend umschalten
    onStChanged: {
        if (!open) return
        if (st.state === "nodaemon" && view !== "nodaemon") { view = "nodaemon"; focusView() }
        else if (st.state && st.state !== "nodaemon" && view === "nodaemon") refresh(true)
    }

    function setView(v) { view = v; focusView() }
    function focusView() {
        Qt.callLater(function () {
            var box = ({ login: loginBox, main: mainBox, places: placesBox, opts: optBox, nodaemon: noBox })[view]
            var f = firstFocus()
            if (vp.open && f) app.setFocus(f, true)
            else if (vp.open && box) { var it = Nav.collect(box); if (it.length) app.setFocus(it[0], true) }
        })
    }
    function firstFocus() {
        if (view === "main") return mainBtn
        if (view === "login") return Nav.collect(keypad)[0] || null
        if (view === "places") return curCountryRow() || Nav.collect(countryCol)[0] || null
        if (view === "nodaemon") return retryBtn
        return Nav.collect(optBox)[0] || null
    }
    function curCountryRow() {
        var it = Nav.collect(countryCol)
        for (var i = 0; i < it.length; i++) if (it[i].cc === (st.cc || selCC)) return it[i]
        return null
    }

    // ---------------------------------------------------------------- Namen
    function cname(cc, fallback) {
        var up = String(cc || "").toUpperCase()
        var n = Ui.regionName(up)
        return n !== up ? n : (fallback || up)
    }
    function countryOf(cc) {
        var l = relays || []
        for (var i = 0; i < l.length; i++) if (l[i].cc === cc) return l[i]
        return null
    }
    function cityName(cc, code) {
        var c = countryOf(cc)
        if (c) for (var i = 0; i < c.cities.length; i++) if (c.cities[i].code === code) return c.cities[i].name
        return code ? code.toUpperCase() : ""
    }
    function countryLocal(name) {               // englischer Name aus Mullvads GeoIP -> Name in der Sprache
        var l = relays || []
        for (var i = 0; i < l.length; i++) if (l[i].name === name) return cname(l[i].cc, name)
        return name || ""
    }
    function placeText(r) { return r.city ? cityName(r.cc, r.city) : cname(r.cc) }
    function daysLeft() {
        if (!acct.expires) return ""
        var d = Math.ceil((new Date(acct.expires + "T23:59:59") - new Date()) / 86400000)
        return d < 0 ? Ui.t("vpn.expired") : Ui.t("vpn.daysLeft", { n: d })
    }
    function dateText(iso) {
        if (!iso) return ""
        var d = new Date(iso + "T12:00:00")
        return isNaN(d.getTime()) ? iso : Ui.loc.toString(d, Ui.t("fmt.dateYear", null, "d. MMMM yyyy"))
    }

    // ---------------------------------------------------------------- Aktionen
    function fail(e) { app.toast(Ui.t("common.failedMsg", { msg: e }), true) }
    function connectTo(cc, city) {
        var body = cc ? { cc: cc, city: city || "" } : { auto: true }
        Api.post("/api/vpn/connect", body, function () { refresh(false) }, fail)
        if (view === "places") setView("main")
    }
    function toggle() {                          // verbinden: zuletzt gewaehlter Ort (bzw. Vorgabe von Mullvad)
        if (active) Api.post("/api/vpn/disconnect", null, null, fail)
        else Api.post("/api/vpn/connect", {}, function () { refresh(false) }, fail)
    }
    function setOpt(key, val) {
        Api.post("/api/vpn/set", { key: key, value: val }, function (s) {
            var p = pg; p.settings = s; pg = null; pg = p
        }, fail)
    }
    function logout() {
        app.dialog(Ui.t("vpn.acct.logout"), Ui.t("vpn.acct.logoutAsk"),
                   [[Ui.t("vpn.acct.logout"), function () {
                       Api.post("/api/vpn/logout", null, function () { digits = ""; refresh(true) }, fail)
                   }], [Ui.t("common.cancel")]])
    }
    function typeDigit(d) {
        if (digits.length < 16) digits += d
        loginErr = ""
    }
    function delDigit() { digits = digits.slice(0, -1); loginErr = "" }
    function submit() {
        if (digits.length !== 16) { loginErr = Ui.t("vpn.err.format"); return }
        if (loggingIn) return
        loggingIn = true
        loginErr = ""
        Api.post("/api/vpn/login", { account: digits }, function (r) {
            loggingIn = false
            if (r && r.ok) { digits = ""; refresh(true) }
            else loginErr = Ui.t("vpn.err." + (r && r.error ? r.error : "other"), { msg: r && r.msg ? r.msg : "" })
        }, function (e) { loggingIn = false; loginErr = Ui.t("vpn.err.other", { msg: e }) })
    }

    // ---------------------------------------------------------------- Tasten
    function handleBack() {
        if (view === "places" || view === "opts") { setView("main"); return true }
        return false
    }
    function secondary() { if (view === "main") setView("opts") }
    function padFilter(k) {
        if (view === "login") {
            if (k === "x") { delDigit(); return true }
            if (k === "start") { submit(); return true }
            if (k === "y") return true
        }
        if (view === "main") {
            if (k === "x") { openPlaces(); return true }
            if (k === "y") { setView("opts"); return true }
        }
        return false
    }
    function keyFilter(e) {
        if (view === "login") {
            if (e.text && /^[0-9]$/.test(e.text)) { typeDigit(e.text); return true }
            if (e.key === Qt.Key_Backspace && digits.length) { delDigit(); return true }
            if (e.key === Qt.Key_Delete) { delDigit(); return true }
        }
        if (view === "main" && e.key === Qt.Key_X) { openPlaces(); return true }
        return false
    }
    function hints() {
        var T = Ui.t
        if (view === "login") return [T("hint.vpnDigit"), T("hint.vpnDel"), T("hint.vpnLogin"), T("hint.back")]
        if (view === "main") return [T("hint.select"), T("hint.vpnPlaces"), T("hint.vpnOpts"), T("hint.back")]
        if (view === "places") return [T("hint.vpnConnect"), T("hint.back")]
        return [T("hint.select"), T("hint.back")]
    }
    function openPlaces() {
        selCC = st.cc || ""
        selCity = st.cityCode || ""
        if (relays) setView("places")
        else loadRelays(function () { setView("places") })
    }

    // ---------------------------------------------------------------- Bausteine
    // Knopf mit Text oder Symbol (Ziffernblock, Laender, Staedte)
    component Key: Focusable {
        id: kb
        property string text: ""
        property string sub: ""
        property string count: ""
        property string iconName: ""
        property color iconColor: Ui.c.textPrimary
        property bool accent: false
        property bool sel: false
        property bool center: false
        property real fontPx: 20 * Ui.f
        readonly property real textW: width - (center ? 12 : 32) * Ui.f - (iconName !== "" ? 36 * Ui.f : 0) - (count !== "" ? 48 * Ui.f : 0)
        height: sub ? 64 * Ui.f : 52 * Ui.f
        Rectangle {
            anchors.fill: parent
            color: kb.accent ? Ui.c.statusOkBg : (kb.focused || kb.sel) ? Ui.c.surfaceActive : Ui.c.surfaceCard
            border.width: kb.focused ? 3 : 0
            border.color: Ui.c.borderFocus
        }
        Row {
            x: kb.center ? (parent.width - width) / 2 : 16 * Ui.f
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12 * Ui.f
            Glyph { visible: kb.iconName !== ""; name: kb.iconName; color: kb.iconColor; width: 24 * Ui.f; height: width
                    anchors.verticalCenter: parent.verticalCenter }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                visible: kb.text !== ""
                Txt { text: kb.text; font.pixelSize: kb.fontPx; width: Math.min(implicitWidth, kb.textW)
                      fontSizeMode: Text.HorizontalFit; minimumPixelSize: kb.fontPx * 0.7 }
                Txt { visible: kb.sub !== ""; text: kb.sub; font.pixelSize: 14 * Ui.f; color: Ui.c.textDim
                      width: Math.min(implicitWidth, kb.textW); fontSizeMode: Text.HorizontalFit; minimumPixelSize: 11 * Ui.f }
            }
        }
        Txt { visible: kb.count !== ""; text: kb.count; color: Ui.c.textFaint; font.pixelSize: 15 * Ui.f
              anchors.right: parent.right; anchors.rightMargin: 16 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
    }
    component Fact: Column {
        property string label: ""
        property string value: ""
        spacing: 2
        Txt { text: parent.label; color: Ui.c.textFaint; font.pixelSize: 14 * Ui.f; width: parent.width }
        Txt { text: parent.value; font.pixelSize: 17 * Ui.f; width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: 12 * Ui.f }
    }

    headRight: NowLine {
        main: vp.view === "login" ? Ui.t("vpn.loggedOut") : app.vpnInfo(vp.st).text
        sub: vp.view === "login" ? "" : vp.daysLeft()
    }

    // ================================================================ Anmelden
    Item {
        id: loginBox
        anchors.fill: parent
        visible: vp.view === "login"
        Col {                                    // scrollt mit dem Fokus, wenn die Hoehe nicht reicht
            id: loginCol
            x: Ui.padX
            maxW: vp.compact ? loginBox.width - 2 * Ui.padX : loginBox.width - 2 * Ui.padX - qrCard.width - Ui.screenW * 0.04
            maxH: loginBox.height
            Txt { text: Ui.t("vpn.login.title"); font.pixelSize: 28 * Ui.f; width: loginCol.maxW }
            Txt { text: vp.loginErr || Ui.t("vpn.login.text"); color: vp.loginErr ? Ui.c.statusDangerText : Ui.c.textDim
                  font.pixelSize: 16 * Ui.f; width: vp.compact ? loginCol.maxW : vp.colW * 1.15; wrapMode: Text.WordWrap
                  elide: Text.ElideNone; height: Math.max(implicitHeight, 2 * 16 * Ui.f * 1.3) }
            Flow {                                   // Nummer und Ziffernblock: untereinander, kompakt nebeneinander
                width: loginCol.maxW
                spacing: 16 * Ui.f
                Column {
                    spacing: 12 * Ui.f
                    Grid {
                        columns: vp.compact ? 2 : 4
                        spacing: 10 * Ui.f
                        Repeater {
                            model: 4
                            Rectangle {
                                readonly property int g: index
                                readonly property bool cur: Math.min(3, Math.floor(vp.digits.length / 4)) === g && vp.digits.length < 16
                                width: grp.implicitWidth + 28 * Ui.f
                                height: grp.implicitHeight + 18 * Ui.f
                                color: Ui.c.surfaceRaised
                                border.width: cur ? 2 : 1
                                border.color: cur ? Ui.c.borderFocus : Ui.c.borderSubtle
                                Txt {
                                    id: grp
                                    anchors.centerIn: parent
                                    font.family: "monospace"
                                    font.pixelSize: (vp.compact ? 22 : 30) * Ui.f
                                    font.letterSpacing: 4 * Ui.f
                                    elide: Text.ElideNone
                                    text: { var s = ""; for (var i = 0; i < 4; i++) { var c = vp.digits.charAt(parent.g * 4 + i); s += c || "·" } return s }
                                    color: vp.digits.length > parent.g * 4 ? Ui.c.textPrimary : Ui.c.textFaint
                                }
                            }
                        }
                    }
                    Txt { visible: vp.compact; text: Ui.t("vpn.login.noAcct") + " mullvad.net"; color: Ui.c.textFaint
                          font.pixelSize: 15 * Ui.f }
                }
                Grid {
                    id: keypad
                    columns: 3
                    spacing: 8 * Ui.f
                    Repeater {
                        model: ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
                        Key { width: 104 * Ui.f; height: 50 * Ui.f; text: modelData; center: true; fontPx: 26 * Ui.f
                              onTriggered: vp.typeDigit(modelData) }
                    }
                    Key { width: 104 * Ui.f; height: 50 * Ui.f; iconName: "backspace"; center: true; onTriggered: vp.delDigit() }
                    Key { width: 104 * Ui.f; height: 50 * Ui.f; text: "0"; center: true; fontPx: 26 * Ui.f; onTriggered: vp.typeDigit("0") }
                    Key { width: 104 * Ui.f; height: 50 * Ui.f; text: vp.loggingIn ? "…" : Ui.t("vpn.login.go"); center: true
                          fontPx: 17 * Ui.f; accent: vp.digits.length === 16; onTriggered: vp.submit() }
                }
            }
        }
        Rectangle {
            id: qrCard
            visible: !vp.compact
            x: parent.width - Ui.padX - width
            width: Math.min(Ui.screenW * 0.33, 500 * Ui.f)
            height: qrCol.implicitHeight + 56 * Ui.f
            color: Ui.c.surfaceDialog
            border.width: 1
            border.color: Ui.c.borderSubtle
            Column {
                id: qrCol
                x: 28 * Ui.f; y: 28 * Ui.f
                width: parent.width - 56 * Ui.f
                spacing: 16 * Ui.f
                Txt { text: Ui.t("vpn.login.noAcct"); font.pixelSize: 24 * Ui.f; width: parent.width }
                Txt { text: Ui.t("vpn.login.qr"); color: Ui.c.textDim; font.pixelSize: 15 * Ui.f; width: parent.width
                      wrapMode: Text.WordWrap; elide: Text.ElideNone }
                Row {
                    spacing: 20 * Ui.f
                    Image { source: Qt.resolvedUrl("vpn/mullvad-account.png"); width: 170 * Ui.f; height: width; smooth: false }
                    Txt { text: "mullvad.net"; color: Ui.c.textDim; font.pixelSize: 15 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
                }
                Txt { text: Ui.t("vpn.login.local"); color: Ui.c.textFaint; font.pixelSize: 14 * Ui.f; width: parent.width
                      wrapMode: Text.WordWrap; elide: Text.ElideNone }
            }
        }
    }

    // ================================================================ Hauptseite
    Item {
        id: mainBox
        anchors.fill: parent
        visible: vp.view === "main"
        readonly property bool hasLoc: vp.st.lat !== undefined && vp.st.lon !== undefined
        Item {
            id: mapBox
            x: Ui.padX + vp.colW + Ui.screenW * 0.06
            width: parent.width - x
            height: parent.height
            clip: true
            VpnMap {
                id: bigMap
                anchors.fill: parent
                dots: vp.mapData
                centerLon: mainBox.hasLoc ? vp.st.lon : 10
                centerLat: mainBox.hasLoc ? vp.st.lat : 50
                spanLon: 55
                highlight: vp.active ? (vp.st.cc || "") : ""
                hlColor: vp.connected ? Ui.c.statusOkText : Ui.c.statusWarnText
                Behavior on centerLon { NumberAnimation { duration: 600; easing.type: Easing.InOutQuad } }
                Behavior on centerLat { NumberAnimation { duration: 600; easing.type: Easing.InOutQuad } }
            }
            Item {                                   // Ort: Server (verbunden) bzw. eigener Anschluss (getrennt)
                visible: mainBox.hasLoc
                x: bigMap.toX(vp.st.lon || 0); y: bigMap.toY(vp.st.lat || 0)
                readonly property color col: vp.connected ? Ui.c.statusOkText : vp.active ? Ui.c.statusWarnText : Ui.c.textSecondary
                Rectangle { visible: vp.active; anchors.centerIn: parent; width: 90 * Ui.f; height: width; radius: width / 2
                            color: Ui.alpha(parent.col, 0.12); border.width: 1; border.color: Ui.alpha(parent.col, 0.4) }
                Rectangle { anchors.centerIn: parent; width: vp.active ? 18 * Ui.f : 14 * Ui.f; height: width; radius: width / 2
                            color: vp.active ? parent.col : Ui.c.bgMain; border.width: vp.active ? 3 : 2
                            border.color: vp.active ? Ui.c.bgMain : parent.col }
                Rectangle {
                    visible: !vp.compact
                    x: parent.x + 56 * Ui.f + width > mapBox.width ? -56 * Ui.f - width : 56 * Ui.f
                    y: -height / 2
                    width: tag.implicitWidth + 28 * Ui.f; height: tag.implicitHeight + 16 * Ui.f
                    color: Ui.alpha(Ui.c.surfaceDialog, 0.92); border.width: 1; border.color: Ui.c.borderSubtle
                    Column {
                        id: tag
                        anchors.centerIn: parent
                        Txt { text: vp.active ? (vp.st.city || vp.st.country || "") : Ui.t("vpn.yourConn"); font.pixelSize: 19 * Ui.f; elide: Text.ElideNone }
                        Txt { visible: text !== ""; text: vp.active ? (vp.st.host || "") : (vp.st.city || vp.countryLocal(vp.st.country))
                              color: Ui.c.textDim; font.pixelSize: 14 * Ui.f; elide: Text.ElideNone }
                    }
                }
            }
            Rectangle {                              // weich in die linke Spalte und nach unten auslaufen
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Ui.c.bgMain }
                    GradientStop { position: 0.18; color: Ui.alpha(Ui.c.bgMain, 0) }
                }
            }
            Rectangle {
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                height: parent.height * 0.22
                gradient: Gradient {
                    GradientStop { position: 0; color: Ui.alpha(Ui.c.bgMain, 0) }
                    GradientStop { position: 1; color: Ui.c.bgMain }
                }
            }
        }

        Col {                                    // scrollt mit dem Fokus, wenn die Spalte nicht ganz passt (720p, grosse Schrift)
            id: leftCol
            x: Ui.padX
            maxW: vp.colW
            maxH: mainBox.height
            Rectangle {
                width: vp.colW
                height: card.implicitHeight + 40 * Ui.f
                color: Ui.c.surfaceCard
                Column {
                    id: card
                    x: 24 * Ui.f; y: 20 * Ui.f
                    width: parent.width - 48 * Ui.f
                    spacing: 12 * Ui.f
                    Row {
                        spacing: 10 * Ui.f
                        Glyph { name: app.vpnInfo(vp.st).icon; color: app.vpnInfo(vp.st).color; width: 28 * Ui.f; height: width
                                anchors.verticalCenter: parent.verticalCenter }
                        Txt { text: app.vpnInfo(vp.st).text.toUpperCase(); color: app.vpnInfo(vp.st).color; font.pixelSize: 16 * Ui.f
                              font.weight: Font.DemiBold; font.letterSpacing: 1.5 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Column {
                        width: parent.width
                        spacing: 2
                        Txt { width: parent.width; font.pixelSize: 34 * Ui.f; font.weight: Font.Light
                              text: vp.active ? (vp.st.city || vp.cname(vp.st.cc, vp.st.country)) : Ui.t("vpn.notProtected") }
                        Txt { width: parent.width; color: Ui.c.textSecondary; font.pixelSize: 17 * Ui.f
                              text: vp.active ? [vp.cname(vp.st.cc, vp.st.country), vp.st.host].filter(Boolean).join(" · ")
                                              : [vp.st.city, vp.countryLocal(vp.st.country)].filter(Boolean).join(", ") }
                    }
                    Rectangle { visible: !vp.compact; width: parent.width; height: 1; color: Ui.c.divider }
                    Grid {
                        visible: !vp.compact
                        width: parent.width
                        columns: 2
                        columnSpacing: 18 * Ui.f
                        rowSpacing: 12 * Ui.f
                        readonly property real cw: (width - columnSpacing) / 2
                        Fact { width: parent.cw; label: Ui.t("vpn.ip"); value: vp.st.ip || "–" }
                        Fact { width: parent.cw; label: Ui.t("vpn.paidUntil"); value: vp.acct.expires ? vp.dateText(vp.acct.expires) : "–" }
                        Fact { width: parent.cw; label: Ui.t("vpn.opt.lockdown"); value: vp.opt && vp.opt.lockdown !== null ? Ui.t(vp.opt.lockdown ? "common.on" : "common.off") : "–" }
                        Fact { width: parent.cw; label: Ui.t("vpn.opt.lan"); value: vp.opt && vp.opt.lan !== null ? Ui.t(vp.opt.lan ? "common.on" : "common.off") : "–" }
                    }
                }
            }
            Row {
                width: vp.colW
                spacing: 8 * Ui.f
                readonly property real bw: (width - 2 * spacing) / 3
                Key { id: mainBtn; width: parent.bw; height: 58 * Ui.f; center: true; fontPx: 18 * Ui.f
                      text: vp.active ? Ui.t("vpn.disconnect") : Ui.t("vpn.connect"); onTriggered: vp.toggle() }
                Key { width: parent.bw; height: 58 * Ui.f; center: true; fontPx: 18 * Ui.f; text: Ui.t("vpn.places"); onTriggered: vp.openPlaces() }
                Key { width: parent.bw; height: 58 * Ui.f; center: true; fontPx: 18 * Ui.f; text: Ui.t("vpn.opts"); onTriggered: vp.setView("opts") }
            }
            Txt { visible: recentRow.visible && !vp.compact; text: Ui.t("vpn.recent"); color: Ui.c.textDim; font.pixelSize: 16 * Ui.f; topPadding: 4 * Ui.f }
            Row {
                id: recentRow
                visible: !!vp.pg && !!vp.pg.recent && vp.pg.recent.length > 0 && !vp.compact
                width: vp.colW
                spacing: 8 * Ui.f
                Repeater {
                    model: vp.pg && vp.pg.recent ? vp.pg.recent : []
                    Key {
                        width: (recentRow.width - 2 * recentRow.spacing) / 3
                        text: vp.placeText(modelData)
                        sub: modelData.city ? vp.cname(modelData.cc) : ""
                        fontPx: 17 * Ui.f
                        onTriggered: vp.connectTo(modelData.cc, modelData.city)
                    }
                }
            }
        }
    }

    // ================================================================ Ort waehlen
    Item {
        id: placesBox
        anchors.fill: parent
        visible: vp.view === "places"
        readonly property real listW: vp.compact ? Ui.screenW * 0.3 : Math.min(Ui.screenW * 0.22, 360 * Ui.f)
        Col {
            id: countryCol
            x: Ui.padX
            maxW: placesBox.listW
            maxH: placesBox.height
            Key {
                width: placesBox.listW
                iconName: "bolt"; iconColor: Ui.c.statusOkText
                text: Ui.t("vpn.auto")
                sub: vp.nearestCC ? vp.cname(vp.nearestCC) : ""
                onTriggered: vp.connectTo(null)
            }
            Repeater {
                model: vp.relays || []
                Key {
                    property string cc: modelData.cc
                    width: placesBox.listW
                    text: vp.cname(modelData.cc, modelData.name)
                    count: String(modelData.cities.length)
                    sel: vp.selCC === modelData.cc
                    iconName: vp.active && vp.st.cc === modelData.cc ? "shieldok" : ""
                    iconColor: Ui.c.statusOkText
                    onFocusedChanged: if (focused) { vp.selCC = modelData.cc; vp.selCity = "" }
                    onTriggered: vp.connectTo(modelData.cc, "")
                }
            }
        }
        Col {
            id: cityCol
            x: Ui.padX + placesBox.listW + 24 * Ui.f
            maxW: placesBox.listW
            maxH: placesBox.height
            Repeater {
                model: vp.countryOf(vp.selCC) ? vp.countryOf(vp.selCC).cities : []
                Key {
                    width: placesBox.listW
                    text: modelData.name
                    sub: Ui.t("vpn.servers", { n: modelData.n })
                    sel: vp.selCity === modelData.code
                    iconName: vp.active && vp.st.cc === vp.selCC && vp.st.cityCode === modelData.code ? "shieldok" : ""
                    iconColor: Ui.c.statusOkText
                    onFocusedChanged: if (focused) vp.selCity = modelData.code
                    onTriggered: vp.connectTo(vp.selCC, modelData.code)
                }
            }
        }
        Item {
            id: worldBox
            x: cityCol.x + placesBox.listW + Ui.screenW * 0.03
            width: parent.width - x - Ui.padX
            height: Math.min(parent.height, width * 0.62)
            VpnMap {
                id: world
                anchors.fill: parent
                dots: vp.mapData
                centerLon: 12; centerLat: 22
                spanLon: 360
                minGap: 6 * Ui.f
                highlight: vp.selCC
                hlColor: Ui.c.statusOkText
            }
            Repeater {                              // alle Orte mit Mullvad-Servern
                model: {
                    var out = [], l = vp.relays || []
                    for (var i = 0; i < l.length; i++)
                        for (var j = 0; j < l[i].cities.length; j++)
                            out.push({ cc: l[i].cc, code: l[i].cities[j].code, lat: l[i].cities[j].lat, lon: l[i].cities[j].lon })
                    return out
                }
                Rectangle {
                    readonly property bool on: modelData.cc === vp.selCC && (!vp.selCity || modelData.code === vp.selCity)
                    x: world.toX(modelData.lon) - width / 2; y: world.toY(modelData.lat) - height / 2
                    width: (on ? 12 : 7) * Ui.f; height: width; radius: width / 2
                    color: on ? Ui.c.statusOkText : Ui.c.textSecondary
                    border.width: on ? 2 : 0; border.color: Ui.c.bgMain
                    z: on ? 2 : 1
                }
            }
        }
    }

    // ================================================================ Optionen
    Item {
        id: optBox
        anchors.fill: parent
        visible: vp.view === "opts"
        Track {
            id: optTrack
            anchors.fill: parent
            SetGroup {
                availH: vp.stage.height
                maxW: vp.optW
                title: Ui.t("vpn.opt.g.conn")
                SetRow {
                    width: vp.optW; label: Ui.t("vpn.opt.autoconnect")
                    Pill { text: Ui.t("common.on"); on: !!vp.opt && vp.opt.autoconnect === true; onTriggered: vp.setOpt("autoconnect", true) }
                    Pill { text: Ui.t("common.off"); on: !!vp.opt && vp.opt.autoconnect === false; onTriggered: vp.setOpt("autoconnect", false) }
                }
                SetRow {
                    width: vp.optW; label: Ui.t("vpn.opt.lockdown")
                    Pill { text: Ui.t("common.on"); on: !!vp.opt && vp.opt.lockdown === true; onTriggered: vp.setOpt("lockdown", true) }
                    Pill { text: Ui.t("common.off"); on: !!vp.opt && vp.opt.lockdown === false; onTriggered: vp.setOpt("lockdown", false) }
                }
                Info { width: vp.optW; html: Ui.esc(Ui.t("vpn.opt.lockdownInfo")); font.pixelSize: 14 * Ui.f }
                SetRow {
                    width: vp.optW; label: Ui.t("vpn.opt.lan")
                    Pill { text: Ui.t("common.on"); on: !!vp.opt && vp.opt.lan === true; onTriggered: vp.setOpt("lan", true) }
                    Pill { text: Ui.t("common.off"); on: !!vp.opt && vp.opt.lan === false; onTriggered: vp.setOpt("lan", false) }
                }
                Info { width: vp.optW; html: Ui.esc(Ui.t("vpn.opt.lanInfo")); font.pixelSize: 14 * Ui.f }
            }
            SetGroup {
                availH: vp.stage.height
                maxW: vp.optW
                title: Ui.t("vpn.opt.g.filter")
                Info { width: vp.optW; html: Ui.esc(Ui.t(vp.opt && vp.opt.customDns ? "vpn.opt.customDns" : "vpn.opt.filterInfo")); font.pixelSize: 14 * Ui.f }
                SetRow {
                    width: vp.optW
                    Repeater {
                        model: ["ads", "trackers", "malware", "gambling", "adult_content", "social_media"]
                        Pill {
                            text: Ui.t("vpn.dns." + modelData)
                            on: !!vp.opt && !!vp.opt.dns && vp.opt.dns[modelData] === true
                            maxWidth: vp.optW
                            onTriggered: vp.setOpt("dns." + modelData, !on)
                        }
                    }
                }
            }
            SetGroup {
                availH: vp.stage.height
                maxW: vp.optW
                title: Ui.t("vpn.opt.g.account")
                Fact { width: vp.optW; label: Ui.t("vpn.acct.number"); value: vp.acct.last4 ? "•••• •••• •••• " + vp.acct.last4 : "–" }
                Fact { width: vp.optW; label: Ui.t("vpn.paidUntil"); value: vp.acct.expires ? vp.dateText(vp.acct.expires) + " · " + vp.daysLeft() : "–" }
                Fact { width: vp.optW; label: Ui.t("vpn.acct.device"); value: vp.acct.device || "–" }
                SetRow {
                    width: vp.optW
                    Btn { text: Ui.t("vpn.acct.logout"); danger: true; onTriggered: vp.logout() }
                }
                Info { width: vp.optW; font.pixelSize: 14 * Ui.f
                       html: Ui.esc(vp.pg && vp.pg.version ? Ui.t("vpn.acct.version", { ver: vp.pg.version }) : "") }
            }
        }
    }

    // ================================================================ Dienst laeuft nicht
    Column {
        id: noBox
        x: Ui.padX
        width: vp.colW * 1.4
        spacing: 20 * Ui.f
        visible: vp.view === "nodaemon"
        Row {
            spacing: 12 * Ui.f
            Glyph { name: "shieldoff"; color: Ui.c.textDim; width: 30 * Ui.f; height: width; anchors.verticalCenter: parent.verticalCenter }
            Txt { text: Ui.t("vpn.state.nodaemon"); font.pixelSize: 28 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
        }
        Txt { text: Ui.t("vpn.nodaemon.text"); color: Ui.c.textDim; font.pixelSize: 16 * Ui.f; width: parent.width
              wrapMode: Text.WordWrap; elide: Text.ElideNone }
        Btn { id: retryBtn; text: Ui.t("vpn.retry"); onTriggered: vp.refresh(true) }
    }
}
