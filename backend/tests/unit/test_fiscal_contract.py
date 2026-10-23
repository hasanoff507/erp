"""FiscalPort contract suite (21 §1, §16.1; 27 B5-T02; COMMON "external systems": port + Fake + contract tests).

The same cases run against every adapter: the FM emulator (``fake``), the partner-cloud adapter over the
in-memory partner, and — once 26 #109 is answered — the real partner client (``ERP_FISCAL_CONTRACT_REAL=1``;
until then skipped as ⛔ 26 #109). The boundary (tiyin ``int64``, 21 §16.1 payload) is unit-tested here too.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    FiscalPort,
    FiscalProviderError,
    FiscalReceiptPayload,
    RefundInfo,
)
from app.modules.integrations.fiscal.domain.boundary import (
    BoundaryError,
    fm_state_of,
    parse_status_result,
    parse_zreport_result,
    port_payload,
    tiyin,
)
from app.modules.integrations.fiscal.infrastructure.fake import FakeFiscalAdapter
from app.modules.integrations.fiscal.infrastructure.fm_emulator import FmEmulator
from app.modules.integrations.fiscal.infrastructure.partner_cloud import (
    FakePartnerCloud,
    PartnerCloudFiscalAdapter,
    UnavailablePartnerCloud,
)

QR = re.compile(r"^https://ofd\.soliq\.uz/check\?t=(\w{14})&r=(\d+)&c=\d{14}&s=(\d{12})$")
BODY: dict[str, Any] = {
    "total": "24000.00",
    "items": [
        {"name": "Coca-Cola 1.5L / Кока-Кола", "mxik": "02202001001000000", "package_code": "1500", "unit_code": "box",
         "qty": "1.000", "price": "12000.0000", "vat_rate": "12.00", "vat_amount": "1285.71", "amount": "12000.00",
         "marking_codes": []},
        {"name": "Hayot suvi", "mxik": "02201001001000000", "package_code": "1", "unit_code": "pcs",
         "qty": "1.000", "price": "12000.0000", "vat_rate": "12.00", "vat_amount": "1285.71", "amount": "12000.00",
         "marking_codes": ["0104600000000000215ABC\x1d93dGVz"]},
    ],
    "payments": [{"method": "cash", "amount": "14000.00"},
                 {"method": "card", "amount": "10000.00", "card_entry_mode": "integrated", "card_type": "personal",
                  "card_mask": "8600****1234", "rrn": "612345678901"}],
}  # fmt: skip


class Harness:
    def __init__(self, port: FiscalPort, offline: Callable[[bool], None]) -> None:
        self.port = port
        self.set_offline = offline


def _fake() -> Harness:
    fake = FakeFiscalAdapter()
    return Harness(fake, lambda off: setattr(fake, "ack", not off))


def _partner() -> Harness:
    cloud = FakePartnerCloud()
    return Harness(PartnerCloudFiscalAdapter(cloud), lambda off: setattr(cloud, "online", not off))


def _real() -> Harness:
    if not os.environ.get("ERP_FISCAL_CONTRACT_REAL"):
        pytest.skip("real fiscal partner adapter — ⛔ 26 #109 (protocol not public)")
    return Harness(PartnerCloudFiscalAdapter(UnavailablePartnerCloud()), lambda off: None)


ADAPTERS = {"fake_fm": _fake, "partner_cloud_fake": _partner, "partner_cloud_real": _real}


@pytest.fixture(params=list(ADAPTERS), name="h")
def harness(request: pytest.FixtureRequest) -> Harness:
    return ADAPTERS[request.param]()


def _receipt(
    register: CashRegisterRef, kind: str = "sale", body: dict[str, Any] | None = None
) -> FiscalReceiptPayload:
    return FiscalReceiptPayload(uuid4(), kind, register, 1, body or BODY)


async def test_contract_fiscal_port_sale_requisites(h: Harness) -> None:
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    res = await h.port.register_sale(_receipt(reg))
    m = QR.match(res.qr_url)
    assert m is not None and m.groups() == (res.terminal_id, str(res.fm_receipt_seq), res.fiscal_sign)
    assert res.fm_receipt_seq > 0 and re.fullmatch(r"\d{12}", res.fiscal_sign)
    assert res.ofd_acked_at is not None  # online: acked at once


async def test_contract_fiscal_port_idempotent_per_receipt(h: Harness) -> None:
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    receipt = _receipt(reg)
    first, again = await h.port.register_sale(receipt), await h.port.register_sale(receipt)
    assert (first.fm_receipt_seq, first.fiscal_sign) == (again.fm_receipt_seq, again.fiscal_sign)
    other = await h.port.register_sale(_receipt(reg))
    assert other.fm_receipt_seq > first.fm_receipt_seq


async def test_contract_fiscal_port_refund_with_refund_info(h: Harness) -> None:
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    sale = await h.port.register_sale(_receipt(reg))
    info = RefundInfo(sale.terminal_id, sale.fm_receipt_seq, sale.fiscal_at, sale.fiscal_sign)
    refund = await h.port.register_refund(_receipt(reg, "return"), info)
    assert refund.fm_receipt_seq > sale.fm_receipt_seq and refund.terminal_id == sale.terminal_id


async def test_contract_fiscal_port_offline_sign_then_resend_acks(h: Harness) -> None:
    """DoD-05: the FM signs without the network; ``resend_unsent`` delivers it and returns ``acked[]``."""
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    h.set_offline(True)
    res = await h.port.register_sale(_receipt(reg))
    assert res.ofd_acked_at is None and QR.match(res.qr_url)
    status = await h.port.get_device_status(reg)
    assert status.pending == 1 and status.oldest_unacked_at is not None
    unsent = await h.port.list_unsent(reg)
    assert [(u.fm_receipt_seq, u.amount_tiyin) for u in unsent] == [(res.fm_receipt_seq, 2_400_000)]
    still = await h.port.resend_unsent(reg)
    assert (still.sent, still.failed, still.acked) == (0, 1, ())
    h.set_offline(False)
    sent = await h.port.resend_unsent(reg)
    assert sent.sent == 1 and [(a.fm_terminal_id, a.fm_receipt_seq) for a in sent.acked] == [
        (res.terminal_id, res.fm_receipt_seq)
    ]
    assert await h.port.list_unsent(reg) == []


async def test_contract_fiscal_port_shift_open_close(h: Harness) -> None:
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    opened = await h.port.open_shift(reg)
    assert opened.terminal_id
    z = await h.port.close_shift(_receipt(reg, "z_report", {"total": "0"}))
    assert z.terminal_id == opened.terminal_id and z.fm_receipt_seq >= 1


async def test_contract_fiscal_port_rejects_non_tiyin_amounts(h: Harness) -> None:
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-1")
    with pytest.raises(FiscalProviderError) as caught:
        await h.port.register_sale(_receipt(reg, body={**BODY, "total": "abc"}))
    assert caught.value.kind == "validation"


async def test_contract_partner_cloud_receives_tiyin_payload() -> None:
    cloud = FakePartnerCloud()
    adapter = PartnerCloudFiscalAdapter(cloud)
    reg = CashRegisterRef(uuid4(), uuid4(), "fm-7")
    await adapter.register_refund(
        _receipt(reg, "return"), RefundInfo("ZZ000000000001", 5, None, "123456789012")
    )
    (_, payload) = cloud.payloads[-1]
    assert payload["total_tiyin"] == 2_400_000 and payload["kind"] == "return"
    assert payload["payments"] == {"payment_form": "mixed", "cash_tiyin": 1_400_000, "card_tiyin": 1_000_000,
                                   "qr_tiyin": 0, "card_type": "personal", "card_mask": "8600****1234",
                                   "rrn": "612345678901"}  # fmt: skip
    first = payload["items"][0]
    assert (first["qty_milli"], first["price_tiyin"], first["amount_tiyin"], first["vat_tiyin"]) == (
        1000,
        1_200_000,
        1_200_000,
        128_571,
    )
    assert payload["items"][1]["marking_codes"] == ["0104600000000000215ABC\x1d93dGVz"]  # GS kept as scanned
    assert payload["refund_info"] == {"fm_terminal_id": "ZZ000000000001", "fm_receipt_seq": 5,
                                      "fiscal_sign": "123456789012"}  # fmt: skip
    assert payload["cash_register"] == {"cash_register_id": str(reg.id), "local_id": "fm-7"}
    assert all(
        isinstance(v, int) for i in payload["items"] for k, v in i.items() if k.endswith(("_tiyin", "_milli"))
    )


async def test_contract_partner_cloud_unavailable_is_transient() -> None:
    adapter = PartnerCloudFiscalAdapter(UnavailablePartnerCloud())
    reg = CashRegisterRef(uuid4(), uuid4())
    with pytest.raises(FiscalProviderError) as caught:
        await adapter.register_sale(_receipt(reg))
    assert caught.value.kind == "transient"
    assert (await adapter.get_device_status(reg)).fm_state == "unknown"


# --- boundary / emulator units ---------------------------------------------------------------------------
def test_tiyin_boundary_int64() -> None:
    assert tiyin("12000.00") == 1_200_000 and tiyin("0.005") == 1 and isinstance(tiyin("1"), int)
    with pytest.raises(BoundaryError):
        tiyin("1e30")
    debt_only = port_payload(kind="debt_settlement", cash_register_id="x", local_id=None, receipt_seq=3,
                             body={"total": "5.00", "items": [], "payments": [{"method": "debt", "amount": "5.00"}]},
                             payment_form=None)  # fmt: skip
    assert debt_only["payments"]["cash_tiyin"] == 0  # debt parts never reach the receipt


def test_fm_state_mapping_and_results() -> None:
    assert [fm_state_of(x) for x in ("OK", "locked", "busy", None)] == ["ok", "locked", "unknown", "unknown"]
    st = parse_status_result({"fm_state": "memory_full", "pending_count": 2, "oldest_unacked_at": "2026-10-18T05:00:00Z",
                              "acked": [{"fm_terminal_id": "ZZ1", "fm_receipt_seq": "7", "acked_at": "2026-10-18T06:00:00Z"}]})  # fmt: skip
    assert st.fm_state == "memory_full" and st.acked[0].fm_receipt_seq == 7
    with pytest.raises(BoundaryError) as caught:
        parse_zreport_result({"fm_terminal_id": "ZZ1", "z_number": 0, "closed_at": "2026-10-18T06:00:00Z"})
    assert caught.value.field == "z_number"


def test_fm_emulator_locks_itself_at_48h() -> None:
    clock = {"now": FmEmulator("ZZ000000000009").clock()}
    fm = FmEmulator("ZZ000000000009", online=False, clock=lambda: clock["now"])
    fm.sign("a", 100)
    clock["now"] += timedelta(hours=47, minutes=59)
    assert fm.fm_state() == "ok"
    clock["now"] += timedelta(minutes=1)
    assert fm.fm_state() == "locked"
    with pytest.raises(PermissionError):
        fm.sign("b", 100)
    fm.online = True
    fm.resend()
    assert fm.fm_state() == "ok" and fm.sign("b", 100).acked_at is not None
