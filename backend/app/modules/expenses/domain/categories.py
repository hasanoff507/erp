"""Default expense categories → default account (13 §2.17, 12 §5.2, 26 #143).

Created per tenant at provisioning; the tenant may change ``default_account``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ExpenseCategoryTemplate:
    code: str
    name: str
    default_account: str
    source_ref: str


_C = ExpenseCategoryTemplate

DEFAULT_EXPENSE_CATEGORIES: Final[tuple[ExpenseCategoryTemplate, ...]] = (
    _C("rent_store", "Ijara — savdo zali/ombor", "9410", "VMQ-54 2.1.2.3"),
    _C("rent_office", "Ijara — ofis", "9420", "VMQ-54 2.2.8"),
    _C("utilities_store", "Kommunal — do'kon", "9410", "VMQ-54 2.1.2.6"),
    _C("utilities_office", "Kommunal — ofis", "9420", "VMQ-54 2.2.4"),
    _C("communication", "Aloqa, internet, telefon", "9420", "VMQ-54 2.2.6"),
    _C("transport_delivery", "Transport — tovar tashish", "9410", "VMQ-54 2.1.1"),
    _C("transport_admin", "Transport — xizmat avtomobili", "9420", "VMQ-54 2.2.3"),
    _C("payroll_sales", "Ish haqi — savdo xodimlari", "9410", "VMQ-54 2.1.2.1"),
    _C("payroll_admin", "Ish haqi — boshqaruv", "9420", "VMQ-54 2.2.1"),
    _C("advertising", "Reklama, marketing", "9410", "VMQ-54 2.1.2.8"),
    _C("repair_store", "Ta'mirlash — savdo", "9410", "VMQ-54 2.1.2.3"),
    _C("repair_admin", "Ta'mirlash — ma'muriy", "9420", "VMQ-54 2.2.9"),
    _C("packaging", "Tara, qadoqlash", "9410", "VMQ-54 2.1.2.10"),
    _C("supplies", "Inventar, xo'jalik buyumlari", "9410", "VMQ-54 2.1.2.5"),
    _C("bank_services", "Bank xizmatlari", "9430", "S1 §410, §412"),
    _C("collection_service", "Inkassatsiya xizmati", "9410", "VMQ-54 2.1.2.18"),
    _C("period_taxes", "Soliq va yig'imlar (davr xarajati)", "9430", "S1 §275"),
    _C("fines", "Jarimalar, penyalar", "9430", "VMQ-54 2.3.15"),
    _C("audit_consulting", "Audit, maslahat, o'qitish", "9430", "S1 §410"),
    _C("tax_payment", "Soliq to'lovi (byudjetga)", "6410", "S1 §275"),
    _C("other", "Boshqa", "9430", "S1 §410"),
)
