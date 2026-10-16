// SPDX-License-Identifier: GPL-3.0-or-later
// Ausschalten: Herunterfahren / Neu starten / Standby (wenn das Geraet es kann) / Abbrechen (Fokus auf Abbrechen)
import QtQuick
import VS

Dlg {
    id: pd
    scope: "dialog"
    function openDlg() {
        var standby = !!(app.sett && app.sett.standby)
        title = Ui.t("power.title")
        text = Ui.t(standby ? "power.textStandby" : "power.text")
        buttons = [[Ui.t("power.off"), function () { app.power("poweroff") }, "danger"],
                   [Ui.t("power.reboot"), function () { app.power("reboot") }]]
                  .concat(standby ? [[Ui.t("power.standby"), function () { app.power("suspend") }]] : [])
                  .concat([[Ui.t("common.cancel")]])
        open = true
        app.updateLayer()
        Qt.callLater(function () { var b = Nav.collect(pd); if (b.length) app.setFocus(b[b.length - 1], true) })
    }
}
