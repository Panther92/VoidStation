# SPDX-License-Identifier: GPL-3.0-or-later
"""Kryptografisches Passwort- und PIN-Hashing im versionierten PHC-Format."""
from __future__ import annotations

import base64
import hashlib
import hmac
import platform
import re
import secrets
import threading
from pathlib import Path
from typing import Any

from .models import ValidationError

try:
    import argon2 as _argon2  # type: ignore[import-not-found]
except ImportError:
    _argon2: Any = None  # type: ignore[no-redef]

PIN_RE = re.compile(r"^\d{4,8}$")
TRIVIAL_PINS = frozenset(
    {
        "0000",
        "1111",
        "2222",
        "3333",
        "4444",
        "5555",
        "6666",
        "7777",
        "8888",
        "9999",
        "1234",
        "4321",
        "12345",
        "123456",
        "654321",
    }
)

ARGON2_MEMORY_KIB = 32768
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 1

SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_N_PASSWORD = 32768
SCRYPT_N_LOWMEM = 16384

PBKDF2_ITERATIONS = 600_000
PBKDF2_DKLEN = 32

# Schuetzt 4-GB-/32-Bit-Systeme bei parallelen Auth-Versuchen vor RAM-Spitzen.
_KDF_SEMAPHORE = threading.Semaphore(2)


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64_decode(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode((txt + pad).encode("ascii"))


def _mem_total_gib() -> float:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                kib = int(line.split()[1])
                return kib / (1024.0 * 1024.0)
    except (OSError, ValueError, IndexError):
        pass
    return 4.0


def _scrypt_n_for_factor(factor: str) -> int:
    if factor == "pin":
        return SCRYPT_N_LOWMEM
    if platform.machine() in ("i386", "i686") or _mem_total_gib() < 3.0:
        return SCRYPT_N_LOWMEM
    return SCRYPT_N_PASSWORD


def _scrypt_maxmem(n: int, r: int, p: int) -> int:
    return max(64 * 1024 * 1024, 128 * r * (n + p + 2) + 4 * 1024 * 1024)


def _scrypt_derive(secret: str, salt: bytes, n: int, r: int, p: int, dklen: int = SCRYPT_DKLEN) -> bytes:
    with _KDF_SEMAPHORE:
        return hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=_scrypt_maxmem(n, r, p),
            dklen=dklen,
        )


def _pbkdf2_derive(secret: str, salt: bytes, iterations: int, dklen: int = PBKDF2_DKLEN) -> bytes:
    with _KDF_SEMAPHORE:
        return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations, dklen=dklen)


def _argon2_available() -> bool:
    return _argon2 is not None and hasattr(_argon2, "low_level")


def _argon2_derive(secret: str, salt: bytes, m_kib: int, t_cost: int, p_cost: int, dklen: int = 32) -> bytes:
    with _KDF_SEMAPHORE:
        return _argon2.low_level.hash_secret_raw(
            secret=secret.encode("utf-8"),
            salt=salt,
            time_cost=t_cost,
            memory_cost=m_kib,
            parallelism=p_cost,
            hash_len=dklen,
            type=_argon2.low_level.Type.ID,
        )


def validate_pin(pin: str) -> str:
    """Prueft das PIN-Format (4-8 Ziffern) und liefert die bereinigte PIN."""
    if not isinstance(pin, str) or not PIN_RE.fullmatch(pin):
        raise ValidationError("account.err.pinFormat", "Invalid PIN format")
    return pin


def validate_password(password: str) -> str:
    """Prueft das Passwortformat (1-200 Zeichen, kein Nullbyte)."""
    if not isinstance(password, str) or not password or len(password) > 200 or "\x00" in password:
        raise ValidationError("account.err.pwFormat", "Invalid password format")
    return password


def is_weak_pin(pin: str) -> bool:
    """Erkennt haeufige triviale PINs (nur fuer optionale UI-Hinweise)."""
    return pin in TRIVIAL_PINS or (len(set(pin)) == 1 and len(pin) >= 4)


def default_algorithm() -> str:
    if _argon2_available():
        return "vs-argon2id"
    if hasattr(hashlib, "scrypt"):
        return "vs-scrypt"
    return "vs-pbkdf2-sha256"


def hash_secret(secret: str, factor: str = "password", preferred_algo: str | None = None) -> str:
    """Erzeugt einen gesalzenen PHC-Hash fuer Passwort oder PIN."""
    if factor == "pin":
        secret = validate_pin(secret)
    elif factor == "password":
        secret = validate_password(secret)
    else:
        raise ValidationError("account.err.invalid", "Invalid credential factor")

    algo = preferred_algo or default_algorithm()
    salt = secrets.token_bytes(16)

    if algo == "vs-argon2id":
        if not _argon2_available():
            algo = "vs-scrypt" if hasattr(hashlib, "scrypt") else "vs-pbkdf2-sha256"
        else:
            digest = _argon2_derive(secret, salt, ARGON2_MEMORY_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM)
            return (
                f"$vs-argon2id$m={ARGON2_MEMORY_KIB},t={ARGON2_TIME_COST},p={ARGON2_PARALLELISM}"
                f"${_b64_encode(salt)}${_b64_encode(digest)}"
            )

    if algo == "vs-scrypt":
        if not hasattr(hashlib, "scrypt"):
            algo = "vs-pbkdf2-sha256"
        else:
            n = _scrypt_n_for_factor(factor)
            digest = _scrypt_derive(secret, salt, n, SCRYPT_R, SCRYPT_P)
            return f"$vs-scrypt$n={n},r={SCRYPT_R},p={SCRYPT_P}${_b64_encode(salt)}${_b64_encode(digest)}"

    if algo == "vs-pbkdf2-sha256":
        digest = _pbkdf2_derive(secret, salt, PBKDF2_ITERATIONS)
        return f"$vs-pbkdf2-sha256$i={PBKDF2_ITERATIONS}${_b64_encode(salt)}${_b64_encode(digest)}"

    raise ValidationError("account.err.invalid", f"Unsupported hash algorithm: {algo}")


def _parse_params(param_str: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in param_str.split(","):
        k, sep, v = part.partition("=")
        if not sep:
            raise ValueError("malformed param")
        out[k] = int(v)
    return out


def verify_secret(secret: str, stored_hash: str, factor: str = "password") -> tuple[bool, bool]:
    """Prueft secret gegen stored_hash und meldet (valid, needs_rehash)."""
    if not isinstance(secret, str) or not secret or "\x00" in secret:
        return False, False
    if not isinstance(stored_hash, str) or not stored_hash.startswith("$"):
        return False, False

    parts = stored_hash.split("$")
    if len(parts) != 5 or parts[0] != "":
        return False, False

    _, algo, param_str, salt_b64, hash_b64 = parts
    try:
        params = _parse_params(param_str)
        salt = _b64_decode(salt_b64)
        expected = _b64_decode(hash_b64)
    except (ValueError, KeyError):
        return False, False

    if len(salt) < 8 or not expected:
        return False, False

    if algo == "vs-argon2id":
        if not _argon2_available():
            return False, False
        m_kib = params.get("m", 0)
        t_cost = params.get("t", 0)
        p_cost = params.get("p", 0)
        if m_kib < 8192 or t_cost < 1 or p_cost < 1 or m_kib > 262144:
            return False, False
        actual = _argon2_derive(secret, salt, m_kib, t_cost, p_cost, dklen=len(expected))
        ok = hmac.compare_digest(actual, expected)
        needs_rehash = ok and (
            default_algorithm() != "vs-argon2id"
            or m_kib < ARGON2_MEMORY_KIB
            or t_cost < ARGON2_TIME_COST
            or p_cost < ARGON2_PARALLELISM
        )
        return ok, needs_rehash

    if algo == "vs-scrypt":
        if not hasattr(hashlib, "scrypt"):
            return False, False
        n = params.get("n", 0)
        r = params.get("r", 0)
        p = params.get("p", 0)
        if n < 1024 or (n & (n - 1)) != 0 or r < 1 or p < 1 or n > 131072 or r > 16 or p > 4:
            return False, False
        actual = _scrypt_derive(secret, salt, n, r, p, dklen=len(expected))
        ok = hmac.compare_digest(actual, expected)
        target_n = _scrypt_n_for_factor(factor)
        needs_rehash = ok and (
            default_algorithm() == "vs-argon2id" or n < target_n or r < SCRYPT_R
        )
        return ok, needs_rehash

    if algo == "vs-pbkdf2-sha256":
        iters = params.get("i", 0)
        if iters < 10_000 or iters > 5_000_000:
            return False, False
        actual = _pbkdf2_derive(secret, salt, iters, dklen=len(expected))
        ok = hmac.compare_digest(actual, expected)
        needs_rehash = ok and (default_algorithm() != "vs-pbkdf2-sha256" or iters < PBKDF2_ITERATIONS)
        return ok, needs_rehash

    return False, False
