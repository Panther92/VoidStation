// SPDX-License-Identifier: GPL-3.0-or-later
// Hangul fuer die Bildschirmtastatur (2-Beolsik): Einzelzeichen (Jamo) setzen sich beim Tippen zu Silben zusammen,
// ㅎ + ㅏ + ㄴ -> 한, wie bei einer koreanischen Eingabemethode – nach festen Regeln, ohne Woerterbuch.
// compose(prev, j): prev = das zuletzt getippte Zeichen, solange zusammengesetzt wird ("" sonst), j = neues Jamo.
//   Ergebnis { replace: prev ersetzen?, out: neue Zeichen }. back(prev): Ruecktaste nimmt den letzten Teil weg
//   (한 -> 하 -> ㅎ -> nichts), Ergebnis = was an Stelle von prev stehen bleibt.
.pragma library

var L = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"                       // Anlaute (19)
var V = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"                // Vokale (21)
var T = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
         "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]    // Auslaute (28, 0 = keiner)
var VV = { "ㅗㅏ": "ㅘ", "ㅗㅐ": "ㅙ", "ㅗㅣ": "ㅚ", "ㅜㅓ": "ㅝ", "ㅜㅔ": "ㅞ", "ㅜㅣ": "ㅟ", "ㅡㅣ": "ㅢ" }
var TT = { "ㄱㅅ": "ㄳ", "ㄴㅈ": "ㄵ", "ㄴㅎ": "ㄶ", "ㄹㄱ": "ㄺ", "ㄹㅁ": "ㄻ", "ㄹㅂ": "ㄼ", "ㄹㅅ": "ㄽ", "ㄹㅌ": "ㄾ",
           "ㄹㅍ": "ㄿ", "ㄹㅎ": "ㅀ", "ㅂㅅ": "ㅄ" }
var BASE = 0xAC00

function isJamo(ch) { return !!ch && ch.length === 1 && (L.indexOf(ch) >= 0 || V.indexOf(ch) >= 0) }
function isVowel(ch) { return !!ch && ch.length === 1 && V.indexOf(ch) >= 0 }
function syl(l, v, t) { return String.fromCharCode(BASE + (l * 21 + v) * 28 + (t || 0)) }
function parts(ch) {                                      // Silbe -> {l, v, t} (Indizes), sonst null
    var c = ch ? ch.charCodeAt(0) - BASE : -1
    if (c < 0 || c >= 11172) return null
    return { l: Math.floor(c / 588), v: Math.floor((c % 588) / 28), t: c % 28 }
}
function split2(map, x) {                                 // zusammengesetztes Zeichen -> [erstes, zweites]
    for (var k in map) if (map[k] === x) return [k.charAt(0), k.charAt(1)]
    return null
}

function compose(prev, j) {
    var p = parts(prev)
    if (!isVowel(j)) {                                    // Konsonant
        if (p && p.t === 0 && T.indexOf(j) > 0) return { replace: true, out: syl(p.l, p.v, T.indexOf(j)) }
        if (p && p.t > 0 && TT[T[p.t] + j]) return { replace: true, out: syl(p.l, p.v, T.indexOf(TT[T[p.t] + j])) }
        return { replace: false, out: j }
    }
    // Vokal
    if (prev && prev.length === 1 && L.indexOf(prev) >= 0) return { replace: true, out: syl(L.indexOf(prev), V.indexOf(j)) }
    if (prev && VV[prev + j]) return { replace: true, out: VV[prev + j] }
    if (p && p.t === 0 && VV[V.charAt(p.v) + j]) return { replace: true, out: syl(p.l, V.indexOf(VV[V.charAt(p.v) + j])) }
    if (p && p.t > 0) {                                   // Auslaut wandert in die neue Silbe: 한 + ㅏ -> 하나
        var tt = T[p.t], two = split2(TT, tt)
        if (two) return { replace: true, out: syl(p.l, p.v, T.indexOf(two[0])) + syl(L.indexOf(two[1]), V.indexOf(j)) }
        if (L.indexOf(tt) >= 0) return { replace: true, out: syl(p.l, p.v) + syl(L.indexOf(tt), V.indexOf(j)) }
    }
    return { replace: false, out: j }
}

function back(prev) {
    var p = parts(prev)
    if (p) {
        if (p.t > 0) {
            var two = split2(TT, T[p.t])
            return syl(p.l, p.v, two ? T.indexOf(two[0]) : 0)
        }
        var vv = split2(VV, V.charAt(p.v))
        return vv ? syl(p.l, V.indexOf(vv[0])) : L.charAt(p.l)
    }
    var v2 = split2(VV, prev)
    return v2 ? v2[0] : ""
}
