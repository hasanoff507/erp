/**
 * Yetkazib beruvchilar (19 §9, 18 §11 — one `counterparties` resource, `is_supplier=true`): list
 * (qidiruv, arxiv), card with «Joriy qarzimiz» (`GET /counterparties/{id}/debt-balance`, payable 6010),
 * create / edit (`version`), archive / unarchive (`purchases.create`), STIR lookup — a suggestion only,
 * saved after the user applies it (`POST /counterparties/lookup-by-stir`).
 */
import { combine, createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  CounterpartyCreate,
  CounterpartyListItem,
  CounterpartyOut,
  CounterpartyPage,
  CounterpartyUpdate,
  DebtBalanceOut,
  StirLookupOut,
} from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

export type Supplier = CounterpartyOut;
export type SupplierRow = CounterpartyListItem;
export type StirSuggestion = StirLookupOut;
export type LoadStatus = "idle" | "loading" | "error";

export const SUPPLIER_PAGE_SIZE = 20;

export interface SupplierFilters {
  search: string;
  archived: boolean;
}

export interface SupplierFormValues {
  kind: "company" | "person";
  name: string;
  stir: string;
  phone: string;
  legalAddress: string;
  bankAccount: string;
  bankMfo: string;
  vatPayer: boolean;
  note: string;
}

// --- lib -------------------------------------------------------------------------------------------

export const EMPTY_FORM: SupplierFormValues = {
  kind: "company",
  name: "",
  stir: "",
  phone: "",
  legalAddress: "",
  bankAccount: "",
  bankMfo: "",
  vatPayer: false,
  note: "",
};

/** STIR — 9 digits (19 §9). */
export function isStir(value: string): boolean {
  return /^\d{9}$/.test(value);
}

const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

export function toCreateBody(v: SupplierFormValues): CounterpartyCreate {
  return {
    kind: v.kind,
    name: v.name.trim(),
    stir: orNull(v.stir),
    phone: orNull(v.phone),
    legal_address: orNull(v.legalAddress),
    bank_account: orNull(v.bankAccount),
    bank_mfo: orNull(v.bankMfo),
    vat_payer: v.vatPayer,
    is_supplier: true,
    is_customer: false,
    note: orNull(v.note),
  };
}

export function toUpdateBody(v: SupplierFormValues, version: number): CounterpartyUpdate {
  const { is_supplier: _s, is_customer: _c, ...rest } = toCreateBody(v);
  return { ...rest, version };
}

export function formOf(s: Supplier): SupplierFormValues {
  return {
    kind: s.kind,
    name: s.name,
    stir: s.stir ?? "",
    phone: s.phone ?? "",
    legalAddress: s.legal_address ?? "",
    bankAccount: s.bank_account ?? "",
    bankMfo: s.bank_mfo ?? "",
    vatPayer: s.vat_payer ?? false,
    note: s.note ?? "",
  };
}

/** Applies a lookup suggestion (19 §9: shown, then saved by the user). */
export function applySuggestion(v: SupplierFormValues, s: StirSuggestion): SupplierFormValues {
  return {
    ...v,
    kind: "company",
    stir: s.stir,
    name: s.name,
    legalAddress: s.legal_address ?? v.legalAddress,
    bankAccount: s.bank_account ?? v.bankAccount,
    bankMfo: s.bank_mfo ?? v.bankMfo,
    vatPayer: s.vat_payer ?? v.vatPayer,
  };
}

export function formErrors(v: SupplierFormValues): Partial<Record<keyof SupplierFormValues, string>> {
  const out: Partial<Record<keyof SupplierFormValues, string>> = {};
  if (v.name.trim() === "") out.name = "validation.required";
  if (v.kind === "company" && v.stir === "") out.stir = "validation.required";
  else if (v.stir !== "" && !isStir(v.stir)) out.stir = "validation.stir_format";
  return out;
}

// --- events / effects ------------------------------------------------------------------------------

export const suppliersOpened = createEvent();
export const searchChanged = createEvent<string>();
export const archivedToggled = createEvent<boolean>();
export const pageChanged = createEvent<number>();
export const reloadRequested = createEvent();
export const supplierSelected = createEvent<string | null>();

export const listSuppliersFx = apiFx<{ filters: SupplierFilters; page: number }, CounterpartyPage>(
  ({ filters, page }) =>
    api.debts.listCounterparties({
      is_supplier: true,
      archived: filters.archived,
      ...(filters.search.trim() ? { search: filters.search.trim() } : {}),
      page,
      size: SUPPLIER_PAGE_SIZE,
    }),
);
export const getSupplierFx = apiFx<string, Supplier>((id) => api.debts.getCounterparty(id));
/** «Joriy qarzimiz» (payable) — `stock.view`. */
export const getDebtFx = apiFx<string, DebtBalanceOut>((id) => api.debts.getCounterpartyDebtBalance(id));
export const createSupplierFx = apiFx<SupplierFormValues, Supplier>((v) =>
  api.debts.createCounterparty(toCreateBody(v)),
);
export const updateSupplierFx = apiFx<{ id: string; values: SupplierFormValues; version: number }, Supplier>(
  ({ id, values, version }) => api.debts.updateCounterparty(id, toUpdateBody(values, version)),
);
export const archiveSupplierFx = apiFx<{ id: string; archive: boolean }, Supplier>(({ id, archive }) =>
  archive ? api.debts.archiveCounterparty(id, {}) : api.debts.unarchiveCounterparty(id, {}),
);
export const lookupStirFx = apiFx<string, StirSuggestion>((stir) =>
  api.debts.lookupCounterpartyByStir({ stir }),
);

// --- stores ----------------------------------------------------------------------------------------

export const $filters = createStore<SupplierFilters>({ search: "", archived: false });
export const $page = createStore(1);
export const $rows = createStore<SupplierRow[]>([]);
export const $total = createStore(0);
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });

export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<Supplier | null>(null, { skipVoid: false });
export const $debt = createStore<DebtBalanceOut | null>(null, { skipVoid: false });
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });

export const $acting = combine(
  createSupplierFx.pending,
  updateSupplierFx.pending,
  archiveSupplierFx.pending,
  (a, b, c) => a || b || c,
);

// --- wiring ----------------------------------------------------------------------------------------

$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(archivedToggled, (f, archived) => ({ ...f, archived }));
$page.on(pageChanged, (_, p) => p).reset(searchChanged, archivedToggled);

sample({
  clock: [
    suppliersOpened,
    searchChanged,
    archivedToggled,
    pageChanged,
    reloadRequested,
    createSupplierFx.done,
    archiveSupplierFx.done,
    updateSupplierFx.done,
  ],
  source: { filters: $filters, page: $page },
  target: listSuppliersFx,
});
const loaded = sample({
  clock: listSuppliersFx.done,
  source: { filters: $filters, page: $page },
  filter: (cur, { params }) =>
    cur.page === params.page &&
    cur.filters.search === params.filters.search &&
    cur.filters.archived === params.filters.archived,
  fn: (_, { result }) => result,
});
$rows.on(loaded, (_, r) => r.items);
$total.on(loaded, (_, r) => r.total);
$status
  .on(listSuppliersFx, () => "loading")
  .on(loaded, () => "idle")
  .on(listSuppliersFx.fail, () => "error");
$error.on(listSuppliersFx.failData, (_, e) => e).reset(listSuppliersFx);

$selectedId.on(supplierSelected, (_, id) => id).on(createSupplierFx.doneData, (_, s) => s.id);
const opened = sample({
  clock: [supplierSelected, createSupplierFx.doneData.map((s) => s.id)],
  filter: (id): id is string => id !== null,
});
sample({ clock: opened, target: getSupplierFx });
sample({ clock: opened, target: getDebtFx });
$detail
  .on(getSupplierFx.doneData, (_, s) => s)
  .on([updateSupplierFx.doneData, archiveSupplierFx.doneData, createSupplierFx.doneData], (_, s) => s)
  .reset(supplierSelected);
$debt.on(getDebtFx.doneData, (_, d) => d).reset(supplierSelected);
$detailError.on(getSupplierFx.failData, (_, e) => e).reset(getSupplierFx, supplierSelected);
