"""Local (offline) PIN verifier — decision D1, 14 §13, 16 §12.

The device checks a PIN offline against ``auth.user_credentials.pin_local_hash``, a
PBKDF2-HMAC-SHA256 verifier the browser can recompute with WebCrypto (the argon2id
``pin_hash`` never leaves the server and needs no WASM under the strict CSP):

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

* password = the PIN as UTF-8 bytes (4–6 ASCII digits);
* salt = 16 random bytes, new each time a verifier is produced;
* derived key = 32 bytes; iterations = 600 000 (OWASP 2023 for PBKDF2-HMAC-SHA256);
* base64 = standard alphabet with ``=`` padding.

The iteration count inside the string is authoritative for verification.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Final

ALGORITHM: Final = "pbkdf2_sha256"
ITERATIONS: Final = 600_000
SALT_BYTES: Final = 16
KEY_BYTES: Final = 32
_MAX_ITERATIONS: Final = 5_000_000  # a malformed string must not turn a check into a DoS


def make_pin_verifier(pin: str, *, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    if not (4 <= len(pin) <= 6 and pin.isdigit() and pin.isascii()):
        raise ValueError("pin must be 4..6 ASCII digits")
    salt = os.urandom(SALT_BYTES) if salt is None else salt
    key = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, KEY_BYTES)
    return f"{ALGORITHM}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}"


def check_pin_verifier(verifier: str, pin: str) -> bool:
    try:
        algorithm, raw_iterations, salt_b64, key_b64 = verifier.split("$")
        iterations = int(raw_iterations)
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
    except ValueError:
        return False
    if algorithm != ALGORITHM or not 1 <= iterations <= _MAX_ITERATIONS or len(expected) != KEY_BYTES:
        return False
    key = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, KEY_BYTES)
    return hmac.compare_digest(key, expected)


def verifier_iterations(verifier: str | None) -> int | None:
    """Iteration count of a stored verifier (``None`` when absent/malformed) — stale ones are replaced."""
    if not verifier:
        return None
    parts = verifier.split("$")
    if len(parts) != 4 or parts[0] != ALGORITHM or not parts[1].isdigit():
        return None
    return int(parts[1])
