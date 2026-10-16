import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";

import {
  $aiTerms,
  $lastConsent,
  $settings,
  TENANT_FIELD_TAB,
  TENANT_TABS,
  buildPatch,
  firstErrorField,
  tabsWithErrors,
  createConsentFx,
  createTaxRegimeFx,
  fetchSettingsFx,
  fetchTermsFx,
  nextMonthStart,
  pageMounted,
  toFormValues,
  updateSettingsFx,
  type TenantSettings,
} from "./index.ts";

const settings = (patch: Partial<TenantSettings> = {}): TenantSettings => ({
  name: "Demo do'kon",
  legal_form: "llc",
  go_live_date: null,
  accepted_terms_version: "2026-01",
  accepted_terms_at: "2026-10-01T10:00:00Z",
  version: 3,
  settings: {
    bank_account: null,
    bank_mfo: null,
    supplier_overpay_policy: "warn",
    vat_diff_tolerance_amount: "1000.00",
    marking_precheck: "warn",
    discount_posting: "gross_9050",
    owner_withdrawal_account: "4890",
    payment_org_commission_account: "9430",
    turnover_tax_account: "9430",
    negative_stock_policy: "allow",
    ai_training_consent: false,
    ai_cross_border_enabled: false,
    card_manual_fallback: "manager_approval",
    fiscal_policy: { debt_receipt_split: "single", credit_sale_receipt: "none" },
  },
  tax_regime: { current: "vat", history: [] },
  integrations: {
    ofd: { status: "connected" },
    faktura_uz: { status: "not_connected", connected_at: null },
    crpt: { status: "not_connected", key_last4: null },
    click: { status: "not_connected", connected_at: null },
    payme: { status: "not_connected", connected_at: null },
    uzum: { status: "not_connected", connected_at: null },
    uzqr: { status: "not_connected", connected_at: null, cash_register_ids: [] },
  },
  ...patch,
});

const terms = {
  items: [
    {
      kind: "terms" as const,
      version: "2026-01",
      text_url: "/t",
      text_sha256: "x",
      effective_from: "2026-01-01",
    },
    {
      kind: "ai_cross_border" as const,
      version: "ai-2026-02",
      text_url: "/ai",
      text_sha256: "y",
      effective_from: "2026-02-01",
    },
  ],
};

describe("BO-14 tenant settings model", () => {
  it("loads settings and the current AI consent text version", async () => {
    const scope = fork({
      handlers: [
        [fetchSettingsFx, vi.fn(() => Promise.resolve(settings()))],
        [fetchTermsFx, vi.fn(() => Promise.resolve(terms))],
      ],
    });
    await allSettled(pageMounted, { scope });
    expect(scope.getState($settings)?.name).toBe("Demo do'kon");
    expect(scope.getState($aiTerms)?.version).toBe("ai-2026-02");
  });

  it("QT-M17-08 (UI side): PATCH carries only changed fields and never ai_cross_border/terms fields", () => {
    const base = toFormValues(settings());
    expect(buildPatch(base, base, 3)).toBeNull();
    const patch = buildPatch(
      base,
      {
        ...base,
        name: " Mega Market ",
        markingPrecheck: "block",
        vatDiffToleranceAmount: "1000",
        creditSaleReceipt: "credit_type",
      },
      3,
    );
    expect(patch).toEqual({
      version: 3,
      name: "Mega Market",
      settings: { marking_precheck: "block", fiscal_policy: { credit_sale_receipt: "credit_type" } },
    });
    expect(JSON.stringify(patch)).not.toMatch(/ai_cross_border|accepted_terms|go_live/);
    expect(buildPatch(base, { ...base, bankAccount: "" }, 3)).toBeNull();
    expect(buildPatch(base, { ...base, bankAccount: "20208000900123456001" }, 3)?.settings).toEqual({
      bank_account: "20208000900123456001",
    });
  });

  it("a saved PATCH merges into the loaded settings (new version)", async () => {
    const scope = fork({
      values: [[$settings, settings()]],
      handlers: [
        [
          updateSettingsFx,
          vi.fn(() => {
            const s = settings({ name: "Mega Market", version: 4 });
            return Promise.resolve({
              name: s.name,
              legal_form: s.legal_form,
              go_live_date: s.go_live_date,
              accepted_terms_version: s.accepted_terms_version,
              accepted_terms_at: s.accepted_terms_at,
              settings: s.settings,
              version: s.version,
            });
          }),
        ],
      ],
    });
    await allSettled(updateSettingsFx, { scope, params: { version: 3, name: "Mega Market" } });
    expect(scope.getState($settings)).toMatchObject({
      name: "Mega Market",
      version: 4,
      tax_regime: { current: "vat" },
    });
  });

  it("tax regime change (from next month) reloads settings for the history", async () => {
    const fetch = vi.fn(() => Promise.resolve(settings()));
    const scope = fork({
      handlers: [
        [
          createTaxRegimeFx,
          vi.fn(() => Promise.resolve({ regime: "turnover" as const, valid_from: "2026-11-01" })),
        ],
        [fetchSettingsFx, fetch],
      ],
    });
    await allSettled(createTaxRegimeFx, { scope, params: { regime: "turnover", validFrom: "2026-11-01" } });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(nextMonthStart(new Date("2026-10-17T12:00:00"))).toBe("2026-11-01");
    expect(nextMonthStart(new Date("2026-12-31T12:00:00"))).toBe("2027-01-01");
  });

  it("AI consent goes only through POST /tenant/consents; the flag follows the answer", async () => {
    const consent = vi.fn(() =>
      Promise.resolve({
        purpose: "ai_cross_border" as const,
        terms_version: "ai-2026-02",
        accepted: true,
        at: "2026-10-17T09:00:00Z",
        ai_cross_border_enabled: true,
      }),
    );
    const scope = fork({
      values: [[$settings, settings()]],
      handlers: [
        [createConsentFx, consent],
        [fetchSettingsFx, vi.fn(() => Promise.resolve(settings({ version: 4 })))],
      ],
    });
    await allSettled(createConsentFx, { scope, params: { accepted: true, termsVersion: "ai-2026-02" } });
    expect(scope.getState($lastConsent)?.at).toBe("2026-10-17T09:00:00Z");
  });

  it("an outdated consent text version reloads the terms", async () => {
    const termsFx = vi.fn(() => Promise.resolve(terms));
    const scope = fork({
      handlers: [
        [
          createConsentFx,
          vi.fn(() =>
            Promise.reject(
              new ApiError({
                status: 422,
                code: "VALIDATION_ERROR",
                messageKey: "errors.validation",
                params: { current_version: "ai-2026-02" },
                details: [{ field: "terms_version", messageKey: "validation.terms_version_not_current" }],
              }),
            ),
          ),
        ],
        [fetchTermsFx, termsFx],
      ],
    });
    await allSettled(createConsentFx, { scope, params: { accepted: true, termsVersion: "old" } });
    expect(termsFx).toHaveBeenCalledTimes(1);
  });
});

describe("BO-14 errors across tabs (WEB-03)", () => {
  it("maps every form field to a tab", () => {
    const fields = Object.keys(toFormValues(settings()));
    expect(Object.keys(TENANT_FIELD_TAB).sort()).toEqual(fields.sort());
    for (const tab of Object.values(TENANT_FIELD_TAB)) expect(TENANT_TABS).toContain(tab);
  });

  it("lists errored tabs in tab order and picks the first errored field to focus", () => {
    expect(tabsWithErrors(["supplierOverpayPolicy", "bankMfo", "unknown", "markingPrecheck"])).toEqual([
      "shop",
      "fiscal",
      "security",
    ]);
    expect(firstErrorField(["aiTrainingConsent", "vatDiffToleranceAmount"])).toBe("vatDiffToleranceAmount");
    expect(firstErrorField(["bankMfo", "name"])).toBe("name");
    expect(tabsWithErrors([])).toEqual([]);
    expect(firstErrorField(["nope"])).toBeNull();
  });
});
