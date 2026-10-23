"""NSBU (BHMS) №21 chart of accounts — MVP subset (13 §1, 27 Bosqich 0, 26 #6/#36).

There is no chart-of-accounts table: ``ledger_entries.account_dt/kt`` are
4-digit TEXT and the allowed list is this application constant (12 §7.17).
New codes are append-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class AccountType(StrEnum):
    ACTIVE = "A"
    PASSIVE = "P"
    CONTRA_ACTIVE = "KA"
    TRANSIT = "T"
    TECHNICAL = "Texnik"


@dataclass(frozen=True, slots=True)
class Account:
    code: str
    name: str
    type: AccountType
    in_use: bool = True


_A, _P, _KA, _T = AccountType.ACTIVE, AccountType.PASSIVE, AccountType.CONTRA_ACTIVE, AccountType.TRANSIT

CHART_OF_ACCOUNTS: Final[tuple[Account, ...]] = (
    Account("0000", "Boshlang'ich qoldiqlar (yordamchi)", AccountType.TECHNICAL),
    Account("2910", "Ombordagi tovarlar", _A),
    Account("2920", "Chakana savdodagi tovarlar", _A),
    Account("2970", "Yo'ldagi tovarlar", _A),
    Account("4010", "Xaridorlar va buyurtmachilardan olinadigan to'lovlar", _A),
    Account(
        "4310",
        "Tovar-moddiy zaxiralar uchun mol yetkazib beruvchilar va pudratchilarga berilgan bo'naklar",
        _A,
    ),
    Account("4410", "Byudjetga soliqlar va yig'imlar bo'yicha bo'nak to'lovlari (turlari bo'yicha)", _A),
    Account("4730", "Moddiy zararni qoplash bo'yicha xodimlarning qarzi", _A),
    Account("4890", "Boshqa debitorlik qarzlar", _A),
    Account("4910", "Shubhali qarzlar bo'yicha rezerv", _KA),
    Account("5010", "Milliy valyutadagi pul mablag'lari", _A),
    Account("5110", "Hisob-kitob hisobvarag'i", _A),
    Account("5710", "Yo'ldagi pul mablag' (o'tkazma)lari", _A),
    Account("5910", "Kamomadlar va qiymatliklarning buzilishidan yo'qotishlar", _A),
    Account("6010", "Mol yetkazib beruvchilar va pudratchilarga to'lovlar", _P),
    Account("6310", "Xaridor va buyurtmachilardan olingan bo'naklar", _P),
    Account("6410", "Byudjetga to'lovlar bo'yicha qarzlar (turlari bo'yicha)", _P),
    Account("6610", "To'lanadigan dividendlar", _P),
    # qaror #52: payroll accounting is out of MVP scope
    Account("6710", "Ish haqi bo'yicha xodimlar bilan hisob-kitoblar", _P, in_use=False),
    Account("8330", "Ulushlar va paylar (ustav kapitali)", _P),
    Account("8530", "Tekinga olingan mulk", _P),
    Account("8710", "Hisobot davrining taqsimlanmagan foydasi (qoplanmagan zarari)", _P),
    Account("8720", "Jamg'arilgan foyda (qoplanmagan zarar)", _P),
    Account("9020", "Tovarlarni sotishdan daromadlar", _T),
    Account("9040", "Sotilgan tovarlar (mahsulotlar)ning qaytishi", _T),
    Account("9050", "Xaridorlar va buyurtmachilarga berilgan chegirmalar", _T),
    Account("9120", "Sotilgan tovarlarning tannarxi", _T),
    Account("9390", "Boshqa operatsion daromadlar", _T),
    Account("9410", "Sotish xarajatlari", _T),
    Account("9420", "Ma'muriy xarajatlar", _T),
    Account("9430", "Boshqa operatsion xarajatlar", _T),
    Account("9820", "Foydadan hisoblangan boshqa soliq majburiyatlari bo'yicha xarajatlar", _T),
    Account("9910", "Yakuniy moliyaviy natija (foyda yoki zarar)", _T),
)

ACCOUNTS_BY_CODE: Final[dict[str, Account]] = {a.code: a for a in CHART_OF_ACCOUNTS}
ALLOWED_ACCOUNT_CODES: Final[frozenset[str]] = frozenset(ACCOUNTS_BY_CODE)


def is_allowed_account(code: str) -> bool:
    return code in ALLOWED_ACCOUNT_CODES
