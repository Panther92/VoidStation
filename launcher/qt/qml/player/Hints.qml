// SPDX-License-Identifier: GPL-3.0-or-later
// Hinweiszeile: welche Taste was tut ("<b>A</b> Info" – mit Controller als Tasten-Symbol, sonst halbfett, wie auf der Startseite)
import QtQuick
import VS

Flow {
    id: h
    property var list: []
    property color textColor: Ui.c.textFaint
    spacing: 24 * Ui.f
    function b(s) { return Ui.keys(s, Ui.c.textSecondary, 14 * Ui.f) }       // Controller-Symbole bzw. halbfett
    Repeater {
        model: h.list
        Txt {
            text: h.b(modelData)
            textFormat: Text.StyledText
            color: h.textColor
            font.pixelSize: 14 * Ui.f
            elide: Text.ElideNone
        }
    }
}
