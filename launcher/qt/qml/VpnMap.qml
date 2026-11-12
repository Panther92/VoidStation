// SPDX-License-Identifier: GPL-3.0-or-later
// Weltkarte fuer Mullvad VPN als Punktraster (Daten: vpn/worldmap.json aus tools/vpn-map.py, ueber /api/vpn/map).
// Gezeichnet wird nur der sichtbare Ausschnitt, einmal je Aenderung. Mercator: x = Laengengrad, y = Mercator-Breite.
// Mittelpunkt (centerLon/centerLat) und Breite des Ausschnitts in Grad (spanLon) bestimmen den Massstab; liegen die
// Punkte enger als minGap, wird jede n-te Zeile/Spalte gezeichnet (auf ganzer Welt etwa jede fuenfte).
import QtQuick
import VS

Item {
    id: vm
    property var dots: null                     // Punktraster (worldmap.json)
    property real centerLon: 10
    property real centerLat: 50
    property real spanLon: 60
    property string highlight: ""                // Land (ISO-Code klein), das hervorgehoben wird
    property color dotColor: Ui.c.surfaceCardHover
    property color hlColor: Ui.c.statusOkText
    property real minGap: 9 * Ui.f
    readonly property real k: width / Math.max(1, spanLon)           // Pixel je Grad
    readonly property real cy: merc(centerLat)

    function merc(lat) {
        var r = Math.max(-85, Math.min(85, lat)) * Math.PI / 180
        return Math.log(Math.tan(Math.PI / 4 + r / 2)) * 180 / Math.PI
    }
    function toX(lon) {
        var d = lon - centerLon
        while (d > 180) d -= 360
        while (d < -180) d += 360
        return width / 2 + d * k
    }
    function toY(lat) { return height / 2 + (cy - merc(lat)) * k }

    onDotsChanged: cv.requestPaint()
    onWidthChanged: cv.requestPaint()
    onHeightChanged: cv.requestPaint()
    onCenterLonChanged: cv.requestPaint()
    onCenterLatChanged: cv.requestPaint()
    onSpanLonChanged: cv.requestPaint()
    onHighlightChanged: cv.requestPaint()
    onDotColorChanged: cv.requestPaint()

    Canvas {
        id: cv
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var d = vm.dots
            if (!d || !d.r || width <= 0 || height <= 0) return
            var s = d.step, k = vm.k, gap = s * k
            var n = Math.max(1, Math.ceil(vm.minGap / gap))           // jede n-te Zeile/Spalte
            var r = Math.max(1, Math.min(gap * n * 0.3, 3.2 * Ui.f))
            var hi = d.cc.indexOf(vm.highlight)
            var x0 = width / 2 - vm.centerLon * k                    // Bildschirm-x von Laengengrad 0
            var y0 = height / 2 + vm.cy * k                          // Bildschirm-y von Mercator-Breite 0
            var plain = [], lit = []
            for (var q = 0; q < d.r.length; q++) {
                var row = d.r[q], j = row[0]
                if (j % n) continue
                var y = y0 - (d.yTop - (j + 0.5) * s) * k
                if (y < -r || y > height + r) continue
                for (var p = 1; p < row.length; p += 3) {
                    var i0 = row[p], len = row[p + 1], c = row[p + 2]
                    var start = i0 + ((n - i0 % n) % n)
                    for (var i = start; i < i0 + len; i += n) {
                        var lon = d.lonLeft + (i + 0.5) * s
                        var x = x0 + lon * k
                        if (x < -r) x += 360 * k                          // Ausschnitt ueber die Datumsgrenze
                        else if (x > width + r) x -= 360 * k
                        if (x < -r || x > width + r) continue
                        if (c === hi) lit.push(x, y); else plain.push(x, y)
                    }
                }
            }
            function paintDots(list, col) {
                if (!list.length) return
                ctx.fillStyle = col
                ctx.beginPath()
                for (var t = 0; t < list.length; t += 2) {
                    ctx.moveTo(list[t] + r, list[t + 1])
                    ctx.arc(list[t], list[t + 1], r, 0, 2 * Math.PI)
                }
                ctx.fill()
            }
            paintDots(plain, vm.dotColor)
            paintDots(lit, vm.hlColor)
        }
    }
}
