"""1CClientBankExchange (.txt) bank statement parser (20 #55g, 26 #124). Pure Python.

The de-facto export format of Uzbek bank-client systems: ``key=value`` lines in sections::

    1CClientBankExchange
    ВерсияФормата=1.03
    Кодировка=Windows
    ...
    СекцияРасчСчет
    РасчСчет=20208000900123456001
    ДатаНачала=16.10.2026
    ...
    КонецРасчСчет
    СекцияДокумент=Платежное поручение
    Номер=101
    Дата=17.10.2026
    Сумма=940500.00
    ...
    КонецДокумента
    КонецФайла

**Encoding**: the header ``Кодировка=`` (``Windows`` → windows-1251, ``UTF-8``/``UTF8`` → UTF-8); without it —
strict UTF-8 first (BOM allowed), then windows-1251. The first line must be ``1CClientBankExchange``. Any
structural problem raises :class:`StatementError` with the 1-based ``line_no`` (→ ``422
BANK_IMPORT_FILE_INVALID``); more lines than ``max_lines`` raise :class:`StatementTooLargeError`
(→ ``413 FILE_TOO_LARGE``, like ``/import-jobs``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

HEADER: Final = "1CClientBankExchange"
ACCOUNT_START: Final = "СекцияРасчСчет"
ACCOUNT_END: Final = "КонецРасчСчет"
DOC_START: Final = "СекцияДокумент"
DOC_END: Final = "КонецДокумента"
FILE_END: Final = "КонецФайла"
_ENCODING_KEY: Final = "Кодировка"
_DATE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_AMOUNT = re.compile(r"^\d{1,16}([.,]\d{1,2})?$")
DOC_REQUIRED: Final = ("Номер", "Дата", "Сумма")


class StatementError(Exception):
    """The file is not a valid 1CClientBankExchange statement."""

    def __init__(self, line_no: int, reason: str) -> None:
        super().__init__(f"line {line_no}: {reason}")
        self.line_no = line_no
        self.reason = reason


class StatementTooLargeError(Exception):
    def __init__(self, max_lines: int) -> None:
        super().__init__(f"more than {max_lines} lines")
        self.max_lines = max_lines


@dataclass(frozen=True, slots=True)
class AccountSection:
    account: str | None
    period_from: date | None
    period_to: date | None
    fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class StatementDoc:
    """One ``СекцияДокумент`` (``line_no`` = the line of its ``СекцияДокумент=`` marker)."""

    line_no: int
    kind: str
    number: str
    doc_date: date
    amount: Decimal
    payer_account: str | None
    payer_name: str | None
    payer_inn: str | None
    recipient_account: str | None
    recipient_name: str | None
    recipient_inn: str | None
    received_date: date | None
    written_off_date: date | None
    purpose: str

    @property
    def entry_date(self) -> date:
        """``ДатаПоступило``, else ``Дата`` (20 #55g)."""
        return self.received_date or self.doc_date


@dataclass(frozen=True, slots=True)
class Statement:
    encoding: str
    header: dict[str, str]
    accounts: tuple[AccountSection, ...]
    documents: tuple[StatementDoc, ...] = field(default_factory=tuple)

    @property
    def period_from(self) -> date | None:
        days = [a.period_from for a in self.accounts if a.period_from is not None]
        return min(days) if days else _date_or_none(self.header.get("ДатаНачала"))

    @property
    def period_to(self) -> date | None:
        days = [a.period_to for a in self.accounts if a.period_to is not None]
        return max(days) if days else _date_or_none(self.header.get("ДатаКонца"))

    @property
    def account_numbers(self) -> tuple[str, ...]:
        """Distinct accounts of the file (``СекцияРасчСчет``, else the header ``РасчСчет``)."""
        found = [a.account for a in self.accounts if a.account]
        if not found and self.header.get("РасчСчет"):
            found = [self.header["РасчСчет"]]
        return tuple(dict.fromkeys(found))


def _date_or_none(raw: str | None) -> date | None:
    if not raw:
        return None
    m = _DATE.match(raw.strip())
    if m is None:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _date(raw: str, line_no: int) -> date:
    value = _date_or_none(raw)
    if value is None:
        raise StatementError(line_no, "date_invalid")
    return value


def parse_amount(raw: str, line_no: int) -> Decimal:
    text = raw.strip().replace(" ", "")
    if not _AMOUNT.match(text):
        raise StatementError(line_no, "amount_invalid")
    try:
        return Decimal(text.replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation as exc:  # pragma: no cover - the regex already guards it
        raise StatementError(line_no, "amount_invalid") from exc


def _declared_encoding(content: bytes) -> str | None:
    """The ``Кодировка=`` header value, found in either encoding without decoding the whole file."""
    for enc in ("utf-8", "cp1251"):
        marker = (_ENCODING_KEY + "=").encode(enc)
        pos = content.find(marker)
        if pos < 0:
            continue
        end = content.find(b"\n", pos)
        raw = content[pos + len(marker) : end if end >= 0 else len(content)]
        value = raw.decode("ascii", errors="replace").strip().lower().replace("-", "")
        if value in ("windows", "cp1251", "windows1251"):
            return "cp1251"
        if value in ("utf8",):
            return "utf-8"
        line_no = content[:pos].count(b"\n") + 1
        raise StatementError(line_no, "encoding_unsupported")
    return None


def decode(content: bytes) -> tuple[str, str]:
    """``(text, encoding)`` — header encoding, else strict UTF-8, else windows-1251."""
    declared = _declared_encoding(content)
    candidates = [declared] if declared else ["utf-8", "cp1251"]
    for enc in candidates:
        try:
            text = content.decode(enc)
        except UnicodeDecodeError:
            continue
        return text.removeprefix("\ufeff"), enc
    raise StatementError(1, "encoding_invalid")


def parse(content: bytes, *, max_lines: int = 20_000) -> Statement:
    text, encoding = decode(content)
    lines = text.splitlines()
    if len(lines) > max_lines:
        raise StatementTooLargeError(max_lines)
    if not lines or lines[0].strip() != HEADER:
        raise StatementError(1, "header_missing")
    header: dict[str, str] = {}
    accounts: list[AccountSection] = []
    docs: list[StatementDoc] = []
    section: str | None = None  # "account" | "doc"
    fields: dict[str, tuple[str, int]] = {}
    start_line = 0
    kind = ""
    ended = False
    for idx, raw in enumerate(lines[1:], start=2):
        line = raw.strip()
        if not line:
            continue
        if ended:
            raise StatementError(idx, "content_after_end")
        key, sep, value = line.partition("=")
        key = key.strip()
        if key == ACCOUNT_START and not sep:
            if section is not None:
                raise StatementError(idx, "section_not_closed")
            section, fields, start_line = "account", {}, idx
            continue
        if key == DOC_START:
            if section is not None:
                raise StatementError(idx, "section_not_closed")
            section, fields, start_line, kind = "doc", {}, idx, value.strip()
            continue
        if key == ACCOUNT_END and not sep:
            if section != "account":
                raise StatementError(idx, "unexpected_section_end")
            accounts.append(_account(fields))
            section = None
            continue
        if key == DOC_END and not sep:
            if section != "doc":
                raise StatementError(idx, "unexpected_section_end")
            docs.append(_document(fields, start_line, kind))
            section = None
            continue
        if key == FILE_END and not sep:
            if section is not None:
                raise StatementError(idx, "section_not_closed")
            ended = True
            continue
        if not sep or not key:
            raise StatementError(idx, "syntax")
        if section is None:
            header[key] = value.strip()
        else:
            fields[key] = (value.strip(), idx)
    if section is not None:
        raise StatementError(start_line, "section_not_closed")
    return Statement(encoding, header, tuple(accounts), tuple(docs))


def _account(fields: dict[str, tuple[str, int]]) -> AccountSection:
    def get(name: str) -> str | None:
        item = fields.get(name)
        return item[0] if item and item[0] else None

    def day(name: str) -> date | None:
        item = fields.get(name)
        return _date(item[0], item[1]) if item and item[0] else None

    return AccountSection(
        account=get("РасчСчет"),
        period_from=day("ДатаНачала"),
        period_to=day("ДатаКонца"),
        fields={k: v for k, (v, _) in fields.items()},
    )


def _document(fields: dict[str, tuple[str, int]], start_line: int, kind: str) -> StatementDoc:
    for name in DOC_REQUIRED:
        if not fields.get(name, ("", 0))[0]:
            raise StatementError(start_line, f"field_missing:{name}")
    if not fields.get("ПлательщикСчет", ("", 0))[0] and not fields.get("ПолучательСчет", ("", 0))[0]:
        raise StatementError(start_line, "field_missing:ПолучательСчет")

    def get(*names: str) -> str | None:
        for name in names:
            item = fields.get(name)
            if item and item[0]:
                return item[0]
        return None

    def day(name: str) -> date | None:
        item = fields.get(name)
        return _date(item[0], item[1]) if item and item[0] else None

    number, _ = fields["Номер"]
    doc_date = _date(*fields["Дата"])
    amount = parse_amount(*fields["Сумма"])
    if amount <= 0:
        raise StatementError(fields["Сумма"][1], "amount_invalid")
    return StatementDoc(
        line_no=start_line,
        kind=kind,
        number=number,
        doc_date=doc_date,
        amount=amount,
        payer_account=get("ПлательщикСчет", "ПлательщикРасчСчет"),
        payer_name=get("Плательщик1", "Плательщик"),
        payer_inn=get("ПлательщикИНН"),
        recipient_account=get("ПолучательСчет", "ПолучательРасчСчет"),
        recipient_name=get("Получатель1", "Получатель"),
        recipient_inn=get("ПолучательИНН"),
        received_date=day("ДатаПоступило"),
        written_off_date=day("ДатаСписано"),
        purpose=get("НазначениеПлатежа") or "",
    )
