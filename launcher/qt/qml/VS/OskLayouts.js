// SPDX-License-Identifier: GPL-3.0-or-later
// Belegungen der Bildschirmtastatur (Startseite, Player, Installer). Kennungen wie die Tastaturen in launcher.py
// (INSTALL_DEFAULTS, setxkbmap): de, us, gb, fr … Je Belegung vier Reihen (Ziffern + drei Buchstabenreihen),
// dazu optional "acc" (Seite mit Akzenten, die auf der Hauptseite keinen Platz haben) und "latin" (griechisch und
// kyrillisch: Umschalter auf lateinische Buchstaben, z. B. fuer WLAN-Passwoerter und Adressen).
// Die Symbol-Seite ist fuer alle gleich und enthaelt jedes ASCII-Satzzeichen – Passwoerter gehen also immer.
.pragma library

var SYM = ["!\"#$%&'()*+", ",-./:;<=>?@", "[\\]^_`{|}~€", "£¥§°µ«»¿¡"]

var L = {
    us: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"] },
    gb: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"], acc: "£€" },
    de: { rows: ["1234567890ß", "qwertzuiopü", "asdfghjklöä", "yxcvbnm,.-"] },
    fr: { rows: ["1234567890", "azertyuiop", "qsdfghjklm", "wxcvbn,.'-"], acc: "éèêëàâîïôùûüÿçœæ", accLabel: "éè" },
    es: { rows: ["1234567890", "qwertyuiop", "asdfghjklñ", "zxcvbnm,.-"], acc: "áéíóúüñ¿¡", accLabel: "áé" },
    it: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"], acc: "àèéìíòóùú", accLabel: "àè" },
    br: { rows: ["1234567890", "qwertyuiop", "asdfghjklç", "zxcvbnm,.-"], acc: "áàâãéêíóôõúüç", accLabel: "ãé" },
    nl: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"], acc: "éèëïöüáóú", accLabel: "éë" },
    lv: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"], acc: "āčēģīķļņšūž", accLabel: "āč" },
    hu: { rows: ["1234567890ö", "qwertzuiopü", "asdfghjkléá", "yxcvbnm,.-"], acc: "áéíóöőúüű", accLabel: "őű" },
    pl: { rows: ["1234567890", "qwertyuiop", "asdfghjkl'", "zxcvbnm,.-"], acc: "ąćęłńóśźż", accLabel: "ąę" },
    cz: { rows: ["1234567890", "qwertzuiopú", "asdfghjklů", "yxcvbnm,.-"], acc: "áčďéěíňóřšťúůýž", accLabel: "čř" },
    sk: { rows: ["1234567890", "qwertzuiopú", "asdfghjklô", "yxcvbnm,.-"], acc: "áäčďéíĺľňóôŕšťúýž", accLabel: "čš" },
    gr: { rows: ["1234567890", ";ςερτυθιοπ", "ασδφγηξκλ", "ζχψωβνμ,.-"], acc: "άέήίόύώϊϋΐΰ", accLabel: "άέ",
          latin: "us", nativeLabel: "ΑΒΓ" },
    ru: { rows: ["1234567890ё", "йцукенгшщзх", "фывапролджэ", "ячсмитьбюъ"], latin: "us", nativeLabel: "АБВ" },
    ua: { rows: ["1234567890ґ", "йцукенгшщзхї", "фівапролджє", "ячсмитьбю'"], latin: "us", nativeLabel: "АБВ" }
}
// Zur Auswahl in den Einstellungen (Reihenfolge der Anzeige); Namen: Texte "inst.kb.<id>"
var LIST = ["de", "us", "gb", "fr", "es", "it", "br", "nl", "lv", "hu", "pl", "cz", "sk", "gr", "ru", "ua"]
// Vorgabe je Sprache der Oberflaeche (wie INSTALL_DEFAULTS in launcher.py; Japanisch ohne eigene Eingabe: US)
var BY_LANG = { de: "de", en: "us", cs: "cz", es: "es", fr: "fr", it: "it", lv: "lv", hu: "hu", nl: "nl", pl: "pl",
                "pt-BR": "br", sk: "sk", el: "gr", ru: "ru", uk: "ua", ja: "us" }

function layout(id) { return L[id] || L.us }
function forLang(lang) { return BY_LANG[lang] || "us" }
function known(id) { return L.hasOwnProperty(id) }

// Akzent-Seite in Reihen von hoechstens zehn Zeichen, gleichmaessig verteilt
function split(s) {
    if (!s) return []
    var n = Math.ceil(s.length / 10), per = Math.ceil(s.length / n), out = []
    for (var i = 0; i < s.length; i += per) out.push(s.slice(i, i + per))
    return out
}
