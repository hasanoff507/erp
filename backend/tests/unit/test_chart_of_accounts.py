"""Chart of accounts constant vs 13-provodka-qoidalari.md (NSBU №21 MVP subset, 13 §1).

The spec is the source of truth: the §1 table is parsed and compared row by row, and every
account any posting rule of 13 references (Dt/Kt/Hisob table columns and inline
"Dt XXXX / Kt YYYY" prose) must exist in the constant.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from app.modules.accounting.domain.chart_of_accounts import (
    ACCOUNTS_BY_CODE,
    ALLOWED_ACCOUNT_CODES,
    CHART_OF_ACCOUNTS,
    AccountType,
    is_allowed_account,
)

SPEC_13 = Path(__file__).resolve().parents[3] / "spec" / "kod-uchun" / "13-provodka-qoidalari.md"
_CODE = re.compile(r"(?<![\d.,§/-])\d{4}(?![\d.,])")
_INLINE_POSTING = re.compile(r"Dt\s+(\d{4})(?:\s*/\s*|\s+)Kt\s+(\d{4})")
_POSTING_COLUMNS = {"dt", "kt", "hisob"}
# accounts 13 §1 lists as present but out of MVP use (qaror #52 — payroll)
_NOT_IN_USE = {"6710"}


def _spec() -> str:
    if not SPEC_13.exists():
        pytest.skip("spec/ not available")
    return SPEC_13.read_text(encoding="utf-8")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _section(text: str, start: str, end_prefix: str) -> list[str]:
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end_prefix))
    return lines[begin:stop]


def _spec_chart() -> dict[str, tuple[str, str]]:
    """13 §1 table → {code: (official name, base type token)}."""
    rows: dict[str, tuple[str, str]] = {}
    for line in _section(_spec(), "## 1.", "## 2."):
        cells = _cells(line) if line.startswith("|") else []
        if len(cells) >= 3 and re.fullmatch(r"\d{4}", cells[0]):
            assert cells[0] not in rows, f"13 §1 lists {cells[0]} twice"
            # "A (tranzit)", "T (kontr-passiv)" → base type letter(s)
            rows[cells[0]] = (cells[1], cells[2].split(" ", 1)[0])
    return rows


def _posting_references() -> dict[str, set[str]]:
    """Every account code used by a posting rule of 13 (§2 onward) → where it appears."""
    refs: dict[str, set[str]] = {}
    heading = ""
    columns: list[int] = []
    for line in _section(_spec(), "## 2.", "## Manbalar"):
        if line.startswith("#"):
            heading, columns = line.lstrip("# ").strip(), []
            continue
        for dt, kt in _INLINE_POSTING.findall(line):
            refs.setdefault(dt, set()).add(heading)
            refs.setdefault(kt, set()).add(heading)
        if not line.startswith("|"):
            columns = []
            continue
        cells = _cells(line)
        if not columns:
            columns = [i for i, c in enumerate(cells) if c.strip("*").lower() in _POSTING_COLUMNS]
            continue
        if set("".join(cells)) <= set("-: "):
            continue  # separator row
        for i in columns:
            if i < len(cells):
                for code in _CODE.findall(cells[i]):
                    refs.setdefault(code, set()).add(heading)
    return refs


def test_constant_is_well_formed() -> None:
    codes = [a.code for a in CHART_OF_ACCOUNTS]
    assert not [c for c, n in Counter(codes).items() if n > 1], "duplicate account codes"
    assert all(re.fullmatch(r"\d{4}", c) for c in codes)
    assert codes == sorted(codes), "keep the constant ordered by code"
    assert all(a.name.strip() == a.name and a.name for a in CHART_OF_ACCOUNTS)
    assert set(ACCOUNTS_BY_CODE) == ALLOWED_ACCOUNT_CODES == set(codes)
    assert is_allowed_account("9390") and not is_allowed_account("9999") and not is_allowed_account("939")


def test_constant_matches_spec_13_chart_table() -> None:
    spec = _spec_chart()
    assert len(spec) >= 30, "13 §1 table not found or truncated"
    ours = {a.code: (a.name, a.type.value) for a in CHART_OF_ACCOUNTS}
    assert set(ours) == set(spec), {"missing": set(spec) - set(ours), "extra": set(ours) - set(spec)}
    mismatches = {code: (ours[code], spec[code]) for code in spec if ours[code] != spec[code]}
    assert not mismatches, mismatches


def test_out_of_mvp_accounts_are_flagged() -> None:
    assert {a.code for a in CHART_OF_ACCOUNTS if not a.in_use} == _NOT_IN_USE
    assert ACCOUNTS_BY_CODE["6710"].type is AccountType.PASSIVE


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        # explicitly named in the G-10 review: tranzit/technical/settlement accounts posting rules use
        ("0000", AccountType.TECHNICAL),
        ("2920", AccountType.ACTIVE),
        ("4890", AccountType.ACTIVE),
        ("4910", AccountType.CONTRA_ACTIVE),
        ("5710", AccountType.ACTIVE),
        ("6610", AccountType.PASSIVE),
        ("8530", AccountType.PASSIVE),
        ("9390", AccountType.TRANSIT),
    ],
)
def test_key_accounts(code: str, kind: AccountType) -> None:
    assert ACCOUNTS_BY_CODE[code].type is kind
    assert ACCOUNTS_BY_CODE[code].in_use


def test_every_account_used_by_a_posting_rule_exists() -> None:
    refs = _posting_references()
    # sanity: the parser really saw the posting tables (sale, receipt, transfer, expense, tax)
    assert {"5010", "9020", "6410", "9120", "6010", "4410", "2970", "9430", "9410", "9420"} <= set(refs)
    unknown = {code: sorted(where) for code, where in refs.items() if code not in ALLOWED_ACCOUNT_CODES}
    assert not unknown, unknown
    unused_payroll = refs.get("6710", set())
    assert not unused_payroll, f"6710 is out of MVP (qaror #52) but posted in {sorted(unused_payroll)}"
