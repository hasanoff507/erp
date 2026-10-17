/**
 * POS-03 payment (07 POS-03; 18 §4.1, §16a; 16 §2.1, §6): cash with change, card (integrated through
 * features/card-payment, or manual — amount only), static UzQR (online only, the cashier confirms), debt part
 * (customer + promise date, over-limit approval online), mixed. The order is strict: card approval →
 * (server-side) fiscal receipt → `sale.created` — an approved integrated card finishes the sale by itself.
 * The `sale.created` client_event_id is allocated when the payment opens, so the card attempt is recorded
 * with the same id the sale event gets (18 §16a.4 manager-resolved unknown attempts).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { newAttemptId as newId } from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";
import {
  $fiscalLadder,
  cardAttempts,
  customers,
  enqueueEvent,
  isOfflineError,
  type CustomerRow,
} from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import {
  $draft,
  $totals,
  changeOf,
  cmpMoney,
  draftReset,
  isPositive,
  minusMoney,
  sumMoney,
  type ApprovalRef,
  type Draft,
  type DraftTotals,
} from "#/entities/receipt-draft/index.ts";
import {
  $posCashier,
  $posDevice,
  $posShift,
  type PosCashier,
  type PosDevice,
  type PosShift,
} from "#/entities/pos-session/index.ts";
import {
  $cardPaymentOutcome,
  cardOutcomeConsumed,
  cardPaymentClosed,
  cardPaymentStarted,
  type CardPaymentOutcome,
} from "#/features/card-payment/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";
import { nextTempNumber } from "#/shared/lib/device-runtime.ts";

import { $fiscalDeviceLocked, $offlineSince, $posSettings } from "./context.ts";
import {
  buildSalePayload,
  debtAmount,
  issuesFiscalReceipt,
  nonDebtAmount,
  paymentForm,
  type PaymentPart,
} from "./lib/sale-payload.ts";
import type { ScanError } from "./scan.ts";

export type PayMode = "cash" | "card" | "uzqr" | "debt" | "mixed";
export type DeliveryReason = "printer_failure" | "customer_request";

export interface PaymentState {
  saleId: string;
  clientEventId: string;
  mode: PayMode | null;
  /** Confirmed non-card parts (cash / uzqr / debt); the card part comes from `$cardPaymentOutcome`. */
  parts: PaymentPart[];
  cashReceived: string;
  dueDate: string | null;
  debtApproval: ApprovalRef | null;
  uzqrRef: string;
  /** Electronic receipt instead of the printed one (07 POS-04: printer failure / customer request). */
  electronic: DeliveryReason | null;
}

/** What POS-04 shows and prints for the sale just finished. */
export interface FinishedSale {
  saleId: string;
  clientEventId: string;
  receiptSeq: number | null;
  createdAt: string;
  tempNumber: string;
  fiscal: boolean;
  totals: DraftTotals;
  parts: PaymentPart[];
  form: "cash" | "card" | "qr" | "mixed";
  received: Money | null;
  change: Money | null;
  delivery: "printed" | "electronic";
  deliveryReason: DeliveryReason | null;
  cashierName: string;
  shiftNo: number | null;
  customerName: string | null;
  isOffline: boolean;
}

export const paymentOpened = createEvent();
export const paymentClosed = createEvent();
export const modeChosen = createEvent<PayMode>();
export const cashReceivedChanged = createEvent<string>();
export const mixedPartAdded = createEvent<PaymentPart>();
export const mixedPartRemoved = createEvent<number>();
export const dueDateChanged = createEvent<string | null>();
export const debtApproved = createEvent<ApprovalRef | null>();
export const uzqrRefChanged = createEvent<string>();
export const electronicChosen = createEvent<DeliveryReason | null>();
/** "To'lov qabul qilindi" (static UzQR) / "TASDIQLASH". */
export const confirmPressed = createEvent();
/** Card part start (whole remaining amount in card mode, the typed amount in mixed mode). */
export const cardStartRequested = createEvent<Money>();
export const paymentErrorShown = createEvent<ScanError>();
export const paymentErrorDismissed = createEvent();

const fresh = (): PaymentState => ({
  saleId: newId(),
  clientEventId: newId(),
  mode: null,
  parts: [],
  cashReceived: "",
  dueDate: null,
  debtApproval: null,
  uzqrRef: "",
  electronic: null,
});

export const $payment = createStore<PaymentState | null>(null);
export const $paymentError = createStore<ScanError | null>(null);
export const $lastSale = createStore<FinishedSale | null>(null);

/** The card part as a payment row (18 §4.1) — only once the card flow produced an outcome. */
export const $cardPart = $cardPaymentOutcome.map((o): PaymentPart | null => cardPartOf(o));

export function cardPartOf(o: CardPaymentOutcome | null): PaymentPart | null {
  if (!o) return null;
  if (o.mode === "integrated") {
    return {
      method: "card",
      amount: o.amount,
      card: {
        mode: "integrated",
        attemptId: o.attemptId,
        cardResult: o.cardResult as unknown as Record<string, unknown>,
      },
    };
  }
  return {
    method: "card",
    amount: o.amount,
    card: { mode: "manual", manualReason: o.manualReason, approval: o.approval, attemptId: o.attemptId },
  };
}

/** Parts of the receipt as they would be sent now. */
export function partsFor(p: PaymentState, total: Money, card: PaymentPart | null): PaymentPart[] {
  switch (p.mode) {
    case "cash":
      return [{ method: "cash", amount: total }];
    case "card":
      return card ? [card] : [];
    case "uzqr":
      return [{ method: "uzqr", amount: total, terminalRef: p.uzqrRef || null }];
    case "debt":
      return [{ method: "debt", amount: total, dueDate: p.dueDate, debtApproval: p.debtApproval }];
    case "mixed": {
      const own = p.parts.map((x) =>
        x.method === "debt" ? { ...x, dueDate: p.dueDate, debtApproval: p.debtApproval } : x,
      );
      return card ? [...own, card] : own;
    }
    default:
      return [];
  }
}

export const $paid = combine($payment, $totals, $cardPart, (p, t, card) =>
  p ? sumMoney(partsFor(p, t.total, card).map((x) => x.amount)) : ("0.00" as Money),
);
export const $remaining = combine($totals, $paid, (t, paid) => {
  const rest = minusMoney(t.total, paid);
  return cmpMoney(rest, "0.00") < 0 ? ("0.00" as Money) : rest;
});
export const $change = combine($payment, $totals, (p, t) =>
  p?.mode === "cash" && p.cashReceived ? changeOf(p.cashReceived, t.total) : null,
);

$payment
  .on(paymentOpened, (p) => p ?? fresh())
  .on(modeChosen, (p, mode) =>
    p ? { ...p, mode, parts: mode === "mixed" ? p.parts : [], debtApproval: null } : p,
  )
  .on(cashReceivedChanged, (p, cashReceived) => (p ? { ...p, cashReceived } : p))
  .on(mixedPartAdded, (p, part) => (p ? { ...p, parts: [...p.parts, part] } : p))
  .on(mixedPartRemoved, (p, i) => (p ? { ...p, parts: p.parts.filter((_, at) => at !== i) } : p))
  .on(dueDateChanged, (p, dueDate) => (p ? { ...p, dueDate } : p))
  .on(debtApproved, (p, debtApproval) => (p ? { ...p, debtApproval } : p))
  .on(uzqrRefChanged, (p, uzqrRef) => (p ? { ...p, uzqrRef: uzqrRef.slice(0, 40) } : p))
  .on(electronicChosen, (p, electronic) => (p ? { ...p, electronic } : p))
  .reset(paymentClosed);

$paymentError
  .on(paymentErrorShown, (_, e) => e)
  .reset(paymentErrorDismissed, paymentClosed, modeChosen, paymentOpened);

// Leaving the payment without a card result: the card flow goes back to idle (only allowed phases).
sample({ clock: paymentClosed, target: cardPaymentClosed });

sample({
  clock: cardStartRequested,
  source: { p: $payment, device: $posDevice, shift: $posShift },
  filter: ({ p, device }) => p !== null && device?.cashRegisterId != null,
  fn: ({ p, device, shift }, amount) => ({
    amount,
    clientEventId: p?.clientEventId ?? newId(),
    cashRegisterId: device?.cashRegisterId ?? "",
    shiftId: shift?.id ?? null,
  }),
  target: cardPaymentStarted,
});

// --- completion -------------------------------------------------------------------------------------

export interface CompleteInput {
  payment: PaymentState;
  draft: Draft;
  totals: DraftTotals;
  card: PaymentPart | null;
  device: PosDevice | null;
  shift: PosShift | null;
  cashier: PosCashier | null;
  online: boolean;
  offlineSince: string | null;
  fiscalBlocked: boolean;
  fiscalLocked: boolean;
  /** `tenant_settings.fiscal_policy.credit_sale_receipt === "credit_type"` (18 §4.1 `credit_receipt_seq`). */
  creditType?: boolean;
}

export class SaleError extends Error {
  constructor(
    readonly code: string,
    readonly params: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

/** Every check the device makes before the receipt is written (the server repeats them). */
export function validateParts(input: CompleteInput): PaymentPart[] {
  const { payment: p, totals } = input;
  if (!input.device?.cashRegisterId) throw new SaleError("DEVICE_NOT_REGISTERED");
  if (!input.shift) throw new SaleError("SHIFT_NOT_OPEN");
  if (!input.cashier) throw new SaleError("PIN_REQUIRED");
  if (input.draft.lines.length === 0 || !isPositive(totals.total)) throw new SaleError("RECEIPT_EMPTY");
  const parts = partsFor(p, totals.total, input.card);
  if (parts.length === 0) throw new SaleError("PAYMENT_METHOD_REQUIRED");
  if (cmpMoney(sumMoney(parts.map((x) => x.amount)), totals.total) !== 0) {
    throw new SaleError("PAYMENT_NOT_COMPLETE");
  }
  if (p.mode === "cash") {
    if (!p.cashReceived || changeOf(p.cashReceived, totals.total) === null) {
      throw new SaleError("CASH_NOT_ENOUGH");
    }
  }
  const anyReceipt = receiptSeqOption(parts, input.creditType === true, "", "") !== null;
  if (anyReceipt && input.fiscalBlocked) throw new SaleError("FISCAL_OFFLINE_48H_BLOCKED");
  if (anyReceipt && input.fiscalLocked) throw new SaleError("FISCAL_DEVICE_LOCKED");
  if (parts.some((x) => x.method === "uzqr") && !input.online) {
    throw new SaleError("PAYMENT_ONLINE_ONLY");
  }
  if (parts.some((x) => x.method === "debt")) {
    if (!input.draft.customerId) throw new SaleError("CUSTOMER_REQUIRED");
    if (!input.cashier.permissions.includes("debts.create")) throw new SaleError("PERMISSION_DENIED");
  }
  for (const line of input.draft.lines) {
    if (line.kind === "marked" && !line.markingCode) throw new SaleError("MARKING_CODE_REQUIRED");
  }
  return parts;
}

/**
 * Device receipt numbers of the sale (18 §4.1, §4.5; SYNC-09): a non-debt part → the `sale` receipt
 * (`receipt_seq`); under `credit_type` a debt part also gets the «kredit» receipt (`credit_receipt_seq`) —
 * two consecutive numbers, or one into `credit_receipt_seq` for a debt-only sale. null = no receipt at all.
 */
export function receiptSeqOption(
  parts: readonly PaymentPart[],
  creditType: boolean,
  cashRegisterId: string,
  shiftId: string,
): { cashRegisterId: string; shiftId: string; count?: 2; target?: "credit_receipt_seq" } | null {
  const sale = issuesFiscalReceipt(parts);
  const credit = creditType && isPositive(debtAmount(parts));
  if (sale && credit) return { cashRegisterId, shiftId, count: 2 };
  if (sale) return { cashRegisterId, shiftId };
  if (credit) return { cashRegisterId, shiftId, target: "credit_receipt_seq" };
  return null;
}

export function creditTypeOf(raw: Record<string, unknown> | null | undefined): boolean {
  const tenant = raw?.tenant_settings as
    { fiscal_policy?: { credit_sale_receipt?: unknown } } | null | undefined;
  return tenant?.fiscal_policy?.credit_sale_receipt === "credit_type";
}

/** Credit-limit check of a debt part (18 §4.3): true → an approval is needed (online only). */
export function debtOverLimit(customer: CustomerRow | undefined, debt: Money): boolean {
  if (!customer || customer.credit_limit === null || customer.credit_limit === undefined) return false;
  const balance = customer.receivable_balance ?? "0.00";
  return cmpMoney(sumMoney([balance, debt]), customer.credit_limit) > 0;
}

export const completeSaleFx = createEffect(async (input: CompleteInput): Promise<FinishedSale> => {
  const parts = validateParts(input);
  const { payment: p, draft, totals } = input;
  const device = input.device as PosDevice;
  const shift = input.shift as PosShift;
  const cashier = input.cashier as PosCashier;
  const cashRegisterId = device.cashRegisterId as string;
  const fiscalReceipt = issuesFiscalReceipt(parts);
  const seqOption = receiptSeqOption(parts, input.creditType === true, cashRegisterId, shift.id);

  const debt = debtAmount(parts);
  const customer = draft.customerId ? await customers.get(draft.customerId) : undefined;
  if (isPositive(debt) && input.online && debtOverLimit(customer, debt) && !p.debtApproval) {
    throw new SaleError("DEBT_LIMIT_EXCEEDED", {
      limit: customer?.credit_limit ?? null,
      requested: sumMoney([customer?.receivable_balance ?? "0.00", debt]),
    });
  }

  const tempNumber = await nextTempNumber(device.deviceId);
  const delivery = p.electronic ? "electronic" : "printed";
  const payload = buildSalePayload(
    totals,
    parts,
    draft.discount?.approval ?? null,
    draft.discount?.pct ?? null,
    {
      saleId: p.saleId,
      branchId: device.branchId,
      cashRegisterId,
      shiftId: shift.id,
      tempNumber,
      docDate: tashkentDate(),
      counterpartyId: draft.customerId,
      isOffline: !input.online,
      offlineSince: input.online ? null : (input.offlineSince ?? new Date().toISOString()),
      delivery,
      deliveryReason: p.electronic,
    },
  );

  // approved integrated attempts leave card_attempts in the same transaction (16 §2.1)
  const removeIds: string[] = [];
  for (const part of parts) {
    if (part.card?.mode === "integrated") {
      const stored = await cardAttempts.get(part.card.attemptId);
      if (stored?.status === "approved") removeIds.push(part.card.attemptId);
    }
  }
  const codes = draft.lines.flatMap((l) => (l.markingCode ? [l.markingCode] : []));
  const cash = parts.find((x) => x.method === "cash");
  const received = p.mode === "cash" && p.cashReceived ? (p.cashReceived as Money) : null;
  const change = p.mode === "cash" ? changeOf(p.cashReceived, totals.total) : null;

  let result;
  try {
    result = await enqueueEvent("sale.created", payload, {
      actorUserId: cashier.userId,
      clientEventId: p.clientEventId,
      ...(seqOption ? { receiptSeq: seqOption } : {}),
      ...(removeIds.length ? { removeCardAttemptIds: removeIds } : {}),
      ...(codes.length ? { markingCodes: codes } : {}),
      history: {
        id: p.saleId,
        kind: "sale",
        total: totals.total,
        number: null,
        customer_id: draft.customerId,
        // POS-05 offline returns read the lines from here (contracts/pos-session.md §3)
        summary: {
          temp_number: tempNumber,
          form: fiscalReceipt ? paymentForm(parts) : "debt",
          lines: totals.lines.map((l) => ({
            id: l.id,
            product_id: l.productId,
            name: l.name,
            unit_code: l.unitCode,
            qty: l.qty,
            price: l.price,
            line_total: l.total,
            vat_rate: l.vatRate,
            vat_exemption_code: l.vatExemptionCode,
            marking_code: l.markingCode,
          })),
          payments: parts.map((x) => ({
            method: x.method,
            amount: x.amount,
            card_entry_mode: x.card?.mode ?? null,
          })),
        },
      },
    });
  } catch (error) {
    if (isOfflineError(error)) throw new SaleError(error.code, { ...error.params });
    throw error;
  }

  return {
    saleId: p.saleId,
    clientEventId: result.clientEventId,
    receiptSeq: result.receiptSeq,
    createdAt: result.createdAt,
    tempNumber,
    fiscal: fiscalReceipt,
    totals,
    parts,
    form: paymentForm(parts),
    received: cash ? received : null,
    change,
    delivery,
    deliveryReason: p.electronic,
    cashierName: cashier.fullName,
    shiftNo: shift.shift_no ?? null,
    customerName: customer?.name ?? null,
    isOffline: !input.online,
  };
});

const $completeSource = combine({
  payment: $payment,
  draft: $draft,
  totals: $totals,
  card: $cardPart,
  device: $posDevice,
  shift: $posShift,
  cashier: $posCashier,
  online: $isOnline,
  offlineSince: $offlineSince,
  fiscalBlocked: $fiscalLadder.map((l) => l.level === "blocked48"),
  fiscalLocked: $fiscalDeviceLocked,
  creditType: $posSettings.map((st) => creditTypeOf(st?.raw)),
});

/** A finish request — TASDIQLASH, or an approved integrated card that covers the rest. */
const finishRequested = createEvent();
sample({ clock: confirmPressed, target: finishRequested });
sample({
  clock: $cardPaymentOutcome,
  source: { p: $payment, totals: $totals },
  filter: ({ p, totals }, outcome) => {
    if (!p || outcome?.mode !== "integrated") return false;
    const others = p.mode === "mixed" ? sumMoney(p.parts.map((x) => x.amount)) : ("0.00" as Money);
    return cmpMoney(sumMoney([others, outcome.amount]), totals.total) === 0;
  },
  target: finishRequested,
});

sample({
  clock: finishRequested,
  source: $completeSource,
  filter: (s, _) => s.payment !== null && !completeSaleFx.pending.getState(),
  fn: (s) => s as CompleteInput,
  target: completeSaleFx,
});

$paymentError.on(completeSaleFx.failData, (_, e) =>
  e instanceof SaleError ? { code: e.code, params: e.params } : { code: "INTERNAL_ERROR" },
);
$lastSale.on(completeSaleFx.doneData, (_, sale) => sale);

/** Sale written → the card outcome is consumed, a fresh draft starts, the payment closes. */
export const saleCompleted = completeSaleFx.doneData;
sample({ clock: saleCompleted, target: [cardOutcomeConsumed, draftReset] });
sample({ clock: saleCompleted, fn: () => null, target: $payment });

export { nonDebtAmount };
