"""Generate ``shared/agent/*.json`` — store-agent protocol test vectors (34 §12.3, contracts/agent-wire.md).

The .NET agent (``agent-1c``) verifies the same files in xunit; the backend checks them in
``tests/unit/test_agent_vectors.py``. Keys are the RFC 8032 §7.1 test keys — public test material only.

    uv run python scripts/gen_agent_vectors.py          # write
    uv run python scripts/gen_agent_vectors.py --check  # exit 1 on drift
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.auth.domain.agent_keys import b64url, jwk_thumbprint
from app.modules.onec_integration.application.jws import (
    public_jwk_of,
    root_kid,
    sign_compact,
    sign_detached_b64,
)
from app.modules.onec_integration.domain.envelope import (
    ALG,
    KEYSET_TYP,
    TASK_TYP,
    LeaseFacts,
    keyset_payload,
    task_claims,
)
from app.modules.onec_integration.domain.jcs import canonicalize, payload_sha256

OUT_DIR = Path(__file__).resolve().parents[2] / "shared" / "agent"

# RFC 8032 §7.1 TEST 1 / TEST 2 secret keys (well-known, test only)
TASK_KEY_SEED = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
ROOT_KEY_SEED = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
TASK_KID = "0192f0c4-7a00-7000-8000-000000000001"
TENANT_ID = "0192f0c4-7a00-7000-8000-0000000000aa"
AGENT_ID = "0192f0c4-7a00-7000-8000-0000000000bb"
TASK_ID = "0192f0c4-7a00-7000-8000-0000000000cc"
LEASE_ID = "0192f0c4-7a00-7000-8000-0000000000dd"
LEASED_AT = datetime(2026, 10, 15, 18, 2, 12, tzinfo=UTC)
KEYSET_IAT = 1760500000

# (name, input JSON text, note) — the agent parses the text, canonicalises, compares bytes and SHA-256
JCS_CASES: list[tuple[str, str, str]] = [
    (
        "rfc8785_3_2_2",
        '{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],'
        '"string":"\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/",'
        '"literals":[null,true,false]}',
        "RFC 8785 §3.2.2 example",
    ),
    (
        "rfc8785_3_2_3_sorting",
        '{"\\u20ac":"Euro Sign","\\r":"Carriage Return","\\ufb33":"Hebrew Letter Dalet With Dagesh",'
        '"1":"One","\\ud83d\\ude00":"Emoji: Grinning Face","\\u0080":"Control",'
        '"\\u00f6":"Latin Small Letter O With Diaeresis"}',
        "RFC 8785 §3.2.3 — member order by UTF-16 code units (surrogate pair sorts below U+FB33)",
    ),
    ("empty_object", "{}", "empty object"),
    ("empty_array", "[]", "empty array"),
    (
        "nested_payload",
        '{ "cash_register_id": "0192f0c4-7a00-7000-8000-000000000123", "shift_id": null,\n'
        '  "b": {"z": 1, "a": [3, 2, 1], "m": {"y": true, "x": false}}, "a": -42 }',
        "whitespace removed, nested objects sorted, arrays keep order",
    ),
    (
        "unicode_and_controls",
        '{"name":"Ўзбекистон — «Do\'kon» ʻ","ctl":"\\u0001\\u001f\\u007f","tab":"a\\tb","slash":"/"}',
        "non-ASCII literal UTF-8, U+0001/U+001F as \\u00xx (lowercase), DEL and '/' literal",
    ),
    ("integers", '{"max":9007199254740991,"min":-9007199254740991,"zero":0,"neg_zero":-0}', "safe integers"),
    ("numbers_es6", "[1e21,1e-7,0.000001,1.2345678901234568e20,5e-324,-1.5,100]", "ECMAScript Number→String"),
]


def _seed_key(seed_hex: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))


def _jcs_vectors() -> dict[str, Any]:
    cases = []
    for name, text, note in JCS_CASES:
        value = json.loads(text)
        canonical = canonicalize(value)
        cases.append(
            {
                "name": name,
                "note": note,
                "input": text,
                "canonical": canonical.decode("utf-8"),
                "canonical_utf8_hex": canonical.hex(),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            }
        )
    return {
        "description": "RFC 8785 JCS cases: parse `input`, canonicalise, expect `canonical` bytes "
        "and `sha256`.",
        "source": "https://www.rfc-editor.org/rfc/rfc8785",
        "cases": cases,
    }


def _envelope_vectors() -> dict[str, Any]:
    key = _seed_key(TASK_KEY_SEED)
    payload = {"cash_register_id": "0192f0c4-7a00-7000-8000-000000000123"}
    psh = payload_sha256(payload)
    facts = LeaseFacts(
        task_id=UUID(TASK_ID),
        attempt=1,
        lease_id=UUID(LEASE_ID),
        tenant_id=UUID(TENANT_ID),
        agent_id=UUID(AGENT_ID),
        base_id=None,
        kind="fiscal.status",
        payload_sha256=psh,
        leased_at=LEASED_AT,
        timeout_s=60,
    )
    header = {"alg": ALG, "typ": TASK_TYP, "kid": TASK_KID}
    claims = task_claims(facts)
    signature = sign_compact(header, claims, key)
    envelope = {
        "task_id": TASK_ID,
        "kind": "fiscal.status",
        "purpose": "device_service",
        "base_id": None,
        "local_id": None,
        "attempt": 1,
        "lease_id": LEASE_ID,
        "lease_until": "2026-10-15T18:03:42Z",
        "timeout_s": 60,
        "payload": payload,
        "payload_sha256": psh,
        "kid": TASK_KID,
        "signature": signature,
    }
    tampered = dict(payload, cash_register_id="0192f0c4-7a00-7000-8000-000000000124")
    return {
        "description": "A-03 task envelope signed with the onec_task key (33 §9.4, 34 §7.5). Verify the "
        "JWS over the received seg0.seg1 bytes with `task_key.public_jwk`; check every claim against the "
        "envelope and the token context; psh == sha256(JCS(payload)).",
        "task_key": {
            "kid": TASK_KID,
            "private_seed_hex": TASK_KEY_SEED,
            "public_jwk": {**public_jwk_of(key.public_key()), "kid": TASK_KID},
        },
        "token_context": {"tenant_id": TENANT_ID, "agent_id": AGENT_ID},
        "now_unix_valid": int(LEASED_AT.timestamp()) + 30,
        "now_unix_expired": claims["exp"] + 121,
        "envelope": envelope,
        "expected_header": header,
        "expected_claims": claims,
        "negative": [
            {"name": "payload_tampered", "payload": tampered, "expect_reason": "payload_hash"},
            {
                "name": "wrong_agent",
                "token_agent_id": "0192f0c4-7a00-7000-8000-0000000000ee",
                "expect_reason": "agent",
            },
            {
                "name": "wrong_tenant",
                "token_tenant_id": "0192f0c4-7a00-7000-8000-0000000000ef",
                "expect_reason": "tenant",
            },
            {"name": "signature_flipped", "signature": _flip_last(signature), "expect_reason": "signature"},
            {
                "name": "unknown_kid",
                "kid": "0192f0c4-7a00-7000-8000-000000000099",
                "expect_reason": "signature",
            },
        ],
    }


def _flip_last(token: str) -> str:
    head, _, sig = token.rpartition(".")
    raw = bytearray(base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4)))
    raw[-1] ^= 0x01
    return f"{head}.{b64url(bytes(raw))}"


def _keyset_vectors() -> dict[str, Any]:
    root = _seed_key(ROOT_KEY_SEED)
    task_key = _seed_key(TASK_KEY_SEED)
    kid = root_kid(root.public_key())
    keys = [
        {
            "kid": TASK_KID,
            **public_jwk_of(task_key.public_key()),
            "nbf": KEYSET_IAT - 86400,
            "exp": KEYSET_IAT + 90 * 86400,
        }
    ]
    payload = keyset_payload(3, KEYSET_IAT, keys)
    header = {"alg": ALG, "typ": KEYSET_TYP, "kid": kid}
    return {
        "description": "task_keyset JWS signed by the OFFLINE agent_update root key (33 §9.4, 34 §5.5). "
        "root kid = RFC 7638 thumbprint of the root public JWK. Agent: alg/typ/kid in RootKeys, signature, "
        "exp > now, ver >= stored ver, keys[] OKP/Ed25519 with 32-byte x.",
        "root_key": {
            "kid": kid,
            "private_seed_hex": ROOT_KEY_SEED,
            "public_jwk": public_jwk_of(root.public_key()),
            "thumbprint_input": json.dumps(
                {"crv": "Ed25519", "kty": "OKP", "x": public_jwk_of(root.public_key())["x"]},
                separators=(",", ":"),
            ),
            "thumbprint": jwk_thumbprint(public_jwk_of(root.public_key())),
        },
        "now_unix_valid": KEYSET_IAT + 3600,
        "task_keyset": sign_compact(header, payload, root),
        "expected_header": header,
        "expected_payload": payload,
    }


def _manifest_vectors() -> dict[str, Any]:
    root = _seed_key(ROOT_KEY_SEED)
    manifest = {
        "product": "erp-onec-agent",
        "version": "1.4.3",
        "channel": "stable",
        "url": "https://erp.example.uz/downloads/erp-onec-agent-1.4.3-setup.exe",
        "sha256": hashlib.sha256(b"erp-onec-agent-1.4.3-setup.exe test bytes").hexdigest(),
        "size": 5242880,
        "min_os": "6.1.7601",
        "min_protocol": 1,
        "rollout_pct": 100,
        "released_at": "2026-10-14T10:00:00Z",
        "notes_uz": "Xatolar tuzatildi",
        "notes_ru": "Исправлены ошибки",
    }
    raw = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")  # exact bytes are signed
    return {
        "description": "A-09 response (33 §9.3, 34 §4.4): Ed25519 over base64-decoded `manifest` bytes "
        "(not re-serialised) with the root key `kid`.",
        "root_kid": root_kid(root.public_key()),
        "response": {
            "manifest": base64.b64encode(raw).decode("ascii"),
            "signature": sign_detached_b64(raw, root),
            "kid": root_kid(root.public_key()),
        },
        "expected_manifest": manifest,
        "installed_version_older": "1.4.2",
        "installed_version_same": "1.4.3",
    }


def build() -> dict[str, str]:
    files = {
        "jcs.json": _jcs_vectors(),
        "task_envelope.json": _envelope_vectors(),
        "task_keyset.json": _keyset_vectors(),
        "update_manifest.json": _manifest_vectors(),
    }
    return {name: json.dumps(data, ensure_ascii=False, indent=2) + "\n" for name, data in files.items()}


def main() -> int:
    check = "--check" in sys.argv
    drift = False
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in build().items():
        path = OUT_DIR / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                print(f"drift: shared/agent/{name}")
                drift = True
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
