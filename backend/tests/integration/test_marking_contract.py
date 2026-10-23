"""Contract tests of ``MarkingPort`` (21 §4; COMMON "external systems without public documentation").

The same suite runs against every adapter: ``fake`` always (CI); ``crpt`` — the real ``CrptXtraceAdapter`` —
only with ``ERP_TEST_CRPT_API_KEY`` (+ ``ERP_TEST_CRPT_CODES``: comma-separated codes the test account owns),
i.e. once 26 #40 is answered and the adapter is implemented. Rules checked: a structurally valid code is
answered (``valid`` or a known reason), a malformed one is never ``valid``, failures surface only as
``MarkingProviderError`` with a 21 §0 class, and every notice is idempotent by document id.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from app.core.db.base import uuid7
from app.modules.integrations.marking.application.ports import MarkingPort, MarkingProviderError
from app.modules.integrations.marking.domain.rules import INVALID_REASONS
from app.modules.integrations.marking.infrastructure.crpt_xtrace import CrptXtraceAdapter
from app.modules.integrations.marking.infrastructure.fake import FakeMarkingAdapter
from tests.support.marking import code

KEY = os.environ.get("ERP_TEST_CRPT_API_KEY")
REAL_CODES = [c for c in os.environ.get("ERP_TEST_CRPT_CODES", "").split(",") if c]


@pytest.fixture(params=["fake", "crpt"])
def adapter(request: pytest.FixtureRequest) -> Iterator[tuple[MarkingPort, list[str]]]:
    if request.param == "crpt":
        if not KEY or not REAL_CODES:
            pytest.skip(
                "real CRPT Turon adapter: ERP_TEST_CRPT_API_KEY / ERP_TEST_CRPT_CODES not set (26 #40)"
            )
        yield CrptXtraceAdapter(KEY), REAL_CODES
        return
    yield FakeMarkingAdapter(), [code(), code()]


async def test_contract_marking_verify_answers_known_shape(adapter: tuple[MarkingPort, list[str]]) -> None:
    port, codes = adapter
    res = await port.verify_code(codes[0])
    assert res.valid or res.reason in INVALID_REASONS
    if res.valid:
        assert res.reason is None and res.status == "in_stock"


async def test_contract_marking_malformed_code_is_never_valid(adapter: tuple[MarkingPort, list[str]]) -> None:
    port, _ = adapter
    malformed = "0104600000000001215abcdefgh93AbCd"  # GTIN check digit wrong
    if isinstance(port, CrptXtraceAdapter):  # the real API may refuse the request itself (validation)
        pytest.skip("covered by the real adapter's validation error once implemented (26 #40)")
    res = await port.verify_code(malformed)
    assert not res.valid and res.reason in INVALID_REASONS


async def test_contract_marking_notices_idempotent(adapter: tuple[MarkingPort, list[str]]) -> None:
    port, codes = adapter
    doc = uuid7()
    first = await port.accept(codes, doc)
    again = await port.accept(codes, doc)
    assert first.status == again.status and first.crpt_doc_id == again.crpt_doc_id
    ret = uuid7()
    assert (await port.supplier_return(codes[:1], ret)).crpt_doc_id == (
        await port.supplier_return(codes[:1], ret)
    ).crpt_doc_id
    wo = uuid7()
    assert (await port.write_off(codes[1:], wo)).crpt_doc_id == (
        await port.write_off(codes[1:], wo)
    ).crpt_doc_id


async def test_contract_marking_failures_are_classified() -> None:
    fake = FakeMarkingAdapter()
    for kind in ("transient", "auth", "validation"):
        fake.fail = kind
        with pytest.raises(MarkingProviderError) as err:
            await fake.accept([code()], uuid7())
        assert err.value.kind == kind
    blocked = CrptXtraceAdapter("k")  # ⛔ 26 #40: "CRPT did not answer" until implemented
    with pytest.raises(MarkingProviderError) as err:
        await blocked.verify_code(code())
    assert err.value.kind == "transient"
