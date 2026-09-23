"""God passkey: shared-secret gate for laws, presets and world control.

First boot has no credential — `POST /api/auth/setup` registers one (the
frontend prompts for it). Afterwards every god-touching call must present the
passkey (`X-God-Key` header on REST, `key` field on WebSocket control
messages). Only a PBKDF2 hash is stored, in the `settings` table; clearing the
database wipes the credential and the next start asks to create it again.

`FLATWORLD_GOD_KEY` seeds (or overrides) the passkey from the environment —
handy for headless deploys and tests.
"""

from collections import OrderedDict
from functools import lru_cache
import hashlib
import hmac
from ipaddress import ip_address, ip_network
import os
import secrets
import threading
import time

from fastapi import HTTPException, Request
from pydantic import BaseModel

from .db import Database

_PBKDF2_ITERATIONS = 120_000
_SETTING_HASH = "god_passkey_hash"
_SETTING_SALT = "god_passkey_salt"
MIN_PASSKEY_LEN = 8
_VERIFY_CACHE_MAX_ENTRIES = 128
_VERIFY_CACHE_TTL_SEC = 60.0


def _hash(passkey: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", passkey.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    ).hex()


class TokenBucket:
    """In-memory thread-safe token bucket rate limiter (per IP)."""

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


_RATE_LIMITERS: dict[str, TokenBucket] = {}
_RATE_LIMIT_LOCK = threading.Lock()


@lru_cache(maxsize=16)
def _parse_trusted_proxies(raw: str) -> tuple[tuple[object, ...], tuple[str, ...]]:
    networks: list[object] = []
    invalid: list[str] = []
    for entry in raw.split(","):
        value = entry.strip()
        if not value:
            continue
        try:
            networks.append(ip_network(value, strict=False))
        except ValueError:
            invalid.append(value)
    return tuple(networks), tuple(invalid)


def _trusted_proxies() -> tuple[tuple[object, ...], tuple[str, ...]]:
    return _parse_trusted_proxies(os.environ.get("FLATWORLD_TRUSTED_PROXIES", ""))


def _is_trusted_proxy(address, networks: tuple[object, ...]) -> bool:
    try:
        parsed = ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def client_ip_from_headers(peer: str, forwarded_for: str | None) -> str:
    """Resolve a client IP only through explicitly trusted proxy peers."""
    networks, _invalid = _trusted_proxies()
    if not networks or not _is_trusted_proxy(peer, networks):
        return peer
    if not forwarded_for:
        return peer
    for candidate in reversed(forwarded_for.split(",")):
        value = candidate.strip()
        if not value or _is_trusted_proxy(value, networks):
            continue
        try:
            return str(ip_address(value))
        except ValueError:
            return peer
    return peer


def request_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    return client_ip_from_headers(peer, request.headers.get("x-forwarded-for"))


def websocket_client_ip(websocket) -> str:
    peer = websocket.client.host if websocket.client else "unknown"
    return client_ip_from_headers(peer, websocket.headers.get("x-forwarded-for"))


def check_client_rate_limit(
    client_ip: str,
    bucket_name: str,
    capacity: float = 60.0,
    refill_rate: float = 5.0,
) -> None:
    full_key = f"{bucket_name}:{client_ip}"
    with _RATE_LIMIT_LOCK:
        if full_key not in _RATE_LIMITERS:
            if len(_RATE_LIMITERS) >= 1000:
                _RATE_LIMITERS.clear()
            _RATE_LIMITERS[full_key] = TokenBucket(capacity, refill_rate)
        bucket = _RATE_LIMITERS[full_key]
    if not bucket.consume(1.0):
        raise HTTPException(429, {"error": "rate_limit_exceeded", "detail": "too many requests; please slow down"})


def check_rate_limit(request: Request, bucket_name: str, capacity: float = 60.0, refill_rate: float = 5.0) -> None:
    check_client_rate_limit(request_client_ip(request), bucket_name, capacity, refill_rate)


class PasskeyAuth:
    """Lazily-loaded passkey state backed by the settings table."""

    def __init__(self, db: Database):
        self._db = db
        self._loaded = False
        self._hash_hex: str | None = None
        self._salt_hex: str | None = None
        self._source = "db"
        self._verify_cache: OrderedDict[str, float] = OrderedDict()
        self._cache_version: int = 0
        self._lock = threading.Lock()
        env_key = os.environ.get("FLATWORLD_GOD_KEY")
        if env_key:
            salt = secrets.token_bytes(16)
            salt_hex = salt.hex()
            self._salt_hex = salt_hex
            self._hash_hex = _hash(env_key, salt)
            self._source = "env"
            self._loaded = True

    def _load(self) -> None:
        if self._loaded:
            return
        if self._source == "env":
            self._loaded = True
            return
        self._salt_hex = self._db.get_setting(_SETTING_SALT)
        self._hash_hex = self._db.get_setting(_SETTING_HASH)
        self._loaded = True

    @property
    def source(self) -> str:
        with self._lock:
            self._load()
            return self._source

    def configured(self) -> bool:
        with self._lock:
            self._load()
            return self._hash_hex is not None and self._salt_hex is not None

    def setup(self, passkey: str) -> None:
        """Register the first credential. Refuses if one already exists."""
        if len(passkey) < MIN_PASSKEY_LEN:
            raise ValueError(f"passkey must be at least {MIN_PASSKEY_LEN} characters")
        with self._lock:
            self._load()
            if self._source == "env":
                raise PermissionError("FLATWORLD_GOD_KEY is authoritative; database setup is disabled")
            if self._hash_hex is not None and self._salt_hex is not None:
                raise PermissionError("a god passkey already exists")
            self._write(passkey)

    def reset(self, passkey: str) -> None:
        """Overwrite a database credential (admin recovery via CLI only)."""
        if len(passkey) < MIN_PASSKEY_LEN:
            raise ValueError(f"passkey must be at least {MIN_PASSKEY_LEN} characters")
        with self._lock:
            self._load()
            if self._source == "env":
                raise PermissionError("FLATWORLD_GOD_KEY is authoritative; unset it before resetting the database credential")
            self._write(passkey)

    def clear(self) -> None:
        """Remove the credential entirely — next start asks to enroll again."""
        with self._lock:
            self._load()
            if self._source == "env":
                raise PermissionError("FLATWORLD_GOD_KEY is authoritative; unset it before clearing the database credential")
            self._db.delete_setting(_SETTING_HASH)
            self._db.delete_setting(_SETTING_SALT)
            self._hash_hex = None
            self._salt_hex = None
            self._source = "db"
            self._loaded = True
            self._verify_cache.clear()
            self._cache_version += 1

    def _write(self, passkey: str) -> None:
        salt = secrets.token_bytes(16)
        salt_hex = salt.hex()
        passkey_hash = _hash(passkey, salt)
        self._db.set_setting(_SETTING_SALT, salt_hex)
        self._db.set_setting(_SETTING_HASH, passkey_hash)
        self._salt_hex = salt_hex
        self._hash_hex = passkey_hash
        self._source = "db"
        self._loaded = True
        self._verify_cache.clear()
        self._cache_version += 1

    def _cache_key(self, passkey: str, salt_hex: str, cache_version: int) -> str:
        salt_bytes = salt_hex.encode("ascii")
        message = f"{passkey}:{cache_version}".encode("utf-8")
        return hmac.new(salt_bytes, message, hashlib.sha256).hexdigest()

    def verify(self, passkey: str | None) -> bool:
        if not isinstance(passkey, str) or not passkey:
            return False
        now = time.monotonic()
        with self._lock:
            self._load()
            if self._hash_hex is None or self._salt_hex is None:
                return False
            salt_hex = self._salt_hex
            expected_hash = self._hash_hex
            cache_version = self._cache_version
            ckey = self._cache_key(passkey, salt_hex, cache_version)
            expires_at = self._verify_cache.get(ckey)
            if expires_at is not None:
                if now < expires_at:
                    self._verify_cache.move_to_end(ckey)
                    return True
                del self._verify_cache[ckey]

        calc = _hash(passkey, bytes.fromhex(salt_hex))
        ok = hmac.compare_digest(calc, expected_hash)
        if not ok:
            return False
        with self._lock:
            if self._salt_hex != salt_hex or self._cache_version != cache_version:
                return False
            if len(self._verify_cache) >= _VERIFY_CACHE_MAX_ENTRIES:
                self._verify_cache.popitem(last=False)
            self._verify_cache[ckey] = now + _VERIFY_CACHE_TTL_SEC
        return True


class SetupPasskey(BaseModel):
    passkey: str


def require_god(request: Request) -> None:
    """FastAPI dependency guarding every god-touching endpoint."""
    check_rate_limit(request, "god_api", capacity=60.0, refill_rate=5.0)
    auth: PasskeyAuth = request.app.state.god_auth
    if not auth.configured():
        raise HTTPException(409, {"error": "god_key_not_configured", "detail": "first-time enrollment required via /api/auth/setup"})
    key = request.headers.get("X-God-Key")
    if not key or not auth.verify(key):
        raise HTTPException(401, {"error": "god_key_required", "detail": "valid X-God-Key header required"})
