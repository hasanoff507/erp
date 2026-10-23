"""Telegram message texts (uz/ru per ``users.locale``) of the M18 notifications (21 §11, US-M18-02/03).
Pure Python.

Event payloads come from many modules (contract 6) and differ in shape: each kind renders the fields it
knows and skips missing ones, so an additional payload field never breaks a message. Plain text only (no
Markdown/HTML ``parse_mode``): nothing user-entered can turn into markup.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Final

Lang = str  # "uz" | "ru"

_SUM: Final = {"uz": "so'm", "ru": "сум"}
MAX_TEXT: Final = 4096  # Telegram sendMessage limit

# kind → (uz title, ru title)
_TITLES: Final[dict[str, tuple[str, str]]] = {
    "low_stock": ("⚠️ Kam qolgan tovar", "⚠️ Заканчивается товар"),
    "expiry_soon": ("⏳ Yaroqlilik muddati yaqinlashmoqda", "⏳ Истекает срок годности"),
    "cash_variance": ("💰 Smena kassa farqi", "💰 Расхождение кассы при закрытии смены"),
    "over_limit_action": ("🔐 Limitdan katta amal", "🔐 Операция сверх лимита"),
    "state_report_diff": ("📑 Davlat hisobotida farq", "📑 Расхождение с госотчётом"),
    "offline_48h": ("📴 Kassa OFD bilan aloqasiz", "📴 Касса без связи с ОФД"),
    "subscription_due": ("💳 Obuna to'lovi eslatmasi", "💳 Напоминание об оплате подписки"),
    "subscription_grace": ("💳 Obuna muddati o'tdi", "💳 Подписка просрочена"),
    "debt_due_today": ("📒 Bugun to'lanishi kerak bo'lgan qarzlar", "📒 Долги со сроком сегодня"),
    "debt_aging_60": ("📒 60 kundan eski qarzlar", "📒 Долги старше 60 дней"),
    "debt_limit_exceeded_offline": ("📒 Offline nasiya limitdan oshdi", "📒 Офлайн-долг сверх лимита"),
    "card_settlement_mismatch": ("💳 Terminal hisoboti farqi", "💳 Расхождение сверки терминала"),
    "recurring_expense_due": ("🧾 Takroriy xarajat vaqti keldi", "🧾 Пора оплатить регулярный расход"),
    "daily_report": ("📊 Kunlik hisobot", "📊 Ежедневный отчёт"),
    "marking_alert": ("🏷 Markirovka kodi muammosi", "🏷 Проблема с кодом маркировки"),
    "marking_acceptance_due": ("🏷 Markirovka qabul muddati", "🏷 Срок приёмки маркировки"),
    "late_in_closed_period": ("📅 Yopilgan davrga kech chek", "📅 Поздний чек в закрытый период"),
    "onec_agent_paired": ("🖥 Do'kon agenti", "🖥 Агент магазина"),
    "onec_base_error": ("⚠ Do'kon agenti ogohlantirishi", "⚠ Предупреждение агента магазина"),
}

# payload field → (uz label, ru label, format) — rendered in this order when present
_FIELDS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("product_name", "Tovar", "Товар", "text"),
    ("name", "Nomi", "Название", "text"),
    ("terminal_name", "Terminal", "Терминал", "text"),
    ("counterparty_name", "Kontragent", "Контрагент", "text"),
    ("qty", "Qoldiq", "Остаток", "qty"),
    ("min_stock", "Minimal chegara", "Минимальный остаток", "qty"),
    ("qty_left", "Partiya qoldig'i", "Остаток партии", "qty"),
    ("expiry_date", "Muddati", "Срок годности", "text"),
    ("days_left", "Qolgan kun", "Осталось дней", "text"),
    ("shift_no", "Smena", "Смена", "text"),
    ("expected_cash", "Kutilgan naqd", "Ожидалось наличных", "money"),
    ("counted_cash", "Sanalgan naqd", "Пересчитано", "money"),
    ("variance", "Farq", "Расхождение", "money"),
    ("amount", "Summa", "Сумма", "money"),
    ("requested_value", "So'ralgan qiymat", "Запрошено", "money"),
    ("limit", "Limit", "Лимит", "money"),
    ("purchase_total", "Terminal bo'yicha", "По терминалу", "money"),
    ("due_date", "To'lov sanasi", "Срок оплаты", "text"),
    ("stage", "Bosqich", "Этап", "stage"),
    ("oldest_unacked_at", "Eng eski yuborilmagan chek", "Самый старый неотправленный чек", "text"),
    ("number", "Hujjat", "Документ", "text"),  # B5 marking
    ("reason", "Sabab", "Причина", "text"),  # B5 marking
    ("state", "Holat", "Состояние", "text"),  # B5 agent: connected / disconnected
)

_STAGES: Final[dict[str, tuple[str, str]]] = {
    "24h": ("24 soat (sariq)", "24 часа (жёлтый)"),
    "40h": ("40 soat (qizil)", "40 часов (красный)"),
    "46h": ("46 soat — 2 soatdan keyin blok", "46 часов — блок через 2 часа"),
    "48h": ("48 soat — fiskal blok", "48 часов — фискальная блокировка"),
    "cleared": ("tiklandi", "восстановлено"),
    "due_soon": ("muddat yaqinlashmoqda (24 soatdan kam)", "срок истекает (меньше 24 часов)"),  # B5 marking
    "overdue": ("muddat o'tdi", "срок истёк"),  # B5 marking
    "fm_locked": (
        "fiskal modul bloklandi — chek chiqmaydi",
        "фискальный модуль заблокирован — чек не выдаётся",
    ),  # B5
}


def lang_of(locale: str | None) -> Lang:
    return "ru" if (locale or "").lower().startswith("ru") else "uz"


def _i(lang: Lang) -> int:
    return 1 if lang == "ru" else 0


def fmt_money(value: Any, lang: Lang) -> str:
    """``"1234567.5"`` → ``"1 234 567.50 so'm"`` (thin grouping by spaces, always 2 decimals)."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return str(value)
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return f"{sign}{grouped}.{frac} {_SUM[lang]}"


def fmt_qty(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = format(number.normalize(), "f")
    return text if text not in {"-0", ""} else "0"


def _value(fmt: str, raw: Any, lang: Lang) -> str:
    if fmt == "money":
        return fmt_money(raw, lang)
    if fmt == "qty":
        return fmt_qty(raw)
    if fmt == "stage":
        key = (
            f"{raw}h" if isinstance(raw, int) and not isinstance(raw, bool) else str(raw)
        )  # monitor: 24/40/46/48
        return _STAGES.get(key, (str(raw), str(raw)))[_i(lang)]
    return str(raw)


def render_event(kind: str, payload: Mapping[str, Any], lang: Lang, *, branch_name: str | None = None) -> str:
    """Text of an immediate alert (US-M18-03): title, the branch, and every known payload field present."""
    title = _TITLES.get(kind, (kind, kind))[_i(lang)]
    lines = [title]
    if branch_name:
        lines.append(("Filial: " if lang == "uz" else "Филиал: ") + branch_name)
    for field, uz, ru, fmt in _FIELDS:
        raw = payload.get(field)
        if raw is None or raw == "":
            continue
        lines.append(f"{uz if lang == 'uz' else ru}: {_value(fmt, raw, lang)}")
    if payload.get("offline"):
        lines.append("Offline tasdiqlangan" if lang == "uz" else "Подтверждено офлайн")
    return "\n".join(lines)[:MAX_TEXT]


def _branch_block(row: Mapping[str, Any], lang: Lang) -> list[str]:
    def m(key: str) -> str:
        return fmt_money(row.get(key, "0"), lang)

    count = row.get("receipts_count", 0)
    if lang == "ru":
        return [
            f"Продажи: {m('sales_total')}",
            f"Чеков: {count} · средний {m('avg_receipt')}",
            f"Возвраты: {m('returns_total')}",
            f"Чистая прибыль: {m('net_profit')}",
            f"Наличные в кассах: {m('cash_on_hand')}",
            f"Новые долги: {m('new_debts')}",
            f"Возвращённые долги: {m('debt_payments')}",
            f"Просроченные долги: {m('overdue_debt_total')}",
        ]
    return [
        f"Savdo: {m('sales_total')}",
        f"Cheklar: {count} · o'rtacha {m('avg_receipt')}",
        f"Qaytarishlar: {m('returns_total')}",
        f"Sof foyda: {m('net_profit')}",
        f"Naqd kassada: {m('cash_on_hand')}",
        f"Yangi qarzlar: {m('new_debts')}",
        f"Qaytgan qarzlar: {m('debt_payments')}",
        f"Muddati o'tgan qarz: {m('overdue_debt_total')}",
    ]


def render_daily_report(report: Mapping[str, Any], lang: Lang) -> str:
    """US-M18-02 / QT-M18-02: today's sales, net profit (M15), cash (M16), new/returned debts and tomorrow's
    debtors (M08); per branch when the recipient sees more than one branch."""
    uz = lang == "uz"
    title = _TITLES["daily_report"][_i(lang)]
    lines = [f"{title} — {report.get('day', '')}", ""]
    total: Mapping[str, Any] = report.get("total") or {}
    lines += _branch_block(total, lang)
    branches: Sequence[Mapping[str, Any]] = report.get("branches") or []
    if len(branches) > 1:
        for branch in branches:
            lines += ["", f"🏬 {branch.get('branch_name', '')}"]
            lines += _branch_block(branch, lang)
    debtors: Sequence[Mapping[str, Any]] = report.get("debtors_due_tomorrow") or []
    if debtors:
        lines += ["", "Ertaga to'lashi kerak:" if uz else "Должны оплатить завтра:"]
        for debtor in debtors[:10]:
            lines.append(f"• {debtor.get('name', '')} — {fmt_money(debtor.get('amount_due', '0'), lang)}")
        if len(debtors) > 10:
            lines.append(f"… +{len(debtors) - 10}")
    attention: list[str] = []
    low = int(total.get("low_stock_count") or 0)
    if low:
        attention.append(f"kam qolgan tovar: {low}" if uz else f"заканчивается товаров: {low}")
    if report.get("unsynced_devices"):
        count = int(report.get("unsynced_device_count") or 0)
        attention.append(
            f"sinxronlanmagan kassalar: {count} (raqamlar to'liq emas)"
            if uz
            else f"несинхронизированных касс: {count} (данные неполные)"
        )
    if attention:
        lines += ["", ("Diqqat: " if uz else "Внимание: ") + "; ".join(attention)]
    return "\n".join(lines)[:MAX_TEXT]


def render(kind: str, payload: Mapping[str, Any], lang: Lang, *, branch_name: str | None = None) -> str:
    if kind == "daily_report":
        report = payload.get("report")
        return render_daily_report(report if isinstance(report, Mapping) else {}, lang)
    return render_event(kind, payload, lang, branch_name=branch_name)


# --- bot replies (webhook) -----------------------------------------------------------------------------
def linked_text(tenant_name: str, user_name: str, lang: Lang) -> str:
    if lang == "ru":
        return (
            f"✅ Telegram подключён: {tenant_name} ({user_name}).\n"
            "Ежедневный отчёт и уведомления будут приходить сюда. Отключить — в Настройки → Telegram."
        )
    return (
        f"✅ Telegram ulandi: {tenant_name} ({user_name}).\n"
        "Kunlik hisobot va ogohlantirishlar shu yerga keladi. Uzish — Sozlamalar → Telegram."
    )


def link_failed_text(lang: Lang) -> str:
    if lang == "ru":
        return (
            "❌ Ссылка недействительна или устарела (действует 10 минут, один раз). "
            "Получите новую в Настройки → Telegram."
        )
    return (
        "❌ Havola yaroqsiz yoki muddati o'tgan (10 daqiqa, bir marta amal qiladi). "
        "Yangisini Sozlamalar → Telegram bo'limidan oling."
    )


def help_text(lang: Lang) -> str:
    if lang == "ru":
        return (
            "Этот бот присылает отчёты магазина. Чтобы подключиться, откройте Настройки → Telegram "
            "и нажмите «Подключить»."
        )
    return (
        "Bu bot do'kon hisobotlarini yuboradi. Ulash uchun Sozlamalar → Telegram bo'limida "
        "«Telegram ulash» tugmasini bosing."
    )
