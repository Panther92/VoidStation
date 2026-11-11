// SPDX-License-Identifier: GPL-3.0-or-later
// VoidStation-Tastatur: meldet, wenn auf einer Seite ein Eingabefeld angewaehlt oder verlassen wird. Die Startseite
// oeffnet dann ihre Bildschirmtastatur ueber Firefox (tippt per XTest wie eine echte Tastatur) und schliesst sie wieder.
// Nur nach einer Bedienung der Seite (Klick, Taste): Felder, die eine Seite beim Laden selbst anwaehlt, oeffnen nichts.
// Getippt wird hier nichts; die Seite bekommt keine neue Schnittstelle.
(function () {
  "use strict";
  const TEXT = new Set(["", "text", "search", "email", "url", "tel", "password", "number"]);
  const api = globalThis.browser || globalThis.chrome;       // Firefox/LibreWolf bzw. Chromium/Brave
  const sid = Math.random().toString(36).slice(2, 10);
  let open = false, touched = false, typed = false, blurTimer = 0, lastFocus = 0;

  function deep(el) {                                   // Ziel auch in Shadow-DOM (Webkomponenten)
    while (el && el.shadowRoot && el.shadowRoot.activeElement) el = el.shadowRoot.activeElement;
    return el;
  }
  function kindOf(el) {
    if (!el || el.disabled || el.readOnly) return null;
    if (el.localName === "textarea") return "textarea";
    if (el.localName === "input") {
      const t = (el.getAttribute("type") || "").toLowerCase();
      return TEXT.has(t) ? (t || "text") : null;
    }
    if (el.isContentEditable) return "textarea";
    return null;
  }
  function pos(el) {                                    // Mitte des Felds als Anteil der Bildschirmhoehe
    try {
      const r = el.getBoundingClientRect();
      // Firefox kennt die Lage des Seiteninhalts, Chromium nur die des Fensters: Leisten oben grob abziehen
      const top = typeof window.mozInnerScreenY === "number" ? window.mozInnerScreenY
                : window.screenY + (window.top === window ? Math.max(0, window.outerHeight - window.innerHeight) : 0);
      return Math.max(0, Math.min(1, (top + r.top + r.height / 2) / (screen.height || 1)));
    } catch (e) {
      return null;
    }
  }
  function send(msg) {
    msg.sid = sid;
    try {
      const p = api.runtime.sendMessage(msg);
      if (p && p.catch) p.catch(() => {});
    } catch (e) { /* Erweiterung neu geladen */ }
  }
  function report(el) {
    const kind = kindOf(el);
    if (!kind || !document.hasFocus()) return;
    if (!touched && !(navigator.userActivation && navigator.userActivation.hasBeenActive)) return;
    clearTimeout(blurTimer);
    open = true;
    typed = false;
    lastFocus = Date.now();
    send({ ev: "focus", kind: kind, pos: pos(el) });
  }

  addEventListener("pointerdown", () => { touched = true; }, true);
  addEventListener("keydown", (e) => {
    touched = true;
    // Echte Tastatur in Gebrauch? Die Startseite unterscheidet das von ihren eigenen Tastendruecken
    if (open && !typed && e.isTrusted && e.key && e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
      typed = true;
      send({ ev: "typed" });
    }
  }, true);
  addEventListener("focusin", (e) => report(deep(e.composedPath()[0] || e.target)), true);
  addEventListener("focusout", () => {
    if (!open) return;
    clearTimeout(blurTimer);
    blurTimer = setTimeout(() => {                      // nur wenn danach kein Feld mehr angewaehlt ist
      if (kindOf(deep(document.activeElement)) && document.hasFocus()) return;
      open = false;
      send({ ev: "blur" });
    }, 250);
  }, true);
  // Tastatur zugemacht, Feld aber noch angewaehlt: erneuter Klick hinein holt sie zurueck
  addEventListener("pointerup", (e) => {
    const el = deep(e.composedPath()[0] || e.target);
    if (el && el === deep(document.activeElement) && Date.now() - lastFocus > 400) report(el);
  }, true);
})();
