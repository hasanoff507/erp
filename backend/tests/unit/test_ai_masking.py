"""QT-AI-PII-01 and the masking layer (22 §7, 15 §5.2, qaror #61)."""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.ai.application.ports import AiRequestContext
from app.modules.ai.application.provider import MaskedAiProvider
from app.modules.ai.infrastructure.fake_provider import FakeAiProvider
from app.modules.ai.privacy.masking import REMOVED, PiiKind, PiiMasker, PiiValue
from app.modules.ai.wiring import build_ai_provider

CTX = AiRequestContext(tenant_id=uuid4(), user_id=uuid4(), feature="AI-01")

TOOL_RESULT = {
    "debtors": [
        {
            "name": "Aliyev Vali",
            "phone": "+998 90 123 45 67",
            "stir": "301234567",
            "pinfl": "31234567890123",
            "address": "Toshkent, Chilonzor 5-kvartal 12-uy",
            "debt": "569000.00",
            "card_number": "8600 1234 5678 9012",
            "password_hash": "$argon2id$...",
        }
    ],
    "product": {"name": "Shakar", "qty": "10.000"},
}


async def test_qt_ai_pii_01_personal_data_is_tokenised_and_restored() -> None:
    raw = FakeAiProvider(reply="mijoz A ning qarzi 569000.00 so'm, telefoni telefon A.")
    provider = MaskedAiProvider(raw)

    answer = await provider.complete(
        "Siz do'kon yordamchisisiz.",
        "Aliyev Vali qancha qarz?",
        context=CTX,
        tool_results=TOOL_RESULT,
    )

    sent = json.dumps(raw.sent, ensure_ascii=False)
    for secret in ("Aliyev", "Vali", "123 45 67", "301234567", "31234567890123", "Chilonzor"):
        assert secret not in sent, secret
    for forbidden in ("8600", "argon2", "card_number", "password_hash"):
        assert forbidden not in sent, forbidden
    assert "mijoz A qancha qarz?" in raw.sent[0]["user"]
    assert "Shakar" in sent  # product names are not personal data
    assert "569000.00" in sent  # code-computed numbers go through unchanged
    assert answer == "Aliyev Vali ning qarzi 569000.00 so'm, telefoni +998 90 123 45 67."


def test_free_text_patterns() -> None:
    masker = PiiMasker()
    text = (
        "Mijoz +998901234567, STIR: 301234567, JShShIR 31234567890123, "
        "karta 8600123456789012, summa 120000.00"
    )
    masked = masker.mask_text(text)
    assert "+998901234567" not in masked and "telefon A" in masked
    assert "301234567" not in masked and "STIR: STIR A" in masked
    assert "31234567890123" not in masked and "JShShIR A" in masked
    assert "8600123456789012" not in masked and REMOVED in masked
    assert "120000.00" in masked
    assert masker.unmask_text(masked).startswith("Mijoz +998901234567, STIR: 301234567")


def test_same_value_same_token_and_longest_match_first() -> None:
    masker = PiiMasker()
    masker.register_all([PiiValue(PiiKind.PERSON, "Aliyev Vali"), PiiValue(PiiKind.PERSON, "Vali")])
    masked = masker.mask_text("Aliyev  Vali va Vali")
    assert masked == "mijoz A va mijoz B"
    assert masker.register(PiiKind.PERSON, "aliyev vali") == "mijoz A"


async def test_structured_answers_are_unmasked() -> None:
    class Explanation(BaseModel):
        summary: str

    raw = FakeAiProvider(structured_reply={"summary": "mijoz A to'lamagan"})
    out = await MaskedAiProvider(raw).complete_structured(
        "s", "Aliyev Vali haqida", Explanation, context=CTX, pii=[PiiValue(PiiKind.PERSON, "Aliyev Vali")]
    )
    assert out.summary == "Aliyev Vali to'lamagan"
    assert "Aliyev" not in raw.sent[0]["user"]


async def test_images_need_cross_border_consent_qaror_61() -> None:
    class Ocr(BaseModel):
        total: str = "0.00"

    raw = FakeAiProvider()
    provider = MaskedAiProvider(raw)
    with pytest.raises(AppError) as err:
        await provider.vision_extract(b"img", Ocr, "o'qing", context=CTX)
    assert err.value.code == "AI_CONSENT_REQUIRED"
    assert raw.sent == []
    await provider.vision_extract(
        b"img", Ocr, "o'qing", context=dataclasses.replace(CTX, cross_border_enabled=True)
    )
    assert raw.sent[0]["method"] == "vision_extract"


def test_masking_cannot_be_switched_off() -> None:
    # no setting exists that could disable it, even if someone sets one in the environment
    assert not [
        name for name in Settings.model_fields if "mask" in name or ("pii" in name and name != "ai_pii_route")
    ]
    settings = Settings(ai_mode="fake", _env_file=None)
    provider = build_ai_provider(settings)
    assert isinstance(provider, MaskedAiProvider)
    import inspect

    for method in ("complete", "complete_structured", "vision_extract"):
        params = inspect.signature(getattr(MaskedAiProvider, method)).parameters
        assert not [p for p in params if "mask" in p], method


def test_no_direct_sdk_calls_outside_ai_adapters() -> None:
    """32 §10: no code may talk to the AI SDK around the masking layer."""
    app_dir = Path(__file__).resolve().parents[2] / "app"
    adapters = app_dir / "modules" / "ai" / "infrastructure"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if adapters in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n.split(".")[0] in {"anthropic", "boto3", "aioboto3"} for n in names):
                offenders.append(str(path))
    assert offenders == []


# -- SEC-1: leaks found in review, one test per leak ---------------------------------------


@pytest.mark.parametrize("phone", ["901234567", "90 123 45 67", "(90) 123-45-67", "998901234567"])
def test_local_phone_formats_are_masked_in_free_text(phone: str) -> None:
    masker = PiiMasker()
    masked = masker.mask_text(f"Mijoz telefoni {phone}, qarzi 569000.00")
    assert phone not in masked
    assert "telefon A" in masked
    assert "569000.00" in masked
    assert masker.unmask_text(masked) == f"Mijoz telefoni {phone}, qarzi 569000.00"


def test_phone_pattern_does_not_eat_amounts_stir_or_pinfl() -> None:
    masker = PiiMasker()
    text = "summa 901234567.00, 750 000 000 so'm, STIR: 331234567, JShShIR 31234567890123"
    masked = masker.mask_text(text)
    assert "901234567.00" in masked
    assert "750 000 000" in masked
    assert "STIR: STIR A" in masked
    assert "JShShIR A" in masked
    assert "telefon" not in masked


@pytest.mark.parametrize(
    "key", ["passport", "pasport", "passport_series", "passportNumber", "biometric", "cardNumber"]
)
def test_passport_and_biometric_keys_are_removed(key: str) -> None:
    masked = PiiMasker().mask_payload({"customer": {key: "AA1234567", "debt": "10.00"}})
    assert masked == {"customer": {"debt": "10.00"}}


@pytest.mark.parametrize(
    ("key", "value", "token"),
    [
        ("firstName", "Anvar", "mijoz A"),
        ("surname", "Karimov", "mijoz A"),
        ("last_name", "Karimov", "mijoz A"),
        ("customerFullName", "Karimov Anvar", "mijoz A"),
        ("phoneNumber", "+998 90 123 45 67", "telefon A"),
        ("mobile_phone", "901234567", "telefon A"),
        ("email", "anvar@mail.uz", "email A"),
        ("customer_pinfl", "31234567890123", "JShShIR A"),
        ("supplierInn", "301234567", "STIR A"),
    ],
)
def test_pii_key_variants_are_tokenised(key: str, value: str, token: str) -> None:
    masker = PiiMasker()
    masked = masker.mask_payload({"row": {key: value, "qty": "1.000"}})
    assert masked == {"row": {key: token, "qty": "1.000"}}
    assert masker.unmask_payload(masked) == {"row": {key: value, "qty": "1.000"}}


@pytest.mark.parametrize("container", ["counterparties", "debts", "debtors", "customers", "topDebtors"])
def test_name_under_plural_person_container_is_masked(container: str) -> None:
    masker = PiiMasker()
    masked = masker.mask_payload({container: [{"name": "Karimov Anvar", "amount": "10.00"}]})
    assert masked == {container: [{"name": "mijoz A", "amount": "10.00"}]}


def test_product_names_stay_visible() -> None:
    masked = PiiMasker().mask_payload(
        {"products": [{"name": "Shakar"}], "categories": [{"name": "Oziq-ovqat"}]}
    )
    assert masked == {"products": [{"name": "Shakar"}], "categories": [{"name": "Oziq-ovqat"}]}


def test_numeric_pii_values_are_tokenised() -> None:
    masker = PiiMasker()
    payload = {"customer": {"phone": 901234567, "pinfl": 31234567890123, "verified": True, "qty": 5}}
    masked = masker.mask_payload(payload)
    assert masked == {"customer": {"phone": "telefon A", "pinfl": "JShShIR A", "verified": True, "qty": 5}}
    sent = json.dumps(masked)
    assert "901234567" not in sent and "31234567890123" not in sent
    assert masker.unmask_text("telefon A, JShShIR A") == "901234567, 31234567890123"


def test_email_in_free_text_is_masked() -> None:
    masker = PiiMasker()
    assert masker.mask_text("yozing: anvar.k@mail.uz") == "yozing: email A"


async def test_logs_and_provider_payload_carry_no_pii(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from structlog.testing import capture_logs

    originals = ("Karimov", "Anvar", "901234567", "31234567890123", "anvar@mail.uz", "AA1234567")
    raw = FakeAiProvider(reply="mijoz A qarzdor, telefon A")
    provider = MaskedAiProvider(raw)
    tool_results = {
        "counterparties": [
            {
                "name": "Karimov Anvar",
                "phoneNumber": 901234567,
                "pinfl": 31234567890123,
                "email": "anvar@mail.uz",
                "passport": "AA1234567",
            }
        ]
    }
    caplog.set_level(logging.DEBUG)
    with capture_logs() as structured:
        answer = await provider.complete("s", "Karimov Anvar haqida", context=CTX, tool_results=tool_results)

    sent = json.dumps(raw.sent, ensure_ascii=False)
    for value in originals:
        assert value not in sent, value
    assert answer == "Karimov Anvar qarzdor, 901234567"

    logged = caplog.text + json.dumps(structured, ensure_ascii=False, default=str)
    for value in originals:
        assert value not in logged, value
