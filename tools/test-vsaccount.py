#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit-Tests fuer Stufe 1 des VoidStation-Account-Systems (launcher/vsaccount/)."""
from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "launcher"))

import vsreport  # noqa: E402
from vsaccount import (  # noqa: E402
    AccountService,
    AuthError,
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


if __name__ == "__main__":
    unittest.main()
