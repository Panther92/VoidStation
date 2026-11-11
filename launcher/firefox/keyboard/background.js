// SPDX-License-Identifier: GPL-3.0-or-later
// VoidStation-Tastatur: reicht die Meldungen der Seiten (focus.js) an den Launcher weiter. Die Seiten selbst duerfen
// den Launcher nicht erreichen (eigener Header X-TV, s. Handler.do_POST in launcher.py) - die Erweiterung schon.
// Dieselbe Datei fuer Firefox/LibreWolf (manifest.json, Hintergrundseite) und Chromium/Brave (manifest.chromium.json,
// Service Worker).
"use strict";
const api = globalThis.browser || globalThis.chrome;
const URL_FIELD = "http://127.0.0.1:8765/api/osk/field";

api.runtime.onMessage.addListener((msg, sender) => {
  if (!sender.tab || !msg || typeof msg.ev !== "string") return;      // nur aus Seiten, nicht von anderen Erweiterungen
  fetch(URL_FIELD, {
    method: "POST",
    headers: { "X-TV": "1", "Content-Type": "application/json" },
    body: JSON.stringify({ ev: msg.ev, kind: msg.kind, pos: msg.pos, sid: msg.sid }),
  }).catch(() => {});                                                   // Launcher gerade nicht da: egal
});
