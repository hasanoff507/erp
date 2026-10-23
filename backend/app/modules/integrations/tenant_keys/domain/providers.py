"""Tenant integration providers and their secret fields (20 #40d; contract ``tenant-integrations.md``).

Pure Python: the URL slug → ``tenant_secrets.kind`` map, the required/optional secret fields per provider, the
credential fingerprint the shop-payment webhooks resolve the tenant by (12 §2.9 ``lookup_hash``) and the
AES-GCM ``aad`` that binds a ciphertext to its row.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final
from uuid import UUID

DIGITS: Final = re.compile(r"^[0-9]{1,20}$")
MAX_FIELD: Final = 512


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    slug: str
    kind: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    # optional fields that come all together or not at all (e.g. Uzum Dynamic QR credentials)
    groups: tuple[tuple[str, ...], ...] = ()
    digits: tuple[str, ...] = ()  # numeric identifiers (Click service_id, Uzum serviceId …)
    flags: tuple[str, ...] = ()  # boolean fields, stored as "true"/"false"
    autofiscal: bool = False  # click/payme/uzum — provider_autofiscal_disabled_confirmed: true required
    per_register: bool = False  # uzqr — tenant_secrets.cash_register_id
    last4_field: str | None = None  # BO-14 key_last4 (crpt)

    @property
    def fields(self) -> tuple[str, ...]:
        return self.required + self.optional


PROVIDERS: Final[Mapping[str, ProviderSpec]] = {
    "faktura-uz": ProviderSpec(
        "faktura-uz", "faktura_uz", ("login", "password", "client_id", "client_secret")
    ),
    "didox": ProviderSpec("didox", "didox", ("login", "password")),
    "crpt": ProviderSpec("crpt", "crpt", ("api_key",), last4_field="api_key"),
    "click": ProviderSpec(
        "click", "click", ("merchant_id", "service_id", "secret_key"), ("merchant_user_id",),
        digits=("merchant_id", "service_id", "merchant_user_id"), autofiscal=True,
    ),
    "payme": ProviderSpec("payme", "payme", ("merchant_id", "key"), ("test_mode",), flags=("test_mode",),
                          autofiscal=True),
    "uzum": ProviderSpec(
        "uzum", "uzum", ("merchant_id", "login", "password"),
        ("dynamic_qr_service_id", "dynamic_qr_user_id", "dynamic_qr_secret_key"),
        groups=(("dynamic_qr_service_id", "dynamic_qr_user_id", "dynamic_qr_secret_key"),),
        digits=("merchant_id", "dynamic_qr_service_id", "dynamic_qr_user_id"), autofiscal=True,
    ),
    "uzqr": ProviderSpec("uzqr", "uzqr", ("merchant_id", "terminal_id"), ("api_key",), per_register=True),
}  # fmt: skip

KIND_TO_SLUG: Final[Mapping[str, str]] = {spec.kind: slug for slug, spec in PROVIDERS.items()}
STATUS_KINDS: Final[tuple[str, ...]] = tuple(spec.kind for spec in PROVIDERS.values())
PAYME_LOGIN: Final = "Paycom"  # Payme Merchant API Basic auth user (developer.help.paycom.uz)


def lookup_hash(kind: str, secret: Mapping[str, str]) -> bytes | None:
    """Credential fingerprint for webhooks that carry no order reference (12 §2.9): SHA-256 of a
    high-entropy merchant credential — never the credential itself."""
    if kind == "payme":
        return credential_hash("payme", PAYME_LOGIN, secret["key"])
    if kind == "uzum":
        return credential_hash("uzum", secret["login"], secret["password"])
    return None


def credential_hash(kind: str, login: str, password: str) -> bytes:
    """``sha256("<kind>:<login>:<password>")`` — the HTTP Basic credentials a webhook presents."""
    return hashlib.sha256(f"{kind}:{login}:{password}".encode()).digest()


def secret_aad(tenant_id: UUID, kind: str, cash_register_id: UUID | None) -> bytes:
    register = "-" if cash_register_id is None else str(cash_register_id)
    return f"tenant_secrets:{tenant_id}:{kind}:{register}".encode()
