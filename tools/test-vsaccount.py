#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit- & Integrations-Tests fuer das VoidStation-Account-System (Stufe 1 + Stufe 2)."""
from __future__ import annotations

import ast
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "launcher"))

import launcher  # noqa: E402
import vsaccount  # noqa: E402
import vsreport  # noqa: E402
from vsaccount import (  # noqa: E402
    AccountService,
    PolicyError,
    ValidationError,
    cli as account_cli,
    crypto as account_crypto,
)


class FakeClock:
    """Deterministische Uhr fuer Cooldown- und Timestamp-Tests."""

    def __init__(self, now: float = 1_700_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


class VsAccountStage1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.base = self.root / "voidstation"
        self.runtime = self.root / "runtime"
        self.base.mkdir(parents=True)
        self.runtime.mkdir(parents=True)
        self.clock = FakeClock()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_crypto_scrypt_pbkdf2_and_validation(self) -> None:
        pw_hash = account_crypto.hash_secret("SuperGeheim!123", factor="password", preferred_algo="vs-scrypt")
        self.assertTrue(pw_hash.startswith("$vs-scrypt$"))
        ok, rehash = account_crypto.verify_secret("SuperGeheim!123", pw_hash, factor="password")
        self.assertTrue(ok)
        self.assertIsInstance(rehash, bool)
        self.assertEqual(account_crypto.verify_secret("falsch", pw_hash, factor="password")[0], False)

        pin_hash = account_crypto.hash_secret("4279", factor="pin", preferred_algo="vs-pbkdf2-sha256")
        self.assertTrue(pin_hash.startswith("$vs-pbkdf2-sha256$"))
        ok_pin, rehash_pin = account_crypto.verify_secret("4279", pin_hash, factor="pin")
        self.assertTrue(ok_pin)
        self.assertTrue(rehash_pin)  # Upgrade von PBKDF2 auf Standard-KDF gewuenscht

        with self.assertRaises(ValidationError) as ctx_pin:
            account_crypto.hash_secret("12ab", factor="pin")
        self.assertNotIn("12ab", str(ctx_pin.exception))

        with self.assertRaises(ValidationError) as ctx_pw:
            account_crypto.hash_secret("", factor="password")
        self.assertEqual(ctx_pw.exception.code, "account.err.pwFormat")

    def test_bruteforce_cooldown_persistence_and_pin_hard_lock(self) -> None:
        svc = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        admin = svc.list_accounts()[0]
        svc.set_credential(admin.id, "password", "ElternPass99")
        svc.set_credential(admin.id, "pin", "2580")

        # 3 Fehlversuche ohne Wartezeit
        for _ in range(3):
            r = svc.authenticate(admin.id, "pin", "9999")
            self.assertFalse(r.ok)
            self.assertEqual(r.retry_after, 0)

        # 4. Fehlversuch loest 15s Cooldown aus
        r4 = svc.authenticate(admin.id, "pin", "9999")
        self.assertFalse(r4.ok)
        self.assertEqual(r4.error, "account.cooldown")
        self.assertEqual(r4.retry_after, 15)

        # Cooldown bleibt nach Neustart des AccountService erhalten
        svc.close()
        svc2 = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        r_blocked = svc2.authenticate(admin.id, "pin", "2580")
        self.assertFalse(r_blocked.ok)
        self.assertEqual(r_blocked.error, "account.cooldown")
        self.assertGreater(r_blocked.retry_after, 0)

        # Nach Ablauf von 15s -> 5. Fehlversuch -> 60s; weiter bis zum Hard-Lock (8. Fehlversuch)
        expected_waits = [60, 300, 900]
        self.clock.advance(16)
        for wait in expected_waits:
            rx = svc2.authenticate(admin.id, "pin", "9999")
            self.assertFalse(rx.ok)
            self.assertEqual(rx.retry_after, wait)
            self.clock.advance(wait + 1)

        # 8. Fehlversuch -> PIN dauerhaft gesperrt, auch richtige PIN wird abgewiesen
        r8 = svc2.authenticate(admin.id, "pin", "9999")
        self.assertTrue(r8.hard_locked)
        self.assertEqual(r8.error, "account.err.pinLocked")
        r_locked = svc2.authenticate(admin.id, "pin", "2580")
        self.assertTrue(r_locked.hard_locked)

        # Entsperrung per Passwort hebt auch die PIN-Sperre auf
        r_pw = svc2.authenticate(admin.id, "password", "ElternPass99")
        self.assertTrue(r_pw.ok)
        self.assertTrue(svc2.authenticate(admin.id, "pin", "2580").ok)

        # Alternative Entsperrung per unlock_account()
        for _ in range(8):
            res = svc2.authenticate(admin.id, "pin", "0000")
            if res.retry_after > 0:
                self.clock.advance(res.retry_after + 1)
        self.assertTrue(svc2.authenticate(admin.id, "pin", "2580").hard_locked)
        svc2.unlock_account(admin.id, "pin")
        self.assertTrue(svc2.authenticate(admin.id, "pin", "2580").ok)
        svc2.close()

    def test_roles_invariants_and_public_dict(self) -> None:
        svc = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        admin = svc.list_accounts()[0]
        self.assertEqual(admin.role, "admin")

        # Letzter Admin darf nicht geloescht oder herabgestuft werden
        with self.assertRaises(PolicyError):
            svc.delete_account(admin.id)
        with self.assertRaises(PolicyError):
            svc.update_account(admin.id, role="standard")
        with self.assertRaises(PolicyError):
            svc.update_account(admin.id, active=False)

        # Kind braucht aktiven Admin als parent_id
        with self.assertRaises(PolicyError):
            svc.create_account("Kind Ohne Eltern", role="child")

        std = svc.create_account("Alex", role="standard", pin="1357")
        with self.assertRaises(PolicyError):
            svc.create_account("Kind Falscher Parent", role="child", parent_id=std.id)

        child = svc.create_account("Lina", role="child", parent_id=admin.id, pin="2468")
        self.assertEqual(child.parent_id, admin.id)

        pub = std.to_public_dict()
        self.assertTrue(pub["has_pin"])
        self.assertFalse(pub["has_password"])
        self.assertNotIn("hash", json.dumps(pub))
        self.assertNotIn("1357", json.dumps(pub))
        svc.close()

    def test_legacy_migration_and_strict_profile_isolation(self) -> None:
        # Legacy-Fixture anlegen
        (self.base / "tiles.json").write_text(json.dumps({"user": "Anna", "groups": []}), encoding="utf-8")
        legacy_settings = {
            "lang": "en",
            "theme": "nord",
            "scale": 1.5,
            "ui_sounds": False,
            "ui_sounds_preset": "retro",
            "resolution": "1920x1080",
            "sysupd_days": 60,
        }
        (self.base / "settings.json").write_text(json.dumps(legacy_settings), encoding="utf-8")
        legacy_radio = [{"name": "FM4", "url": "https://example.invalid/fm4"}]
        legacy_tv = [{"id": "arte", "name": "ARTE"}]
        (self.base / "radio.json").write_text(json.dumps(legacy_radio), encoding="utf-8")
        (self.base / "tvfavs.json").write_text(json.dumps(legacy_tv), encoding="utf-8")
        (self.base / "resume.json").write_text(json.dumps({"movie.mkv": 120}), encoding="utf-8")
        (self.base / "yt-subs.json").write_text(json.dumps([{"id": "UC1"}]), encoding="utf-8")

        svc = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        self.assertTrue(svc.migration_report.migrated)
        self.assertEqual(svc.migration_report.display_name, "Anna")
        admin_id = svc.migration_report.admin_id

        # Alte globale Dateien bleiben als unveraendertes Backup bestehen
        self.assertEqual(json.loads((self.base / "radio.json").read_text(encoding="utf-8")), legacy_radio)

        # Profil-Dateien und prefs liegen in accounts/data/<admin_id>/
        pdir = self.base / "accounts" / "data" / admin_id
        self.assertTrue((pdir / "radio.json").is_file())
        self.assertTrue((pdir / "tvfavs.json").is_file())
        self.assertTrue((pdir / "resume.json").is_file())
        self.assertTrue((pdir / "yt-subs.json").is_file())
        prefs = svc.load_profile_prefs({"lang": "de", "theme": "default-dark"})
        self.assertEqual(prefs["lang"], "en")
        self.assertEqual(prefs["theme"], "nord")
        self.assertEqual(prefs["ui_sounds_preset"], "retro")
        self.assertNotIn("resolution", prefs)  # geraeteweit, nicht im Profil

        # Aenderungen schreiben ausschliesslich ins Profil, nie in die alten globalen Dateien
        svc.save_profile_prefs({"theme": "high-contrast"})
        radio_path = svc.profile_path("radio.json")
        self.assertEqual(radio_path.parent, pdir)
        radio_path.write_text(json.dumps([{"name": "Changed"}]), encoding="utf-8")
        self.assertEqual(json.loads((self.base / "radio.json").read_text(encoding="utf-8")), legacy_radio)
        self.assertEqual(json.loads((self.base / "settings.json").read_text(encoding="utf-8"))["theme"], "nord")

        # Zweites Profil hat komplett getrennte Dateien
        bob = svc.create_account("Bob", role="standard")
        svc.switch_account(bob.id)
        self.assertNotEqual(svc.profile_path("radio.json"), radio_path)
        self.assertFalse(svc.profile_path("radio.json").exists())

        # Zweiter Start migriert nicht nochmal
        svc.close()
        svc2 = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        self.assertFalse(svc2.migration_report.migrated)
        self.assertEqual(len(svc2.list_accounts()), 2)
        svc2.close()

    def test_guest_session_ephemeral_and_permissions(self) -> None:
        svc = AccountService(self.base, runtime_dir=self.runtime, clock=self.clock)
        admin = svc.list_accounts()[0]

        with self.assertRaises(PolicyError):
            svc.start_guest_session()

        svc.set_device_policy(guest_enabled=True)
        guest = svc.start_guest_session()
        self.assertTrue(guest.is_guest)

        guest_radio = svc.profile_path("radio.json")
        guest_radio.write_text("[]", encoding="utf-8")
        svc.save_profile_prefs({"lang": "en"})
        guest_dir = self.runtime / "voidstation-guest"
        self.assertTrue(guest_dir.is_dir())
        self.assertEqual(_mode(guest_dir), 0o700)

        # Berechtigungen pruefen
        self.assertEqual(_mode(self.base / "accounts"), 0o700)
        self.assertEqual(_mode(self.base / "accounts" / "accounts.db"), 0o600)
        self.assertEqual(_mode(self.base / "accounts" / "tokens.db"), 0o600)
        self.assertEqual(_mode(self.base / "accounts" / "data" / admin.id), 0o700)

        # Wechsel oder Lock loescht Gast-Verzeichnis restlos
        svc.switch_account(admin.id)
        self.assertFalse(guest_dir.exists())

        svc.start_guest_session()
        svc.profile_path("tvfavs.json").write_text("[]", encoding="utf-8")
        self.assertTrue(guest_dir.exists())
        svc.lock_session()
        self.assertFalse(guest_dir.exists())

        svc.start_guest_session()
        self.assertTrue(guest_dir.exists())
        svc.close()
        self.assertFalse(guest_dir.exists())

    def test_vsreport_scrubs_hashes_pins_and_tokens(self) -> None:
        scrub = vsreport.Scrub()
        sample = "\n".join(
            [
                "hash=$vs-scrypt$n=32768,r=8,p=1$c2FsdA$aGFzaA",
                "argon=$vs-argon2id$m=32768,t=3,p=1$c2FsdA$aGFzaA",
                "pbkdf=$vs-pbkdf2-sha256$i=600000$c2FsdA$aGFzaA",
                "pin=2580",
                "X-VS-Token: super_secret_runtime_token_123456",
                "refresh_token=rt_secret_value_abc",
            ]
        )
        cleaned = scrub(sample)
        self.assertNotIn("c2FsdA", cleaned)
        self.assertNotIn("2580", cleaned)
        self.assertNotIn("super_secret_runtime_token_123456", cleaned)
        self.assertNotIn("rt_secret_value_abc", cleaned)
        self.assertIn("[hash]", cleaned)

    def test_cli_bootstrap_status_list_unlock(self) -> None:
        payload = json.dumps({"display_name": "Wohnzimmer", "password": "StartPass123", "pin": "5588"})
        orig_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(payload)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = account_cli.main(["--base", str(self.base), "bootstrap"])
            self.assertEqual(rc, 0)
            boot_out = json.loads(buf.getvalue())
            self.assertTrue(boot_out["ok"])
            self.assertEqual(boot_out["admin"]["display_name"], "Wohnzimmer")
            self.assertTrue(boot_out["admin"]["has_pin"])
            self.assertTrue(boot_out["admin"]["has_password"])
        finally:
            sys.stdin = orig_stdin

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = account_cli.main(["--base", str(self.base), "list"])
        self.assertEqual(rc, 0)
        listed = json.loads(buf.getvalue())
        self.assertEqual(len(listed), 1)
        self.assertNotIn("5588", buf.getvalue())
        self.assertNotIn("StartPass123", buf.getvalue())

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = account_cli.main(["--base", str(self.base), "status"])
        self.assertEqual(rc, 0)
        st = json.loads(buf.getvalue())
        self.assertEqual(st["accounts_count"], 1)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = account_cli.main(["--base", str(self.base), "unlock", "Wohnzimmer"])
        self.assertEqual(rc, 0)

        # Ungueltige Permissions auf secret-file ablehnen
        bad_secret = self.root / "bad.json"
        bad_secret.write_text(payload, encoding="utf-8")
        os.chmod(bad_secret, 0o644)
        rc_bad = account_cli.main(["--base", str(self.base), "bootstrap", "--secret-file", str(bad_secret)])
        self.assertEqual(rc_bad, 1)


class VsAccountStage2BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.base = self.root / "voidstation"
        self.runtime = self.root / "runtime"
        self.share = self.root / "share"
        self.base.mkdir(parents=True)
        self.runtime.mkdir(parents=True)
        self.share.mkdir(parents=True)
        self.clock = FakeClock()

        self._orig_env = {
            k: os.environ.get(k)
            for k in ("VS_NO_DESKTOP_SYNC", "VS_SOUNDS", "XDG_RUNTIME_DIR", "VOIDSTATION_BASE")
        }
        os.environ["VS_NO_DESKTOP_SYNC"] = "1"
        os.environ["VS_SOUNDS"] = "0"
        os.environ["XDG_RUNTIME_DIR"] = str(self.runtime)
        os.environ["VOIDSTATION_BASE"] = str(self.base)

        self._orig_settings = launcher.SETTINGS
        self._orig_config = launcher.CONFIG
        self._orig_share = launcher.MEDIA.share

        self.tiles_path = self.base / "tiles.json"
        self.settings_path = self.base / "settings.json"
        self.tiles_path.write_text(
            json.dumps(
                {
                    "title": "Start",
                    "user": "LegacyUser",
                    "groups": [{"name": "System", "tiles": [{"id": "settings", "label": "Settings"}]}],
                }
            ),
            encoding="utf-8",
        )
        self.settings_path.write_text(
            json.dumps({"lang": "de", "theme": "default-dark", "padmouse": True, "sysupd_days": 90}),
            encoding="utf-8",
        )
        launcher.CONFIG = self.tiles_path
        launcher.SETTINGS = self.settings_path
        launcher.MEDIA.share = lambda: self.share  # type: ignore[method-assign]

        self.token = launcher.init_api_token(runtime_dir=self.runtime)
        self.svc = launcher.init_accounts(base_dir=self.base, runtime_dir=self.runtime, clock=self.clock)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), launcher.Handler)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        launcher.close_accounts()
        launcher.CONFIG = self._orig_config
        launcher.SETTINGS = self._orig_settings
        launcher.MEDIA.share = self._orig_share  # type: ignore[method-assign]
        with launcher._API_TOKEN_LOCK:
            launcher._API_TOKEN = ""
            launcher._RUNTIME_DIR_OVERRIDE = None
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def _req(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        xtv: bool = True,
        token: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        headers: dict[str, str] = {}
        if xtv:
            headers["X-TV"] = "1"
        tok = self.token if token is None else token
        if tok:
            headers[vsaccount.API_TOKEN_HEADER] = tok
        data: bytes | None = None
        if body is not None or method == "POST":
            headers["Content-Type"] = "application/json"
            data = json.dumps({} if body is None else body).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            with exc:
                raw = exc.read().decode("utf-8", "replace")
                code = exc.code
            try:
                parsed = json.loads(raw) if raw else {}
            except ValueError:
                parsed = {"raw": raw}
            return code, parsed

    def test_runtime_token_permissions_enforcement_and_osk_compat(self) -> None:
        tok_file = self.runtime / vsaccount.API_TOKEN_FILENAME
        self.assertTrue(tok_file.is_file())
        self.assertEqual(_mode(tok_file), 0o600)
        self.assertEqual(tok_file.read_text(encoding="utf-8").strip(), self.token)

        for method, path in (
            ("GET", "/api/session"),
            ("GET", "/api/accounts"),
            ("POST", "/api/session/lock"),
            ("POST", "/api/accounts/create"),
        ):
            code_missing, _ = self._req(method, path, token="")
            self.assertEqual(code_missing, 403, f"expected 403 without token on {method} {path}")
            code_wrong, _ = self._req(method, path, token="wrong-token-value")
            self.assertEqual(code_wrong, 403, f"expected 403 with wrong token on {method} {path}")
            code_no_xtv, _ = self._req(method, path, xtv=False, token=self.token)
            self.assertEqual(code_no_xtv, 403, f"expected 403 without X-TV on {method} {path}")

        code_sess, sess_data = self._req("GET", "/api/session")
        self.assertEqual(code_sess, 200)
        self.assertEqual(sess_data["session"]["display_name"], "LegacyUser")

        # Browser-OSK-Erweiterung nutzt weiterhin ausschliesslich X-TV: 1 ohne Token
        code_osk, osk_data = self._req("POST", "/api/osk/field", {"ev": "blur"}, xtv=True, token="")
        self.assertEqual(code_osk, 200)
        self.assertTrue(osk_data["ok"])
        code_osk_no_xtv, _ = self._req("POST", "/api/osk/field", {"ev": "blur"}, xtv=False, token=self.token)
        self.assertEqual(code_osk_no_xtv, 403)

    def test_session_and_account_routes_rbac_and_tiles_compat(self) -> None:
        admin_id = self.svc.list_accounts()[0].id

        code_st, st = self._req("GET", "/api/status", xtv=False, token="")
        self.assertEqual(code_st, 200)
        self.assertEqual(st["account"]["id"], admin_id)
        self.assertEqual(st["account"]["name"], "LegacyUser")
        self.assertEqual(st["account"]["role"], "admin")
        self.assertEqual(st["account"]["count"], 1)

        code_tiles, tiles = self._req("GET", "/tiles.json", xtv=False, token="")
        self.assertEqual(code_tiles, 200)
        self.assertEqual(tiles["user"], "LegacyUser")

        # Konten anlegen
        c_std, d_std = self._req(
            "POST",
            "/api/accounts/create",
            {"display_name": "Alex", "role": "standard", "pin": "2468"},
        )
        self.assertEqual(c_std, 200)
        std_id = d_std["account"]["id"]
        self.assertTrue(d_std["account"]["has_pin"])

        c_child_fail, _ = self._req("POST", "/api/accounts/create", {"display_name": "Kind", "role": "child"})
        self.assertEqual(c_child_fail, 403)

        c_child, d_child = self._req(
            "POST",
            "/api/accounts/create",
            {"display_name": "Lina", "role": "child", "parent_id": admin_id, "pin": "1357"},
        )
        self.assertEqual(c_child, 200)
        child_id = d_child["account"]["id"]

        # Admin umbenennen -> /tiles.json["user"] spiegelt neuen Namen, Datei auf Platte bleibt unberuehrt
        c_upd, _ = self._req("POST", "/api/accounts/update", {"account_id": admin_id, "display_name": "Eltern"})
        self.assertEqual(c_upd, 200)
        _, tiles_after = self._req("GET", "/tiles.json", xtv=False, token="")
        self.assertEqual(tiles_after["user"], "Eltern")
        self.assertEqual(json.loads(self.tiles_path.read_text(encoding="utf-8"))["user"], "LegacyUser")

        # Credentials setzen (inkl. weak_pin-Hinweis), pruefen beim Wechsel + Cooldown
        c_cred, d_cred = self._req(
            "POST",
            "/api/accounts/credentials",
            {"account_id": std_id, "factor": "pin", "secret": "1234"},
        )
        self.assertEqual(c_cred, 200)
        self.assertTrue(d_cred["weak_pin"])

        c_acc, d_acc = self._req("GET", "/api/accounts")
        self.assertEqual(c_acc, 200)
        self.assertEqual(len(d_acc["accounts"]), 3)
        self.assertNotIn("hash", json.dumps(d_acc))
        self.assertNotIn("1234", json.dumps(d_acc))

        for _ in range(3):
            c_bad, _ = self._req("POST", "/api/session/switch", {"account_id": std_id, "pin": "9999"})
            self.assertEqual(c_bad, 401)
        c_cd, d_cd = self._req("POST", "/api/session/switch", {"account_id": std_id, "pin": "9999"})
        self.assertEqual(c_cd, 429)
        self.assertEqual(d_cd["error"], "account.cooldown")
        self.assertEqual(d_cd["retry_after"], 15)

        self.clock.advance(16)
        c_ok, d_ok = self._req("POST", "/api/session/switch", {"account_id": std_id, "pin": "1234"})
        self.assertEqual(c_ok, 200)
        self.assertEqual(d_ok["session"]["account_id"], std_id)

        _, st2 = self._req("GET", "/api/status", xtv=False, token="")
        self.assertEqual(st2["account"]["id"], std_id)
        self.assertEqual(st2["account"]["name"], "Alex")
        _, tiles2 = self._req("GET", "/tiles.json", xtv=False, token="")
        self.assertEqual(tiles2["user"], "Alex")

        # RBAC als Standard-User: verbotene Admin-Aktionen -> 403, eigenes kosmetisches Update -> 200
        self.assertEqual(self._req("POST", "/api/accounts/create", {"display_name": "X"})[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/delete", {"account_id": child_id})[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/device-policy", {"guest_enabled": True})[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/update", {"account_id": std_id, "role": "admin"})[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/update", {"account_id": admin_id, "display_name": "Hack"})[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/update", {"account_id": std_id, "avatar": "gamepad"})[0], 200)

        # Child darf keine Konto-Mutationen durchfuehren
        self.assertEqual(self._req("POST", "/api/session/switch", {"account_id": child_id, "pin": "1357"})[0], 200)
        self.assertEqual(self._req("POST", "/api/accounts/update", {"account_id": child_id, "avatar": "star"})[0], 403)

        # Lock sperrt geschuetzte Mutationen
        c_lock, d_lock = self._req("POST", "/api/session/lock")
        self.assertEqual(c_lock, 200)
        self.assertTrue(d_lock["session"]["locked"])
        self.assertEqual(self._req("POST", "/api/accounts/create", {"display_name": "Locked"})[0], 403)

        # Als Admin wieder anmelden, Policy setzen, Standard-Konto loeschen (letzter Admin bleibt geschuetzt)
        self.assertEqual(self._req("POST", "/api/session/switch", {"account_id": admin_id})[0], 200)
        c_pol, d_pol = self._req(
            "POST",
            "/api/accounts/device-policy",
            {"ask_on_boot": True, "guest_enabled": True, "guest_allowed_tiles": ["tv", "radio"]},
        )
        self.assertEqual(c_pol, 200)
        self.assertTrue(d_pol["device_policy"]["ask_on_boot"])
        self.assertEqual(d_pol["device_policy"]["guest_allowed_tiles"], ["tv", "radio"])

        self.assertEqual(self._req("POST", "/api/accounts/delete", {"account_id": admin_id})[0], 403)
        c_del, _ = self._req("POST", "/api/accounts/delete", {"account_id": std_id})
        self.assertEqual(c_del, 200)
        self.assertFalse((self.base / "accounts" / "data" / std_id).exists())

    def test_profile_files_and_prefs_strict_isolation_via_backend(self) -> None:
        admin_id = self.svc.list_accounts()[0].id
        _, d_bob = self._req("POST", "/api/accounts/create", {"display_name": "Bob", "role": "standard"})
        bob_id = d_bob["account"]["id"]

        # Legacy-Dateien in base_dir duerfen bei Profil-Schreibvorgaengen nie ueberschrieben werden
        legacy_radio = [{"name": "LegacyFM", "url": "https://legacy.invalid/fm"}]
        legacy_tvfavs = [{"key": "legacy1", "name": "LegacyTV", "url": "https://legacy.invalid/tv"}]
        legacy_tvrecent = [{"key": "legacy1", "name": "LegacyTV", "url": "https://legacy.invalid/tv"}]
        legacy_resume = {"legacy.mkv": {"pos": 90, "dur": 600, "t": 1}}
        legacy_yt = [{"id": "UClegacy"}]
        (self.base / "radio.json").write_text(json.dumps(legacy_radio), encoding="utf-8")
        (self.base / "tvfavs.json").write_text(json.dumps(legacy_tvfavs), encoding="utf-8")
        (self.base / "tvrecent.json").write_text(json.dumps(legacy_tvrecent), encoding="utf-8")
        (self.base / "resume.json").write_text(json.dumps(legacy_resume), encoding="utf-8")
        (self.base / "yt-subs.json").write_text(json.dumps(legacy_yt), encoding="utf-8")
        (self.base / "yt-history.json").write_text(json.dumps(legacy_yt), encoding="utf-8")
        (self.base / "yt-later.json").write_text(json.dumps(legacy_yt), encoding="utf-8")

        video_file = self.share / "Videos" / "demo.mkv"
        video_file.parent.mkdir(parents=True, exist_ok=True)
        video_file.write_bytes(b"demo")

        # Profil Admin schreibt Daten & Praeferenzen
        self.assertEqual(
            self._req(
                "POST",
                "/api/radio/fav",
                {"name": "AdminRadio", "url": "https://example.invalid/admin", "country": "DE"},
            )[0],
            200,
        )
        launcher.tvfavs_save([{"key": "admin_tv", "name": "AdminTV", "url": "https://example.invalid/tv"}])
        launcher.tvrecent_save([{"key": "admin_tv", "name": "AdminTV", "url": "https://example.invalid/tv"}])
        launcher.MEDIA.resume_set(str(video_file), 120, 600)
        launcher.YT.sub_set({"item": {"id": "UC1234567890123456789012", "title": "AdminChan"}, "on": True})
        launcher.YT.later_set({"item": {"id": "dQw4w9WgXcQ", "title": "AdminLater"}, "on": True})
        launcher.YT.progress({"id": "dQw4w9WgXcQ", "title": "AdminHist", "pos": 50, "dur": 200})

        self.assertEqual(self._req("POST", "/api/settings/lang", {"lang": "en"})[0], 200)
        self.assertEqual(self._req("POST", "/api/settings/theme", {"theme": "nord"})[0], 200)
        self.assertEqual(self._req("POST", "/api/settings/scale", {"scale": 1.5})[0], 200)
        self.assertEqual(self._req("POST", "/api/settings/sounds", {"on": False, "preset": "retro", "volume": 45})[0], 200)
        self.assertEqual(self._req("POST", "/api/settings/osk", {"layout": "us", "mode": "always"})[0], 200)

        # Globale Altdateien & settings.json bleiben unberuehrt
        self.assertEqual(json.loads((self.base / "radio.json").read_text(encoding="utf-8")), legacy_radio)
        self.assertEqual(json.loads((self.base / "tvfavs.json").read_text(encoding="utf-8")), legacy_tvfavs)
        self.assertEqual(json.loads((self.base / "tvrecent.json").read_text(encoding="utf-8")), legacy_tvrecent)
        self.assertEqual(json.loads((self.base / "resume.json").read_text(encoding="utf-8")), legacy_resume)
        self.assertEqual(json.loads((self.base / "yt-subs.json").read_text(encoding="utf-8")), legacy_yt)
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8"))["theme"], "default-dark")
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8"))["lang"], "de")

        # Geraeteweite Einstellung aendert settings.json, ohne Profil-Praeferenzen dorthin zu schreiben
        self.assertEqual(self._req("POST", "/api/settings/padmouse", {"on": False})[0], 200)
        raw_sett = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertFalse(raw_sett["padmouse"])
        self.assertEqual(raw_sett["theme"], "default-dark")
        self.assertEqual(raw_sett["lang"], "de")

        # Wechsel zu Bob: komplett getrennte Profildaten und Praeferenzen
        self.assertEqual(self._req("POST", "/api/session/switch", {"account_id": bob_id})[0], 200)
        _, bob_favs = self._req("GET", "/api/radio/favs")
        self.assertEqual(bob_favs, [])
        self.assertEqual(launcher.tvfavs_load(), [])
        self.assertEqual(launcher.tvrecent_load(), [])
        self.assertEqual(launcher.MEDIA.resume_load(), {})
        self.assertEqual(launcher.YT.subs(), [])
        self.assertEqual(launcher.YT.later()["items"], [])
        self.assertEqual(launcher.YT.history()["items"], [])

        _, bob_sett = self._req("GET", "/api/settings")
        self.assertEqual(bob_sett["lang"], "de")
        self.assertEqual(bob_sett["theme"], "default-dark")
        self.assertEqual(bob_sett["scale"], 1.75)
        self.assertFalse(bob_sett["padmouse"])

        # Zurueck zu Admin: dessen Dateien & Praeferenzen sind intakt
        self.assertEqual(self._req("POST", "/api/session/switch", {"account_id": admin_id})[0], 200)
        _, admin_favs = self._req("GET", "/api/radio/favs")
        self.assertEqual(len(admin_favs), 1)
        self.assertEqual(admin_favs[0]["name"], "AdminRadio")
        _, admin_sett = self._req("GET", "/api/settings")
        self.assertEqual(admin_sett["lang"], "en")
        self.assertEqual(admin_sett["theme"], "nord")
        self.assertEqual(admin_sett["sounds"]["preset"], "retro")

    def test_guest_mode_ephemeral_and_cleanup(self) -> None:
        admin_id = self.svc.list_accounts()[0].id
        guest_dir = self.runtime / "voidstation-guest"

        # Gast deaktiviert -> 403
        self.assertEqual(self._req("POST", "/api/session/guest")[0], 403)
        self.assertEqual(self._req("POST", "/api/accounts/device-policy", {"guest_enabled": True})[0], 200)

        # Gast starten & Daten schreiben -> liegen nur im fluchtigen Runtime-Ordner
        c_g, d_g = self._req("POST", "/api/session/guest", {"display_name": "Besucher"})
        self.assertEqual(c_g, 200)
        self.assertTrue(d_g["session"]["is_guest"])
        self.assertEqual(
            self._req("POST", "/api/radio/fav", {"name": "GuestFM", "url": "https://example.invalid/guest"})[0],
            200,
        )
        self.assertEqual(self._req("POST", "/api/settings/lang", {"lang": "en"})[0], 200)
        self.assertTrue((guest_dir / "radio.json").is_file())
        self.assertTrue((guest_dir / "prefs.json").is_file())

        # Cleanup (a) beim Profilwechsel
        self.assertEqual(self._req("POST", "/api/session/switch", {"account_id": admin_id})[0], 200)
        self.assertFalse(guest_dir.exists())

        # Cleanup (b) beim Sperren
        self.assertEqual(self._req("POST", "/api/session/guest")[0], 200)
        self.assertTrue(guest_dir.is_dir())
        self.assertEqual(self._req("POST", "/api/session/lock")[0], 200)
        self.assertFalse(guest_dir.exists())

        # Cleanup (c) beim Beenden des Backends
        self.assertEqual(self._req("POST", "/api/session/guest")[0], 200)
        self.assertTrue(guest_dir.is_dir())
        launcher.close_accounts()
        self.assertFalse(guest_dir.exists())

    def test_vsctl_and_token_helpers(self) -> None:
        env = dict(os.environ)
        env["VS_API"] = f"http://127.0.0.1:{self.port}"
        env["XDG_RUNTIME_DIR"] = str(self.runtime)

        proc = subprocess.run(
            [str(REPO / "launcher" / "vsctl"), "status"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        status_json = json.loads(proc.stdout)
        self.assertIn("account", status_json)

        # Token-Hilfsfunktionen & Symlink-Abwehr
        self.assertTrue(vsaccount.verify_api_token(self.token, self.token))
        self.assertFalse(vsaccount.verify_api_token("invalid", self.token))
        sym_rt = self.root / "sym_rt"
        sym_rt.mkdir()
        target = self.root / "target.txt"
        target.write_text("evil", encoding="utf-8")
        (sym_rt / vsaccount.API_TOKEN_FILENAME).symlink_to(target)
        self.assertEqual(vsaccount.read_api_token(sym_rt), "")
        created = vsaccount.ensure_api_token(sym_rt)
        self.assertTrue(vsaccount.verify_api_token(created, vsaccount.read_api_token(sym_rt)))
        self.assertEqual(_mode(sym_rt / vsaccount.API_TOKEN_FILENAME), 0o600)

        # Statische Pruefung von launcher/qt/vscommon.py (ohne PySide6-Import)
        vscommon_src = (REPO / "launcher" / "qt" / "vscommon.py").read_text(encoding="utf-8")
        ast.parse(vscommon_src)
        self.assertIn("API_TOKEN_HEADER", vscommon_src)
        self.assertIn("read_api_token", vscommon_src)


if __name__ == "__main__":
    unittest.main()
