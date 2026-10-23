/**
 * @shared/lib/debt-allocation — debt payment allocation and `debt_settlement` receipt lines
 * (18-api-kassa.md §12.2, 13 §2.14, 16 §1; qaror #45, #67).
 *
 * TS twin of backend `app/shared/debt_allocation.py`: ONE formula for the offline POS and the server posting.
 * Both test suites read `<repo>/shared/debt-allocation-vectors.json` (32 §6.3) — keep them in lock-step.
 *
 * Order: open `sales` + `debt_openings` by `COALESCE(due_date, doc_date), doc_date, doc_id`; then
 * `debt_writeoffs` by `doc_date, doc_id`; the rest is `unallocated_amount` (offline overpayment, Kt 6310).
 * A line returned against the sale keeps only its remainder (ACC-01, 13 §2.5): `eff_total_i =
 * max(line_total_i − returned_amount_i, 0)`, `eff_qty_i = qty_i − returned_qty_i`; lines with `eff_total_i = 0`
 * are skipped (`returned_*` are optional — absent = 0).
 * Receipt lines per sale allocation `a` (`total = Σ eff_total_i`, `room_i = max(eff_total_i − settled_amount_i,
 * 0)`, `goods = min(a, Σ room_i)`): closing (`goods = Σ room_i`) → `amt_i = room_i`; otherwise
 * `amt_i = min(ROUND_HALF_UP(eff_total_i × goods / total, 2), room_i)` with the rounding rest on the largest
 * `eff_total` (ties — larger line number); `qty_i = max(R3(eff_qty_i × (settled_i + amt_i) / eff_total_i) −
 * R3(eff_qty_i × settled_i / eff_total_i), 0.001)` (ACC-10 — one line's receipts sum to exactly `eff_qty_i`);
 * `vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)`; marking code only on a line the receipt closes.
 * Openings, write-offs, the unallocated rest and anything above a sale's fiscal room → ONE general line
 * (no goods, qty 1.000, vat 0.00). Money in and out as decimal strings — never JS numbers.
 * The server sends `open_amount` already reconciled to the customer's balance (ACC-02, 16 §1).
 */
import Decimal from "decimal.js";

import { toDecimal, type Money } from "#/money/index.ts";

const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });

export type DebtTargetType = "sales" | "debt_openings" | "debt_writeoffs";

/** 16 §1 `open_debt_docs[].lines[]` (only the fields the formula reads are required). */
export interface OpenDebtLine {
  sale_line_id: string;
  product_id: string | null;
  qty: string;
  line_total: string;
  vat_rate: string;
  settled_amount: string;
  marking_code: string | null;
  /** Σ posted return_lines.qty of this sale line (16 §1; absent = "0.000"). */
  returned_qty?: string;
  /** Σ posted return_lines.line_total of this sale line (16 §1; absent = "0.00"). */
  returned_amount?: string;
  [extra: string]: unknown;
}

/** 16 §1 `customers[].open_debt_docs[]`. */
export interface OpenDebtDoc {
  doc_type: DebtTargetType;
  doc_id: string;
  doc_date: string;
  due_date: string | null;
  open_amount: string;
  lines?: OpenDebtLine[];
  [extra: string]: unknown;
}

/** 18 §12.2 `allocations[]`. */
export interface DebtAllocation {
  target_doc_type: DebtTargetType;
  target_doc_id: string;
  amount: Money;
}

/** 18 §12.2 `fiscal_lines[]`. */
export interface DebtFiscalLine {
  sale_id: string | null;
  sale_line_id: string | null;
  product_id: string | null;
  qty: string;
  amount: Money;
  vat_rate: string;
  vat_amount: Money;
  marking_code: string | null;
}

export interface DebtAllocationResult {
  allocations: DebtAllocation[];
  unallocated_amount: Money;
  fiscal_lines: DebtFiscalLine[];
}

const TARGET_TYPES: readonly string[] = ["sales", "debt_openings", "debt_writeoffs"];
const ZERO = new D(0);
const MIN_QTY = new D("0.001");

function dec(value: string): Decimal {
  return new D(toDecimal(value).toString());
}

function round(value: Decimal, places: number): Decimal {
  return value.toDecimalPlaces(places, D.ROUND_HALF_UP);
}

function asMoney(value: Decimal): Money {
  return round(value, 2).toFixed(2) as Money;
}

function cmp(a: string, b: string): number {
  if (a < b) return -1;
  return a > b ? 1 : 0;
}

/** Debts first (sales + openings), then write-offs — the allocation order of 18 §12.2. */
export function allocationOrder(docs: readonly OpenDebtDoc[]): OpenDebtDoc[] {
  const debts = docs.filter((d) => d.doc_type !== "debt_writeoffs");
  const writeoffs = docs.filter((d) => d.doc_type === "debt_writeoffs");
  debts.sort(
    (a, b) =>
      cmp(a.due_date ?? a.doc_date, b.due_date ?? b.doc_date) ||
      cmp(a.doc_date, b.doc_date) ||
      cmp(a.doc_id.toLowerCase(), b.doc_id.toLowerCase()),
  );
  writeoffs.sort(
    (a, b) => cmp(a.doc_date, b.doc_date) || cmp(a.doc_id.toLowerCase(), b.doc_id.toLowerCase()),
  );
  return [...debts, ...writeoffs];
}

function vatOf(amount: Decimal, rate: Decimal): Decimal {
  return round(amount.times(rate).div(rate.plus(100)), 2);
}

/** ACC-10: the quantity telescopes over the cumulative `settled_amount` (one line's receipts sum to `effQty`). */
function qtyTelescoped(effQty: Decimal, settled: Decimal, amt: Decimal, effTotal: Decimal): Decimal {
  if (effTotal.lte(0)) return MIN_QTY;
  const before = round(effQty.times(D.min(settled, effTotal)).div(effTotal), 3);
  const after = round(effQty.times(D.min(settled.plus(amt), effTotal)).div(effTotal), 3);
  return D.max(after.minus(before), MIN_QTY);
}

function sum(values: readonly Decimal[]): Decimal {
  return values.reduce((acc, v) => acc.plus(v), ZERO);
}

function saleLines(doc: OpenDebtDoc, alloc: Decimal): { lines: DebtFiscalLine[]; excess: Decimal } {
  const effTotal = (ln: OpenDebtLine): Decimal =>
    D.max(round(dec(ln.line_total), 2).minus(round(dec(ln.returned_amount ?? "0.00"), 2)), ZERO);
  const src = (doc.lines ?? []).filter((ln) => effTotal(ln).gt(0));
  const totals = src.map(effTotal);
  const rooms = src.map((ln, i) => D.max((totals[i] ?? ZERO).minus(round(dec(ln.settled_amount), 2)), ZERO));
  const total = sum(totals);
  const room = sum(rooms);
  const goods = D.min(alloc, room);
  const excess = alloc.minus(goods);
  if (goods.lte(0) || total.lte(0)) return { lines: [], excess: alloc };
  const closing = goods.eq(room);
  const amounts: Decimal[] = closing
    ? [...rooms]
    : totals.map((t, i) => D.min(round(t.times(goods).div(total), 2), rooms[i] ?? ZERO));
  if (!closing) {
    let diff = goods.minus(sum(amounts));
    const order = src
      .map((_, i) => i)
      .sort((a, b) => (totals[b] ?? ZERO).comparedTo(totals[a] ?? ZERO) || b - a);
    for (const i of order) {
      if (diff.isZero()) break;
      const current = amounts[i] ?? ZERO;
      const step = diff.gt(0)
        ? D.min(diff, (rooms[i] ?? ZERO).minus(current))
        : D.min(diff.neg(), current).neg();
      amounts[i] = current.plus(step);
      diff = diff.minus(step);
    }
  }
  const lines: DebtFiscalLine[] = [];
  src.forEach((ln, i) => {
    const amt = amounts[i] ?? ZERO;
    const roomI = rooms[i] ?? ZERO;
    if (amt.lte(0)) return;
    const closes = amt.eq(roomI);
    const effQty = D.max(round(dec(ln.qty), 3).minus(round(dec(ln.returned_qty ?? "0.000"), 3)), ZERO);
    const q = qtyTelescoped(effQty, round(dec(ln.settled_amount), 2), amt, totals[i] ?? ZERO);
    const rate = dec(ln.vat_rate);
    lines.push({
      sale_id: doc.doc_id.toLowerCase(),
      sale_line_id: ln.sale_line_id.toLowerCase(),
      product_id: ln.product_id === null ? null : ln.product_id.toLowerCase(),
      qty: q.toFixed(3),
      amount: asMoney(amt),
      vat_rate: round(rate, 2).toFixed(2),
      vat_amount: asMoney(vatOf(amt, rate)),
      marking_code: closes ? ln.marking_code : null,
    });
  });
  return { lines, excess };
}

/**
 * Allocates `amount` (Money string > 0) over the customer's open debt documents.
 * `fiscal=false` (bank payment — no receipt) returns no `fiscal_lines`.
 */
export function allocateDebtPayment(
  amount: string,
  docs: readonly OpenDebtDoc[],
  options: { fiscal?: boolean } = {},
): DebtAllocationResult {
  const fiscal = options.fiscal ?? true;
  let rest = round(dec(amount), 2);
  if (rest.lte(0)) throw new RangeError("payment amount must be positive");
  for (const doc of docs) {
    if (!TARGET_TYPES.includes(doc.doc_type)) throw new RangeError(`unknown target doc_type ${doc.doc_type}`);
  }
  const allocations: DebtAllocation[] = [];
  const lines: DebtFiscalLine[] = [];
  let general = ZERO;
  for (const doc of allocationOrder(docs)) {
    if (rest.lte(0)) break;
    const open = round(dec(doc.open_amount), 2);
    if (open.lte(0)) continue;
    const take = D.min(rest, open);
    rest = rest.minus(take);
    allocations.push({
      target_doc_type: doc.doc_type,
      target_doc_id: doc.doc_id.toLowerCase(),
      amount: asMoney(take),
    });
    if (doc.doc_type === "sales" && fiscal) {
      const part = saleLines(doc, take);
      lines.push(...part.lines);
      general = general.plus(part.excess);
    } else {
      general = general.plus(take);
    }
  }
  general = general.plus(rest);
  if (fiscal && general.gt(0)) {
    lines.push({
      sale_id: null,
      sale_line_id: null,
      product_id: null,
      qty: "1.000",
      amount: asMoney(general),
      vat_rate: "0.00",
      vat_amount: "0.00" as Money,
      marking_code: null,
    });
  }
  return { allocations, unallocated_amount: asMoney(rest), fiscal_lines: fiscal ? lines : [] };
}
