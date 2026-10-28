// SPDX-License-Identifier: GPL-3.0-or-later
// Skizze einer Konsole fuer die Tastenbelegung (KeymapLayer): Gehaeuse, Bildschirm, Tasten an ihrer Lage.
// Schlichte Umrisse ohne Logos und Schriftzuege. Je Konsole ein Eintrag in `specs` (Einheiten w × h);
// die Kennungen der Tasten sind die aus EMU_LAYOUTS im Launcher.
//   body   SVG-Pfad des Gehaeuses
//   screen Bildschirm (zeigt die gefragte Taste); plain: true = kein Bildschirm, nur Text auf dem Gehaeuse
//   deco   Teile ohne Taste (Sticks, Touchscreen, Speicherkarten-Schacht)
//   keys   Tasten: id, t (Beschriftung), x/y (Mitte), w/h, r (Rundung)
// cur = Taste, die gerade abgefragt wird (pulsiert), done = in diesem Durchgang schon belegt (dezent gruen),
// screenText = Text im Bildschirm (die gefragte Taste – auch Extras wie "Speichern", die es auf der Konsole nicht gibt).
import QtQuick
import VS

Item {
    id: pic
    property string kind: "gba"
    property string cur: ""
    property var done: []
    property string screenText: ""
    // Steuerkreuz um (cx, cy), Tastengroesse s
    function dpad(cx, cy, s) {
        return [
            { id: "Up", t: "▲", x: cx, y: cy - s, w: s, h: s * 1.05, r: s * 0.12 },
            { id: "Down", t: "▼", x: cx, y: cy + s, w: s, h: s * 1.05, r: s * 0.12 },
            { id: "Left", t: "◀", x: cx - s, y: cy, w: s * 1.05, h: s, r: s * 0.12 },
            { id: "Right", t: "▶", x: cx + s, y: cy, w: s * 1.05, h: s, r: s * 0.12 }
        ]
    }
    // Vier Tasten in Rautenform um (cx, cy): oben, unten, links, rechts; Abstand a, Durchmesser d
    function diamond(cx, cy, a, d, top, bottom, left, right) {
        return [
            { id: top[0], t: top[1], x: cx, y: cy - a, w: d, h: d, r: d / 2 },
            { id: bottom[0], t: bottom[1], x: cx, y: cy + a, w: d, h: d, r: d / 2 },
            { id: left[0], t: left[1], x: cx - a, y: cy, w: d, h: d, r: d / 2 },
            { id: right[0], t: right[1], x: cx + a, y: cy, w: d, h: d, r: d / 2 }
        ]
    }
    readonly property var specs: ({
        // Game Boy Advance: quer, Bildschirm in der Mitte, Kreuz links, A/B rechts, L/R oben, Start/Select links unten
        gba: {
            w: 100, h: 62,
            body: "M14 6H86C95 6 99 14 99 26V40C99 52 92 58 82 58C74 58 70 54 64 54H36C30 54 26 58 18 58"
                + "C8 58 1 52 1 40V26C1 14 5 6 14 6Z",
            screen: { x: 29, y: 11, w: 42, h: 34, r: 2 },
            deco: [],
            keys: [
                { id: "L", t: "L", x: 18, y: 5, w: 18, h: 4.2, r: 2.1 },
                { id: "R", t: "R", x: 82, y: 5, w: 18, h: 4.2, r: 2.1 },
                { id: "A", t: "A", x: 88.5, y: 22, w: 8.4, h: 8.4, r: 4.2 },
                { id: "B", t: "B", x: 79, y: 28.5, w: 8.4, h: 8.4, r: 4.2 },
                { id: "Start", t: "Start", x: 16, y: 40.5, w: 11, h: 3.8, r: 1.9 },
                { id: "Select", t: "Select", x: 16, y: 46.5, w: 11, h: 3.8, r: 1.9 }
            ].concat(dpad(16, 25, 4.6))
        },
        // NES: flaches Rechteck, Kreuz links, Select/Start in der Mitte, B/A rechts
        nes: {
            w: 100, h: 44,
            body: "M3 6H97C98.7 6 100 7.3 100 9V38C100 39.7 98.7 41 97 41H3C1.3 41 0 39.7 0 38V9C0 7.3 1.3 6 3 6Z",
            screen: { x: 32, y: 10, w: 36, h: 12, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "Select", t: "Select", x: 42, y: 30, w: 10, h: 3.4, r: 1.7 },
                { id: "Start", t: "Start", x: 57, y: 30, w: 10, h: 3.4, r: 1.7 },
                { id: "B", t: "B", x: 75, y: 27, w: 8.5, h: 8.5, r: 4.25 },
                { id: "A", t: "A", x: 88, y: 27, w: 8.5, h: 8.5, r: 4.25 }
            ].concat(dpad(17, 24, 5))
        },
        // Super Nintendo: Knochenform, L/R oben, Kreuz links, vier Tasten rechts (X oben, B unten, Y links, A rechts)
        snes: {
            w: 100, h: 50,
            body: "M24 6H76C90 6 99 15 99 27C99 39 90 46 78 46C70 46 66 42 62 40H38C34 42 30 46 22 46"
                + "C10 46 1 39 1 27C1 15 10 6 24 6Z",
            screen: { x: 36, y: 11, w: 28, h: 12, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "L", t: "L", x: 21, y: 5.5, w: 22, h: 4, r: 2 },
                { id: "R", t: "R", x: 79, y: 5.5, w: 22, h: 4, r: 2 },
                { id: "Select", t: "Select", x: 43, y: 30, w: 9, h: 3, r: 1.5 },
                { id: "Start", t: "Start", x: 57, y: 30, w: 9, h: 3, r: 1.5 }
            ].concat(dpad(23, 27, 5)).concat(diamond(78, 27, 7, 6.5, ["X", "X"], ["B", "B"], ["Y", "Y"], ["A", "A"]))
        },
        // Nintendo DS: aufgeklappt, oben Bildschirm, unten Touchscreen; Kreuz links, vier Tasten rechts
        nds: {
            w: 100, h: 110,
            body: "M10 2H90C95 2 98 5 98 10V46C98 49 96 50 93 50H7C4 50 2 49 2 46V10C2 5 5 2 10 2Z"
                + "M7 54H93C96 54 98 56 98 59V100C98 105 95 108 90 108H10C5 108 2 105 2 100V59C2 56 4 54 7 54Z",
            screen: { x: 24, y: 8, w: 52, h: 38, r: 1.5 },
            deco: [ { x: 50, y: 78, w: 40, h: 30, r: 1 } ],
            keys: [
                { id: "L", t: "L", x: 12, y: 55, w: 16, h: 3.4, r: 1.7 },
                { id: "R", t: "R", x: 88, y: 55, w: 16, h: 3.4, r: 1.7 },
                { id: "Start", t: "Start", x: 86, y: 92, w: 11, h: 3.4, r: 1.7 },
                { id: "Select", t: "Select", x: 86, y: 98, w: 11, h: 3.4, r: 1.7 }
            ].concat(dpad(15, 73, 5)).concat(diamond(86, 73, 6, 5.6, ["X", "X"], ["B", "B"], ["Y", "Y"], ["A", "A"]))
        },
        // PlayStation-Pad: Griffe, Kreuz links, △○✕□ rechts, L1/L2 und R1/R2 oben, zwei Sticks (L3/R3)
        psx: {
            w: 100, h: 66,
            body: "M22 12H78C88 12 94 18 96 28L99 50C100 60 92 66 84 60L72 48H28L16 60C8 66 0 60 1 50L4 28C6 18 12 12 22 12Z",
            screen: { x: 36, y: 13, w: 28, h: 9, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "L2", t: "L2", x: 22, y: 3, w: 16, h: 4.5, r: 1.6 },
                { id: "R2", t: "R2", x: 78, y: 3, w: 16, h: 4.5, r: 1.6 },
                { id: "L1", t: "L1", x: 22, y: 8.5, w: 18, h: 4, r: 1.4 },
                { id: "R1", t: "R1", x: 78, y: 8.5, w: 18, h: 4, r: 1.4 },
                { id: "Select", t: "Select", x: 42, y: 27, w: 8, h: 3, r: 1.5 },
                { id: "Start", t: "Start", x: 58, y: 27, w: 8, h: 3, r: 1.5 },
                { id: "L3", t: "L3", x: 37, y: 41, w: 10, h: 10, r: 5 },
                { id: "R3", t: "R3", x: 63, y: 41, w: 10, h: 10, r: 5 }
            ].concat(dpad(22, 28, 5)).concat(diamond(78, 28, 6, 6.2, ["Triangle", "△"], ["Cross", "✕"], ["Square", "□"], ["Circle", "○"]))
        },
        // PSP: quer, breiter Bildschirm, Kreuz und Analog-Knubbel links, △○✕□ rechts, Start/Select unten rechts
        psp: {
            w: 100, h: 44,
            body: "M12 4H88C96 4 99 10 99 22C99 34 96 40 88 40H12C4 40 1 34 1 22C1 10 4 4 12 4Z",
            screen: { x: 25, y: 7, w: 50, h: 30, r: 1 },
            deco: [ { x: 12, y: 32, w: 6, h: 6, r: 3 } ],
            keys: [
                { id: "L", t: "L", x: 12, y: 3.5, w: 16, h: 3, r: 1.5 },
                { id: "R", t: "R", x: 88, y: 3.5, w: 16, h: 3, r: 1.5 },
                { id: "Select", t: "Select", x: 83, y: 35, w: 8, h: 2.8, r: 1.4 },
                { id: "Start", t: "Start", x: 92, y: 35, w: 8, h: 2.8, r: 1.4 }
            ].concat(dpad(12, 17, 4)).concat(diamond(88, 18, 4.8, 4.6, ["Triangle", "△"], ["Cross", "✕"], ["Square", "□"], ["Circle", "○"]))
        },
        // GameCube-Pad: Griffe, Stick oben links, Kreuz unten links, C-Stick unten rechts, grosse A-Taste
        gc: {
            w: 100, h: 70,
            body: "M24 10H76C88 10 96 18 97 30L99 52C100 64 90 70 82 62L70 50H30L18 62C10 70 0 64 1 52L3 30C4 18 12 10 24 10Z",
            screen: { x: 39, y: 14, w: 22, h: 10, r: 1, plain: true },
            deco: [ { x: 22, y: 27, w: 11, h: 11, r: 5.5 }, { x: 65, y: 44, w: 8, h: 8, r: 4 } ],
            keys: [
                { id: "L", t: "L", x: 20, y: 5, w: 18, h: 4.5, r: 1.8 },
                { id: "R", t: "R", x: 80, y: 5, w: 18, h: 4.5, r: 1.8 },
                { id: "Z", t: "Z", x: 80, y: 10.5, w: 12, h: 3, r: 1.2 },
                { id: "Start", t: "Start", x: 50, y: 31, w: 9, h: 3.6, r: 1.8 },
                { id: "A", t: "A", x: 79, y: 29, w: 10, h: 10, r: 5 },
                { id: "B", t: "B", x: 70.5, y: 35.5, w: 6, h: 6, r: 3 },
                { id: "X", t: "X", x: 88, y: 26, w: 5, h: 8, r: 2.5 },
                { id: "Y", t: "Y", x: 78, y: 20.5, w: 8, h: 5, r: 2.5 }
            ].concat(dpad(35, 44, 4))
        },
        // Dreamcast-Pad: Trigger oben, Stick oben links, Kreuz darunter, Schacht fuer die Speicherkarte in der Mitte
        dc: {
            w: 100, h: 80,
            body: "M14 8H86C94 8 99 14 98 24L94 58C92 70 84 76 76 70L64 60H36L24 70C16 76 8 70 6 58L2 24C1 14 6 8 14 8Z",
            screen: { x: 39, y: 17, w: 22, h: 24, r: 2 },
            deco: [ { x: 24, y: 23, w: 11, h: 11, r: 5.5 } ],
            keys: [
                { id: "L", t: "L", x: 18, y: 4, w: 18, h: 5, r: 2 },
                { id: "R", t: "R", x: 82, y: 4, w: 18, h: 5, r: 2 },
                { id: "Start", t: "Start", x: 50, y: 50, w: 9, h: 4, r: 2 }
            ].concat(dpad(24, 43, 5)).concat(diamond(78, 37, 7, 6.2, ["Y", "Y"], ["A", "A"], ["X", "X"], ["B", "B"]))
        },
        // Nintendo 64: drei Griffe, Stick auf dem mittleren (Z dahinter), Kreuz links, A/B und vier C-Tasten rechts
        n64: {
            w: 100, h: 80,
            body: "M18 10H82C92 10 98 18 98 28C98 40 92 48 86 54L80 66C78 72 72 72 70 66L66 52H60L56 74C55 79 45 79 44 74"
                + "L40 52H34L30 66C28 72 22 72 20 66L14 54C8 48 2 40 2 28C2 18 8 10 18 10Z",
            screen: { x: 38, y: 13, w: 24, h: 9, r: 1, plain: true },
            deco: [ { x: 50, y: 44, w: 10, h: 10, r: 5 } ],
            keys: [
                { id: "L", t: "L", x: 18, y: 7, w: 20, h: 4, r: 1.6 },
                { id: "R", t: "R", x: 82, y: 7, w: 20, h: 4, r: 1.6 },
                { id: "Z", t: "Z", x: 50, y: 64, w: 8, h: 5, r: 1.6 },
                { id: "Start", t: "Start", x: 50, y: 29, w: 9, h: 4, r: 2 },
                { id: "A", t: "A", x: 75, y: 38, w: 8, h: 8, r: 4 },
                { id: "B", t: "B", x: 67, y: 32, w: 7, h: 7, r: 3.5 }
            ].concat(dpad(19, 29, 4.6)).concat(diamond(84, 23, 5, 4.6, ["CUp", "▲"], ["CDown", "▼"], ["CLeft", "◀"], ["CRight", "▶"]))
        },
        // Xbox-Pad (Controller S): Stick links oben, Kreuz darunter, A/B/X/Y rechts, Weiss/Schwarz darunter, Trigger oben
        xbox: {
            w: 100, h: 70,
            body: "M22 10H78C90 10 97 20 98 32L99 52C100 64 90 70 82 62L70 50H30L18 62C10 70 0 64 1 52L2 32C3 20 10 10 22 10Z",
            screen: { x: 38, y: 13, w: 24, h: 9, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "LT", t: "LT", x: 22, y: 5, w: 16, h: 4.5, r: 1.8 },
                { id: "RT", t: "RT", x: 78, y: 5, w: 16, h: 4.5, r: 1.8 },
                { id: "LS", t: "LS", x: 21, y: 27, w: 11, h: 11, r: 5.5 },
                { id: "RS", t: "RS", x: 64, y: 44, w: 10, h: 10, r: 5 },
                { id: "Back", t: "Back", x: 43, y: 31, w: 8, h: 3.2, r: 1.6 },
                { id: "Start", t: "Start", x: 57, y: 31, w: 8, h: 3.2, r: 1.6 },
                { id: "White", t: "○", x: 74, y: 40, w: 5, h: 5, r: 2.5 },
                { id: "Black", t: "●", x: 86, y: 41, w: 5, h: 5, r: 2.5 }
            ].concat(dpad(36, 44, 4)).concat(diamond(80, 25, 6, 6, ["Y", "Y"], ["A", "A"], ["X", "X"], ["B", "B"]))
        },
        // Nintendo 3DS: aufgeklappt, oben breiter Bildschirm; Schiebepad ueber dem Kreuz, ZL/ZR neben L/R
        n3ds: {
            w: 100, h: 110,
            body: "M10 2H90C95 2 98 5 98 10V46C98 49 96 50 93 50H7C4 50 2 49 2 46V10C2 5 5 2 10 2Z"
                + "M7 54H93C96 54 98 56 98 59V100C98 105 95 108 90 108H10C5 108 2 105 2 100V59C2 56 4 54 7 54Z",
            screen: { x: 17, y: 8, w: 66, h: 38, r: 1.5 },
            deco: [ { x: 50, y: 77, w: 40, h: 30, r: 1 }, { x: 15, y: 67, w: 10, h: 10, r: 5 } ],
            keys: [
                { id: "L", t: "L", x: 10, y: 55, w: 13, h: 3.4, r: 1.7 },
                { id: "ZL", t: "ZL", x: 24, y: 55, w: 10, h: 3.4, r: 1.7 },
                { id: "ZR", t: "ZR", x: 76, y: 55, w: 10, h: 3.4, r: 1.7 },
                { id: "R", t: "R", x: 90, y: 55, w: 13, h: 3.4, r: 1.7 },
                { id: "Select", t: "Select", x: 40, y: 99, w: 11, h: 3.4, r: 1.7 },
                { id: "Start", t: "Start", x: 60, y: 99, w: 11, h: 3.4, r: 1.7 }
            ].concat(dpad(15, 88, 4.4)).concat(diamond(86, 72, 6, 5.6, ["X", "X"], ["B", "B"], ["Y", "Y"], ["A", "A"]))
        },
        // Wii U GamePad: breites Tablet, Bildschirm in der Mitte, Sticks oben (L3/R3), Kreuz und A/B/X/Y darunter
        wiiu: {
            w: 100, h: 56,
            body: "M8 6H92C97 6 100 10 100 16V42C100 49 96 53 90 53H10C4 53 0 49 0 42V16C0 10 3 6 8 6Z",
            screen: { x: 24, y: 11, w: 52, h: 36, r: 1 },
            deco: [],
            keys: [
                { id: "ZL", t: "ZL", x: 9, y: 3.2, w: 11, h: 3.4, r: 1.5 },
                { id: "L", t: "L", x: 22, y: 3.2, w: 10, h: 3.4, r: 1.5 },
                { id: "R", t: "R", x: 78, y: 3.2, w: 10, h: 3.4, r: 1.5 },
                { id: "ZR", t: "ZR", x: 91, y: 3.2, w: 11, h: 3.4, r: 1.5 },
                { id: "L3", t: "L3", x: 12, y: 18, w: 9, h: 9, r: 4.5 },
                { id: "R3", t: "R3", x: 88, y: 18, w: 9, h: 9, r: 4.5 },
                { id: "Minus", t: "−", x: 82, y: 48, w: 6, h: 3, r: 1.5 },
                { id: "Plus", t: "+", x: 92, y: 48, w: 6, h: 3, r: 1.5 }
            ].concat(dpad(12, 36, 3.8)).concat(diamond(88, 35, 5, 4.4, ["X", "X"], ["B", "B"], ["Y", "Y"], ["A", "A"]))
        },
        // Arcade-Bedienfeld: Joystick links, sechs Tasten in zwei Reihen, Muenze und Start in der Mitte
        arcade: {
            w: 100, h: 50,
            body: "M8 8H92C95 8 96 9 97 12L100 42C100 45 98 46 96 46H4C2 46 0 45 0 42L3 12C4 9 5 8 8 8Z",
            screen: { x: 36, y: 11, w: 28, h: 8, r: 1, plain: true },
            deco: [ { x: 20, y: 28, w: 7, h: 7, r: 3.5 } ],
            keys: [
                { id: "Coin", t: "Coin", x: 43, y: 24, w: 10, h: 3.6, r: 1.8 },
                { id: "Start", t: "Start", x: 57, y: 24, w: 10, h: 3.6, r: 1.8 },
                { id: "Button1", t: "1", x: 66, y: 27, w: 8, h: 8, r: 4 },
                { id: "Button2", t: "2", x: 77, y: 25, w: 8, h: 8, r: 4 },
                { id: "Button3", t: "3", x: 88, y: 23, w: 8, h: 8, r: 4 },
                { id: "Button4", t: "4", x: 66, y: 38, w: 8, h: 8, r: 4 },
                { id: "Button5", t: "5", x: 77, y: 36, w: 8, h: 8, r: 4 },
                { id: "Button6", t: "6", x: 88, y: 34, w: 8, h: 8, r: 4 }
            ].concat(dpad(20, 28, 6))
        },
        // Tastatur (DOS): die Tasten, die der Controller tippt
        keyboard: {
            w: 100, h: 48,
            body: "M4 2H96C98 2 100 4 100 6V42C100 44 98 46 96 46H4C2 46 0 44 0 42V6C0 4 2 2 4 2Z",
            screen: { x: 30, y: 5, w: 44, h: 9, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "Esc", t: "Esc", x: 8, y: 9, w: 9, h: 5.5, r: 1 },
                { id: "F1", t: "F1", x: 20, y: 9, w: 7, h: 5.5, r: 1 },
                { id: "Tab", t: "Tab", x: 9, y: 18, w: 11, h: 5.5, r: 1 },
                { id: "KeyY", t: "Y", x: 41, y: 25, w: 7, h: 5.5, r: 1 },
                { id: "KeyN", t: "N", x: 52, y: 25, w: 7, h: 5.5, r: 1 },
                { id: "Enter", t: "Enter", x: 70, y: 22, w: 10, h: 13, r: 1 },
                { id: "Shift", t: "Shift", x: 11, y: 32, w: 15, h: 5.5, r: 1 },
                { id: "Ctrl", t: "Ctrl", x: 9, y: 40, w: 11, h: 5.5, r: 1 },
                { id: "Alt", t: "Alt", x: 22, y: 40, w: 9, h: 5.5, r: 1 },
                { id: "Space", t: "␣", x: 47, y: 40, w: 32, h: 5.5, r: 1 },
                { id: "KeyUp", t: "▲", x: 88, y: 32, w: 6.5, h: 5.5, r: 1 },
                { id: "KeyLeft", t: "◀", x: 80.5, y: 40, w: 6.5, h: 5.5, r: 1 },
                { id: "KeyDown", t: "▼", x: 88, y: 40, w: 6.5, h: 5.5, r: 1 },
                { id: "KeyRight", t: "▶", x: 95.5, y: 40, w: 6.5, h: 5.5, r: 1 }
            ]
        },
        // RetroPad (RetroArch): Griffe, Kreuz links, X/B/Y/A rechts (wie SNES), L/R und L2/R2 oben, zwei Sticks
        retropad: {
            w: 100, h: 66,
            body: "M22 12H78C88 12 94 18 96 28L99 50C100 60 92 66 84 60L72 48H28L16 60C8 66 0 60 1 50L4 28C6 18 12 12 22 12Z",
            screen: { x: 36, y: 13, w: 28, h: 9, r: 1, plain: true },
            deco: [],
            keys: [
                { id: "L2", t: "L2", x: 22, y: 3, w: 16, h: 4.5, r: 1.6 },
                { id: "R2", t: "R2", x: 78, y: 3, w: 16, h: 4.5, r: 1.6 },
                { id: "L", t: "L", x: 22, y: 8.5, w: 18, h: 4, r: 1.4 },
                { id: "R", t: "R", x: 78, y: 8.5, w: 18, h: 4, r: 1.4 },
                { id: "Select", t: "Select", x: 42, y: 27, w: 8, h: 3, r: 1.5 },
                { id: "Start", t: "Start", x: 58, y: 27, w: 8, h: 3, r: 1.5 },
                { id: "L3", t: "L3", x: 37, y: 41, w: 10, h: 10, r: 5 },
                { id: "R3", t: "R3", x: 63, y: 41, w: 10, h: 10, r: 5 }
            ].concat(dpad(22, 28, 5)).concat(diamond(78, 28, 6, 6.2, ["X", "X"], ["B", "B"], ["Y", "Y"], ["A", "A"]))
        }
    })
    // Konsolen mit gleicher Skizze: PlayStation 2 = PlayStation-Pad (DualShock)
    readonly property var alias: ({ ps2: "psx" })
    readonly property var spec: specs[kind] || specs[alias[kind]] || specs.gba
    readonly property real aspect: spec.h / spec.w
    readonly property real k: width / spec.w
    height: width * aspect

    function fill(id) {
        if (id === cur) return Ui.c.borderFocus
        if (done.indexOf(id) >= 0) return Ui.alpha(Ui.c.statusOkBg, 0.6)
        return Ui.c.surfaceCard
    }

    Canvas {
        id: body
        anchors.fill: parent
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.scale(pic.k, pic.k)
            c.path = pic.spec.body
            c.fillStyle = String(Ui.c.surfaceRaised)
            c.fill()
            c.lineWidth = 0.5
            c.strokeStyle = String(Ui.c.borderMuted)
            c.stroke()
        }
        onWidthChanged: requestPaint()
        Connections { target: vs; function onThemeChanged() { body.requestPaint() } }
        Connections { target: pic; function onKindChanged() { body.requestPaint() } }
    }
    // Teile ohne Taste
    Repeater {
        model: pic.spec.deco || []
        Rectangle {
            x: (modelData.x - modelData.w / 2) * pic.k; y: (modelData.y - modelData.h / 2) * pic.k
            width: modelData.w * pic.k; height: modelData.h * pic.k
            radius: modelData.r * pic.k
            color: Ui.c.surfaceCard
            border.width: Math.max(1, 0.25 * pic.k)
            border.color: Ui.c.borderMuted
        }
    }
    // Bildschirm (zeigt die gefragte Taste); bei Pads nur der Text auf dem Gehaeuse
    Rectangle {
        readonly property var sc: pic.spec.screen
        x: sc.x * pic.k; y: sc.y * pic.k
        width: sc.w * pic.k; height: sc.h * pic.k
        radius: sc.r * pic.k
        color: sc.plain ? "transparent" : Ui.c.bgMain
        border.width: sc.plain ? 0 : Math.max(1, 0.4 * pic.k)
        border.color: Ui.c.borderMuted
        Txt {
            anchors.centerIn: parent
            width: parent.width - 2 * pic.k
            horizontalAlignment: Text.AlignHCenter
            text: pic.screenText
            color: Ui.c.textPrimary
            font.pixelSize: Math.max(12, Math.min(parent.height * 0.42, (text.length > 3 ? 4.2 : 8) * pic.k))
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            elide: Text.ElideNone
        }
    }
    Repeater {
        model: pic.spec.keys
        Rectangle {
            readonly property var kd: modelData
            x: (kd.x - kd.w / 2) * pic.k
            y: (kd.y - kd.h / 2) * pic.k
            width: kd.w * pic.k
            height: kd.h * pic.k
            radius: kd.r * pic.k
            color: pic.fill(kd.id)
            border.width: Math.max(1, 0.25 * pic.k)
            border.color: kd.id === pic.cur ? Ui.c.borderFocus : pic.done.indexOf(kd.id) >= 0 ? Ui.c.statusOkText : Ui.c.borderMuted
            SequentialAnimation on opacity {
                running: kd.id === pic.cur
                loops: Animation.Infinite
                alwaysRunToEnd: true
                NumberAnimation { to: 0.45; duration: 450; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 1; duration: 450; easing.type: Easing.InOutQuad }
            }
            Txt {
                anchors.centerIn: parent
                text: kd.t
                color: kd.id === pic.cur ? Ui.c.bgMain : Ui.c.textPrimary
                font.pixelSize: Math.max(8, Math.min(parent.height * 0.55, parent.width * (kd.t.length > 2 ? 0.28 : 0.6), 2.6 * pic.k))
                font.weight: Font.DemiBold
                elide: Text.ElideNone
            }
        }
    }
}
