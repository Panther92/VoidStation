// SPDX-License-Identifier: GPL-3.0-or-later
// Waagrechte Buehne mit Gruppen: folgt dem Fokus (6 % Rand), blaettert gruppenweise (LT/RT, Bild auf/ab)
import QtQuick

Flickable {
    id: tr
    property real spacing: Ui.u * 0.4
    property real pad: Ui.padX
    default property alias groups: row.data
    readonly property real maxX: Math.max(0, contentWidth - width)
    readonly property bool scrollable: maxX > 4
    interactive: false
    clip: false
    flickableDirection: Flickable.HorizontalFlick
    contentWidth: row.width + 2 * pad
    contentHeight: height
    boundsBehavior: Flickable.StopAtBounds

    Row {
        id: row
        x: tr.pad
        spacing: tr.spacing
        height: tr.height
    }
    NumberAnimation { id: anim; target: tr; property: "contentX"; duration: 450; easing.type: Easing.OutQuint }

    function scrollTo(x, instant) {
        x = Math.max(0, Math.min(maxX, x))
        anim.stop()
        if (instant) contentX = x
        else { anim.from = contentX; anim.to = x; anim.start() }
    }
    function reset() { anim.stop(); contentX = 0 }
    function ensureVisible(item, instant) {
        var p = item.mapToItem(tr.contentItem, 0, 0)
        var target = anim.running ? anim.to : contentX
        var margin = Ui.screenW * 0.06
        var x = target
        if (p.x + item.width > target + width - margin) x = p.x + item.width - (width - margin)
        if (p.x < x + margin) x = p.x - margin
        x = Math.max(0, Math.min(maxX, x))
        if (Math.abs(x - target) > 0.5 || instant) scrollTo(x, instant)
    }
    // Gruppen auch eine Ebene tiefer (z. B. in einem Loader, der je nach Schritt andere Gruppen zeigt)
    function groupList() {
        var out = []
        function walk(it, depth) {
            for (var i = 0; i < it.children.length; i++) {
                var g = it.children[i]
                if (!g.visible) continue
                if (g.isGroup) out.push(g)
                else if (depth < 3) walk(g, depth + 1)
            }
        }
        walk(row, 0)
        return out
    }
    // Linke Kante einer Gruppe (Inhaltskoordinaten)
    function groupX(g) { return g.mapToItem(tr.contentItem, 0, 0).x }
    // Gruppe an den linken Rand holen – mit demselben Abstand wie die erste Gruppe
    function alignGroup(g, instant) { scrollTo(groupX(g) - pad, instant) }
    // Blaetter-Pfeile: naechste / vorige Gruppe vom sichtbaren Ausschnitt aus, nicht vom Fokus
    // (der steht bei Mausbedienung oft schon in der Gruppe ganz rechts, die man auf dem Weg zum Pfeil ueberfahren hat)
    function pageTarget(dir, groups) {
        var base = anim.running ? anim.to : contentX
        var i
        if (dir > 0) {
            for (i = 0; i < groups.length; i++) if (groupX(groups[i]) - pad > base + 2) return groups[i]
        } else {
            for (i = groups.length - 1; i >= 0; i--) if (groupX(groups[i]) - pad < base - 2) return groups[i]
        }
        return null
    }
    function groupOf(item) {
        var g = null
        for (var p = item; p && p !== row; p = p.parent) if (p.isGroup) g = p
        return g
    }
    WheelHandler {
        onWheel: function (ev) {
            var d = ev.angleDelta.y || ev.angleDelta.x
            if (Ui.app && d) Ui.app.move(d < 0 ? "right" : "left")
        }
    }
}
