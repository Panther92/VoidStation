#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI-Werkzeug fuer Notfall-Wiederherstellung, Inspektion und Installer-Bootstrap.

Wichtig: Passwoerter und PINs werden niemals ueber Kommandozeilenargumente entgegengenommen,
sondern ausschliesslich ueber stdin, 0600-Dateien oder interaktives getpass().
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vsaccount import AccountError, AccountService


def _default_base() -> Path:
    env = os.environ.get("VOIDSTATION_BASE", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".local" / "share" / "voidstation"


def _read_secret_json(secret_file: str | None) -> dict[str, Any]:
    if secret_file:
        p = Path(secret_file)
        st = p.stat()
        if stat.S_IMODE(st.st_mode) & 0o077:
            raise AccountError("account.err.invalid", "Secret file permissions must be 0600 or stricter")
        raw = p.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise AccountError("account.err.invalid", "Bootstrap payload must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vsaccount.cli", description="VoidStation Account CLI")
    ap.add_argument("--base", type=Path, default=None, help="VoidStation data directory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show account system status as JSON")
    sub.add_parser("list", help="List public account metadata as JSON")

    p_unlock = sub.add_parser("unlock", help="Clear auth cooldown and PIN lock for an account")
    p_unlock.add_argument("target", help="Account id or display name")

    p_pin = sub.add_parser("reset-pin", help="Interactively set or remove an account PIN")
    p_pin.add_argument("target", help="Account id or display name")
    p_pin.add_argument("--remove", action="store_true", help="Remove PIN instead of setting a new one")

    p_boot = sub.add_parser("bootstrap", help="Create/update initial admin from stdin or 0600 JSON file")
    p_boot.add_argument("--secret-file", default=None, help="Path to 0600 JSON file")

    args = ap.parse_args(argv)
    base_dir = args.base or _default_base()
    svc = AccountService(base_dir)
    try:
        if args.cmd == "status":
            accounts = svc.list_accounts()
            out = {
                "base": str(base_dir),
                "accounts_count": len(accounts),
                "migrated": svc.migration_report.migrated,
                "device_policy": svc.get_device_policy().to_dict(),
                "session": svc.get_session().to_public_dict(),
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "list":
            out_list = [a.to_public_dict() for a in svc.list_accounts()]
            print(json.dumps(out_list, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "unlock":
            acc = svc.find_account(args.target)
            if not acc:
                print(f"Account not found: {args.target}", file=sys.stderr)
                return 1
            svc.unlock_account(acc.id)
            print(json.dumps({"ok": True, "account_id": acc.id}, ensure_ascii=False))
            return 0

        if args.cmd == "reset-pin":
            acc = svc.find_account(args.target)
            if not acc:
                print(f"Account not found: {args.target}", file=sys.stderr)
                return 1
            if args.remove:
                svc.remove_credential(acc.id, "pin")
                print(json.dumps({"ok": True, "account_id": acc.id, "has_pin": False}, ensure_ascii=False))
                return 0
            p1 = getpass.getpass("New PIN (4-8 digits): ")
            p2 = getpass.getpass("Repeat PIN: ")
            if p1 != p2:
                print("PINs do not match", file=sys.stderr)
                return 1
            updated = svc.set_credential(acc.id, "pin", p1)
            print(json.dumps({"ok": True, "account_id": updated.id, "has_pin": updated.has_pin}, ensure_ascii=False))
            return 0

        if args.cmd == "bootstrap":
            payload = _read_secret_json(args.secret_file)
            name = str(payload.get("display_name") or "").strip()
            auto_login = payload.get("auto_login")
            password = payload.get("password")
            pin = payload.get("pin")
            accounts = svc.list_accounts()
            admin = next((a for a in accounts if a.role == "admin"), None)
            if admin is None:
                admin = svc.create_account(
                    display_name=name or "VoidStation",
                    role="admin",
                    auto_login=True if auto_login is None else bool(auto_login),
                    password=str(password) if password is not None else None,
                    pin=str(pin) if pin is not None else None,
                )
            else:
                if name or auto_login is not None:
                    admin = svc.update_account(
                        admin.id,
                        display_name=name or None,
                        auto_login=bool(auto_login) if auto_login is not None else None,
                    )
                if password is not None:
                    admin = svc.set_credential(admin.id, "password", str(password))
                if pin is not None:
                    admin = svc.set_credential(admin.id, "pin", str(pin))
            print(json.dumps({"ok": True, "admin": admin.to_public_dict()}, ensure_ascii=False))
            return 0
    except (AccountError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        svc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
