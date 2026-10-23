/**
 * «Ortiqcha to'lovlar» block (07 BO-06, qaror #67): offline POS debt payments above the debt — unreviewed
 * `sync_exceptions(kind='debt_overpayment_offline')` (details: counterparty_id, amount, unallocated_amount;
 * the excess sits on `Kt 6310`). The list API has no `kind` filter, so the unreviewed rows are read and
 * filtered here. Resolution (07 BO-06 actions, `accounting.post`):
 * - «Qaytarish» — `POST /cash-movements {reason:'other', direction:'out', account:'6310', counterparty_id,
 *   amount ≤ unallocated, cash_register_id, shift_id (an OPEN shift of that register), comment, doc_date}`
 *   (Dt 6310 / Kt 5010). The server also needs `cash.withdraw`; over the user's limit it answers
 *   `202 {status:'draft', approval_request_id}` (BO-16 approval posts it). A posted refund of the whole excess
 *   marks the exception reviewed (`POST /sync-exceptions/{id}/review`) so it cannot be paid back twice;
 * - «Keyingi qarzga hisoblash» — `POST /ledger-adjustments {branch_id, doc_date: today, account_dt:'6310',
 *   account_kt:'4010', amount ≤ unallocated, comment, analytics:{counterparty_id}}` (20 #10, 13 §2.14 (b),
 *   B5-T14): the advance is set off against the customer's open debt, no cash moves. The server refuses more than
 *   the customer's 6310 balance or receivable (`validation.adjustment_exceeds_balance`, `params.available`).
 *   Offsetting the whole excess marks the exception reviewed, like a full refund.
 */
import { api, type ApiError } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import type {
  CashMovementIn,
  CashRegisterOut,
  LedgerAdjustmentIn,
  ShiftListItem,
  SyncExceptionOut,
} from "@shared/models";

import { apiFx, readAllPages } from "#/shared/lib/effect.ts";

export interface Overpayment {
  id: string;
  counterpartyId: string | null;
  amount: string | null;
  unallocated: string;
  createdAt: string;
  deviceId: string | null;
  docId: string | null;
}

const str = (v: unknown): string | null => (typeof v === "string" && v !== "" ? v : null);

export function toOverpayments(rows: readonly SyncExceptionOut[]): Overpayment[] {
  return rows
    .filter((r) => r.kind === "debt_overpayment_offline" && r.reviewed_at === null)
    .map((r) => {
      const d = (r.details ?? {}) as Record<string, unknown>;
      return {
        id: r.id,
        counterpartyId: str(d.counterparty_id),
        amount: str(d.amount),
        unallocated: str(d.unallocated_amount) ?? "0.00",
        createdAt: r.created_at,
        deviceId: r.device_id,
        docId: r.doc_id,
      };
    });
}

export const loadOverpaymentsFx = apiFx<void, Overpayment[]>(async () => {
  const { items } = await readAllPages(
    (cursor) =>
      api.branches.listSyncExceptions({ reviewed: false, limit: 200, ...(cursor ? { cursor } : {}) }),
    3,
  );
  return toOverpayments(items);
});

// --- «Qaytarish» ---------------------------------------------------------------------------------------

export interface RefundForm {
  amount: string;
  /** Reason / comment — required by the server for `reason='other'`. */
  comment: string;
  /** The chosen OPEN shift (its register comes with it). */
  shiftId: string;
}

export type RefundField = "amount" | "comment" | "shiftId";
export type RefundErrors = Partial<Record<RefundField, string>>;

export interface OpenShift {
  shift: ShiftListItem;
  register: CashRegisterOut | null;
}

export function validateRefund(form: RefundForm, unallocated: Money): RefundErrors {
  const errors: RefundErrors = {};
  if (!form.amount.trim() || !isMoney(form.amount)) {
    errors.amount = "validation.required";
  } else if (compareMoney(money(form.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.must_be_positive";
  } else if (compareMoney(money(form.amount), money(unallocated)) > 0) {
    errors.amount = "debts:overpay.refund.exceeds";
  }
  if (!form.comment.trim()) errors.comment = "validation.required";
  if (!form.shiftId) errors.shiftId = "validation.required";
  return errors;
}

export function toRefundBody(
  row: Overpayment,
  form: RefundForm,
  shift: ShiftListItem,
  today: string,
): CashMovementIn {
  return {
    reason: "other",
    direction: "out",
    account: "6310",
    counterparty_id: row.counterpartyId,
    amount: money(form.amount),
    cash_register_id: shift.cash_register_id,
    shift_id: shift.id,
    comment: form.comment.trim(),
    doc_date: today,
  };
}

/** Server `details[].field` → refund form field. */
const FIELD_MAP: Readonly<Record<string, RefundField>> = {
  amount: "amount",
  comment: "comment",
  shift_id: "shiftId",
  cash_register_id: "shiftId",
};

/** `details[]` on the form fields; `rest` — something is left for the banner (`errorText`). */
export function refundFieldErrors(error: ApiError): { fields: RefundErrors; rest: boolean } {
  const fields: RefundErrors = {};
  let rest = error.details.length === 0;
  for (const d of error.details) {
    const field = FIELD_MAP[d.field.replace(/^body\./, "")];
    if (field && !fields[field]) fields[field] = d.messageKey;
    else if (!field) rest = true;
  }
  return { fields, rest };
}

/** Open shifts with their register names (cash leaves the till of an OPEN shift — 13 §2.16). */
export const openShiftsFx = apiFx<void, OpenShift[]>(async () => {
  const [shifts, registers] = await Promise.all([
    api.cash.listShifts({ status: "open", limit: 100 }),
    api.branches.cashRegistersList(),
  ]);
  return shifts.items.map((shift) => ({
    shift,
    register: registers.items.find((r) => r.id === shift.cash_register_id) ?? null,
  }));
});

export interface RefundRequest {
  row: Overpayment;
  form: RefundForm;
  shift: ShiftListItem;
  today: string;
}

export interface RefundResult {
  /** `posted` (201) or `draft` — over the limit, waiting for approval (202, BO-16). */
  status: "posted" | "draft";
  approvalRequestId: string | null;
  /** The exception was closed (the whole excess paid back). */
  reviewed: boolean;
}

export const submitRefundFx = apiFx<RefundRequest, RefundResult>(async ({ row, form, shift, today }) => {
  const body = toRefundBody(row, form, shift, today);
  const created = await api.cash.createCashMovement(body);
  if (created.status !== "posted") {
    return { status: "draft", approvalRequestId: created.approval_request_id ?? null, reviewed: false };
  }
  let reviewed = false;
  if (compareMoney(body.amount as Money, money(row.unallocated)) === 0) {
    try {
      await api.branches.reviewSyncException(row.id, {
        review_note: `refund 6310: cash_movement ${created.id}, ${body.amount}`,
      });
      reviewed = true;
    } catch {
      // the refund is posted; the row stays until it is reviewed (BO-14)
    }
  }
  return { status: "posted", approvalRequestId: null, reviewed };
});

// --- «Keyingi qarzga hisoblash» (Dt 6310 / Kt 4010) ---------------------------------------------------

export interface OffsetForm {
  amount: string;
  comment: string;
  branchId: string;
}

export type OffsetField = keyof OffsetForm;
export type OffsetErrors = Partial<Record<OffsetField, string>>;

export function validateOffset(form: OffsetForm, unallocated: Money): OffsetErrors {
  const errors: OffsetErrors = {};
  if (!form.amount.trim() || !isMoney(form.amount)) {
    errors.amount = "validation.required";
  } else if (compareMoney(money(form.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.must_be_positive";
  } else if (compareMoney(money(form.amount), money(unallocated)) > 0) {
    errors.amount = "debts:overpay.offset.exceeds";
  }
  if (!form.comment.trim()) errors.comment = "validation.required";
  if (!form.branchId) errors.branchId = "validation.required";
  return errors;
}

export function toOffsetBody(row: Overpayment, form: OffsetForm, today: string): LedgerAdjustmentIn {
  return {
    branch_id: form.branchId,
    doc_date: today,
    account_dt: "6310",
    account_kt: "4010",
    amount: money(form.amount),
    comment: form.comment.trim(),
    analytics: { counterparty_id: row.counterpartyId ?? "" },
  };
}

/** `validation.adjustment_exceeds_balance` → the amount the server allows (`params.available`). */
export function offsetAvailable(error: ApiError): Money | null {
  if (!error.details.some((d) => d.messageKey === "validation.adjustment_exceeds_balance")) return null;
  const available = error.params.available;
  return typeof available === "string" && isMoney(available) ? money(available) : null;
}

export interface OffsetRequest {
  row: Overpayment;
  form: OffsetForm;
  today: string;
}

export interface OffsetResult {
  number: string | null;
  /** The exception was closed (the whole excess set off). */
  reviewed: boolean;
}

export const submitOffsetFx = apiFx<OffsetRequest, OffsetResult>(async ({ row, form, today }) => {
  const body = toOffsetBody(row, form, today);
  const posted = await api.accounting.createLedgerAdjustment(body);
  let reviewed = false;
  if (compareMoney(body.amount as Money, money(row.unallocated)) === 0) {
    try {
      await api.branches.reviewSyncException(row.id, {
        review_note: `offset 6310→4010: ledger_adjustment ${posted.number ?? posted.id}, ${body.amount}`,
      });
      reviewed = true;
    } catch {
      // the offset is posted; the row stays until it is reviewed (BO-14)
    }
  }
  return { number: posted.number, reviewed };
});
