/**
 * POS-13 — Qarz daftari (tezkor) model (07 POS-13; 18 §12.1, §12.2; 16 §1, §5; qaror #30, #45, #67).
 * Pure rules + effects, the screen keeps its form state (like the other POS operation screens):
 * - `planPayment` — the device allocation over the local open documents (`@shared/lib/debt-allocation`, the
 *   same function as the server posting), which sales the payment closes fully / partly, the debt after it;
 *   online a payment above what is owed is refused (`debt_payment_exceeds_balance`, qaror #45 — change in cash),
 *   offline it is accepted with a warning (the excess → `unallocated_amount`, Kt 6310, qaror #67);
 * - `acceptDebtPayment` — `debt_payment.created` with the next `receipt_seq` (one payment = one
 *   `debt_settlement` receipt, fiscalised server-side like the sale, qaror #68);
 * - `debtReceiptDoc` — the receipt printed through the POS printer (two languages, goods lines of the closed
 *   sales, the general «Qarz to'lovi (boshlang'ich qoldiq)» line).
 */
import { createEffect } from "effector";

import { api } from "@shared/api";
import type { DebtAllocationResult, DebtFiscalLine } from "@shared/lib/debt-allocation";
import { addMoney, compareMoney, isMoney, money, subtractMoney, type Money } from "@shared/lib/money";
import type { ReceiptDoc, ReceiptLine, ReceiptPayment } from "@shared/lib/receipt";
import {
  allocateOnDevice,
  cardAttempts,
  catalog,
  enqueueDebtPayment,
  isOfflineError,
  type CustomerDebtView,
  type DebtPaymentMethod,
  type OpenDebtDocRow,
} from "@shared/offline";
import type { DebtLedgerOut } from "@shared/models";

const ZERO = "0.00" as Money;

export type PayMethodKey = DebtPaymentMethod;
export const DEBT_PAY_METHODS: readonly PayMethodKey[] = ["cash", "card", "uzqr"];

export interface AllocationRow {
  docType: OpenDebtDocRow["doc_type"];
  docId: string;
  number: string | null;
  docDate: string;
  /** Part of this payment that goes to the document. */
  amount: Money;
  /** What stays open on the document after the payment. */
  left: Money;
  closes: boolean;
  local: boolean;
}

export type PlanError = "amount_required" | "debt_payment_exceeds_balance" | "nothing_owed";

export interface PaymentPlan {
  amount: Money | null;
  error: PlanError | null;
  /** Offline only: received above what is owed (→ `unallocated_amount`, Kt 6310). */
  overpay: Money;
  /** Debt after this payment (and the earlier unsynced ones). */
  after: Money;
  allocation: DebtAllocationResult | null;
  rows: AllocationRow[];
}

function docKey(type: string, id: string): string {
  return `${type}:${id.toLowerCase()}`;
}

export function allocationRows(view: CustomerDebtView, allocation: DebtAllocationResult): AllocationRow[] {
  const docs = new Map(view.openDocs.map((d) => [docKey(d.doc_type, d.doc_id), d]));
  return allocation.allocations.map((a) => {
    const doc = docs.get(docKey(a.target_doc_type, a.target_doc_id));
    const open = doc ? money(doc.open_amount) : a.amount;
    const left = subtractMoney(open, a.amount);
    return {
      docType: a.target_doc_type,
      docId: a.target_doc_id,
      number: doc?.number ?? null,
      docDate: doc?.doc_date ?? "",
      amount: a.amount,
      left: compareMoney(left, ZERO) > 0 ? left : ZERO,
      closes: compareMoney(left, ZERO) <= 0,
      local: doc?.local === true,
    };
  });
}

export function planPayment(view: CustomerDebtView | null, amountText: string, online: boolean): PaymentPlan {
  const balanceLeft = (paidToReceivable: Money): Money => {
    if (!view) return ZERO;
    const after = subtractMoney(subtractMoney(view.balance, view.pendingPayments), paidToReceivable);
    return compareMoney(after, ZERO) > 0 ? after : ZERO;
  };
  const empty: PaymentPlan = {
    amount: null,
    error: "amount_required",
    overpay: ZERO,
    after: balanceLeft(ZERO),
    allocation: null,
    rows: [],
  };
  if (!view) return empty;
  if (!amountText || !isMoney(amountText)) return empty;
  const amount = money(amountText);
  if (compareMoney(amount, ZERO) <= 0) return empty;
  if (compareMoney(view.payable, ZERO) <= 0 && online) return { ...empty, amount, error: "nothing_owed" };
  if (online && compareMoney(amount, view.payable) > 0) {
    return { ...empty, amount, error: "debt_payment_exceeds_balance" };
  }
  const allocation = allocateOnDevice(amount, view);
  const toReceivable = addMoney(
    ZERO,
    ...allocation.allocations.filter((a) => a.target_doc_type !== "debt_writeoffs").map((a) => a.amount),
  );
  return {
    amount,
    error: null,
    overpay: allocation.unallocated_amount,
    after: balanceLeft(toReceivable),
    allocation,
    rows: allocationRows(view, allocation),
  };
}

// --- receipt ----------------------------------------------------------------------------------------------

export interface LineInfo {
  name: string;
  nameRu: string | null;
  unitCode: string;
  mxik: string | null;
  barcode: string | null;
  price: string | null;
  vatExemptionCode: string | null;
}

export const GENERAL_LINE_NAME = "Qarz to'lovi (boshlang'ich qoldiq)";
export const GENERAL_LINE_NAME_RU = "Погашение долга (начальный остаток)";

/** Goods details of the open sale lines (pulled rows carry them; a local sale's lines come from the catalog). */
export const loadLineInfoFx = createEffect(
  async (view: CustomerDebtView): Promise<Record<string, LineInfo>> => {
    const out: Record<string, LineInfo> = {};
    for (const doc of view.openDocs) {
      for (const l of doc.lines ?? []) {
        let name = l.name ?? null;
        let nameRu = l.name_ru ?? null;
        let mxik = l.mxik_code ?? null;
        let barcode = l.barcode ?? null;
        if (!name && l.product_id) {
          const p = await catalog.get(l.product_id).catch(() => null);
          name = p?.product.name ?? null;
          nameRu = p?.product.name_ru ?? null;
          mxik = typeof p?.product.mxik_code === "string" ? p.product.mxik_code : null;
          const codes = await catalog.barcodesOf(l.product_id).catch(() => []);
          barcode = codes[0]?.barcode ?? null;
        }
        out[l.sale_line_id.toLowerCase()] = {
          name: name ?? "—",
          nameRu,
          unitCode: l.unit_code ?? "",
          mxik,
          barcode,
          price: l.price ?? null,
          vatExemptionCode: l.vat_exemption_code ?? null,
        };
      }
    }
    return out;
  },
);

const integerQty = (qty: string) => /\.0*$/.test(qty) || !qty.includes(".");

export function receiptLines(
  lines: readonly DebtFiscalLine[],
  info: Readonly<Record<string, LineInfo>>,
): ReceiptLine[] {
  return lines.map((l) => {
    const i = l.sale_line_id ? info[l.sale_line_id.toLowerCase()] : undefined;
    const general = l.sale_line_id === null;
    const exempt = !general && !!i?.vatExemptionCode && l.vat_rate === "0.00";
    return {
      name: general ? GENERAL_LINE_NAME : (i?.name ?? "—"),
      nameRu: general ? GENERAL_LINE_NAME_RU : (i?.nameRu ?? null),
      qty: l.qty,
      qtyKind: integerQty(l.qty) ? "integer" : "fractional",
      unitPrice: general ? l.amount : (i?.price ?? l.amount),
      unitLabel: general ? "" : (i?.unitCode ?? ""),
      total: l.amount,
      mxik: general ? null : (i?.mxik ?? null),
      barcode: general ? null : (i?.barcode ?? null),
      vatRate: exempt ? null : l.vat_rate.replace(/\.00$/, ""),
      vat: l.vat_amount,
      vatExemptCode: exempt ? (i?.vatExemptionCode ?? null) : null,
      markingCodes: l.marking_code ? [l.marking_code] : [],
    };
  });
}

export interface FinishedDebtPayment {
  paymentId: string;
  clientEventId: string;
  receiptSeq: number | null;
  createdAt: string;
  customerName: string;
  amount: Money;
  method: PayMethodKey;
  cardManual: boolean;
  received: Money | null;
  change: Money | null;
  fiscalLines: DebtFiscalLine[];
  overpay: Money;
  isOffline: boolean;
}

export function debtReceiptDoc(
  done: FinishedDebtPayment,
  info: Readonly<Record<string, LineInfo>>,
  store: { name: string; stir: string | null; branchName: string | null; registerName: string | null },
  cashierName: string,
  shiftNo: number | null,
  copy = false,
): ReceiptDoc {
  const vat = new Map<string, Money>();
  for (const l of done.fiscalLines) vat.set(l.vat_rate, addMoney(vat.get(l.vat_rate) ?? ZERO, l.vat_amount));
  const payment: ReceiptPayment = {
    method: done.method,
    amount: done.amount,
    card: done.method === "card" ? { entryMode: done.cardManual ? "manual" : "integrated" } : null,
  };
  return {
    kind: "debt_settlement",
    copy,
    store: { name: store.name, stir: store.stir, branchName: store.branchName },
    number: `${done.paymentId.slice(-6).toUpperCase()}`,
    issuedAt: done.createdAt,
    cashierName,
    shiftNo,
    registerNo: store.registerName,
    receiptSeq: done.receiptSeq,
    lines: receiptLines(done.fiscalLines, info),
    totals: {
      total: done.amount,
      discount: ZERO,
      vat: [...vat.entries()]
        .filter(([, a]) => compareMoney(a, ZERO) > 0)
        .map(([rate, amount]) => ({ rate, amount })),
    },
    payments: {
      form: done.method === "cash" ? "cash" : done.method === "card" ? "card" : "qr",
      items: [payment],
      received: done.received,
      change: done.change,
    },
    fiscal: null,
  };
}

// --- accept -----------------------------------------------------------------------------------------------

export class DebtPaymentError extends Error {
  constructor(
    readonly code: string,
    readonly params: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

export interface AcceptInput {
  view: CustomerDebtView;
  plan: PaymentPlan;
  method: PayMethodKey;
  device: { branchId: string; cashRegisterId: string | null } | null;
  shiftId: string | null;
  cashier: { userId: string; permissions: readonly string[] } | null;
  online: boolean;
  offlineSince: string | null;
  fiscalBlocked: boolean;
  promiseDate: string | null;
  comment: string | null;
  /** cash: money received (≥ amount) — the change is given in cash. */
  cashReceived: Money | null;
  /** card: the outcome of the card flow. */
  card?:
    | { mode: "integrated"; attemptId: string; cardResult: Record<string, unknown> }
    | {
        mode: "manual";
        manualReason: string;
        approval: Record<string, unknown> | null;
        attemptId: string | null;
      }
    | null;
  /** card: the client_event_id the card attempt was started with (16 §2.1). */
  clientEventId?: string;
  terminalRef?: string | null;
}

/** Every check the device makes before the payment is written (the server repeats them). */
export function validateAccept(input: AcceptInput): void {
  if (!input.device?.cashRegisterId) throw new DebtPaymentError("DEVICE_NOT_REGISTERED");
  if (!input.shiftId) throw new DebtPaymentError("SHIFT_NOT_OPEN");
  if (!input.cashier) throw new DebtPaymentError("PIN_REQUIRED");
  if (!input.cashier.permissions.includes("debts.payment.accept"))
    throw new DebtPaymentError("PERMISSION_DENIED");
  if (input.fiscalBlocked) throw new DebtPaymentError("FISCAL_OFFLINE_48H_BLOCKED");
  if (input.plan.error === "debt_payment_exceeds_balance") {
    throw new DebtPaymentError("VALIDATION_ERROR", {
      balance: input.view.payable,
      requested: input.plan.amount,
    });
  }
  if (input.plan.error || !input.plan.amount || !input.plan.allocation)
    throw new DebtPaymentError("VALIDATION_ERROR");
  if (input.method === "uzqr" && !input.online) throw new DebtPaymentError("PAYMENT_ONLINE_ONLY");
  if (input.method === "card" && !input.card) throw new DebtPaymentError("PAYMENT_NOT_COMPLETE");
  if (input.method === "cash") {
    if (!input.cashReceived || compareMoney(input.cashReceived, input.plan.amount) < 0) {
      throw new DebtPaymentError("CASH_NOT_ENOUGH");
    }
  }
}

export const acceptDebtPaymentFx = createEffect(async (input: AcceptInput): Promise<FinishedDebtPayment> => {
  validateAccept(input);
  const plan = input.plan;
  const amount = plan.amount as Money;
  const allocation = plan.allocation as DebtAllocationResult;
  const removeIds: string[] = [];
  if (input.card?.mode === "integrated") {
    const stored = await cardAttempts.get(input.card.attemptId);
    if (stored?.status === "approved") removeIds.push(input.card.attemptId);
  }
  let result;
  try {
    result = await enqueueDebtPayment(
      {
        counterpartyId: input.view.customer.id,
        branchId: input.device?.branchId ?? "",
        cashRegisterId: input.device?.cashRegisterId ?? "",
        shiftId: input.shiftId ?? "",
        amount,
        method: input.method,
        isOffline: !input.online,
        offlineSince: input.online ? null : (input.offlineSince ?? new Date().toISOString()),
        promiseDate: compareMoney(plan.after, ZERO) > 0 ? input.promiseDate : null,
        comment: input.comment,
        card: input.card
          ? input.card.mode === "integrated"
            ? { mode: "integrated", cardResult: input.card.cardResult }
            : { mode: "manual", manualReason: input.card.manualReason, approval: input.card.approval }
          : undefined,
        terminalRef: input.terminalRef ?? null,
        allocation,
      },
      {
        actorUserId: input.cashier?.userId ?? "",
        ...(input.clientEventId ? { clientEventId: input.clientEventId } : {}),
        ...(removeIds.length ? { removeCardAttemptIds: removeIds } : {}),
      },
    );
  } catch (error) {
    if (isOfflineError(error)) throw new DebtPaymentError(error.code, { ...error.params });
    throw error;
  }
  const received = input.method === "cash" ? input.cashReceived : null;
  return {
    paymentId: String(result.payload.id),
    clientEventId: result.clientEventId,
    receiptSeq: result.receiptSeq,
    createdAt: result.createdAt,
    customerName: input.view.customer.name,
    amount,
    method: input.method,
    cardManual: input.card?.mode === "manual",
    received,
    change: received ? subtractMoney(received, amount) : null,
    fiscalLines: allocation.fiscal_lines,
    overpay: allocation.unallocated_amount,
    isOffline: !input.online,
  };
});

/** Online: the last rows of the paper book (18 §12.1) — offline the screen shows the local open documents. */
export const loadRecentLedgerFx = createEffect((counterpartyId: string): Promise<DebtLedgerOut> =>
  api.debts.getCounterpartyDebtLedger(counterpartyId, { direction: "receivable", limit: 30 }),
);
