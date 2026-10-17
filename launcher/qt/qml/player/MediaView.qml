// SPDX-License-Identifier: GPL-3.0-or-later
// Videos & Musik: Mediathek fuer ~/share/Videos, ~/share/Musik und USB-Laufwerke (Liste vom Launcher, /api/media/…)
// und die Wiedergabe – Videos vollflaechig mit Leiste unten, Musik mit Cover und Titelliste.
// Angefangene Videos merkt sich der Launcher (Weiterschauen).
// Tasten Video: A Pause, ◀▶ 10 s, LB/RB 1 min, ▲▼ Lautstaerke, Start Ton & Untertitel, Select Technik, B Stopp
// Tasten Musik: A Pause, ◀▶ Titel zurueck/vor, LB/RB 10 s, ▲▼ Lautstaerke, B Stopp
import QtQuick
import VS

Item {
    id: mv
    readonly property Item navRoot: dlg.open ? dlg : browser
    readonly property bool wantVideo: phase === "video"
    readonly property var track: phase === "browse" ? trk : null
    readonly property var player: app.player
    readonly property var st: app.st || {}

    property string phase: "browse"               // browse | video | audio
    property var roots: []
    property var resumes: []
    property string path: ""                      // "" = Startseite der Mediathek
    property string parentPath: ""
    property string folderName: ""
    property var items: []
    property string msg: ""
    property string selectAfter: ""               // nach dem Laden diesen Eintrag fokussieren (zurueck aus einem Ordner)
    property var playing: null                    // laufender Eintrag (Video) bzw. Liste (Musik)
    property var playlist: []
    property bool osdOn: false
    property real seekAcc: 0
    readonly property var audioItems: items.filter(function (i) { return i.kind === "audio" })
    readonly property var fit: Ui.fitRows(browser.stage.height - 18 * Ui.f * 1.36 - 14 * Ui.f - 4, Ui.u * 0.86, Ui.gap, 3)
    readonly property real cell: Ui.u * 0.86 * fit.k

    // ------------------------------------------------------------ Mediathek
    function start(arg) {
        browser.show()
        if (arg) openArg(arg); else openPath("")
    }
    function remote(m) {
        if (m.cmd !== "open") return
        if (m.path) openArg(m.path)
    }
    function openArg(p) {
        if (phase !== "browse") stopPlayback(true)
        openPath(p, true)
    }
    function decorate(list) {
        return (list || []).map(function (it) {
            var o = {}
            for (var k in it) o[k] = it[k]
            o.size = (it.kind === "video" || it.kind === "resume") && it.thumb ? "wide" : "medium"
            if (it.kind === "resume" && it.resume) o.sub = Ui.t("player.media.resumeAt", { time: vs.fmtTime(it.resume.pos, "") })
            if (it.kind === "videos") { o.title = Ui.t("player.media.videos") }
            if (it.kind === "music") { o.title = Ui.t("player.media.music") }
            if (it.kind === "drive" && !it.title) o.title = Ui.t("player.media.drive")
            if (it.kind === "video" && it.resume && it.resume.pos > 0) o.sub = Ui.t("player.media.resumeAt", { time: vs.fmtTime(it.resume.pos, "") })
            return o
        })
    }
    function openPath(p, fromArg) {
        msg = ""
        if (!p) {
            Api.get("/api/media/roots", function (r) {
                r = r || {}
                path = ""; parentPath = ""; folderName = ""
                roots = decorate(r.roots)
                resumes = decorate(r.resume)
                items = []
                focusLater()
            }, function () { msg = Ui.t("player.media.unreachable") })
            return
        }
        Api.get("/api/media/list?path=" + encodeURIComponent(p), function (r) {
            r = r || {}
            path = r.path || p
            parentPath = r.parent || ""
            folderName = r.name || ""
            items = decorate((r.audio && r.audio > 1 ? [{ kind: "playall", title: Ui.t("player.media.playAll"), sub: Ui.t("player.media.tracks", { n: r.audio }) }] : []).concat(r.items || []))
            if (!r.items || !r.items.length) msg = Ui.t("player.media.folderEmpty")
            if (fromArg && r.select) {
                for (var i = 0; i < items.length; i++) if (items[i].path === r.select) { activate(items[i]); break }
            }
            focusLater()
        }, function (e) {
            msg = Ui.t("player.media.notFound")
            if (!path) openPath("")
        })
    }
    function focusLater() {
        Qt.callLater(function () {
            var all = Nav.collect(browser)
            var pick = null
            for (var i = 0; i < all.length; i++) if (all[i].it && all[i].it.path && all[i].it.path === selectAfter) pick = all[i]
            if (!pick) for (i = 0; i < all.length; i++) if (all[i].it) { pick = all[i]; break }
            selectAfter = ""
            trk.reset()
            if (pick) app.setFocus(pick, true)
        })
    }
    function up() {
        if (!path) return app.leave()
        selectAfter = path
        openPath(parentPath)
    }
    function activate(it) {
        if (!it) return
        if (it.kind === "dir" || it.kind === "videos" || it.kind === "music" || it.kind === "drive") return openPath(it.path)
        if (it.kind === "playall") return playAudio(audioItems, 0)
        if (it.kind === "audio") return playAudio(audioItems, Math.max(0, audioItems.indexOf(it)))
        if (it.kind === "video" || it.kind === "resume") {
            if (it.resume && it.resume.pos > 30) return dlg.ask(it)
            return playVideo(it, 0)
        }
    }

    // ------------------------------------------------------------ Wiedergabe
    function playVideo(it, from) {
        playing = it
        playlist = []
        phase = "video"
        if (app.embedded) browser.hide()
        var o = {}
        if (from > 0) o.start = String(Math.floor(from))
        vs.setTitle(it.title || it.name || "")
        player.play(it.path, o)
        Api.post("/api/radio/stop", null)
        showOsd()
    }
    function playAudio(list, index) {
        if (!list.length) return
        playlist = list
        playing = list[index]
        phase = "audio"
        browser.hide()
        player.playList(list.map(function (i) { return i.path }), index, {})
        vs.setTitle(Ui.t("player.media.music"))
        Api.post("/api/radio/stop", null)
    }
    function saveResume(finished) {
        if (phase !== "video" || !playing || !playing.path) return
        var dur = st.duration || 0, pos = finished ? dur : (st.position || 0)
        if (dur <= 0) return
        Api.post("/api/media/resume", { path: playing.path, pos: pos, dur: dur })
    }
    Timer { interval: 10000; repeat: true; running: mv.phase === "video" && !mv.st.paused; onTriggered: mv.saveResume(false) }
    function stopPlayback(silent) {
        saveResume(false)
        player.stop()
        backToBrowser(silent)
    }
    function backToBrowser(silent) {
        var was = playing
        phase = "browse"
        osdOn = false
        menu.hide()
        tech.open = false
        playing = null
        vs.setTitle(Ui.t("player.media.title"))
        browser.show()
        if (was && was.path) selectAfter = was.path
        if (!silent) openPath(path)                 // Fortschritt (Weiterschauen) neu laden
    }
    Connections {
        target: mv.player
        enabled: vsMode === "media"
        function onEnded(reason, cause) {
            if (mv.phase === "browse") return
            if (reason === "error") {
                app.toast(Ui.t("player.media.cantPlay"), true)
                return mv.backToBrowser()
            }
            if (reason === "quit") return mv.backToBrowser()          // mpv-Fenster geschlossen (Stufe 2)
            if (reason === "eof") {
                if (mv.phase === "video") { mv.saveResume(true); return mv.backToBrowser() }
                endCheck.restart()                                    // Musik: naechster Titel oder Ende der Liste?
            }
        }
    }
    Timer { id: endCheck; interval: 400; onTriggered: if (mv.phase === "audio" && mv.st.idle) mv.backToBrowser() }

    function showOsd() { osdOn = true; osdT.restart() }
    Timer { id: osdT; interval: 3500; onTriggered: if (!mv.st.paused) mv.osdOn = false }
    function seek(d) {
        seekAcc += d
        seekT.restart()
        player.seek(d)
        showOsd()
        player.osdText((d > 0 ? "+" : "−") + vs.fmtTime(Math.abs(d), ""), "1200")
    }
    Timer { id: seekT; interval: 1200; onTriggered: mv.seekAcc = 0 }

    function key(k) {
        if (dlg.open) return dlg.key(k)
        if (menu.open) return menu.key(k)
        if (phase === "browse") {
            if (k === "b") return up()
            if (k === "a" || k === "play") { if (Nav.current) Nav.current.activate(); return }
            if (k === "up" || k === "down" || k === "left" || k === "right") return app.move(k)
            if (k === "chup" || k === "lt") { for (var i = 0; i < 4; i++) app.move("left"); return }
            if (k === "chdown" || k === "rt") { for (i = 0; i < 4; i++) app.move("right"); return }
            return
        }
        if (k === "b" || k === "stop") return stopPlayback()
        if (k === "a" || k === "play") { player.togglePause(); showOsd(); return }
        if (k === "up" || k === "volup") return app.volume("up")
        if (k === "down" || k === "voldown") return app.volume("down")
        if (k === "select") { tech.open = !tech.open; return }
        if (k === "start") return menu.show()
        if (phase === "video") {
            if (k === "left") return seek(-10)
            if (k === "right") return seek(10)
            if (k === "lb" || k === "chdown") return seek(-60)
            if (k === "rb" || k === "chup") return seek(60)
            if (k === "x" || k === "y") return showOsd()
        } else {
            if (k === "left" || k === "prev") return prevTrack()
            if (k === "right" || k === "next") return nextTrack()
            if (k === "lb" || k === "chdown") return player.seek(-10)
            if (k === "rb" || k === "chup") return player.seek(10)
        }
    }
    function prevTrack() {
        if ((st.position || 0) > 4 || (st.plpos || 0) <= 0) return player.seekTo(0)
        player.playlistGo(st.plpos - 1)
    }
    function nextTrack() { if ((st.plpos || 0) < (st.plcount || 0) - 1) player.playlistGo(st.plpos + 1) }
    readonly property var curTrackItem: phase === "audio" && st.plpos >= 0 && playlist[st.plpos] ? playlist[st.plpos] : playing

    // ------------------------------------------------------------ Mediathek-Seite
    Layer {
        id: browser
        scope: "media"
        title: mv.path ? mv.folderName : Ui.t("player.media.title")
        track: trk
        anchors.fill: parent
        headRight: NowLine {
            main: mv.path ? Ui.t("player.media.items", { n: Ui.num(mv.items.filter(function (i) { return i.kind !== "playall" }).length, 0) }) : ""
            sub: ""
        }
        Track {
            id: trk
            anchors.fill: parent
            Group {
                visible: !mv.path && mv.resumes.length > 0
                title: Ui.t("player.media.resume")
                TileGrid { items: mv.path ? [] : mv.resumes; rows: mv.fit.n; cellW: mv.cell; cellH: mv.cell; delegate: tileDelegate }
            }
            Group {
                visible: !mv.path
                title: Ui.t("player.media.library")
                TileGrid { items: mv.path ? [] : mv.roots; rows: mv.fit.n; cellW: mv.cell; cellH: mv.cell; delegate: tileDelegate }
            }
            Group {
                visible: !!mv.path
                title: mv.folderName
                showTitle: false
                Column {
                    spacing: 12 * Ui.f
                    Txt {
                        visible: mv.msg !== ""
                        text: mv.msg
                        width: Math.min(implicitWidth, Ui.screenW * 0.5)
                        wrapMode: Text.Wrap; elide: Text.ElideNone
                        color: Ui.c.textFaint
                    }
                    TileGrid { items: mv.path ? mv.items : []; rows: mv.fit.n; cellW: mv.cell; cellH: mv.cell; delegate: tileDelegate }
                }
            }
        }
    }
    Component {
        id: tileDelegate
        MediaTile {
            it: modelData
            onTriggered: mv.activate(modelData)
        }
    }
    Hints {
        visible: mv.phase === "browse"
        x: Ui.padX
        width: parent.width - 2 * Ui.padX
        anchors.bottom: parent.bottom; anchors.bottomMargin: 14 * Ui.f
        z: 31
        list: [Ui.t("hint.open"), Ui.t("hint.back")].concat(trk.scrollable ? [Ui.t("player.hint.pages")] : [])
    }

    // ------------------------------------------------------------ Video
    MouseArea {
        anchors.fill: parent
        visible: mv.phase === "video"
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPositionChanged: { mv.showOsd(); mouseBar.poke() }
        onClicked: function (m) { if (m.button === Qt.RightButton) mv.key("b"); else mv.key("a") }
        onWheel: function (w) { app.volume(w.angleDelta.y > 0 ? "up" : "down") }
    }
    Rectangle {                                    // Stufe 2: Bild im eigenen Fenster
        anchors.fill: parent
        visible: mv.phase === "video" && !app.embedded
        color: Ui.c.bgMain
        Txt { anchors.centerIn: parent; text: Ui.t("player.ownWindow"); color: Ui.c.textDim }
    }
    Column {
        anchors.centerIn: parent
        visible: app.embedded && mv.phase === "video" && (!!mv.st.buffering || (!mv.st.duration && mv.st.active))
        spacing: 14 * Ui.f
        Spinner { anchors.horizontalCenter: parent.horizontalCenter; size: 54 * Ui.f; line: 4 * Ui.f }
    }
    Rectangle {                                    // Pause
        anchors.centerIn: parent
        visible: mv.phase === "video" && !!mv.st.paused
        width: 110 * Ui.f; height: width; radius: width / 2
        color: Ui.alpha(Ui.c.surfaceDialog, 0.75)
        Glyph { anchors.centerIn: parent; name: "pause"; width: parent.width * 0.42; height: width }
    }
    Item {
        id: vosd
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: vbox.height + 70 * Ui.f
        opacity: mv.phase === "video" && (mv.osdOn || !!mv.st.paused) ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.4; color: Ui.alpha(Ui.c.bgMain, 0.75) }
                GradientStop { position: 1.0; color: Ui.alpha(Ui.c.bgMain, 0.95) }
            }
        }
        Column {
            id: vbox
            x: Ui.padX
            width: parent.width - 2 * Ui.padX
            anchors.bottom: parent.bottom; anchors.bottomMargin: 22 * Ui.f
            spacing: 12 * Ui.f
            Txt { width: parent.width; text: mv.playing ? (mv.playing.title || mv.playing.name || "") : ""; font.pixelSize: 26 * Ui.f; font.weight: Font.Light }
            Row {
                width: parent.width
                spacing: 18 * Ui.f
                Txt { id: tPos; text: vs.fmtTime(mv.st.position || 0, ""); font.pixelSize: 16 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
                Bar {
                    width: parent.width - tPos.width - tDur.width - 36 * Ui.f
                    anchors.verticalCenter: parent.verticalCenter
                    value: mv.st.duration > 0 ? (mv.st.position || 0) / mv.st.duration : 0
                    buffered: mv.st.duration > 0 ? ((mv.st.position || 0) + (mv.st.cache || 0)) / mv.st.duration : 0
                    seekable: true
                    onSeek: function (f) { mv.player.seekTo(f * mv.st.duration); mv.showOsd() }
                }
                Txt { id: tDur; text: mv.st.duration > 0 ? vs.fmtTime(mv.st.duration, "") : "–"; color: Ui.c.textDim; font.pixelSize: 16 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
            }
            Hints {
                width: parent.width
                list: [Ui.t("player.hint.pause"), Ui.t("player.hint.seek"), Ui.t("player.hint.seekBig"), Ui.t("player.hint.volumeUD"),
                       Ui.t("player.hint.menu"), Ui.t("player.hint.stop")]
            }
        }
    }

    // ------------------------------------------------------------ Musik
    Rectangle {
        id: music
        anchors.fill: parent
        visible: mv.phase === "audio"
        color: Ui.c.bgMain
        Background { anchors.fill: parent }
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: function (m) { if (m.button === Qt.RightButton) mv.key("b"); else mv.key("a") }
            onWheel: function (w) { app.volume(w.angleDelta.y > 0 ? "up" : "down") }
        }
        Rectangle {
            id: cover
            x: Ui.padX
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -20 * Ui.f
            width: Math.min(parent.height * 0.5, parent.width * 0.32); height: width
            color: Ui.c.surfaceCard
            Image {
                id: coverImg
                anchors.fill: parent
                source: mv.curTrackItem && mv.curTrackItem.thumb ? Ui.url(mv.curTrackItem.thumb) : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Qt.size(Math.ceil(width), Math.ceil(height))
                visible: status === Image.Ready
            }
            Glyph { anchors.centerIn: parent; visible: coverImg.status !== Image.Ready; name: "music"; width: parent.width * 0.36; height: width; opacity: 0.6 }
        }
        Column {
            anchors.left: cover.right; anchors.leftMargin: 48 * Ui.f
            anchors.right: parent.right; anchors.rightMargin: Ui.padX
            anchors.top: cover.top
            spacing: 10 * Ui.f
            Txt {
                width: parent.width
                text: (mv.st.meta && mv.st.meta.title) || (mv.curTrackItem ? (mv.curTrackItem.title || mv.curTrackItem.name) : "")
                font.pixelSize: 36 * Ui.f; font.weight: Font.Light
                wrapMode: Text.WordWrap; maximumLineCount: 2
            }
            Txt {
                width: parent.width
                visible: text !== ""
                text: [(mv.st.meta && (mv.st.meta.artist || mv.st.meta.album_artist)) || "", (mv.st.meta && mv.st.meta.album) || ""].filter(function (s) { return s }).join(" · ")
                color: Ui.c.textSecondary
                font.pixelSize: 19 * Ui.f
            }
            Item { width: 1; height: 10 * Ui.f }
            Row {
                width: parent.width
                spacing: 18 * Ui.f
                Glyph { name: mv.st.paused ? "pause" : "playfill"; width: 22 * Ui.f; height: width; anchors.verticalCenter: parent.verticalCenter }
                Txt { id: mPos; text: vs.fmtTime(mv.st.position || 0, ""); font.pixelSize: 15 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
                Bar {
                    width: parent.width - 22 * Ui.f - mPos.width - mDur.width - 54 * Ui.f
                    anchors.verticalCenter: parent.verticalCenter
                    value: mv.st.duration > 0 ? (mv.st.position || 0) / mv.st.duration : 0
                    seekable: true
                    onSeek: function (f) { mv.player.seekTo(f * mv.st.duration) }
                }
                Txt { id: mDur; text: mv.st.duration > 0 ? vs.fmtTime(mv.st.duration, "") : "–"; color: Ui.c.textDim; font.pixelSize: 15 * Ui.f; anchors.verticalCenter: parent.verticalCenter }
            }
            Txt {
                visible: mv.st.plcount > 1
                text: Ui.t("player.media.trackOf", { n: (mv.st.plpos || 0) + 1, total: mv.st.plcount || 0 })
                color: Ui.c.textDim
                font.pixelSize: 15 * Ui.f
            }
            Item { width: 1; height: 8 * Ui.f }
            Repeater {                                  // die naechsten Titel
                model: mv.playlist.slice((mv.st.plpos || 0) + 1, (mv.st.plpos || 0) + 6)
                Txt {
                    width: parent.width
                    text: (index === 0 ? Ui.t("player.media.upNext") + "  " : "") + (modelData.title || modelData.name)
                    color: index === 0 ? Ui.c.textSecondary : Ui.c.textFaint
                    font.pixelSize: 16 * Ui.f
                }
            }
        }
        Hints {
            x: Ui.padX
            width: parent.width - 2 * Ui.padX
            anchors.bottom: parent.bottom; anchors.bottomMargin: 14 * Ui.f
            list: [Ui.t("player.hint.pause"), Ui.t("player.hint.tracks"), Ui.t("player.hint.seekSmall"), Ui.t("player.hint.volumeUD"), Ui.t("player.hint.stop")]
        }
    }

    // ------------------------------------------------------------ Fortsetzen?
    Rectangle {
        id: dlg
        property bool open: false
        property var it: null
        readonly property bool navBarrier: true
        anchors.fill: parent
        visible: open
        z: 48
        color: Ui.c.surfaceOverlay
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onClicked: function (m) { if (m.button === Qt.RightButton) dlg.close() } }
        function ask(item) {
            it = item
            open = true
            Qt.callLater(function () { app.setFocus(btnResume, true) })
        }
        function close() {
            open = false
            Qt.callLater(mv.focusLater)
        }
        function key(k) {
            if (k === "b") return close()
            if (k === "a" || k === "play") { if (Nav.current) Nav.current.activate(); return }
            if (k === "left" || k === "right" || k === "up" || k === "down") return app.move(k)
        }
        Rectangle {
            anchors.centerIn: parent
            width: Math.max(dcol.implicitWidth, 420 * Ui.f) + 64 * Ui.f
            height: dcol.implicitHeight + 56 * Ui.f
            color: Ui.c.surfaceDialog
            border.width: 1
            border.color: Ui.c.borderSubtle
            Column {
                id: dcol
                anchors.centerIn: parent
                spacing: 16 * Ui.f
                Txt { text: dlg.it ? (dlg.it.title || dlg.it.name || "") : ""; font.pixelSize: 24 * Ui.f; font.weight: Font.Light; width: Math.min(implicitWidth, Ui.screenW * 0.5) }
                Txt { text: dlg.it && dlg.it.resume ? Ui.t("player.media.resumeAsk", { time: vs.fmtTime(dlg.it.resume.pos, "") }) : ""; color: Ui.c.textDim }
                Row {
                    spacing: 12 * Ui.f
                    Btn { id: btnResume; text: Ui.t("player.media.resumeYes"); onTriggered: { var i = dlg.it; dlg.open = false; mv.playVideo(i, i.resume.pos - 3) } }
                    Btn { text: Ui.t("player.media.fromStart"); onTriggered: { var i = dlg.it; dlg.open = false; mv.playVideo(i, 0) } }
                }
            }
        }
    }

    MouseBar {
        id: mouseBar
        visible: mv.phase === "video" && !menu.open && !dlg.open && opacity > 0
        buttons: [
            { icon: "pause", tip: Ui.t("player.paused"), act: function () { mv.player.togglePause(); mv.showOsd() } },
            { icon: "subs", tip: Ui.t("player.menu.title"), act: function () { menu.show() } },
            { icon: "minus", tip: Ui.t("player.volume"), act: function () { app.volume("down") } },
            { icon: "plus", tip: Ui.t("player.volume"), act: function () { app.volume("up") } },
            { icon: "stop", tip: Ui.t("player.btn.stop"), act: function () { mv.stopPlayback() } }
        ]
    }
    TechInfo { id: tech }
    TrackMenu { id: menu }
}
