// SPDX-License-Identifier: GPL-3.0-or-later
// Hinweiszeile: welche Taste was tut ("<b>A</b> Info" – Taste halbfett in der Zweitfarbe, wie auf der Startseite)
import QtQuick
import VS

Flow {
    id: h
    property var list: []
    property color textColor: Ui.c.textFaint
    spacing: 24 * Ui.f
    function b(s) { return String(s).replace(/<b>(.*?)<\/b>/g, "<b><font color='" + Ui.c.textSecondary + "'>$1</font></b>") }
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
