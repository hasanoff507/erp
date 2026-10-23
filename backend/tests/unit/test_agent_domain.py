"""Pure store-agent rules: JCS (RFC 8785), pairing keys (RFC 7638/8037/8628), capabilities, log masking,
versions/rollout, envelope claims, update manifest, and the shared ``shared/agent`` vectors (34 §12.3)."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.modules.auth.application.compact_jws import (
    JwsError,
    public_key_from_jwk,
    sign_compact,
    verify_compact,
)
from app.modules.auth.domain.agent_keys import (
    InvalidAgentKeyError,
    display_user_code,
    jwk_thumbprint,
    new_device_code,
    new_user_code,
    normalize_user_code,
    parse_public_jwk,
)
from app.modules.onec_integration.domain.capabilities import (
    CapabilitiesError,
    capability_devices,
    capability_enabled,
    normalize_capabilities,
)
from app.modules.onec_integration.domain.envelope import (
    LeaseFacts,
    ManifestError,
    task_claims,
    validate_manifest,
)
from app.modules.onec_integration.domain.jcs import (
    JcsError,
    canonicalize,
    contains_non_integer_number,
    payload_sha256,
)
from app.modules.onec_integration.domain.kinds import clamp_timeout, default_timeout_s, family_of
from app.modules.onec_integration.domain.masking import mask_context, mask_text
from app.modules.onec_integration.domain.versions import in_rollout, rollout_bucket, version_lt

BACKEND = Path(__file__).resolve().parents[2]
SHARED = BACKEND.parent / "shared" / "agent"


# --- JCS (RFC 8785) --------------------------------------------------------------------------------
def _double(hex_bits: str) -> float:
    value: float = struct.unpack(">d", bytes.fromhex(hex_bits))[0]
    return value


@pytest.mark.parametrize(
    ("bits", "expected"),
    [  # RFC 8785 Appendix B (IEEE 754 → ECMAScript string)
        ("0000000000000000", "0"),
        ("8000000000000000", "0"),
        ("0000000000000001", "5e-324"),
        ("8000000000000001", "-5e-324"),
        ("7fefffffffffffff", "1.7976931348623157e+308"),
        ("ffefffffffffffff", "-1.7976931348623157e+308"),
        ("4340000000000000", "9007199254740992"),
        ("c340000000000000", "-9007199254740992"),
        ("4430000000000000", "295147905179352830000"),
        ("44b52d02c7e14af5", "9.999999999999997e+22"),
        ("44b52d02c7e14af6", "1e+23"),
        ("44b52d02c7e14af7", "1.0000000000000001e+23"),
        ("444b1ae4d6e2ef4e", "999999999999999700000"),
        ("444b1ae4d6e2ef4f", "999999999999999900000"),
        ("444b1ae4d6e2ef50", "1e+21"),
        ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
        ("3eb0c6f7a0b5ed8d", "0.000001"),
        ("41b3de4355555553", "333333333.3333332"),
        ("41b3de4355555554", "333333333.33333325"),
        ("41b3de4355555555", "333333333.3333333"),
        ("41b3de4355555556", "333333333.3333334"),
        ("41b3de4355555557", "333333333.33333343"),
        ("becbf647612f3696", "-0.0000033333333333333333"),
        ("43143ff3c1cb0959", "1424953923781206.2"),
    ],
)
def test_jcs_rfc8785_number_serialisation(bits: str, expected: str) -> None:
    assert canonicalize(_double(bits)).decode() == expected


def test_jcs_rfc8785_examples_and_sorting() -> None:
    value = json.loads(
        '{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],'
        '"string":"\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/","literals":[null,true,false]}'
    )
    assert canonicalize(value).decode() == (
        '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )
    sorted_keys = json.loads(canonicalize({"€": 1, "\r": 2, "דּ": 3, "1": 4, "\U0001f600": 5, "\u0080": 6}))
    assert list(sorted_keys) == ["\r", "1", "\u0080", "€", "\U0001f600", "דּ"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 2**53, "\ud800", {1: "x"}, b"raw"])
def test_jcs_rejects_non_json(bad: object) -> None:
    with pytest.raises(JcsError):
        canonicalize(bad)


def test_jcs_payload_sha256_ignores_order_and_whitespace() -> None:
    assert payload_sha256({"b": 1, "a": [1, 2]}) == payload_sha256(json.loads('{ "a": [1,2], "b": 1 }'))
    assert contains_non_integer_number({"a": [1, {"b": 1.5}]}) and not contains_non_integer_number(
        {"a": True}
    )


def test_agent_shared_vectors_are_current() -> None:
    """``shared/agent/*.json`` (consumed by the .NET agent) are exactly what the generator writes."""
    done = subprocess.run(
        [sys.executable, "scripts/gen_agent_vectors.py", "--check"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_agent_shared_vectors_verify() -> None:
    jcs = json.loads((SHARED / "jcs.json").read_text(encoding="utf-8"))
    for case in jcs["cases"]:
        assert canonicalize(json.loads(case["input"])).decode() == case["canonical"], case["name"]
    env = json.loads((SHARED / "task_envelope.json").read_text(encoding="utf-8"))
    header, claims = verify_compact(
        env["envelope"]["signature"], public_key_from_jwk(env["task_key"]["public_jwk"])
    )
    assert header == env["expected_header"] and claims == env["expected_claims"]
    assert claims["psh"] == payload_sha256(env["envelope"]["payload"])
    flipped = next(n for n in env["negative"] if n["name"] == "signature_flipped")
    with pytest.raises(JwsError):
        verify_compact(flipped["signature"], public_key_from_jwk(env["task_key"]["public_jwk"]))
    keyset = json.loads((SHARED / "task_keyset.json").read_text(encoding="utf-8"))
    _, payload = verify_compact(keyset["task_keyset"], public_key_from_jwk(keyset["root_key"]["public_jwk"]))
    assert payload == keyset["expected_payload"]
    assert keyset["root_key"]["kid"] == jwk_thumbprint(keyset["root_key"]["public_jwk"])


# --- pairing primitives -------------------------------------------------------------------------------
def test_device_grant_thumbprint_rfc8037_vector() -> None:
    """RFC 8037 Appendix A.3: the Ed25519 JWK thumbprint (RFC 7638)."""
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}
    assert jwk_thumbprint(jwk) == "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"
    assert parse_public_jwk(json.dumps({**jwk, "kid": "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"})) == jwk
    with pytest.raises(InvalidAgentKeyError):
        parse_public_jwk(json.dumps({**jwk, "kid": "other"}))
    with pytest.raises(InvalidAgentKeyError):
        parse_public_jwk(json.dumps({**jwk, "x": jwk["x"] + "="}))


def test_device_grant_user_and_device_codes() -> None:
    codes = {new_user_code() for _ in range(200)}
    assert len(codes) > 190 and all(normalize_user_code(c) == c for c in codes)
    assert normalize_user_code("wdjb-mjht") == "WDJBMJHT" and display_user_code("WDJBMJHT") == "WDJB-MJHT"
    assert normalize_user_code("WDJB-MJHA") is None and normalize_user_code("") is None  # vowel A not allowed
    assert len(new_device_code()) == 43


# --- capabilities ------------------------------------------------------------------------------------
def test_onec_agent_capabilities_normalised() -> None:
    assert normalize_capabilities(None) == {"onec": {"enabled": True, "version": 1}}
    caps = normalize_capabilities(
        {
            "fiscal": {
                "enabled": True,
                "version": 1,
                "provider": "multikassa_local",
                "devices": [{"local_id": "fm-1", "status": "ok", "secret": "x" * 300}],
            },
            "print": {"version": 1},
            "robot": {"enabled": True},
        }
    )
    assert set(caps) == {"fiscal", "print"} and caps["print"]["enabled"] is False
    assert capability_enabled(caps, "fiscal") and not capability_enabled(caps, "print")
    assert capability_devices(caps, "fiscal")[0]["local_id"] == "fm-1"
    assert capability_devices(caps, "card_terminal") == []
    for bad, field in (
        ({"fiscal": {"enabled": 1}}, "capabilities.fiscal.enabled"),
        (
            {"print": {"enabled": True, "devices": [{"status": "ok"}]}},
            "capabilities.print.devices[0].local_id",
        ),
        ({"print": "on"}, "capabilities.print"),
    ):
        with pytest.raises(CapabilitiesError) as err:
            normalize_capabilities(bad)
        assert err.value.field == field


def test_onec_agent_kinds() -> None:
    assert family_of("card.settlement") == "card_terminal" and family_of("write_object") is None
    assert (
        default_timeout_s("fiscal.resend_unsent") == 300 and default_timeout_s("collect_diagnostics") == 300
    )
    assert clamp_timeout(1) == 10 and clamp_timeout(99999) == 1800


# --- masking -----------------------------------------------------------------------------------------
def test_onec_agent_log_masking() -> None:
    text = "Srvr=x;Ref=y;Usr=u;Pwd=P@ss; password = 'q' Bearer abc.def access_token=zzz eyJa1.eyJb2.sig 4111 1111 1111 1111"
    masked = mask_text(text)
    for secret in ("P@ss", "abc.def", "zzz", "eyJa1", "4111 1111 1111 1111"):
        assert secret not in masked
    assert masked.endswith("***1111") and "Usr=u" in masked
    assert len(mask_text("x" * 5000, limit=4000)) == 4000
    ctx = mask_context({"Pwd": "1", "token": "2", "card_number": "3", "nested": [{"note": "Pwd=9"}], "ok": 1})
    assert ctx == {
        "Pwd": "***",
        "token": "***",
        "card_number": "***",
        "nested": [{"note": "Pwd=***"}],
        "ok": 1,
    }


# --- versions / rollout / envelope / manifest ------------------------------------------------------------
def test_onec_agent_versions_and_rollout() -> None:
    assert (
        version_lt("1.4.2", "1.4.3") and not version_lt("1.4.3", "1.4.3") and not version_lt("2.0.0", "1.9.9")
    )
    assert version_lt(None, "1.0.0") and version_lt("garbage", "1.0.0") and not version_lt("1.0.0", None)
    agent = UUID("0192f0c4-7a00-7000-8000-0000000000bb")
    bucket = rollout_bucket(agent)
    assert 0 <= bucket < 100 and in_rollout(agent, 100) and not in_rollout(agent, 0)
    assert in_rollout(agent, bucket + 1) and not in_rollout(agent, bucket)


def test_onec_agent_task_claims() -> None:
    leased = datetime(2026, 10, 15, 18, 2, 12, tzinfo=UTC)
    facts = LeaseFacts(
        UUID(int=1), 2, UUID(int=3), UUID(int=4), UUID(int=5), None, "print.raw", "ab" * 32, leased, 60
    )
    claims = task_claims(facts)
    assert (
        claims["aud"] == f"urn:erp:onec-agent:{UUID(int=5)}" and claims["att"] == 2 and claims["bid"] is None
    )
    assert claims["exp"] == int(leased.timestamp()) + 60 + 300


def test_onec_agent_manifest_validation() -> None:
    good = {
        "product": "erp-onec-agent",
        "version": "1.4.3",
        "channel": "stable",
        "url": "https://erp.example.uz/x.exe",
        "sha256": "a" * 64,
        "size": 10,
        "min_os": "6.1.7601",
        "min_protocol": 1,
        "rollout_pct": 50,
        "released_at": "2026-10-14T10:00:00Z",
    }
    assert validate_manifest(good)["version"] == "1.4.3"
    for field, value in (
        ("url", "http://x/y"),
        ("url", "https://u:p@x/y"),
        ("rollout_pct", 101),
        ("channel", "beta"),
        ("sha256", "A" * 64),
        ("product", "other"),
    ):
        with pytest.raises(ManifestError) as err:
            validate_manifest({**good, field: value})
        assert err.value.field == field


def test_onec_agent_jws_round_trip() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    token = sign_compact({"alg": "EdDSA", "typ": "JWT"}, {"a": "ö"}, key)
    assert verify_compact(token, key.public_key())[1] == {"a": "ö"}
    with pytest.raises(JwsError):
        verify_compact(token, Ed25519PrivateKey.generate().public_key())
    with pytest.raises(JwsError):
        verify_compact("a.b", key.public_key())
