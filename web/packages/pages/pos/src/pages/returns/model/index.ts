/**
 * POS-05 — Mijozdan tovar qaytarish (07 POS-05; 18 §7.1, §2.4, §2.7; 16 §2.1, §7; US-M02-01…03;
 * QT-M02-01…04). The original receipt comes from `GET /sales` (online) or the local 90-day history
 * (offline); the return is ONE `return.created` outbox event. Approval (single ApprovalGate call on the
 * server): no receipt → `return_no_receipt` (always, any amount); expired goods line → `return_over_limit`
 * that only an unlimited `returns.approve` covers; otherwise the amount above the cashier's own
 * `returns.approve` limit (default 100 000 so'm). Marked goods: online only (MARKING_RETURN_REQUIRES_ONLINE).
 */
import Decimal from "decimal.js";

import { api } from "@shared/api";
import type { SaleOut } from "@shared/models";
import {
  addMoney,
  compareMoney,
  money,
  subtractMoney,
  toDecimal,
  vatIncluded,
  type Money,
} from "@shared/lib/money";

import { isOwner, limitCovers, type PosCashier } from "#/entities/pos-session/index.ts";
import type { ApprovalRef } from "#/features/manager-approval/index.ts";

export type ReturnReason = "defective" | "wrong_item" | "customer_changed_mind" | "other";
export type RefundMethod = "cash" | "card" | "uzqr" | "click" | "payme" | "uzum" | "debt_adjustment";

export const REASONS: ReturnReason[] = ["defective", "wrong_item", "customer_changed_mind", "other"];
export const REFUND_METHODS: RefundMethod[] = [
  "cash",
  "card",
  "uzqr",
  "click",
  "payme",
  "uzum",
  "debt_adjustment",
];

export interface SourceLine {
  saleLineId: string | null;
  productId: string;
  name: string;
  unitCode: string;
  fractional: boolean;
  qty: string;
  /** Already returned (server + this device's unsynced returns). */
  returnedQty: string;
  /** 4-place price string as stored (`sale_lines.price`). */
  price: string;
  lineTotal: Money;
  vatRate: string;
  vatExemptionCode: string | null;
  markingCode: string | null;
}

export interface SourcePayment {
  method: string;
  amount: Money;
  cardEntryMode: string | null;
  rrn: string | null;
}

export interface ReturnSource {
  saleId: string;
  number: string | null;
  createdAt: string;
  counterpartyId: string | null;
  payments: SourcePayment[];
  lines: SourceLine[];
  origin: "server" | "local";
}

export interface LineState {
  key: string;
  selected: boolean;
  qty: string;
  restock: boolean;
  /** Cashier marked the goods expired (lot expiry is not on the device) → restock false + approval. */
  expired: boolean;
}

const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });

export const lineKey = (l: Pick<SourceLine, "saleLineId" | "productId">, i: number): string =>
  l.saleLineId ?? `${l.productId}#${i}`;

export function qtyLeft(line: Pick<SourceLine, "qty" | "returnedQty">): string {
  const left = toDecimal(line.qty).minus(toDecimal(line.returnedQty));
  return (left.isNegative() ? new D(0) : left).toFixed(3);
}

/**
 * 18 §7.1: `refund_line = ROUND_HALF_UP(line_total × ret_qty / sale_qty, 0)`; the last return of a line takes
 * the rest (`line_total − refund of what was returned before`). Display / approval estimate — the server
 * computes the posted amount.
 */
export function refundLine(
  line: Pick<SourceLine, "lineTotal" | "qty" | "returnedQty">,
  retQty: string,
): Money {
  const total = toDecimal(line.lineTotal);
  const saleQty = toDecimal(line.qty);
  if (saleQty.isZero()) return "0.00" as Money;
  const part = (q: Decimal) => total.times(q).div(saleQty).toDecimalPlaces(0, Decimal.ROUND_HALF_UP);
  const ret = toDecimal(retQty);
  const before = toDecimal(line.returnedQty);
  if (ret.plus(before).greaterThanOrEqualTo(saleQty)) return total.minus(part(before)).toFixed(2) as Money;
  return part(ret).toFixed(2) as Money;
}

/** Validates a return qty against the unit and the not-yet-returned rest (07 POS-05 `returnQty`). */
export function qtyValid(line: SourceLine, qty: string): boolean {
  if (!/^\d+(\.\d{1,3})?$/.test(qty)) return false;
  const q = toDecimal(qty);
  if (q.lessThanOrEqualTo(0)) return false;
  if (!line.fractional && !q.isInteger()) return false;
  return q.lessThanOrEqualTo(toDecimal(qtyLeft(line)));
}

export interface ReturnTotals {
  amount: Money;
  vat: Money;
  /** Pieces in the selected lines (display). */
  count: number;
  /** Money returned by `refund_method` (debt of the sale is reduced first, 18 §7.1). */
  moneyPart: Money;
  debtPart: Money;
  expired: boolean;
  marked: boolean;
}

export function returnTotals(
  source: ReturnSource | null,
  lines: readonly SourceLine[],
  state: readonly LineState[],
): ReturnTotals {
  let amount = "0.00" as Money;
  let vat = "0.00" as Money;
  let count = 0;
  let expired = false;
  let marked = false;
  lines.forEach((line, i) => {
    const s = state[i];
    if (!s?.selected || !qtyValid(line, s.qty)) return;
    const refund = source
      ? refundLine(line, s.qty)
      : (toDecimal(s.qty)
          .times(toDecimal(line.price))
          .toDecimalPlaces(0, Decimal.ROUND_HALF_UP)
          .toFixed(2) as Money);
    amount = addMoney(amount, refund);
    if (compareMoney(money(line.vatRate), "0.00" as Money) > 0)
      vat = addMoney(vat, vatIncluded(refund, line.vatRate));
    count += 1;
    expired ||= s.expired;
    marked ||= line.markingCode !== null;
  });
  // the sale's debt is reduced first; the device assumes it is still fully open (conservative)
  const debtOfSale = (source?.payments ?? [])
    .filter((p) => p.method === "debt")
    .reduce((a, p) => addMoney(a, p.amount), "0.00" as Money);
  const debtPart = compareMoney(amount, debtOfSale) < 0 ? amount : debtOfSale;
  return { amount, vat, count, moneyPart: subtractMoney(amount, debtPart), debtPart, expired, marked };
}

export type ApprovalNeed =
  | { needed: false }
  | {
      needed: true;
      kind: "return_no_receipt" | "return_over_limit";
      amount: Money | null;
      reason: "no_receipt" | "expired" | "over_limit";
    };

/** 18 §7.1 / ApprovalGate (QT-M02-02, -03, -04; QT-PERM-01 owner bypass). */
export function returnApprovalNeed(input: {
  cashier: Pick<PosCashier, "roleCodes">;
  ownLimit: string | null | undefined;
  amount: Money;
  noReceipt: boolean;
  expired: boolean;
}): ApprovalNeed {
  if (isOwner(input.cashier.roleCodes)) return { needed: false };
  if (input.noReceipt)
    return { needed: true, kind: "return_no_receipt", amount: input.amount, reason: "no_receipt" };
  if (input.expired) {
    return input.ownLimit === null
      ? { needed: false }
      : { needed: true, kind: "return_over_limit", amount: null, reason: "expired" };
  }
  if (limitCovers(input.ownLimit, input.amount)) return { needed: false };
  return { needed: true, kind: "return_over_limit", amount: input.amount, reason: "over_limit" };
}

/** Default refund method = the original payment method (largest payment), 07 POS-05. */
export function defaultRefundMethod(source: ReturnSource | null): RefundMethod {
  const main = [...(source?.payments ?? [])]
    .filter((p) => p.method !== "debt")
    .sort((a, b) => compareMoney(b.amount, a.amount))[0];
  const m = main?.method;
  return m && (REFUND_METHODS as string[]).includes(m) ? (m as RefundMethod) : "cash";
}

export interface RefundCard {
  card_entry_mode: "integrated" | "manual";
  card_result: Record<string, unknown> | null;
  card_type: null;
  card_mask: null;
  rrn: null;
  approval_code: null;
  card_scheme: null;
  manual_reason: string | null;
  card_manual_approval: ApprovalRef | null;
}

/** 18 §7.1 payload — exactly the documented fields (`receipt_seq` is filled by enqueueEvent). */
export function returnPayload(input: {
  id: string;
  branchId: string;
  shiftId: string;
  cashRegisterId: string;
  source: ReturnSource | null;
  lines: readonly SourceLine[];
  state: readonly LineState[];
  reason: ReturnReason;
  refundMethod: RefundMethod;
  refundCard: RefundCard | null;
  approval: ApprovalRef | null;
  isOffline: boolean;
  counterpartyId: string | null;
}) {
  const lines = input.lines
    .map((line, i) => ({ line, s: input.state[i] }))
    .filter(({ s }) => s?.selected)
    .map(({ line, s }) => ({
      sale_line_id: input.source ? line.saleLineId : null,
      product_id: line.productId,
      qty: toDecimal(s?.qty ?? "0").toFixed(3),
      price: toDecimal(line.price).toFixed(4),
      vat_rate: toDecimal(line.vatRate).toFixed(2),
      vat_exemption_code: line.vatExemptionCode,
      marking_code: line.markingCode,
      restock: s?.expired ? false : (s?.restock ?? true),
    }));
  return {
    id: input.id,
    branch_id: input.branchId,
    shift_id: input.shiftId,
    cash_register_id: input.cashRegisterId,
    receipt_seq: null as number | null,
    fiscal_result: null,
    sale_id: input.source?.saleId ?? null,
    counterparty_id: input.counterpartyId,
    is_offline: input.isOffline,
    lines,
    reason: input.reason,
    refund_method: input.refundMethod,
    refund_card: input.refundMethod === "card" ? input.refundCard : null,
    approval: input.approval,
  };
}

// ---- sources -------------------------------------------------------------------------------------

const FRACTIONAL_UNITS = new Set(["kg", "g", "l", "ml", "m", "m2", "m3", "t"]);

export function fromServerSale(
  sale: SaleOut,
  localReturned: Readonly<Record<string, string>> = {},
): ReturnSource {
  return {
    saleId: sale.id,
    number: sale.number ?? sale.temp_number,
    createdAt: sale.created_at,
    counterpartyId: sale.counterparty_id,
    payments: sale.payments.map((p) => ({
      method: p.method,
      amount: money(p.amount),
      cardEntryMode: p.card_entry_mode ?? null,
      rrn: p.rrn,
    })),
    lines: sale.lines.map((l) => ({
      saleLineId: l.sale_line_id,
      productId: l.product_id,
      name: l.product_name,
      unitCode: l.unit_code,
      fractional: FRACTIONAL_UNITS.has(l.unit_code),
      qty: l.qty,
      returnedQty: toDecimal(l.returned_qty)
        .plus(toDecimal(localReturned[l.sale_line_id] ?? "0"))
        .toFixed(3),
      price: l.price,
      lineTotal: money(l.line_total),
      vatRate: l.vat_rate,
      vatExemptionCode: l.vat_exemption_code,
      markingCode: l.marking_code,
    })),
    origin: "server",
  };
}

/**
 * Local receipt history row (16 §10; written by the sale screen with `history.summary`, contract
 * pos-session.md §3): `summary.lines[]` / `summary.payments[]` as in the `sale.created` payload plus names.
 */
export function fromLocalHistory(
  row: {
    id: string;
    number?: string | null;
    created_at: string;
    customer_id?: string | null;
    summary?: Record<string, unknown>;
  },
  localReturned: Readonly<Record<string, string>> = {},
): ReturnSource | null {
  const summary = row.summary ?? {};
  const rawLines = Array.isArray(summary.lines) ? (summary.lines as Record<string, unknown>[]) : null;
  if (!rawLines || rawLines.length === 0) return null;
  const str = (v: unknown, d = ""): string => (typeof v === "string" ? v : d);
  const payments = Array.isArray(summary.payments) ? (summary.payments as Record<string, unknown>[]) : [];
  return {
    saleId: row.id,
    number: row.number ?? (typeof summary.temp_number === "string" ? summary.temp_number : null),
    createdAt: row.created_at,
    counterpartyId: row.customer_id ?? null,
    payments: payments.map((p) => ({
      method: str(p.method, "cash"),
      amount: money(str(p.amount, "0")),
      cardEntryMode: typeof p.card_entry_mode === "string" ? p.card_entry_mode : null,
      rrn: null,
    })),
    lines: rawLines.map((l, i) => {
      const id = str(l.id) || str(l.sale_line_id) || `${str(l.product_id)}#${i}`;
      const unit = str(l.unit_code, "pcs");
      return {
        saleLineId: id,
        productId: str(l.product_id),
        name: str(l.name) || str(l.product_name),
        unitCode: unit,
        fractional: FRACTIONAL_UNITS.has(unit),
        qty: str(l.qty, "0"),
        returnedQty: toDecimal(localReturned[id] ?? "0").toFixed(3),
        price: str(l.price, "0"),
        lineTotal: money(str(l.line_total, "0")),
        vatRate: str(l.vat_rate, "0.00"),
        vatExemptionCode: typeof l.vat_exemption_code === "string" ? l.vat_exemption_code : null,
        markingCode: typeof l.marking_code === "string" ? l.marking_code : null,
      };
    }),
    origin: "local",
  };
}

/** Σ qty per sale line of this device's own `return.created` events for `saleId` (not yet on the server). */
export function localReturnedQty(
  events: readonly {
    type: string;
    status: string;
    retryable: boolean | null;
    payload: Record<string, unknown>;
  }[],
  saleId: string,
  onlyUnsynced: boolean,
): Record<string, string> {
  const out: Record<string, Decimal> = {};
  for (const e of events) {
    if (e.type !== "return.created" || e.payload.sale_id !== saleId) continue;
    if (e.status === "rejected" && e.retryable !== true) continue;
    if (onlyUnsynced && (e.status === "accepted" || e.status === "duplicate")) continue;
    const lines = Array.isArray(e.payload.lines) ? (e.payload.lines as Record<string, unknown>[]) : [];
    for (const l of lines) {
      const id = typeof l.sale_line_id === "string" ? l.sale_line_id : null;
      if (!id || typeof l.qty !== "string") continue;
      out[id] = (out[id] ?? new D(0)).plus(toDecimal(l.qty));
    }
  }
  return Object.fromEntries(Object.entries(out).map(([k, v]) => [k, v.toFixed(3)]));
}

/** `GET /sales?number=` (+ `fiscal_receipt_seq` for a bare number) → the sale, or null. */
export async function findServerSale(query: string): Promise<SaleOut | null> {
  const q = query.trim();
  if (!q) return null;
  let page = await api.sales.listSales({ number: q, limit: 5 });
  if (page.items.length === 0 && /^\d{1,9}$/.test(q)) {
    let seq = 0;
    for (const ch of q) seq = seq * 10 + "0123456789".indexOf(ch);
    page = await api.sales.listSales({ fiscal_receipt_seq: seq, limit: 5 });
  }
  const hit = page.items[0];
  return hit ? api.sales.getSale(hit.id) : null;
}

/** Matches a local history row by number / temp number / id (offline search). */
export function matchesQuery(
  row: { id: string; number?: string | null; summary?: Record<string, unknown> },
  query: string,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  const temp = typeof row.summary?.temp_number === "string" ? row.summary.temp_number.toLowerCase() : "";
  return (
    row.id.toLowerCase() === q ||
    (row.number ?? "").toLowerCase() === q ||
    temp === q ||
    (row.number ?? "").toLowerCase().endsWith(q)
  );
}

/** POS-05 Esc (UX-03): nothing while the terminal may move money; else close the open panel, else back. */
export function returnsEscape(input: {
  cardPending: boolean;
  approvalOpen: boolean;
  manualOpen: boolean;
}): "none" | "close_approval" | "close_manual" | "back" {
  if (input.cardPending) return "none";
  if (input.approvalOpen) return "close_approval";
  if (input.manualOpen) return "close_manual";
  return "back";
}
