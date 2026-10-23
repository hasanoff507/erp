"""``__Host-erp_device`` — the browser's proof that it is a registered web device (14 §7.2).

HttpOnly, signed (itsdangerous, own salt) ``"<device_id>:<tenant_id>"``; JS never reads it. It survives
logout so the next login on the same browser is device-bound again; the device row stays the source
of truth (revoked/foreign-tenant devices are never bound, 14 §7.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from itsdangerous import BadSignature, Signer

DEVICE_COOKIE: Final = "__Host-erp_device"


@dataclass(frozen=True, slots=True)
class DeviceCookie:
    device_id: UUID
    tenant_id: UUID


class DeviceCookieSigner:
    def __init__(self, secret: str) -> None:
        self._signer = Signer(secret, salt="erp.device")

    def sign(self, device_id: UUID, tenant_id: UUID) -> str:
        return self._signer.sign(f"{device_id}:{tenant_id}").decode("ascii")

    def unsign(self, value: str | None) -> DeviceCookie | None:
        if not value:
            return None
        try:
            device, _, tenant = self._signer.unsign(value).decode("ascii").partition(":")
            return DeviceCookie(UUID(device), UUID(tenant))
        except (BadSignature, ValueError):
            return None
