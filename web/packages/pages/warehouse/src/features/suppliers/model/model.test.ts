import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $debt,
  $detail,
  $page,
  $rows,
  EMPTY_FORM,
  applySuggestion,
  createSupplierFx,
  formErrors,
  getDebtFx,
  getSupplierFx,
  listSuppliersFx,
  pageChanged,
  searchChanged,
  suppliersOpened,
  toCreateBody,
  toUpdateBody,
  type Supplier,
  type SupplierFilters,
  type SupplierRow,
} from "./index.ts";

function supplier(id: string, patch: Partial<Supplier> = {}): Supplier {
  return {
    id,
    kind: "company",
    name: "«Barakali Don» MChJ",
    phone: null,
    stir: "305112847",
    legal_address: null,
    bank_account: null,
    bank_mfo: null,
    vat_payer: true,
    is_customer: false,
    is_supplier: true,
    credit_limit: null,
    standing_discount_pct: null,
    notify_consent: false,
    notify_consent_at: null,
    note: null,
    archived_at: null,
    created_at: "2026-10-01T05:00:00Z",
    updated_at: "2026-10-01T05:00:00Z",
    version: 1,
    ...patch,
  };
}

const row = (id: string): SupplierRow => ({
  ...supplier(id),
  receivable_balance: "0.00",
  payable_balance: "2400000.00",
});

describe("Yetkazib beruvchilar model (19 §9)", () => {
  it("lists suppliers only; a search resets to page 1; a new supplier opens with its debt", async () => {
    const calls: { filters: SupplierFilters; page: number }[] = [];
    const s = fork({
      handlers: [
        [
          listSuppliersFx,
          (p: { filters: SupplierFilters; page: number }) => {
            calls.push(p);
            return { items: [row("s-1")], total: 41, page: p.page, size: 20 };
          },
        ],
        [createSupplierFx, () => supplier("s-2")],
        [getSupplierFx, (id: string) => supplier(id)],
        [getDebtFx, () => ({ payable: "120000.00", receivable: "0.00" })],
      ],
    });
    await allSettled(suppliersOpened, { scope: s });
    await allSettled(pageChanged, { scope: s, params: 3 });
    expect(calls.at(-1)?.page).toBe(3);
    await allSettled(searchChanged, { scope: s, params: "Baraka" });
    expect(s.getState($page)).toBe(1);
    expect(calls.at(-1)).toEqual({ filters: { search: "Baraka", archived: false }, page: 1 });
    expect(s.getState($rows)).toHaveLength(1);

    await allSettled(createSupplierFx, { scope: s, params: { ...EMPTY_FORM, name: "X", stir: "123456789" } });
    expect(s.getState($detail)?.id).toBe("s-2");
    expect(s.getState($debt)?.payable).toBe("120000.00");
  });
});

describe("suppliers lib", () => {
  it("STIR rules, lookup suggestion and request bodies", () => {
    expect(formErrors(EMPTY_FORM)).toEqual({ name: "validation.required", stir: "validation.required" });
    expect(formErrors({ ...EMPTY_FORM, name: "A", stir: "12345" }).stir).toBe("validation.stir_format");
    expect(formErrors({ ...EMPTY_FORM, kind: "person", name: "Ali" })).toEqual({});
    const filled = applySuggestion(EMPTY_FORM, {
      stir: "305112847",
      kind: "company",
      name: "Barakali Don",
      legal_address: "Toshkent",
      bank_account: "2020800",
      bank_mfo: "00014",
      vat_payer: true,
      director_name: "A. Karimov",
      existing_counterparty_id: null,
    });
    expect(filled).toMatchObject({
      name: "Barakali Don",
      stir: "305112847",
      legalAddress: "Toshkent",
      vatPayer: true,
    });
    expect(toCreateBody({ ...filled, phone: " " })).toMatchObject({
      is_supplier: true,
      is_customer: false,
      phone: null,
    });
    expect(toUpdateBody(filled, 4)).toMatchObject({ version: 4, name: "Barakali Don" });
    expect("is_supplier" in toUpdateBody(filled, 4)).toBe(false);
  });
});
