/**
 * BO-08 «Tuzatuvchi yozuv» (07 BO-08; 20 #10 / #10a / #10b; 13 §2.23, §5.1; US-M11-02): a manual one-line
 * correcting entry `Dt account_dt / Kt account_kt = amount` in the **open** period (a `0000` opening line —
 * only on `go_live_date − 1`), `correction_of_period` — the closed month it corrects, comment required;
 * 4010 / 6010 / 6310 need `analytics.counterparty_id`. Cancel = storno (reason). Register-managed stock
 * accounts 2910 / 2920 / 2970 are refused (only stock documents move them). sample() only (24 §2).
 */
import { combine, createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import type {
  CounterpartyOut,
  LedgerAdjustmentIn,
  LedgerAdjustmentOut,
  LedgerAdjustmentPage,
} from "@shared/models";

import { apiFx, type LoadStatus } from "#/shared/lib/effect.ts";

export type LedgerAdjustment = LedgerAdjustmentOut;
export type Counterparty = Pick<CounterpartyOut, "id" | "name">;

/** 13 §2.23: stock-value accounts move only with stock documents (`validation.account_register_managed`). */
export const REGISTER_MANAGED = ["2910", "2920", "2970"] as const;
/** Accounts whose line needs `analytics.counterparty_id` (debt registers / customer advances). */
export const COUNTERPARTY_ACCOUNTS = ["4010", "6010", "6310"] as const;
export const ADJUSTMENTS_PAGE_SIZE = 20;
export const COMMENT_MAX = 1000;

export interface AdjustmentForm {
  branchId: string;
  docDate: string;
  accountDt: string;
  accountKt: string;
  amount: string;
  /** `YYYY-MM` of the closed month this entry corrects, or "" (none). */
  correctionOfPeriod: string;
  counterpartyId: string;
  comment: string;
}

export type AdjustmentField = keyof AdjustmentForm;
export type AdjustmentErrors = Partial<Record<AdjustmentField, string>>;

export function emptyForm(today: string, branchId: string | null): AdjustmentForm {
  return {
    branchId: branchId ?? "",
    docDate: today,
    accountDt: "",
    accountKt: "",
    amount: "",
    correctionOfPeriod: "",
    counterpartyId: "",
    comment: "",
  };
}

const ACCOUNT = /^\d{4}$/;
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function needsCounterparty(form: Pick<AdjustmentForm, "accountDt" | "accountKt">): boolean {
  return (COUNTERPARTY_ACCOUNTS as readonly string[]).some((a) => a === form.accountDt || a === form.accountKt);
}

export function isRegisterManaged(account: string): boolean {
  return (REGISTER_MANAGED as readonly string[]).includes(account);
}

/** Client checks before `POST /ledger-adjustments` (the server repeats them and checks the chart / period). */
export function validateAdjustment(form: AdjustmentForm, today: string): AdjustmentErrors {
  const errors: AdjustmentErrors = {};
  if (!form.branchId) errors.branchId = "validation.required";
  if (!DATE.test(form.docDate)) errors.docDate = "validation.required";
  else if (form.docDate > today) errors.docDate = "validation.doc_date_in_future";
  for (const field of ["accountDt", "accountKt"] as const) {
    const v = form[field];
    if (!v) errors[field] = "validation.required";
    else if (!ACCOUNT.test(v)) errors[field] = "validation.account_not_allowed";
    else if (isRegisterManaged(v)) errors[field] = "validation.account_register_managed";
  }
  if (!errors.accountKt && form.accountDt && form.accountDt === form.accountKt) {
    errors.accountKt = "validation.same_account";
  }
  const amount = form.amount.trim();
  if (amount === "" || !isMoney(amount)) errors.amount = "validation.required";
  else if (compareMoney(money(amount), "0.00" as Money) <= 0) errors.amount = "validation.positive";
  if (form.correctionOfPeriod && !MONTH.test(form.correctionOfPeriod)) {
    errors.correctionOfPeriod = "validation.period_format";
  }
  if (needsCounterparty(form) && !form.counterpartyId) errors.counterpartyId = "validation.required";
  if (form.comment.trim() === "") errors.comment = "validation.required";
  return errors;
}

export function toAdjustmentBody(form: AdjustmentForm): LedgerAdjustmentIn {
  return {
    branch_id: form.branchId,
    doc_date: form.docDate,
    account_dt: form.accountDt,
    account_kt: form.accountKt,
    amount: money(form.amount.trim()),
    comment: form.comment.trim(),
    ...(form.correctionOfPeriod ? { correction_of_period: form.correctionOfPeriod } : {}),
    ...(needsCounterparty(form) && form.counterpartyId
      ? { analytics: { counterparty_id: form.counterpartyId } }
      : {}),
  };
}

/** Server `details[].field` (`body.account_dt`, `analytics.counterparty_id` …) → form field. */
const FIELD_MAP: Readonly<Record<string, AdjustmentField>> = {
  branch_id: "branchId",
  doc_date: "docDate",
  account_dt: "accountDt",
  account_kt: "accountKt",
  amount: "amount",
  correction_of_period: "correctionOfPeriod",
  counterparty_id: "counterpartyId",
  "analytics.counterparty_id": "counterpartyId",
  analytics: "counterpartyId",
  comment: "comment",
};

export interface FieldErrorsResult {
  fields: AdjustmentErrors;
  /** Something is left for the banner (`PERIOD_CLOSED`, a detail without a field …). */
  rest: boolean;
}

export function adjustmentFieldErrors(error: ApiError): FieldErrorsResult {
  const fields: AdjustmentErrors = {};
  let rest = error.details.length === 0;
  for (const d of error.details) {
    const field = FIELD_MAP[d.field.replace(/^body\./, "")];
    if (field && !fields[field]) fields[field] = d.messageKey;
    else if (!field) rest = true;
  }
  return { fields, rest };
}

/** `validation.adjustment_exceeds_balance` → `params.available` of the refusal (BO-06 offset limit). */
export function availableOf(error: ApiError): string | null {
  const refused = error.details.some((d) => d.messageKey === "validation.adjustment_exceeds_balance");
  const available = error.params.available;
  return refused && typeof available === "string" && isMoney(available) ? available : null;
}

// --- units ---------------------------------------------------------------------------------------------
export const adjustmentsMounted = createEvent();
export const adjustmentsReloadRequested = createEvent();
export const adjustmentsMoreRequested = createEvent();

export const listAdjustmentsFx = apiFx<string | null, LedgerAdjustmentPage>((cursor) =>
  api.accounting.listLedgerAdjustments({ limit: ADJUSTMENTS_PAGE_SIZE, ...(cursor ? { cursor } : {}) }),
);
export const createAdjustmentFx = apiFx<LedgerAdjustmentIn, LedgerAdjustment>((body) =>
  api.accounting.createLedgerAdjustment(body),
);
export const cancelAdjustmentFx = apiFx<{ id: string; reason: string }, unknown>(({ id, reason }) =>
  api.accounting.cancelLedgerAdjustment(id, { reason }),
);
/** Counterparties for the 4010 / 6010 / 6310 analytics (name / phone / STIR search). */
export const searchCounterpartiesFx = apiFx<string, Counterparty[]>(async (search) => {
  const page = await api.debts.listCounterparties({
    archived: false,
    size: 20,
    ...(search.trim() ? { search: search.trim() } : {}),
  });
  return page.items.map((c) => ({ id: c.id, name: c.name }));
});

export const $adjustments = createStore<LedgerAdjustment[]>([]);
export const $adjustmentsCursor = createStore<string | null>(null, { skipVoid: false });
export const $adjustmentsStatus = createStore<LoadStatus>("idle");
export const $adjustmentsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $adjustmentsMoreLoading = combine(
  listAdjustmentsFx.pending,
  $adjustmentsStatus,
  (pending, status) => pending && status !== "loading",
);

sample({
  clock: [adjustmentsMounted, adjustmentsReloadRequested],
  fn: () => null,
  target: listAdjustmentsFx,
});
sample({
  clock: adjustmentsMoreRequested,
  source: { cursor: $adjustmentsCursor, pending: listAdjustmentsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ cursor }) => cursor,
  target: listAdjustmentsFx,
});
$adjustments.on(listAdjustmentsFx.done, (list, { params, result }) =>
  params ? [...list, ...result.items] : result.items,
);
$adjustmentsCursor.on(listAdjustmentsFx.doneData, (_, page) => page.next_cursor);
$adjustmentsStatus
  .on(listAdjustmentsFx, (status, cursor) => (cursor === null ? "loading" : status))
  .on(listAdjustmentsFx.done, () => "idle")
  .on(listAdjustmentsFx.fail, (status, { params }) => (params === null ? "error" : status));
$adjustmentsError.on(listAdjustmentsFx.failData, (_, e) => e).reset(listAdjustmentsFx);

// A posted or cancelled entry changes the list (and the journal — the page reloads it).
sample({
  clock: [createAdjustmentFx.done, cancelAdjustmentFx.done],
  fn: () => undefined,
  target: adjustmentsReloadRequested,
});
