"""Envelope encryption (15 §4.2, qaror #65).

Every secret gets its own random DEK (AES-256-GCM); the DEK is wrapped with the
platform KEK (AES-256-GCM, from the deploy environment) and stored next to the
ciphertext. ``aad`` binds a ciphertext to its row (e.g. ``signing_keys:<kid>``),
so a value copied into another row does not decrypt.

Format: ``v1.<kek_version>.<b64(nonce‖wrapped_dek)>.<b64(nonce‖ciphertext)>``.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_FORMAT = "v1"
_NONCE = 12
_KEY = 32


class SecretDecryptionError(ValueError):
    """Ciphertext is malformed, was produced with an unknown KEK or was tampered with."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise SecretDecryptionError("bad base64") from exc


def decode_kek(value: str) -> bytes:
    key = _b64d(value.strip())
    if len(key) != _KEY:
        raise ValueError("KEK must be 32 bytes (urlsafe base64)")
    return key


class EnvelopeCipher:
    def __init__(self, keks: Mapping[int, bytes], current_version: int) -> None:
        if current_version not in keks:
            raise ValueError("current KEK version is missing")
        self._keks = dict(keks)
        self._current = current_version

    @classmethod
    def from_settings(cls, kek: str, version: int, previous: Mapping[int, str]) -> EnvelopeCipher:
        keks = {v: decode_kek(k) for v, k in previous.items()}
        keks[version] = decode_kek(kek)
        return cls(keks, version)

    def encrypt(self, plaintext: bytes, aad: bytes) -> str:
        dek = AESGCM.generate_key(bit_length=256)
        n_data, n_key = os.urandom(_NONCE), os.urandom(_NONCE)
        sealed = AESGCM(dek).encrypt(n_data, plaintext, aad)
        wrapped = AESGCM(self._keks[self._current]).encrypt(n_key, dek, b"dek|" + aad)
        return ".".join((_FORMAT, str(self._current), _b64e(n_key + wrapped), _b64e(n_data + sealed)))

    def decrypt(self, token: str, aad: bytes) -> bytes:
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != _FORMAT or not parts[1].isdigit():
            raise SecretDecryptionError("unknown envelope format")
        kek = self._keks.get(int(parts[1]))
        if kek is None:
            raise SecretDecryptionError("unknown KEK version")
        key_blob, data_blob = _b64d(parts[2]), _b64d(parts[3])
        try:
            dek = AESGCM(kek).decrypt(key_blob[:_NONCE], key_blob[_NONCE:], b"dek|" + aad)
            return AESGCM(dek).decrypt(data_blob[:_NONCE], data_blob[_NONCE:], aad)
        except InvalidTag as exc:
            raise SecretDecryptionError("integrity check failed") from exc

    def needs_rewrap(self, token: str) -> bool:
        """True when the value was sealed with an older KEK (yearly rotation, 15 §4.2)."""
        parts = token.split(".")
        return len(parts) < 2 or parts[1] != str(self._current)
