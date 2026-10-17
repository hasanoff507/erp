import { addMoney, compareMoney, money, type Money } from "@shared/lib/money";
import type { ListVatMovesParams } from "@shared/models";

import {
  MOVES_PAGE_SIZE,
  MOVE_DOC_TYPES,
  MOVE_KINDS,
  type MoveDocType,
  type MoveKind,
  type MovesRequest,
  type PeriodKey,
  type SummaryView,
  type VatSummary,
} from "../types/index.ts";

/** Digits → integer without Number()/parseInt (money lint rule, qaror #57). */
function int(digits: string | undefined): number {
  let n = 0;
  for (const c of digits ?? "") n = n * 10 + (c.charCodeAt(0) - 48);
  return n;
}

const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/;
const QUARTER = /^(\d{4})-Q([1-4])$/;

export function isPeriodKey(value: string): boolean {
  return MONTH.test(value) || QUARTER.test(value);
}

/** Months of a period key (`2026-09` → [`2026-09`], `2026-Q3` → [`2026-07`, `2026-08`, `2026-09`]). */
export function periodMonths(key: PeriodKey): string[] {
  if (MONTH.test(key)) return [key];
  const q = QUARTER.exec(key);
  if (!q) return [];
  const year = q[1] ?? "";
  const first = (int(q[2]) - 1) * 3 + 1;
  return [first, first + 1, first + 2].map((m) => `${year}-${String(m).padStart(2, "0")}`);
}

/** `YYYY-MM` shifted by `delta` months. */
export function shiftMonth(month: string, delta: number): string {
  const m = MONTH.exec(month);
  if (!m) return month;
  const index = int(m[1]) * 12 + int(m[2]) - 1 + delta;
  const year = Math.floor(index / 12);
  return `${year}-${String((index % 12) + 1).padStart(2, "0")}`;
}

export function quarterOf(month: string): PeriodKey {
  const m = MONTH.exec(month);
  if (!m) return month;
  return `${m[1]}-Q${Math.floor((int(m[2]) - 1) / 3) + 1}`;
}

/** Period choices: the last 12 months (newest first) and the last 4 quarters. */
export function periodOptions(today: string): { months: string[]; quarters: string[] } {
  const current = today.slice(0, 7);
  const months = Array.from({ length: 12 }, (_, i) => shiftMonth(current, -i));
  const quarters: string[] = [];
  for (const month of Array.from({ length: 12 }, (_, i) => shiftMonth(current, -i))) {
    const q = quarterOf(month);
    if (!quarters.includes(q)) quarters.push(q);
  }
  return { months, quarters: quarters.slice(0, 4) };
}

function sum(values: readonly (string | null)[]): string | null {
  const present = values.filter((v): v is string => v !== null);
  return present.length === 0 ? null : addMoney(...present.map((v) => money(v)));
}

/**
 * One month → as is; a quarter → output/input/net/turnover sums of its months (decimal strings, never
 * floats), red invoices counted, the credit share left empty (a share is not additive), the regime of
 * the last month (+ `mixedRegime` when a month differs).
 */
export function summarize(period: PeriodKey, list: readonly VatSummary[]): SummaryView | null {
  const last = list.at(-1);
  if (!last) return null;
  const single = list.length === 1;
  const reds = list.map((s) => s.pending_credit_red_invoices).filter((n): n is number => n !== null);
  return {
    period,
    months: list.map((s) => s.period),
    regime: last.regime,
    outputVat: sum(list.map((s) => s.output_vat)),
    inputVat: sum(list.map((s) => s.input_vat)),
    netVat: sum(list.map((s) => s.net_vat)),
    pendingRedInvoices: reds.length === 0 ? null : reds.reduce((a, b) => a + b, 0),
    pendingCreditPct: single ? last.pending_credit_pct : null,
    turnoverBase: sum(list.map((s) => s.turnover_base)),
    turnoverRatePct: last.turnover_rate_pct,
    turnoverAmount: sum(list.map((s) => s.turnover_amount)),
    mixedRegime: list.some((s) => s.regime !== last.regime),
    taxSettlementId: single ? last.tax_settlement_id : null,
  };
}

/** Nothing was recorded in the period (every amount empty or zero) → the «empty» state. */
export function isEmptySummary(view: SummaryView): boolean {
  const zero = money("0");
  return [view.outputVat, view.inputVat, view.netVat, view.turnoverBase, view.turnoverAmount].every(
    (v) => v === null || compareMoney(money(v), zero) === 0,
  );
}

/** `net_vat > 0` — payable to the budget; `< 0` — carried forward (credit). */
export function netSign(net: string | null): -1 | 0 | 1 {
  return net === null ? 0 : compareMoney(money(net), money("0"));
}

/** Red-invoice credit share above the 10% limit (VM 830). */
export function overCreditLimit(pct: string | null, limit: string): boolean {
  return pct !== null && compareMoney(money(pct), money(limit)) > 0;
}

export function toMovesParams(req: MovesRequest): ListVatMovesParams {
  const period = req.months[req.monthIndex];
  return {
    ...(period ? { period } : {}),
    ...(req.filters.kind ? { kind: req.filters.kind } : {}),
    ...(req.filters.docType ? { doc_type: req.filters.docType } : {}),
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: MOVES_PAGE_SIZE,
  };
}

/** Total of the loaded register rows (base, VAT). */
export function movesTotals(list: readonly { base_amount: string; vat_amount: string }[]): {
  base: Money;
  vat: Money;
} {
  return {
    base: addMoney(...list.map((m) => money(m.base_amount))),
    vat: addMoney(...list.map((m) => money(m.vat_amount))),
  };
}

export function isMoveKind(value: string | null): value is MoveKind {
  return value !== null && (MOVE_KINDS as readonly string[]).includes(value);
}

export function isMoveDocType(value: string | null): value is MoveDocType {
  return value !== null && (MOVE_DOC_TYPES as readonly string[]).includes(value);
}
