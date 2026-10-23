"""Pure rules of BO-24 bank settlements: 1CClientBankExchange parser, 13 §2.18a postings, 55g matching.

Fixtures in ``tests/fixtures/bank/`` are synthetic and anonymised (invented names, INNs, accounts); a real
anonymised sample from the pilot shop's accountant is still wanted (27 Bosqich 4, 26 #124).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.cash.domain.bank_matching import detect_branches, detect_method, rrn_registry
from app.modules.cash.domain.bank_settlements import (
    Amounts,
    commission_account,
    fifo_remaining,
    match_days,
    oldest_unsettled,
    posting_lines,
    validate,
)
from app.modules.cash.domain.bank_statement import (
    StatementError,
    StatementTooLargeError,
    decode,
    parse,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "bank"
D = Decimal


def _amounts(**over: object) -> Amounts:
    base: dict[str, object] = {
        "method": "card", "doc_date": date(2026, 10, 17), "settled_from": date(2026, 10, 16),
        "settled_to": date(2026, 10, 16), "gross": D("950000.00"), "commission": D("9500.00"),
        "variance": D("0.00"),
    }  # fmt: skip
    base.update(over)
    return Amounts(**base)  # type: ignore[arg-type]


# --- parser ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name", ["statement_card_collection.cp1251.txt", "statement_card_collection.utf8_bom.txt"]
)
def test_parse_fixture_both_encodings(name: str) -> None:
    st = parse((FIXTURES / name).read_bytes())
    assert st.encoding == ("cp1251" if "cp1251" in name else "utf-8")
    assert st.account_numbers == ("20208000900100000001",)
    assert (st.period_from, st.period_to) == (date(2026, 10, 17), date(2026, 10, 17))
    assert [(d.number, d.amount, d.entry_date) for d in st.documents] == [
        ("5521", D("940500.00"), date(2026, 10, 17)),
        ("7730", D("1990000.00"), date(2026, 10, 17)),
        ("12", D("150000.00"), date(2026, 10, 17)),
    ]
    card = st.documents[0]
    assert card.payer_inn == "200000001" and card.recipient_account == "20208000900100000001"
    assert "эквайринг" in card.purpose and card.payer_name == 'ATB "NAMUNA BANK" (ekvayer)'


def test_parse_header_missing_and_syntax_errors() -> None:
    with pytest.raises(StatementError) as exc:
        parse("Выписка\nНомер=1\n".encode())
    assert exc.value.line_no == 1 and exc.value.reason == "header_missing"
    with pytest.raises(StatementError) as exc:
        parse("1CClientBankExchange\nРасчСчет=1\nмусор без знака\n".encode())
    assert exc.value.line_no == 3 and exc.value.reason == "syntax"
    with pytest.raises(StatementError) as exc:
        parse("1CClientBankExchange\nСекцияДокумент=ПП\nНомер=1\nДата=17.10.2026\n".encode())
    assert exc.value.reason == "section_not_closed" and exc.value.line_no == 2
    with pytest.raises(StatementError) as exc:
        parse("1CClientBankExchange\nСекцияДокумент=ПП\nНомер=1\nДата=17.10.2026\nКонецДокумента\n".encode())
    assert exc.value.reason == "field_missing:Сумма"
    with pytest.raises(StatementError) as exc:
        parse(
            "1CClientBankExchange\nСекцияДокумент=ПП\nНомер=1\nДата=32.10.2026\nСумма=1.00\n"
            "ПолучательСчет=1\nКонецДокумента\n".encode()
        )
    assert exc.value.reason == "date_invalid" and exc.value.line_no == 4
    with pytest.raises(StatementError) as exc:
        parse("1CClientBankExchange\nКодировка=DOS\n".encode())
    assert exc.value.reason == "encoding_unsupported" and exc.value.line_no == 2


def test_parse_line_limit_and_amount_formats() -> None:
    text = "1CClientBankExchange\n" + "Получатель=x\n" * 10
    with pytest.raises(StatementTooLargeError):
        parse(text.encode(), max_lines=5)
    doc = (
        "1CClientBankExchange\nСекцияДокумент=ПП\nНомер=9\nДата=17.10.2026\nСумма={}\nПолучательСчет=1\n"
        "КонецДокумента\nКонецФайла\n"
    )
    assert parse(doc.format("1200,5").encode()).documents[0].amount == D("1200.50")
    assert parse(doc.format("1200").encode()).documents[0].amount == D("1200.00")
    with pytest.raises(StatementError) as exc:
        parse(doc.format("12.345").encode())
    assert exc.value.reason == "amount_invalid" and exc.value.line_no == 5


def test_decode_without_header_falls_back_to_windows_1251() -> None:
    raw = "1CClientBankExchange\nПолучатель=Тест\n".encode("cp1251")
    text, enc = decode(raw)
    assert enc == "cp1251" and "Тест" in text
    assert decode("\ufeff1CClientBankExchange\n".encode())[0].startswith("1CClient")


# --- 13 §2.18a postings ---------------------------------------------------------------------------
def test_13_2_18a_card_example_lines() -> None:
    """13 §2.18a example: gross 950 000, commission 9 500 → Dt 5110 940 500, Dt 9430 9 500."""
    lines = posting_lines(_amounts(), provider_account=None, analytics={"bank_ref": "5521"})
    assert [(x.account_dt, x.account_kt, x.amount) for x in lines] == [
        ("5110", "5710", D("940500.00")),
        ("9430", "5710", D("9500.00")),
    ]
    assert all(x.analytics == {"payment_method": "card", "bank_ref": "5521"} for x in lines)


def test_collection_shortage_surplus_and_commission_accounts() -> None:
    short = _amounts(
        method="collection", gross=D("2000000.00"), commission=D("5000.00"), variance=D("-5000.00")
    )
    rows = [
        (x.account_dt, x.account_kt, x.amount)
        for x in posting_lines(short, provider_account=None, analytics={})
    ]
    assert rows == [
        ("5110", "5710", D("1990000.00")),
        ("9410", "5710", D("5000.00")),
        ("5910", "5710", D("5000.00")),
    ]
    surplus = _amounts(method="collection", gross=D("100.00"), commission=D("0.00"), variance=D("3.00"))
    rows = [
        (x.account_dt, x.account_kt, x.amount)
        for x in posting_lines(surplus, provider_account=None, analytics={})
    ]
    assert rows == [("5110", "5710", D("103.00")), ("5710", "9390", D("3.00"))]
    assert commission_account("uzqr", "9410") == "9430"
    assert commission_account("click", "9410") == "9410"
    assert commission_account("payme", None) == "9430"
    assert commission_account("uzum", "1234") == "9430"
    assert commission_account("collection", None) == "9410"


def test_validation_rules() -> None:
    assert validate(_amounts()) == []
    keys = {(v.field, v.message_key) for v in validate(_amounts(commission=D("950000.00")))}
    assert keys == {("commission_amount", "validation.bank_commission_ge_gross")}
    keys = {(v.field, v.message_key) for v in validate(_amounts(settled_from=date(2026, 10, 18)))}
    assert ("settled_from", "validation.date_range") in keys and (
        "settled_to",
        "validation.date_range",
    ) not in keys
    keys = {
        (v.field, v.message_key)
        for v in validate(_amounts(settled_to=date(2026, 10, 18), settled_from=date(2026, 10, 18)))
    }
    assert keys == {("settled_to", "validation.date_range")}
    keys = {(v.field, v.message_key) for v in validate(_amounts(variance=D("-1.00")))}
    assert keys == {("variance_amount", "validation.not_allowed")}
    keys = {
        (v.field, v.message_key) for v in validate(_amounts(method="collection", variance=D("-940500.00")))
    }
    assert keys == {("variance_amount", "validation.must_be_positive")}
    keys = {(v.field, v.message_key) for v in validate(_amounts(gross=D("0.00"), commission=D("0.00")))}
    assert ("gross_amount", "validation.must_be_positive") in keys


# --- matching -------------------------------------------------------------------------------------
def test_fifo_and_oldest_unsettled() -> None:
    d1, d2, d3 = date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16)
    inflows = [(d1, D("100.00")), (d2, D("200.00")), (d3, D("300.00"))]
    assert fifo_remaining(inflows, D("150.00")) == [(d2, D("150.00")), (d3, D("300.00"))]
    assert oldest_unsettled(inflows, D("450.00")) == d2
    assert oldest_unsettled(inflows, D("600.00")) == d1
    assert oldest_unsettled(inflows, D("0.00")) is None
    assert fifo_remaining([(d1, D("-5.00")), (d2, D("10.00"))], D("0.00")) == [(d2, D("10.00"))]


def test_match_days_five_percent_rule() -> None:
    d1, d2 = date(2026, 10, 15), date(2026, 10, 16)
    m = match_days([(d1, D("950000.00"))], D("940500.00"))
    assert m is not None and (m.gross, m.settled_from, m.settled_to) == (D("950000.00"), d1, d1)
    m = match_days([(d1, D("500000.00")), (d2, D("500000.00"))], D("980000.00"))
    assert m is not None and (m.gross, m.settled_from, m.settled_to) == (D("1000000.00"), d1, d2)
    assert match_days([(d1, D("1000000.00"))], D("940000.00")) is None  # 6% > 5%
    assert match_days([(d1, D("100.00"))], D("200.00")) is None


def test_method_branch_and_rrn_recognition() -> None:
    assert detect_method("Оплата через CLICK за 16.10", None, None, []) == "click"
    assert detect_method("to'lov", "PAYME MChJ", None, []) == "payme"
    assert detect_method("Uzum Bank merchant 16.10", None, None, []) == "uzum"
    assert detect_method("Оплата по QR-код UzQR", None, None, []) == "uzqr"
    assert detect_method("Зачисление инкассированной выручки", None, None, []) == "collection"
    assert detect_method("Возмещение по эквайрингу", None, None, []) == "card"
    assert detect_method("Перевод средств", "Bank", "200000001", ["200000001"]) == "card"
    assert detect_method("Оплата за товар", "MChJ", "300000002", ["200000001"]) is None
    b1, b2 = uuid4(), uuid4()
    terminals = {"T1": b1, "MID777": b2}
    assert detect_branches("Возмещение TID T1 за 16.10", terminals) == {b1}
    assert detect_branches("mid777 / T1", terminals) == {b1, b2}
    assert detect_branches("T10 terminal", terminals) == set()
    assert rrn_registry("Эквайринг TID T1 RRN: 000000000001, 000000000002; комиссия") == (
        "000000000001",
        "000000000002",
    )
    assert rrn_registry("эквайринг без реестра 16.10.2026") == ()
