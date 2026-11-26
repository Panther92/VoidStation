# SPDX-License-Identifier: GPL-3.0-or-later
"""Modulare Online-/Store-Identity-Schnittstelle (Offline-First, Device-Code-Flow, Token-Vault, Entitlement-Cache)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .models import (
    AccountError,
    AuthError,
    IdentityLink,
    NotFoundError,
    PolicyError,
    ValidationError,
)
from .storage import SAFE_ID_RE
from .store import AccountStore

DEFAULT_OFFLINE_GRACE_SECONDS = 14 * 86400
DEFAULT_ENTITLEMENT_TTL_SECONDS = 86400
TOKEN_KEY_FILENAME = "tokens.key"
_VAULT_MAGIC = b"VS1\x01"
_NONCE_LEN = 16
_MAC_LEN = 32


class IdentityError(AccountError):
    """Basisfehler fuer Online-/Store-Identity-Provider."""


class IdentityOfflineError(IdentityError):
    """Netzwerk-/Provider-Zugriff ist offline oder nicht erreichbar."""

    def __init__(self, code: str = "identity.err.offline", message: str = "Identity provider unreachable") -> None:
        super().__init__(code, message)


@dataclass(slots=True)
class ProviderInfo:
    """Oeffentliche Beschreibung eines registrierten Identity-/Store-Providers."""

    provider_id: str
    display_name: str
    description: str = ""
    supports_device_code: bool = True
    supports_entitlements: bool = True
    offline_grace_seconds: int = DEFAULT_OFFLINE_GRACE_SECONDS
    capabilities: tuple[str, ...] = ("device_code", "entitlements")

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "description": self.description,
            "supports_device_code": self.supports_device_code,
            "supports_entitlements": self.supports_entitlements,
            "offline_grace_seconds": int(self.offline_grace_seconds),
            "capabilities": list(self.capabilities),
        }


@dataclass(slots=True)
class DeviceCodeChallenge:
    """RFC-8628-konforme Device-Code-Anfrage; `device_code` verlaesst nie das Backend."""

    provider_id: str
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str = ""
    expires_at: int = 0
    interval: int = 5

    def to_public_dict(self) -> dict[str, Any]:
        """Liefert ausschliesslich UI-/QR-Daten ohne das geheime `device_code`-Feld."""
        return {
            "provider_id": self.provider_id,
            "user_code": self.user_code,
            "verification_uri": self.verification_uri,
            "verification_uri_complete": self.verification_uri_complete or self.verification_uri,
            "expires_at": int(self.expires_at),
            "interval": max(1, int(self.interval)),
        }


@dataclass(slots=True)
class ProviderAuthTokens:
    """Geheime Provider-Tokens (ausschliesslich fuer den verschluesselten TokenVault)."""

    access_token: str
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_at: int = 0
    scope: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_secret_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": int(self.expires_at),
            "scope": self.scope,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_secret_dict(cls, data: dict[str, Any]) -> ProviderAuthTokens:
        raw_extra = data.get("extra")
        return cls(
            access_token=str(data.get("access_token") or ""),
            refresh_token=str(data.get("refresh_token") or ""),
            token_type=str(data.get("token_type") or "Bearer"),
            expires_at=int(data.get("expires_at") or 0),
            scope=str(data.get("scope") or ""),
            extra=dict(raw_extra) if isinstance(raw_extra, dict) else {},
        )


@dataclass(slots=True)
class Entitlement:
    """Gecachte Store-/Provider-Berechtigung fuer ein verknuepftes Profil."""

    id: str
    kind: str = "app"
    source: str = ""
    granted_at: int = 0
    expires_at: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "granted_at": int(self.granted_at),
            "expires_at": int(self.expires_at),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entitlement:
        raw_meta = data.get("metadata")
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or "app"),
            source=str(data.get("source") or ""),
            granted_at=int(data.get("granted_at") or 0),
            expires_at=int(data.get("expires_at") or 0),
            metadata=dict(raw_meta) if isinstance(raw_meta, dict) else {},
        )


@dataclass(slots=True)
class DevicePollResult:
    """Antwort eines Providers beim Polling einer Device-Code-Anmeldung."""

    status: str  # pending | slow_down | authorized | expired | denied | error
    subject: str = ""
    display_handle: str = ""
    tokens: ProviderAuthTokens | None = None
    entitlements: list[Entitlement] = field(default_factory=list)
    entitlements_ttl: int = DEFAULT_ENTITLEMENT_TTL_SECONDS
    interval: int = 0
    error: str = ""


@dataclass(slots=True)
class IdentitySyncResult:
    """Ergebnis eines Entitlement-/Status-Abgleichs inkl. Offline-Grace-Metadaten."""

    link: IdentityLink
    entitlements: list[Entitlement]
    entitlements_expires_at: int
    from_cache: bool = False
    offline: bool = False
    grace_active: bool = False
    grace_until: int = 0
    error: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "link": self.link.to_public_dict(),
            "entitlements": [e.to_dict() for e in self.entitlements],
            "entitlements_expires_at": int(self.entitlements_expires_at),
            "from_cache": self.from_cache,
            "offline": self.offline,
            "grace_active": self.grace_active,
            "grace_until": int(self.grace_until),
            "error": self.error,
        }


class IdentityProvider(ABC):
    """Abstrakte Provider-Schnittstelle fuer spaetere Store-/Online-Anbindungen."""

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Metadaten und Faehigkeiten dieses Providers."""

    @abstractmethod
    def begin_device_auth(self, account_id: str, device_id: str, locale: str = "de") -> DeviceCodeChallenge:
        """Startet einen Device-Code-/QR-Anmeldefluss."""

    @abstractmethod
    def poll_device_auth(self, challenge: DeviceCodeChallenge, device_id: str) -> DevicePollResult:
        """Fragt den Stand einer laufenden Device-Code-Anmeldung ab."""

    @abstractmethod
    def refresh_tokens(
        self,
        link: IdentityLink,
        tokens: ProviderAuthTokens,
        device_id: str,
    ) -> ProviderAuthTokens:
        """Erneuert abgelaufene Provider-Tokens."""

    @abstractmethod
    def fetch_entitlements(
        self,
        link: IdentityLink,
        tokens: ProviderAuthTokens,
        device_id: str,
    ) -> tuple[list[Entitlement], int]:
        """Laedt Berechtigungen und gibt (entitlements, ttl_seconds) zurueck."""

    def revoke(
        self,
        link: IdentityLink,
        tokens: ProviderAuthTokens | None,
        device_id: str,
    ) -> None:
        """Optionaler Widerruf auf Serverseite; Standard ist No-Op."""
        return None


class IdentityRegistry:
    """Thread-sichere Registry aktiver IdentityProvider-Implementierungen."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, IdentityProvider] = {}

    def register(self, provider: IdentityProvider) -> ProviderInfo:
        info = provider.info()
        pid = str(info.provider_id or "").strip()
        if not SAFE_ID_RE.fullmatch(pid):
            raise ValidationError("account.err.invalid", "Invalid provider_id")
        if not str(info.display_name or "").strip():
            raise ValidationError("account.err.invalid", "Provider display_name required")
        with self._lock:
            self._providers[pid] = provider
        return info

    def unregister(self, provider_id: str) -> bool:
        with self._lock:
            return self._providers.pop(provider_id, None) is not None

    def get(self, provider_id: str) -> IdentityProvider | None:
        with self._lock:
            return self._providers.get(provider_id)

    def list_providers(self) -> list[ProviderInfo]:
        with self._lock:
            return [p.info() for p in self._providers.values()]

    def has_providers(self) -> bool:
        with self._lock:
            return bool(self._providers)

    def clear(self) -> None:
        with self._lock:
            self._providers.clear()


class TokenVault:
    """Authentifiziert verschluesselte Token-Ablage in `accounts/tokens.db` (Key in `accounts/tokens.key`, 0600)."""

    def __init__(self, store: AccountStore, accounts_dir: Path) -> None:
        self._store = store
        self._accounts_dir = Path(accounts_dir)
        self._key_path = self._accounts_dir / TOKEN_KEY_FILENAME
        self._lock = threading.RLock()

    def _ensure_master_key(self) -> bytes:
        with self._lock:
            self._accounts_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self._accounts_dir, 0o700)
            if self._key_path.is_symlink():
                self._key_path.unlink(missing_ok=True)
            if self._key_path.is_file():
                os.chmod(self._key_path, 0o600)
                raw = self._key_path.read_bytes()
                if len(raw) == 32:
                    return raw
            key = secrets.token_bytes(32)
            tmp = self._key_path.with_name(f".{self._key_path.name}.tmp.{os.getpid()}")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(key)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.chmod(tmp, 0o600)
                os.replace(tmp, self._key_path)
            except Exception:
                tmp.unlink(missing_ok=True)
                raise
            return key

    @staticmethod
    def _derive_subkeys(master_key: bytes) -> tuple[bytes, bytes]:
        enc_key = hmac.new(master_key, b"vs-enc-v1", hashlib.sha256).digest()
        mac_key = hmac.new(master_key, b"vs-mac-v1", hashlib.sha256).digest()
        return enc_key, mac_key

    @staticmethod
    def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
        chunks: list[bytes] = []
        counter = 0
        total = 0
        while total < length:
            block = hmac.new(enc_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            chunks.append(block)
            total += len(block)
            counter += 1
        return b"".join(chunks)[:length]

    @staticmethod
    def _aad(link_id: str, provider_id: str, account_id: str) -> bytes:
        return f"{link_id}:{provider_id}:{account_id}".encode("utf-8")

    def seal(self, link_id: str, provider_id: str, account_id: str, plaintext: bytes) -> bytes:
        master = self._ensure_master_key()
        enc_key, mac_key = self._derive_subkeys(master)
        nonce = secrets.token_bytes(_NONCE_LEN)
        stream = self._keystream(enc_key, nonce, len(plaintext))
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
        aad = self._aad(link_id, provider_id, account_id)
        tag = hmac.new(mac_key, _VAULT_MAGIC + nonce + aad + ciphertext, hashlib.sha256).digest()
        return _VAULT_MAGIC + nonce + ciphertext + tag

    def unseal(self, link_id: str, provider_id: str, account_id: str, blob: bytes) -> bytes:
        min_len = len(_VAULT_MAGIC) + _NONCE_LEN + _MAC_LEN
        if len(blob) < min_len or not blob.startswith(_VAULT_MAGIC):
            raise IdentityError("identity.err.tokenCorrupt", "Encrypted token payload is invalid")
        master = self._ensure_master_key()
        enc_key, mac_key = self._derive_subkeys(master)
        nonce = blob[len(_VAULT_MAGIC) : len(_VAULT_MAGIC) + _NONCE_LEN]
        ciphertext = blob[len(_VAULT_MAGIC) + _NONCE_LEN : -_MAC_LEN]
        tag = blob[-_MAC_LEN:]
        aad = self._aad(link_id, provider_id, account_id)
        expected_tag = hmac.new(mac_key, _VAULT_MAGIC + nonce + aad + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise IdentityError("identity.err.tokenCorrupt", "Token integrity check failed")
        stream = self._keystream(enc_key, nonce, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream))

    def save_tokens(
        self,
        link_id: str,
        provider_id: str,
        account_id: str,
        tokens: ProviderAuthTokens,
    ) -> None:
        raw = json.dumps(tokens.to_secret_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        enc = self.seal(link_id, provider_id, account_id, raw)
        self._store.save_token_blob(
            link_id=link_id,
            provider_id=provider_id,
            account_id=account_id,
            payload_enc=enc,
            expires_at=int(tokens.expires_at),
            key_version=1,
        )

    def load_tokens(
        self,
        link_id: str,
        provider_id: str,
        account_id: str,
    ) -> ProviderAuthTokens | None:
        blob = self._store.load_token_blob(link_id)
        if blob is None:
            return None
        raw = self.unseal(link_id, provider_id, account_id, blob)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise IdentityError("identity.err.tokenCorrupt", "Stored token JSON is invalid") from exc
        if not isinstance(parsed, dict):
            raise IdentityError("identity.err.tokenCorrupt", "Stored token payload must be a JSON object")
        return ProviderAuthTokens.from_secret_dict(parsed)

    def delete_tokens(self, link_id: str) -> None:
        self._store.delete_token_blob(link_id)


@dataclass(slots=True)
class _PendingChallenge:
    challenge_id: str
    account_id: str
    challenge: DeviceCodeChallenge
    created_at: int


def _normalize_entitlements(raw_items: list[dict[str, Any]], now: int) -> list[Entitlement]:
    out: list[Entitlement] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        ent = Entitlement.from_dict(item)
        if not ent.id:
            continue
        if ent.expires_at > 0 and now > ent.expires_at:
            continue
        out.append(ent)
    return out


class IdentityManager:
    """Offline-First-Koordinator fuer Provider-Verknuepfung, Token-Vault und Entitlement-Cache."""

    def __init__(
        self,
        store: AccountStore,
        registry: IdentityRegistry,
        accounts_dir: Path,
        clock: Callable[[], float] | None = None,
        lock: threading.RLock | None = None,
    ) -> None:
        self._store = store
        self._registry = registry
        self._clock = clock or time.time
        self._lock = lock or threading.RLock()
        self.vault = TokenVault(store, accounts_dir)
        self._pending: dict[str, _PendingChallenge] = {}

    def _now(self) -> int:
        return int(self._clock())

    def _device_id(self) -> str:
        return self._store.get_meta("device_id", "")

    def _grace_for(self, provider_id: str) -> int:
        prov = self._registry.get(provider_id)
        if prov is not None:
            return max(0, int(prov.info().offline_grace_seconds))
        return DEFAULT_OFFLINE_GRACE_SECONDS

    def _purge_expired_pending(self, now: int) -> None:
        expired = [
            cid
            for cid, p in self._pending.items()
            if p.challenge.expires_at > 0 and now > p.challenge.expires_at
        ]
        for cid in expired:
            self._pending.pop(cid, None)

    def _find_pending(
        self,
        account_id: str,
        *,
        challenge_id: str = "",
        provider_id: str = "",
    ) -> _PendingChallenge | None:
        if challenge_id:
            cand = self._pending.get(challenge_id)
            if cand and cand.account_id == account_id:
                return cand
            return None
        for cand in self._pending.values():
            if cand.account_id == account_id and (not provider_id or cand.challenge.provider_id == provider_id):
                return cand
        return None

    def _evaluate_cache(self, link: IdentityLink, now: int) -> tuple[list[Entitlement], int, str, bool, int]:
        raw_ents, exp_at = self._store.get_identity_entitlements(link.id)
        ents = _normalize_entitlements(raw_ents, now)
        grace_sec = self._grace_for(link.provider_id)
        base_ts = max(int(exp_at), int(link.last_sync_at), int(link.linked_at))
        grace_until = base_ts + grace_sec
        if exp_at > 0 and now <= exp_at:
            return ents, exp_at, "fresh", False, grace_until
        if grace_sec > 0 and now <= grace_until:
            return ents, exp_at, "grace", True, grace_until
        return [], exp_at, "expired", False, grace_until

    def list_providers(self) -> list[ProviderInfo]:
        return self._registry.list_providers()

    def has_providers(self) -> bool:
        return self._registry.has_providers()

    def get_status(self, account_id: str) -> dict[str, Any]:
        with self._lock:
            now = self._now()
            self._purge_expired_pending(now)
            providers = [p.to_public_dict() for p in self._registry.list_providers()]
            links = self._store.list_identity_links(account_id) if account_id else []
            link_entries: list[dict[str, Any]] = []
            merged_ents: list[dict[str, Any]] = []
            any_grace = False
            for ln in links:
                ents, exp_at, cache_state, grace_active, grace_until = self._evaluate_cache(ln, now)
                if grace_active:
                    any_grace = True
                for ent in ents:
                    d = ent.to_dict()
                    d.setdefault("provider_id", ln.provider_id)
                    merged_ents.append(d)
                entry = ln.to_public_dict()
                entry.update(
                    {
                        "cache_state": cache_state,
                        "grace_active": grace_active,
                        "grace_until": grace_until,
                        "entitlements_count": len(ents),
                        "entitlements_expires_at": exp_at,
                        "provider_available": self._registry.get(ln.provider_id) is not None,
                    }
                )
                link_entries.append(entry)

            pend = self._find_pending(account_id) if account_id else None
            pending_out: dict[str, Any] | None = None
            if pend is not None:
                pending_out = {
                    "challenge_id": pend.challenge_id,
                    "challenge": pend.challenge.to_public_dict(),
                }

            return {
                "available": bool(providers),
                "offline_first": True,
                "account_id": account_id,
                "providers": providers,
                "links": link_entries,
                "entitlements": merged_ents,
                "offline_grace_active": any_grace,
                "pending": pending_out,
            }

    def begin_link(self, account_id: str, provider_id: str, locale: str = "de") -> dict[str, Any]:
        with self._lock:
            acc = self._store.get_account(account_id)
            if not acc or not acc.active:
                raise NotFoundError("account.err.notFound", "Account not found")
            if acc.role == "child":
                raise PolicyError("identity.err.notAllowed", "Child accounts cannot link online identities")

            pid = str(provider_id or "").strip()
            provider = self._registry.get(pid)
            if provider is None:
                raise NotFoundError("identity.err.providerNotFound", "Identity provider not registered")

            try:
                challenge = provider.begin_device_auth(account_id, self._device_id(), locale=locale)
            except IdentityOfflineError:
                raise
            except (OSError, TimeoutError, ConnectionError) as exc:
                raise IdentityOfflineError("identity.err.offline", str(exc) or "Provider unreachable") from exc

            now = self._now()
            self._purge_expired_pending(now)
            for k in [
                cid
                for cid, p in self._pending.items()
                if p.account_id == account_id and p.challenge.provider_id == pid
            ]:
                self._pending.pop(k, None)

            cid = uuid.uuid4().hex[:16]
            self._pending[cid] = _PendingChallenge(
                challenge_id=cid,
                account_id=account_id,
                challenge=challenge,
                created_at=now,
            )
            return {
                "ok": True,
                "challenge_id": cid,
                "challenge": challenge.to_public_dict(),
            }

    def poll_link(
        self,
        account_id: str,
        *,
        challenge_id: str = "",
        provider_id: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            now = self._now()
            pend = self._find_pending(account_id, challenge_id=challenge_id, provider_id=provider_id)
            if pend is None:
                raise NotFoundError("identity.err.expired", "No active link challenge")
            if pend.challenge.expires_at > 0 and now > pend.challenge.expires_at:
                self._pending.pop(pend.challenge_id, None)
                return {
                    "ok": False,
                    "status": "expired",
                    "challenge_id": pend.challenge_id,
                    "error": "identity.err.expired",
                }

            provider = self._registry.get(pend.challenge.provider_id)
            if provider is None:
                self._pending.pop(pend.challenge_id, None)
                raise NotFoundError("identity.err.providerNotFound", "Identity provider not registered")

            try:
                res = provider.poll_device_auth(pend.challenge, self._device_id())
            except IdentityOfflineError:
                raise
            except (OSError, TimeoutError, ConnectionError) as exc:
                raise IdentityOfflineError("identity.err.offline", str(exc) or "Provider unreachable") from exc

            status = str(res.status or "pending").strip().lower()
            if status in ("pending", "slow_down"):
                if status == "slow_down":
                    pend.challenge.interval = max(
                        pend.challenge.interval + 5,
                        int(res.interval or pend.challenge.interval + 5),
                    )
                elif res.interval > 0:
                    pend.challenge.interval = int(res.interval)
                return {
                    "ok": True,
                    "status": status,
                    "challenge_id": pend.challenge_id,
                    "interval": pend.challenge.interval,
                }

            self._pending.pop(pend.challenge_id, None)
            if status != "authorized":
                err_code = res.error or (
                    "identity.err.expired" if status == "expired" else "identity.err.denied"
                )
                return {
                    "ok": False,
                    "status": status,
                    "challenge_id": pend.challenge_id,
                    "error": err_code,
                }

            existing = self._store.get_identity_link_for_provider(account_id, pend.challenge.provider_id)
            link_id = existing.id if existing else uuid.uuid4().hex[:16]
            subject = str(res.subject or "").strip()
            if not subject:
                raise IdentityError("account.err.invalid", "Provider returned empty subject")
            handle = str(res.display_handle or subject).strip()
            ttl = max(60, int(res.entitlements_ttl or DEFAULT_ENTITLEMENT_TTL_SECONDS))
            exp_at = now + ttl
            ent_dicts = [e.to_dict() for e in res.entitlements]

            link = IdentityLink(
                id=link_id,
                account_id=account_id,
                provider_id=pend.challenge.provider_id,
                subject=subject,
                display_handle=handle,
                status="linked",
                linked_at=existing.linked_at if existing else now,
                last_sync_at=now,
            )
            saved = self._store.upsert_identity_link(
                link,
                entitlements=ent_dicts,
                entitlements_expires_at=exp_at,
            )
            if res.tokens is not None:
                self.vault.save_tokens(saved.id, saved.provider_id, account_id, res.tokens)
            self._store.append_audit(
                "identity_linked",
                account_id=account_id,
                actor_id=account_id,
                detail={"provider_id": saved.provider_id, "link_id": saved.id},
            )
            return {
                "ok": True,
                "status": "authorized",
                "challenge_id": pend.challenge_id,
                "link": saved.to_public_dict(),
                "entitlements": ent_dicts,
                "entitlements_expires_at": exp_at,
            }

    def cancel_link(
        self,
        account_id: str,
        *,
        challenge_id: str = "",
        provider_id: str = "",
    ) -> bool:
        with self._lock:
            removed = False
            for cid, pend in list(self._pending.items()):
                if pend.account_id != account_id:
                    continue
                if challenge_id and cid != challenge_id:
                    continue
                if provider_id and pend.challenge.provider_id != provider_id:
                    continue
                self._pending.pop(cid, None)
                removed = True
            return removed

    def _sync_single_link(self, link: IdentityLink, now: int) -> IdentitySyncResult:
        provider = self._registry.get(link.provider_id)
        ents_cached, exp_cached, _state, grace_active, grace_until = self._evaluate_cache(link, now)
        if provider is None:
            return IdentitySyncResult(
                link=link,
                entitlements=ents_cached,
                entitlements_expires_at=exp_cached,
                from_cache=True,
                offline=True,
                grace_active=grace_active,
                grace_until=grace_until,
                error="identity.err.providerNotFound",
            )

        tokens = self.vault.load_tokens(link.id, link.provider_id, link.account_id)
        if tokens is None:
            updated = self._store.set_identity_link_status(link.id, "reauth_required")
            return IdentitySyncResult(
                link=updated,
                entitlements=ents_cached,
                entitlements_expires_at=exp_cached,
                from_cache=True,
                offline=False,
                grace_active=grace_active,
                grace_until=grace_until,
                error="account.err.invalid",
            )

        device_id = self._device_id()
        try:
            if tokens.expires_at > 0 and now >= tokens.expires_at and tokens.refresh_token:
                tokens = provider.refresh_tokens(link, tokens, device_id)
                self.vault.save_tokens(link.id, link.provider_id, link.account_id, tokens)

            try:
                fresh_ents, ttl = provider.fetch_entitlements(link, tokens, device_id)
            except AuthError:
                if not tokens.refresh_token:
                    raise
                tokens = provider.refresh_tokens(link, tokens, device_id)
                self.vault.save_tokens(link.id, link.provider_id, link.account_id, tokens)
                fresh_ents, ttl = provider.fetch_entitlements(link, tokens, device_id)
        except (IdentityOfflineError, OSError, TimeoutError, ConnectionError) as exc:
            return IdentitySyncResult(
                link=link,
                entitlements=ents_cached,
                entitlements_expires_at=exp_cached,
                from_cache=True,
                offline=True,
                grace_active=grace_active,
                grace_until=grace_until,
                error=exc.code if isinstance(exc, IdentityOfflineError) else "identity.err.offline",
            )
        except AuthError as exc:
            updated = self._store.set_identity_link_status(link.id, "reauth_required")
            return IdentitySyncResult(
                link=updated,
                entitlements=ents_cached,
                entitlements_expires_at=exp_cached,
                from_cache=True,
                offline=False,
                grace_active=grace_active,
                grace_until=grace_until,
                error=exc.code,
            )

        exp_at = now + max(60, int(ttl or DEFAULT_ENTITLEMENT_TTL_SECONDS))
        ent_dicts = [e.to_dict() for e in fresh_ents]
        updated = self._store.update_identity_entitlements(
            link.id,
            entitlements=ent_dicts,
            entitlements_expires_at=exp_at,
            status="linked",
            last_sync_at=now,
        )
        self._store.append_audit(
            "identity_synced",
            account_id=link.account_id,
            actor_id=link.account_id,
            detail={"provider_id": link.provider_id, "count": len(fresh_ents)},
        )
        grace_until_new = max(exp_at, now) + self._grace_for(link.provider_id)
        return IdentitySyncResult(
            link=updated,
            entitlements=_normalize_entitlements(ent_dicts, now),
            entitlements_expires_at=exp_at,
            from_cache=False,
            offline=False,
            grace_active=False,
            grace_until=grace_until_new,
        )

    def sync(self, account_id: str, provider_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            acc = self._store.get_account(account_id)
            if not acc or not acc.active:
                raise NotFoundError("account.err.notFound", "Account not found")
            now = self._now()
            links = self._store.list_identity_links(account_id)
            if provider_id:
                links = [ln for ln in links if ln.provider_id == provider_id]
                if not links:
                    raise NotFoundError("account.err.notFound", "Identity link not found")
            results = [self._sync_single_link(ln, now) for ln in links]
            return {
                "ok": True,
                "account_id": account_id,
                "offline": any(r.offline for r in results),
                "from_cache": any(r.from_cache for r in results),
                "results": [r.to_public_dict() for r in results],
            }

    def unlink(
        self,
        account_id: str,
        *,
        provider_id: str = "",
        link_id: str = "",
    ) -> bool:
        with self._lock:
            acc = self._store.get_account(account_id)
            if not acc:
                raise NotFoundError("account.err.notFound", "Account not found")

            target: IdentityLink | None = None
            if link_id:
                cand = self._store.get_identity_link(link_id)
                if cand and cand.account_id == account_id:
                    target = cand
            elif provider_id:
                target = self._store.get_identity_link_for_provider(account_id, provider_id)
            else:
                links = self._store.list_identity_links(account_id)
                target = links[0] if links else None

            if target is None:
                raise NotFoundError("account.err.notFound", "Identity link not found")

            self.cancel_link(account_id, provider_id=target.provider_id)
            provider = self._registry.get(target.provider_id)
            if provider is not None:
                try:
                    tokens = self.vault.load_tokens(target.id, target.provider_id, account_id)
                except IdentityError:
                    tokens = None
                try:
                    provider.revoke(target, tokens, self._device_id())
                except (IdentityError, OSError, TimeoutError, ConnectionError):
                    # Offline-Entkopplung muss lokal immer zuverlaessig gelingen
                    pass

            deleted = self._store.delete_identity_link(target.id)
            if deleted:
                self._store.append_audit(
                    "identity_unlinked",
                    account_id=account_id,
                    actor_id=account_id,
                    detail={"provider_id": target.provider_id, "link_id": target.id},
                )
            return deleted

    def get_entitlements(self, account_id: str) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            now = self._now()
            out: list[dict[str, Any]] = []
            any_grace = False
            for ln in self._store.list_identity_links(account_id):
                ents, _exp_at, _state, grace_active, _grace_until = self._evaluate_cache(ln, now)
                if grace_active:
                    any_grace = True
                for ent in ents:
                    d = ent.to_dict()
                    d.setdefault("provider_id", ln.provider_id)
                    out.append(d)
            return out, any_grace

    def has_entitlement(self, account_id: str, entitlement_id: str, kind: str | None = None) -> bool:
        ents, _ = self.get_entitlements(account_id)
        for ent in ents:
            if ent.get("id") == entitlement_id and (kind is None or ent.get("kind") == kind):
                return True
        return False
