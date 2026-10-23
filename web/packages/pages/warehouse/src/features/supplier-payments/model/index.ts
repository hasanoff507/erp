/**
 * Yetkazib beruvchiga to'lov (07 BO-04 «Yetkazib beruvchiga to'lov»; 19 §11; 13 §2.16, §2.8; qaror #47;
 * US-M07-04, US-M08-11; QT-M07-05): list (filters status / method) with «Bekor qilish» (storno; a cash
 * payment only while its shift is open), and the payment form — supplier → open documents (oldest first,
 * payable balance, deferred VAT), method bank / cash from the till (an open shift), amount, date, the
 * allocation (auto oldest-first preview — the server allocates when `allocations` is omitted — or a manual
 * split whose Σ must equal the debt part), the overpay warning (→ advance 4310) or the `block` policy error.
 */
import { combine, createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import { addMoney, compareMoney, money, subtractMoney, type Money } from "@shared/lib/money";
import type {
  AllocationIn,
  CashRegisterOut,
  ListSupplierPaymentsParams,
  OpenDocOut,
  OpenDocsOut,
  PaymentCreated,
  PaymentIn,
  PaymentOut,
  PaymentPage,
  ShiftListItem,
} from "@shared/models";

import { apiFx, PAGE_LIMIT } from "#/shared/lib/effect.ts";

export type Payment = PaymentOut;
export type OpenDoc = OpenDocOut;
export type OpenDocs = OpenDocsOut;
export type PaymentMethod = PaymentIn["method"];
export type PaymentStatus = PaymentOut["status"];
/** List filter statuses (19 §11: payments are created posted; `draft` never appears in the list). */
export type PaymentFilterStatus = Exclude<ListSupplierPaymentsParams["status"], null | undefined>;
export type LoadStatus = "idle" | "loading" | "error";

export const PAYMENT_METHODS: readonly PaymentMethod[] = ["bank", "cash"];
export const PAYMENT_STATUSES: readonly PaymentFilterStatus[] = ["posted", "cancelled"];
export const COMMENT_MAX = 1000;

const ZERO = "0.00" as Money;

// --- lib -------------------------------------------------------------------------------------------

export function isPaymentMethod(v: string | null): v is PaymentMethod {
  return v !== null && (PAYMENT_METHODS as readonly string[]).includes(v);
}
export function isPaymentStatus(v: string | null): v is PaymentFilterStatus {
  return v !== null && (PAYMENT_STATUSES as readonly string[]).includes(v);
}

/** A typed MoneyInput value as Money (empty / invalid → null). */
export function toMoney(value: string): Money | null {
  if (value.trim() === "") return null;
  try {
    return money(value);
  } catch {
    return null;
  }
}

const maxZero = (v: Money): Money => (compareMoney(v, ZERO) > 0 ? v : ZERO);
const min = (a: Money, b: Money): Money => (compareMoney(a, b) <= 0 ? a : b);

/** Σ outstanding of the open documents. */
export function openTotal(items: readonly OpenDoc[]): Money {
  return addMoney(ZERO, ...items.map((d) => money(d.outstanding)));
}

/** 13 §2.16 debt part = min(amount, max(payable, 0), Σ open); the rest is an advance (Dt 4310). */
export function debtPart(amount: Money, docs: Pick<OpenDocs, "payable_balance" | "items">): Money {
  return min(min(amount, maxZero(money(docs.payable_balance))), openTotal(docs.items));
}

export function advanceOf(amount: Money, docs: Pick<OpenDocs, "payable_balance" | "items">): Money {
  return subtractMoney(amount, debtPart(amount, docs));
}

/** The server's default allocation preview: the debt part over the documents, oldest first (served order). */
export function autoAllocation(amount: Money, docs: OpenDocs): Record<string, Money> {
  let left = debtPart(amount, docs);
  const out: Record<string, Money> = {};
  for (const d of docs.items) {
    if (compareMoney(left, ZERO) <= 0) break;
    const part = min(left, money(d.outstanding));
    out[d.target_doc_id] = part;
    left = subtractMoney(left, part);
  }
  return out;
}

export type AllocationProblem = "exceeds" | "sum";

/** Manual split checks (19 §11): each line ≤ the document's outstanding; Σ = the debt part. */
export function checkManual(
  split: Readonly<Record<string, string>>,
  amount: Money,
  docs: OpenDocs,
): { lines: Record<string, AllocationProblem>; sum: Money; sumOk: boolean } {
  const lines: Record<string, AllocationProblem> = {};
  let sum = ZERO;
  for (const d of docs.items) {
    const v = toMoney(split[d.target_doc_id] ?? "");
    if (!v || compareMoney(v, ZERO) === 0) continue;
    if (compareMoney(v, ZERO) < 0 || compareMoney(v, money(d.outstanding)) > 0)
      lines[d.target_doc_id] = "exceeds";
    sum = addMoney(sum, v);
  }
  return { lines, sum, sumOk: compareMoney(sum, debtPart(amount, docs)) === 0 };
}

export interface PaymentForm {
  supplierId: string;
  method: PaymentMethod;
  /** `cash`: the chosen open shift (its register comes with it). */
  shiftId: string;
  amount: string;
  docDate: string;
  manual: boolean;
  split: Record<string, string>;
  comment: string;
}

export type PaymentFormField = "supplierId" | "shiftId" | "amount" | "docDate" | "allocations" | "comment";

export function validatePayment(
  form: PaymentForm,
  docs: OpenDocs | null,
  today: string,
): Partial<Record<PaymentFormField, string>> {
  const e: Partial<Record<PaymentFormField, string>> = {};
  if (form.supplierId === "") e.supplierId = "validation.required";
  if (form.method === "cash" && form.shiftId === "") e.shiftId = "validation.required";
  const amount = toMoney(form.amount);
  if (form.amount.trim() === "") e.amount = "validation.required";
  else if (!amount || compareMoney(amount, ZERO) <= 0) e.amount = "validation.must_be_positive";
  if (form.docDate === "") e.docDate = "validation.required";
  else if (form.docDate > today) e.docDate = "validation.doc_date_in_future";
  if (form.comment.length > COMMENT_MAX) e.comment = "validation.max_length";
  if (form.manual && docs && amount) {
    const check = checkManual(form.split, amount, docs);
    if (Object.keys(check.lines).length > 0) e.allocations = "validation.allocation_exceeds_outstanding";
    else if (!check.sumOk) e.allocations = "validation.allocation_sum_mismatch";
  }
  return e;
}

export function toPaymentBody(
  form: PaymentForm,
  docs: OpenDocs | null,
  shift: ShiftListItem | null,
): PaymentIn {
  const amount = toMoney(form.amount) ?? ZERO;
  const allocations: AllocationIn[] | null =
    form.manual && docs
      ? docs.items
          .map((d) => ({ d, v: toMoney(form.split[d.target_doc_id] ?? "") }))
          .filter((x): x is { d: OpenDoc; v: Money } => x.v !== null && compareMoney(x.v, ZERO) > 0)
          .map(({ d, v }) => ({
            target_doc_type: d.target_doc_type,
            target_doc_id: d.target_doc_id,
            amount: v,
          }))
      : null;
  return {
    supplier_id: form.supplierId,
    amount,
    method: form.method,
    doc_date: form.docDate,
    ...(form.method === "cash" && shift
      ? { cash_register_id: shift.cash_register_id, shift_id: shift.id }
      : {}),
    ...(allocations ? { allocations } : {}),
    comment: form.comment.trim() || null,
  };
}

// --- units -----------------------------------------------------------------------------------------

export interface PaymentFilters {
  status: PaymentFilterStatus | null;
  method: PaymentMethod | null;
}

export const paymentsOpened = createEvent();
export const paymentFiltersChanged = createEvent<Partial<PaymentFilters>>();
export const paymentsMoreRequested = createEvent();
export const paymentsReloadRequested = createEvent();
export const paymentSelected = createEvent<string | null>();
/** The form's supplier changed → its open documents. */
export const supplierChosen = createEvent<string | null>();
export const paymentFormOpened = createEvent<{ supplierId: string | null }>();
export const paymentFormClosed = createEvent();

export function toListParams(f: PaymentFilters, cursor: string | null): ListSupplierPaymentsParams {
  return {
    ...(f.status ? { status: f.status } : {}),
    ...(f.method ? { method: f.method } : {}),
    ...(cursor ? { cursor } : {}),
    limit: PAGE_LIMIT,
  };
}

export const listPaymentsFx = apiFx<{ filters: PaymentFilters; cursor: string | null }, PaymentPage>(
  ({ filters, cursor }) => api.purchasing.listSupplierPayments(toListParams(filters, cursor)),
);
export const getPaymentFx = apiFx<string, Payment>((id) => api.purchasing.getSupplierPayment(id));
export const openDocsFx = apiFx<string, OpenDocs>((supplierId) =>
  api.purchasing.listSupplierOpenDocuments({ supplier_id: supplierId }),
);
/** Open shifts with their register names (cash from the till — 13 §2.16, an OPEN shift of that register). */
export const openShiftsFx = apiFx<void, { shift: ShiftListItem; register: CashRegisterOut | null }[]>(
  async () => {
    const [shifts, registers] = await Promise.all([
      api.cash.listShifts({ status: "open", limit: 100 }),
      api.branches.cashRegistersList(),
    ]);
    return shifts.items.map((shift) => ({
      shift,
      register: registers.items.find((r) => r.id === shift.cash_register_id) ?? null,
    }));
  },
);
export const createPaymentFx = apiFx<PaymentIn, PaymentCreated>((body) =>
  api.purchasing.createSupplierPayment(body),
);
export const cancelPaymentFx = apiFx<{ id: string; reason: string }, Payment>(({ id, reason }) =>
  api.purchasing.cancelSupplierPayment(id, { reason }),
);

export const $paymentFilters = createStore<PaymentFilters>({ status: null, method: null });
export const $payments = createStore<Payment[]>([]);
export const $paymentsCursor = createStore<string | null>(null, { skipVoid: false });
export const $paymentsStatus = createStore<LoadStatus>("idle");
export const $paymentsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $selectedPaymentId = createStore<string | null>(null, { skipVoid: false });
export const $paymentDetail = createStore<Payment | null>(null, { skipVoid: false });

export const $paymentFormOpen = createStore(false);
/** Supplier preset of the form («Men qarzdorman → To'lash» / a receipt). */
export const $paymentFormSupplier = createStore<string | null>(null, { skipVoid: false });
export const $openDocs = createStore<OpenDocs | null>(null, { skipVoid: false });
export const $openDocsStatus = createStore<LoadStatus>("idle");
export const $openShifts = createStore<{ shift: ShiftListItem; register: CashRegisterOut | null }[]>([]);
/** The last created payment's warnings (`SUPPLIER_OVERPAY_ADVANCE`) shown above the list. */
export const $lastCreated = createStore<PaymentCreated | null>(null, { skipVoid: false });

export const $paymentsMoreLoading = combine(
  listPaymentsFx.pending,
  $paymentsStatus,
  (p, s) => p && s !== "loading",
);

$paymentFilters.on(paymentFiltersChanged, (f, patch) => ({ ...f, ...patch }));
sample({
  clock: [
    paymentsOpened,
    paymentFiltersChanged,
    paymentsReloadRequested,
    createPaymentFx.done,
    cancelPaymentFx.done,
  ],
  source: $paymentFilters,
  fn: (filters) => ({ filters, cursor: null }),
  target: listPaymentsFx,
});
sample({
  clock: paymentsMoreRequested,
  source: { filters: $paymentFilters, cursor: $paymentsCursor, pending: listPaymentsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }) => ({ filters, cursor }),
  target: listPaymentsFx,
});
const listed = sample({
  clock: listPaymentsFx.done,
  source: $paymentFilters,
  filter: (f, { params }) => f.status === params.filters.status && f.method === params.filters.method,
  fn: (_, payload) => payload,
});
$payments.on(listed, (list, { params, result }) =>
  params.cursor === null ? result.items : [...list, ...result.items],
);
$paymentsCursor.on(listed, (_, { result }) => result.next_cursor);
$paymentsStatus
  .on(listPaymentsFx, (s, p) => (p.cursor === null ? "loading" : s))
  .on(listed, () => "idle")
  .on(listPaymentsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$paymentsError.on(listPaymentsFx.failData, (_, e) => e).reset(listPaymentsFx);

$selectedPaymentId.on(paymentSelected, (_, id) => id);
$paymentDetail.on(paymentSelected, () => null);
sample({ clock: paymentSelected, filter: (id): id is string => id !== null, target: getPaymentFx });
$paymentDetail.on(getPaymentFx.doneData, (_, p) => p).on(cancelPaymentFx.doneData, (_, p) => p);

// --- form ------------------------------------------------------------------------------------------
$paymentFormOpen.on(paymentFormOpened, () => true).on(paymentFormClosed, () => false);
$paymentFormSupplier.on(paymentFormOpened, (_, { supplierId }) => supplierId);
$openDocs.reset(paymentFormOpened, supplierChosen);
sample({ clock: paymentFormOpened, fn: () => undefined, target: openShiftsFx });
sample({
  clock: [supplierChosen, paymentFormOpened.map(({ supplierId }) => supplierId)],
  filter: (id): id is string => id !== null,
  target: openDocsFx,
});
$openDocs.on(openDocsFx.doneData, (_, d) => d);
$openDocsStatus
  .on(openDocsFx, () => "loading")
  .on(openDocsFx.done, () => "idle")
  .on(openDocsFx.fail, () => "error");
$openShifts.on(openShiftsFx.doneData, (_, list) => list);
$lastCreated.on(createPaymentFx.doneData, (_, p) => p).reset(paymentsOpened, paymentFormOpened);
sample({ clock: createPaymentFx.done, fn: () => undefined, target: paymentFormClosed });
