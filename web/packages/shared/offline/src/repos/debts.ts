/**
 * Debt book on the device (B4, w-debts) — 16 §1 `customers` (`receivable_balance`, `credit_limit`,
 * `open_debt_docs[]`), §5 (limit / balance conflicts), 18 §11.1 `counterparty.created`, §12.2
 * `debt_payment.created`; contracts b4/customers-pull.md, b4/debt-allocation.md.
 *
 * The pulled row is the server truth; outbox events of this device that the row does not reflect yet
 * (pending, retryable-rejected, or accepted after the row was pulled) are overlaid CONSERVATIVELY:
 * - a debt sale (`sale.created` with a `debt` payment) raises the balance at once and becomes a local
 *   open document (so an offline payment can allocate to it);
 * - a debt payment lowers the balance only once the server accepted it (never below the server value
 *   before that), but its allocations / receipt lines are taken off the open documents at once, so a
 *   second offline payment does not allocate the same documents again.
 * A rejected non-retryable event never posted (16 §3.4) and is ignored.
 */
import { v7 as uuidv7 } from "uuid";

import { allocateDebtPayment, type DebtAllocationResult } from "@shared/lib/debt-allocation";
import { addMoney, compareMoney, money, subtractMoney, toDecimal, type Money } from "@shared/lib/money";

import { invalidateMemoryIndex } from "../lib/memory-index.ts";
import { searchTokens } from "../lib/search.ts";
import { enqueueEvent, type EnqueueResult } from "../outbox/enqueue.ts";
import { posDb } from "../runtime.ts";
import type { CustomerRow, OpenDebtDocLine, OpenDebtDocRow, OutboxRow } from "../types.ts";

const ZERO = "0.00" as Money;

/** What a debt screen needs about one customer (POS-02/03/06/13). Money = decimal strings. */
export interface CustomerDebtView {
  customer: CustomerRow;
  /** `receivable_balance` of the pulled row. */
  serverBalance: Money;
  /** Debt sales of this device the row does not reflect yet. */
  pendingDebt: Money;
  /** Debt payments of this device waiting for the server (not taken off the balance yet). */
  pendingPayments: Money;
  /** Debt payments the server accepted after the row was pulled (already taken off). */
  syncedPayments: Money;
  /** Current debt = server + pending debt sales − accepted payments (never lowered by a pending payment). */
  balance: Money;
  creditLimit: Money | null;
  /** `creditLimit − balance` (negative = over the limit); null = no limit. */
  available: Money | null;
  /** Open documents for the allocation (pulled − local payments + local debt sales), allocation order. */
  openDocs: OpenDebtDocRow[];
  /** Σ open_amount of `openDocs` incl. open written-off debt — the most a payment can close. */
  payable: Money;
  /** Quick customer created on this device, not on the server yet. */
  local: boolean;
}

const str = (v: unknown): string | null => (typeof v === "string" && v !== "" ? v : null);

function safeMoney(v: unknown): Money {
  const s = str(v);
  if (!s) return ZERO;
  try {
    return money(s);
  } catch {
    return ZERO;
  }
}

function maxMoney(a: Money, b: Money): Money {
  return compareMoney(a, b) >= 0 ? a : b;
}

/** The pulled row does not contain this event yet (16 §3.4: a non-retryable rejection never posted). */
export function unreflected(
  row: Pick<OutboxRow, "status" | "retryable" | "result_at">,
  pulledAt?: string,
): boolean {
  if (row.status === "pending") return true;
  if (row.status === "rejected") return row.retryable === true;
  if (!pulledAt || !row.result_at) return true;
  return row.result_at > pulledAt;
}

const accepted = (row: Pick<OutboxRow, "status">) => row.status === "accepted" || row.status === "duplicate";

function rows(v: unknown): Record<string, unknown>[] {
  return Array.isArray(v) ? v.filter((r): r is Record<string, unknown> => !!r && typeof r === "object") : [];
}

/** Debt part of a `sale.created` payload (Σ `payments[method=debt].amount`). */
export function saleDebtPart(payload: Record<string, unknown>): Money {
  return addMoney(
    ZERO,
    ...rows(payload.payments)
      .filter((p) => p.method === "debt")
      .map((p) => safeMoney(p.amount)),
  );
}

/**
 * Fiscalized share of each line of a mixed sale (first receipt, 18 §4.5 — the backend `fiscal_shares`):
 * `amt_i = ROUND_HALF_UP(line_total_i × non_debt / total, 2)`, rounding rest on the largest line (ties → later).
 */
export function fiscalShares(totals: readonly Money[], nonDebt: Money): Money[] {
  const total = addMoney(ZERO, ...totals);
  if (compareMoney(nonDebt, total) >= 0) return [...totals];
  if (compareMoney(total, ZERO) <= 0 || compareMoney(nonDebt, ZERO) <= 0) return totals.map(() => ZERO);
  const nd = toDecimal(nonDebt);
  const t = toDecimal(total);
  const out = totals.map((v) => money(toDecimal(v).times(nd).div(t).toFixed(10)));
  let diff = subtractMoney(nonDebt, addMoney(ZERO, ...out));
  if (compareMoney(diff, ZERO) !== 0) {
    let best = 0;
    totals.forEach((v, i) => {
      if (compareMoney(v, totals[best] ?? ZERO) >= 0) best = i;
    });
    out[best] = addMoney(out[best] ?? ZERO, diff);
    diff = ZERO;
  }
  return out;
}

/** A local debt sale as an open document (16 §1 shape). */
export function localSaleDoc(payload: Record<string, unknown>): OpenDebtDocRow | null {
  const id = str(payload.id);
  const debt = saleDebtPart(payload);
  if (!id || compareMoney(debt, ZERO) <= 0) return null;
  const lines = rows(payload.lines);
  const totals = lines.map((l) => safeMoney(l.line_total));
  const total = addMoney(ZERO, ...totals);
  const settled = fiscalShares(totals, maxMoney(subtractMoney(total, debt), ZERO));
  const due = rows(payload.payments).find((p) => p.method === "debt")?.due_date;
  return {
    doc_type: "sales",
    doc_id: id,
    number: str(payload.temp_number),
    doc_date: str(payload.doc_date) ?? "",
    due_date: str(due),
    open_amount: debt,
    local: true,
    lines: lines.map((l, i): OpenDebtDocLine => ({
      sale_line_id: String(l.id),
      line_no: i + 1,
      product_id: str(l.product_id),
      unit_code: str(l.unit_code) ?? "",
      qty: str(l.qty) ?? "1.000",
      price: str(l.price) ?? undefined,
      line_total: totals[i] ?? ZERO,
      vat_rate: str(l.vat_rate) ?? "0.00",
      vat_exemption_code: str(l.vat_exemption_code),
      settled_amount: settled[i] ?? ZERO,
      marking_code: str(l.marking_code),
    })),
  };
}

function applyPayment(docs: OpenDebtDocRow[], payload: Record<string, unknown>): OpenDebtDocRow[] {
  const settledByLine = new Map<string, Money>();
  for (const fl of rows(payload.fiscal_lines)) {
    const lineId = str(fl.sale_line_id);
    const saleId = str(fl.sale_id);
    if (!lineId || !saleId) continue;
    const key = `${saleId.toLowerCase()}:${lineId.toLowerCase()}`;
    settledByLine.set(key, addMoney(settledByLine.get(key) ?? ZERO, safeMoney(fl.amount)));
  }
  const byDoc = new Map<string, Money>();
  for (const a of rows(payload.allocations)) {
    const key = `${String(a.target_doc_type)}:${String(a.target_doc_id).toLowerCase()}`;
    byDoc.set(key, addMoney(byDoc.get(key) ?? ZERO, safeMoney(a.amount)));
  }
  return docs
    .map((d) => {
      const taken = byDoc.get(`${d.doc_type}:${d.doc_id.toLowerCase()}`);
      if (!taken) return d;
      return {
        ...d,
        open_amount: maxMoney(subtractMoney(safeMoney(d.open_amount), taken), ZERO),
        lines: d.lines?.map((l) => {
          const add = settledByLine.get(`${d.doc_id.toLowerCase()}:${l.sale_line_id.toLowerCase()}`);
          return add ? { ...l, settled_amount: addMoney(safeMoney(l.settled_amount), add) } : l;
        }),
      };
    })
    .filter((d) => compareMoney(safeMoney(d.open_amount), ZERO) > 0);
}

/** Pure overlay of the device's own events on a pulled customer row (seq order). */
export function customerDebtView(customer: CustomerRow, events: readonly OutboxRow[]): CustomerDebtView {
  const serverBalance = safeMoney(customer.receivable_balance ?? "0.00");
  let pendingDebt = ZERO;
  let pendingPayments = ZERO;
  let syncedPayments = ZERO;
  let docs: OpenDebtDocRow[] = [...(customer.open_debt_docs ?? [])];
  const mine = [...events]
    .filter((e) => str(e.payload.counterparty_id) === customer.id && unreflected(e, customer._pulled_at))
    .sort((a, b) => a.seq - b.seq);
  for (const e of mine) {
    if (e.type === "sale.created") {
      const doc = localSaleDoc(e.payload);
      if (!doc) continue;
      pendingDebt = addMoney(pendingDebt, safeMoney(doc.open_amount));
      docs.push(doc);
    } else if (e.type === "debt_payment.created") {
      const amount = safeMoney(e.payload.amount);
      if (accepted(e)) syncedPayments = addMoney(syncedPayments, amount);
      else pendingPayments = addMoney(pendingPayments, amount);
      docs = applyPayment(docs, e.payload);
    }
  }
  const balance = subtractMoney(addMoney(serverBalance, pendingDebt), syncedPayments);
  const limit = str(customer.credit_limit);
  const creditLimit = limit ? safeMoney(limit) : null;
  return {
    customer,
    serverBalance,
    pendingDebt,
    pendingPayments,
    syncedPayments,
    balance,
    creditLimit,
    available: creditLimit === null ? null : subtractMoney(creditLimit, balance),
    openDocs: docs,
    payable: addMoney(ZERO, ...docs.map((d) => safeMoney(d.open_amount))),
    local: customer._local === true,
  };
}

/** A debt of `amount` more would exceed the credit limit (16 §5: last known balance + local sales). */
export function overCreditLimit(
  view: Pick<CustomerDebtView, "balance" | "creditLimit">,
  amount: Money,
): boolean {
  if (view.creditLimit === null) return false;
  return compareMoney(addMoney(view.balance, amount), view.creditLimit) > 0;
}

async function relevantEvents(): Promise<OutboxRow[]> {
  const all = await posDb().outbox.toArray();
  return all.filter((e) => e.type === "sale.created" || e.type === "debt_payment.created");
}

export const customerDebts = {
  /** Debt view of one customer (undefined = not on this device). */
  async view(customerId: string): Promise<CustomerDebtView | undefined> {
    const customer = await posDb().customers.get(customerId);
    if (!customer) return undefined;
    return customerDebtView(customer, await relevantEvents());
  },
  /** Views of every customer that owes something or has local activity (POS-13 debtor list). */
  async debtors(): Promise<CustomerDebtView[]> {
    const [all, events] = await Promise.all([posDb().customers.toArray(), relevantEvents()]);
    const active = new Set(events.map((e) => str(e.payload.counterparty_id)).filter((x): x is string => !!x));
    return all
      .filter(
        (c) =>
          compareMoney(safeMoney(c.receivable_balance ?? "0.00"), ZERO) > 0 ||
          (c.open_debt_docs?.length ?? 0) > 0 ||
          active.has(c.id),
      )
      .map((c) => customerDebtView(c, events))
      .filter((v) => compareMoney(v.balance, ZERO) > 0 || compareMoney(v.payable, ZERO) > 0)
      .sort((a, b) => compareMoney(b.balance, a.balance) || a.customer.name.localeCompare(b.customer.name));
  },
};

// --- quick customer (18 §11.1) -------------------------------------------------------------------------

export interface QuickCustomerInput {
  name: string;
  /** E.164 (`+998901234567`). */
  phone: string;
  notifyConsent?: boolean;
}

/** `counterparty.created` payload (18 §11.1, backend `CounterpartyCreatedPayload`). */
export function quickCustomerPayload(id: string, input: QuickCustomerInput): Record<string, unknown> {
  return {
    id,
    kind: "person",
    name: input.name.trim().slice(0, 255),
    phone: input.phone,
    notify_consent: input.notifyConsent === true,
  };
}

/**
 * «+ Yangi mijoz» (US-M08-05, offline too): `counterparty.created` into the outbox and the row into the local
 * `customers` table at once, so the sale / payment that follows can use the id (same push, seq order).
 */
export async function createQuickCustomer(
  input: QuickCustomerInput,
  opts: { actorUserId: string },
): Promise<CustomerRow> {
  const id = uuidv7();
  const payload = quickCustomerPayload(id, input);
  await enqueueEvent("counterparty.created", payload, { actorUserId: opts.actorUserId });
  const digits = input.phone.replace(/\D+/g, "");
  const row: CustomerRow = {
    id,
    kind: "person",
    name: String(payload.name),
    phone: input.phone,
    receivable_balance: "0.00",
    credit_limit: null,
    open_debt_docs: [],
    _local: true,
    tokens: searchTokens(String(payload.name), digits, digits.length > 9 ? digits.slice(-9) : null),
  };
  // a pull may have brought the server row meanwhile — never overwrite it
  const db = posDb();
  await db.transaction("rw", db.customers, async () => {
    if (!(await db.customers.get(id))) await db.customers.put(row);
  });
  invalidateMemoryIndex("customers");
  return row;
}

// --- debt payment (18 §12.2) -----------------------------------------------------------------------------

export type DebtPaymentMethod = "cash" | "card" | "uzqr";

export interface DebtPaymentInput {
  id?: string;
  counterpartyId: string;
  branchId: string;
  cashRegisterId: string;
  shiftId: string;
  amount: Money;
  method: DebtPaymentMethod;
  isOffline: boolean;
  offlineSince: string | null;
  promiseDate: string | null;
  comment: string | null;
  /** method=card: the outcome of the card flow (integrated → `card_result`; manual → reason + approval). */
  card?:
    | { mode: "integrated"; cardResult: Record<string, unknown> }
    | { mode: "manual"; manualReason: string; approval: Record<string, unknown> | null };
  /** method=uzqr (static only — the cashier confirms, online). */
  terminalRef?: string | null;
  allocation: DebtAllocationResult;
}

/** `debt_payment.created` payload (18 §12.2; backend `DebtPaymentCreatedPayload`, `extra="forbid"`). */
export function debtPaymentPayload(input: DebtPaymentInput): Record<string, unknown> {
  const out: Record<string, unknown> = {
    id: input.id ?? uuidv7(),
    counterparty_id: input.counterpartyId,
    branch_id: input.branchId,
    cash_register_id: input.cashRegisterId,
    shift_id: input.shiftId,
    receipt_seq: null, // enqueueEvent writes it (opts.receiptSeq)
    is_offline: input.isOffline,
    offline_since: input.isOffline ? input.offlineSince : null,
    amount: input.amount,
    method: input.method,
    promise_date: input.promiseDate,
    comment: input.comment?.trim() ? input.comment.trim().slice(0, 1000) : null,
    allocations: input.allocation.allocations,
    fiscal_lines: input.allocation.fiscal_lines,
    fiscal_result: null, // server-side fiscalisation (qaror #68), as the sale
  };
  if (input.method === "card" && input.card) {
    if (input.card.mode === "integrated") {
      out.card_entry_mode = "integrated";
      out.card_result = input.card.cardResult;
    } else {
      out.card_entry_mode = "manual";
      out.manual_reason = input.card.manualReason;
      out.card_manual_approval = input.card.approval;
    }
  }
  if (input.method === "uzqr") {
    out.qr_type = "static";
    out.terminal_ref = input.terminalRef?.trim() ? input.terminalRef.trim().slice(0, 40) : null;
  }
  return out;
}

/** Allocation of a POS debt payment over the device's open documents (fiscal receipt lines included). */
export function allocateOnDevice(
  amount: Money,
  view: Pick<CustomerDebtView, "openDocs">,
): DebtAllocationResult {
  return allocateDebtPayment(amount, view.openDocs, { fiscal: true });
}

/**
 * Writes `debt_payment.created` with the next `receipt_seq` of (cash register, shift) — one payment, one
 * `debt_settlement` receipt (18 §12.2). Approved integrated card attempts leave in the same transaction.
 */
export async function enqueueDebtPayment(
  input: DebtPaymentInput,
  opts: { actorUserId: string; clientEventId?: string; removeCardAttemptIds?: string[] },
): Promise<EnqueueResult & { payload: Record<string, unknown> }> {
  const payload = debtPaymentPayload(input);
  const result = await enqueueEvent("debt_payment.created", payload, {
    actorUserId: opts.actorUserId,
    ...(opts.clientEventId ? { clientEventId: opts.clientEventId } : {}),
    receiptSeq: { cashRegisterId: input.cashRegisterId, shiftId: input.shiftId },
    ...(opts.removeCardAttemptIds?.length ? { removeCardAttemptIds: opts.removeCardAttemptIds } : {}),
  });
  return { ...result, payload: { ...payload, receipt_seq: result.receiptSeq } };
}
