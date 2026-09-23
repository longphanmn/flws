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
import hashlib
import hmac
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


def check_rate_limit(request: Request, bucket_name: str, capacity: float = 60.0, refill_rate: float = 5.0) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if client_ip == "testclient":
        return
    full_key = f"{bucket_name}:{client_ip}"
    with _RATE_LIMIT_LOCK:
        if full_key not in _RATE_LIMITERS:
            if len(_RATE_LIMITERS) >= 1000:
                _RATE_LIMITERS.clear()
            _RATE_LIMITERS[full_key] = TokenBucket(capacity, refill_rate)
        bucket = _RATE_LIMITERS[full_key]
    if not bucket.consume(1.0):
        raise HTTPException(429, {"error": "rate_limit_exceeded", "detail": "too many requests; please slow down"})


class PasskeyAuth:
    """Lazily-loaded passkey state backed by the settings table."""

    def __init__(self, db: Database):
        self._db = db
        self._loaded = False
        self._hash_hex: str | None = None
        self._salt_hex: str | None = None
        self._verify_cache: OrderedDict[str, tuple[bool, float]] = OrderedDict()
        self._cache_version: int = 0
        self._lock = threading.Lock()
        env_key = os.environ.get("FLATWORLD_GOD_KEY")
        if env_key:
            salt = secrets.token_bytes(16)
            self._salt_hex = salt.hex()
            self._hash_hex = _hash(env_key, salt)
            self._loaded = True

    def _load(self) -> None:
        if not self._loaded:
            self._salt_hex = self._db.get_setting(_SETTING_SALT)
            self._hash_hex = self._db.get_setting(_SETTING_HASH)
            self._loaded = True

    def configured(self) -> bool:
        with self._lock:
            self._load()
            return self._hash_hex is not None and self._salt_hex is not None

    def setup(self, passkey: str) -> None:
        """Register the first credential. Refuses if one already exists."""
        if len(passkey) < MIN_PASSKEY_LEN:
            raise ValueError(f"passkey must be at least {MIN_PASSKEY_LEN} characters")
        with self._lock:
            self._loaded = False
            self._load()
            if self._hash_hex is not None and self._salt_hex is not None:
                raise PermissionError("a god passkey already exists")
            self._write(passkey)

    def reset(self, passkey: str) -> None:
        """Overwrite any existing credential (admin recovery via CLI only)."""
        if len(passkey) < MIN_PASSKEY_LEN:
            raise ValueError(f"passkey must be at least {MIN_PASSKEY_LEN} characters")
        with self._lock:
            self._write(passkey)

    def clear(self) -> None:
        """Remove the credential entirely — next start asks to enroll again."""
        with self._lock:
            self._db.delete_setting(_SETTING_HASH)
            self._db.delete_setting(_SETTING_SALT)
            self._hash_hex = None
            self._salt_hex = None
            self._loaded = True
            self._verify_cache.clear()
            self._cache_version += 1

    def _write(self, passkey: str) -> None:
        salt = secrets.token_bytes(16)
        self._db.set_setting(_SETTING_SALT, salt.hex())
        self._db.set_setting(_SETTING_HASH, _hash(passkey, salt))
        self._salt_hex = salt.hex()
        self._hash_hex = _hash(passkey, salt)
        self._loaded = True
        self._verify_cache.clear()
        self._cache_version += 1

    def _cache_key(self, passkey: str) -> str:
        salt_bytes = (self._salt_hex or "none").encode("ascii")
        return hmac.new(salt_bytes, f"{passkey}:{self._cache_version}".encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, passkey: str | None) -> bool:
        if not passkey or not self.configured():
            return False
        ckey = self._cache_key(passkey)
        now = time.monotonic()
        with self._lock:
            if ckey in self._verify_cache:
                ok, exp = self._verify_cache[ckey]
                if now < exp:
                    self._verify_cache.move_to_end(ckey)
                    return ok
                else:
                    del self._verify_cache[ckey]

        calc = _hash(passkey, bytes.fromhex(self._salt_hex or ""))
        ok = hmac.compare_digest(calc, self._hash_hex or "")
        with self._lock:
            if len(self._verify_cache) >= _VERIFY_CACHE_MAX_ENTRIES:
                self._verify_cache.popitem(last=False)
            self._verify_cache[ckey] = (ok, now + _VERIFY_CACHE_TTL_SEC)
        return ok


class SetupPasskey(BaseModel):
    passkey: str


def require_god(request: Request) -> None:
    """FastAPI dependency guarding every god-touching endpoint."""
    auth: PasskeyAuth = request.app.state.god_auth
    if not auth.configured():
        raise HTTPException(409, {"error": "god_key_not_configured", "detail": "first-time enrollment required via /api/auth/setup"})
    check_rate_limit(request, "god_api", capacity=60.0, refill_rate=5.0)
    key = request.headers.get("X-God-Key")
    if not key or not auth.verify(key):
        raise HTTPException(401, {"error": "god_key_required", "detail": "valid X-God-Key header required"})
