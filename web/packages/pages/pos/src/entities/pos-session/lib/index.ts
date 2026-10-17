/**
 * Pure helpers of the POS session (POS-01/05/07/14/15): ids, permission checks against the cashier's
 * staff snapshot, the local shift totals (offline `running_totals`, 18 §3.3) computed from the outbox,
 * the next shift number and approval-need rules (18 §2.4, §7.1, §13.1). Money stays decimal strings.
 */
import { newAttemptId } from "@shared/lib/card-terminal";
import { addMoney, compareMoney, lineTotal, money, subtractMoney, type Money } from "@shared/lib/money";

/** UUIDv7 (RFC 9562) — document / shift ids created on the device (18 §3.1, §7.1, §13.1). */
export const uuidv7 = (now: number = Date.now()): string => newAttemptId(now);

export const ZERO = "0.00" as Money;

/** 18 §3.3 `totals_by_method` keys; card split by entry mode (07 POS-07, qaror #71). */
export interface LocalMethodTotals {
  cash: Money;
  card: Money;
  uzqr: Money;
  click: Money;
  payme: Money;
  uzum: Money;
  debt: Money;
}

export interface MethodRow {
  key: "cash" | "card_integrated" | "card_manual" | "qr" | "debt";
  count: number;
  sales: Money;
  returns: Money;
  net: Money;
}

export interface LocalShiftTotals {
  openingCash: Money;
  totalsByMethod: LocalMethodTotals;
  cardSplit: { integrated: Money; manual: Money };
  /** POS-07 table rows: cash / card integrated / card manual / QR (UzQR, Click, Payme, Uzum) / debt. */
  rows: MethodRow[];
  salesCount: number;
  salesTotal: Money;
  voidedCount: number;
  returnsCount: number;
  returnsTotal: Money;
  cashSales: Money;
  cashReturns: Money;
  cashIn: Money;
  cashOut: Money;
  /** Cash debt payments of the shift (`debt_payment.created`, method `cash`) — `cash_moves` +X (WEB-01). */
  debtCashIn: Money;
  /** = opening + Σ signed `cash_moves(method='cash')` of this device's events (18 §3.2). */
  expectedCash: Money;
  /** Shift cash movements for the POS-14 list (newest first). */
  movements: LocalMovement[];
}

export interface LocalMovement {
  id: string;
  createdAt: string;
  direction: "in" | "out";
  reason: string;
  amount: Money;
  comment: string | null;
  approvedBy: string | null;
}

/** Minimal outbox row view (structurally `OutboxRow` of @shared/offline). */
export interface ShiftEventRow {
  client_event_id: string;
  type: string;
  created_at: string;
  status: string;
  retryable: boolean | null;
  payload: Record<string, unknown>;
}

/** Local return history row (structurally `SalesHistoryRow`): `summary.refund_method`, `summary.money_part`. */
export interface ReturnHistoryRow {
  client_event_id: string;
  kind: string;
  shift_id: string | null;
  total: string;
  summary?: Record<string, unknown>;
}

const asString = (v: unknown): string | null => (typeof v === "string" && v !== "" ? v : null);

function safeMoney(v: unknown): Money {
  const s = asString(v);
  if (!s) return ZERO;
  try {
    return money(s);
  } catch {
    return ZERO;
  }
}

/** A rejected non-retryable event never posted on the server — it does not count (16 §3.4). */
export const countsLocally = (row: Pick<ShiftEventRow, "status" | "retryable">): boolean =>
  row.status !== "rejected" || row.retryable === true;

/** The shift an outbox event belongs to (payload `shift_id`, `shift.opened` → its own `id`). */
export function eventShiftId(row: Pick<ShiftEventRow, "type" | "payload">): string | null {
  if (row.type === "shift.opened") return asString(row.payload.id);
  return asString(row.payload.shift_id);
}

const QR_METHODS = new Set(["uzqr", "click", "payme", "uzum"]);

export function localShiftTotals(
  openingCash: string,
  events: readonly ShiftEventRow[],
  returns: readonly ReturnHistoryRow[] = [],
): LocalShiftTotals {
  const byMethod: LocalMethodTotals = {
    cash: ZERO,
    card: ZERO,
    uzqr: ZERO,
    click: ZERO,
    payme: ZERO,
    uzum: ZERO,
    debt: ZERO,
  };
  const rows: Record<MethodRow["key"], MethodRow> = {
    cash: { key: "cash", count: 0, sales: ZERO, returns: ZERO, net: ZERO },
    card_integrated: { key: "card_integrated", count: 0, sales: ZERO, returns: ZERO, net: ZERO },
    card_manual: { key: "card_manual", count: 0, sales: ZERO, returns: ZERO, net: ZERO },
    qr: { key: "qr", count: 0, sales: ZERO, returns: ZERO, net: ZERO },
    debt: { key: "debt", count: 0, sales: ZERO, returns: ZERO, net: ZERO },
  };
  let integrated = ZERO;
  let manual = ZERO;
  let salesCount = 0;
  let salesTotal = ZERO;
  let voidedCount = 0;
  let cashIn = ZERO;
  let cashOut = ZERO;
  let debtCashIn = ZERO;
  const movements: LocalMovement[] = [];

  for (const row of events) {
    if (!countsLocally(row)) continue;
    if (row.type === "sale.created") {
      salesCount += 1;
      const payments = Array.isArray(row.payload.payments) ? (row.payload.payments as unknown[]) : [];
      const seen = new Set<MethodRow["key"]>();
      for (const raw of payments) {
        const p = (raw ?? {}) as Record<string, unknown>;
        const method = asString(p.method) ?? "cash";
        const amount = safeMoney(p.amount);
        salesTotal = addMoney(salesTotal, amount);
        if (method in byMethod) {
          const k = method as keyof LocalMethodTotals;
          byMethod[k] = addMoney(byMethod[k], amount);
        }
        let key: MethodRow["key"];
        if (method === "card") {
          key = p.card_entry_mode === "manual" ? "card_manual" : "card_integrated";
          if (key === "card_manual") manual = addMoney(manual, amount);
          else integrated = addMoney(integrated, amount);
        } else if (QR_METHODS.has(method)) key = "qr";
        else if (method === "debt") key = "debt";
        else key = "cash";
        rows[key].sales = addMoney(rows[key].sales, amount);
        if (!seen.has(key)) {
          rows[key].count += 1;
          seen.add(key);
        }
      }
    } else if (row.type === "sale.draft_voided") {
      voidedCount += 1;
    } else if (row.type === "cash_movement.created") {
      const amount = safeMoney(row.payload.amount);
      const direction = row.payload.direction === "in" ? "in" : "out";
      if (direction === "in") cashIn = addMoney(cashIn, amount);
      else cashOut = addMoney(cashOut, amount);
      const approval = (row.payload.approval ?? null) as Record<string, unknown> | null;
      movements.push({
        id: asString(row.payload.id) ?? row.client_event_id,
        createdAt: row.created_at,
        direction,
        reason: asString(row.payload.reason) ?? "other",
        amount,
        comment: asString(row.payload.comment),
        approvedBy: approval ? asString(approval.approved_by) : null,
      });
    } else if (row.type === "expense.created") {
      // B4 POS-14 «Xarajat» (18 §13.2): cash paid out of the till (`cash_moves` −X on the server)
      const amount = safeMoney(row.payload.amount);
      cashOut = addMoney(cashOut, amount);
      const approval = (row.payload.approval ?? null) as Record<string, unknown> | null;
      movements.push({
        id: asString(row.payload.id) ?? row.client_event_id,
        createdAt: row.created_at,
        direction: "out",
        reason: "expense",
        amount,
        comment: asString(row.payload.comment),
        approvedBy: approval ? asString(approval.approved_by) : null,
      });
    } else if (row.type === "debt_payment.created") {
      // POS-13 (18 §12.2): the server writes `cash_moves(+amount, method)`; only `cash` reaches the drawer
      if (row.payload.method === "cash") debtCashIn = addMoney(debtCashIn, safeMoney(row.payload.amount));
    }
  }

  const counted = new Set(events.filter(countsLocally).map((e) => e.client_event_id));
  let returnsCount = 0;
  let returnsTotal = ZERO;
  let cashReturns = ZERO;
  for (const r of returns) {
    if (r.kind !== "return" || !counted.has(r.client_event_id)) continue;
    returnsCount += 1;
    const total = safeMoney(r.total);
    returnsTotal = addMoney(returnsTotal, total);
    const method = asString(r.summary?.refund_method) ?? "cash";
    const moneyPart = r.summary?.money_part !== undefined ? safeMoney(r.summary.money_part) : total;
    let key: MethodRow["key"];
    if (method === "card") key = r.summary?.card_entry_mode === "manual" ? "card_manual" : "card_integrated";
    else if (QR_METHODS.has(method)) key = "qr";
    else if (method === "debt_adjustment") key = "debt";
    else key = "cash";
    rows[key].returns = addMoney(rows[key].returns, moneyPart);
    if (method === "cash") cashReturns = addMoney(cashReturns, moneyPart);
  }

  for (const r of Object.values(rows)) r.net = subtractMoney(r.sales, r.returns);
  const opening = safeMoney(openingCash);
  const cashSales = byMethod.cash;
  // server rule (18 §3.2, 13 X-01): expected_cash = opening_cash + Σ cash_moves(shift, method='cash')
  const expectedCash = subtractMoney(
    addMoney(opening, cashSales, cashIn, debtCashIn),
    addMoney(cashReturns, cashOut),
  );
  movements.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return {
    openingCash: opening,
    totalsByMethod: byMethod,
    cardSplit: { integrated, manual },
    rows: [rows.cash, rows.card_integrated, rows.card_manual, rows.qr, rows.debt],
    salesCount,
    salesTotal,
    voidedCount,
    returnsCount,
    returnsTotal,
    cashSales,
    cashReturns,
    cashIn,
    cashOut,
    debtCashIn,
    expectedCash,
    movements,
  };
}

/** Next OFD shift number of this register: one above everything known (server snapshot, local). */
export function nextShiftNo(...known: (number | null | undefined)[]): number {
  let max = 0;
  for (const n of known) if (typeof n === "number" && Number.isInteger(n) && n > max) max = n;
  return max + 1;
}

/**
 * 18 §2.4 / ApprovalGate: the actor's own limit for `code` covers `amount`?
 * `limit` — `undefined` = no such permission (nothing covered), `null` = unlimited.
 */
export function limitCovers(limit: string | null | undefined, amount: string): boolean {
  if (limit === undefined) return false;
  if (limit === null) return true;
  try {
    return compareMoney(money(amount), money(limit)) <= 0;
  } catch {
    return false;
  }
}

/** Owner bypass (QT-PERM-01): the owner's own action never needs an approval. */
export const isOwner = (roleCodes: readonly string[]): boolean => roleCodes.includes("owner");

/** Variance = counted − expected (18 §3.2); note required when ≠ 0. */
export function cashVariance(counted: string, expected: string): Money {
  return subtractMoney(safeMoney(counted), safeMoney(expected));
}

/** Σ denomination × count (POS-15 helper; counts are whole numbers ≥ 0). */
export function denominationsTotal(counts: Readonly<Record<string, number>>): Money {
  let total = ZERO;
  for (const [denomination, count] of Object.entries(counts)) {
    if (!Number.isInteger(count) || count <= 0) continue;
    total = addMoney(total, lineTotal(String(count), denomination));
  }
  return total;
}

/** POS-15: banknotes of the so'm in circulation (largest first). */
export const DENOMINATIONS = [
  "200000",
  "100000",
  "50000",
  "20000",
  "10000",
  "5000",
  "2000",
  "1000",
  "500",
  "200",
];
