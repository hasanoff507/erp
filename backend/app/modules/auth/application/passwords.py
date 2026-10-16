"""Password hashing — argon2id, OWASP parameters m=19 MiB, t=2, p=1 (14 §4.1, 26 #76)."""

from __future__ import annotations

from typing import Final

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PASSWORD_MIN: Final = 8
PASSWORD_MAX: Final = 128

_HASHER: Final = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1, type=Type.ID)
# verified against when the phone is unknown or has no password, so the response
# time does not reveal whether the account exists (14 §12 "Enumeratsiya")
_DUMMY_HASH: Final = _HASHER.hash("timing-equaliser-not-a-password")


def hash_password(password: str) -> str:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValueError("password length must be 8..128")
    return _HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-shape check: always runs one argon2 verification."""
    too_long = len(password) > PASSWORD_MAX
    if too_long:
        password_hash = None  # never matches, still spends the same work
        password = password[:PASSWORD_MAX]
    target = password_hash or _DUMMY_HASH
    try:
        ok = _HASHER.verify(target, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return ok and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _HASHER.check_needs_rehash(password_hash)
