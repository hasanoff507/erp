import { dayjs } from "@shared/lib/date";
import { toDecimal } from "@shared/lib/money";
import type { SettingsPatchIn, TenantSettingsPatchIn } from "@shared/models";

import { TENANT_TABS } from "../types/index.ts";
import type { TenantFormValues, TenantSettings, TenantTab, TermsVersion } from "../types/index.ts";

export function toFormValues(s: TenantSettings): TenantFormValues {
  return {
    name: s.name,
    legalForm: s.legal_form,
    bankAccount: s.settings.bank_account ?? "",
    bankMfo: s.settings.bank_mfo ?? "",
    vatDiffToleranceAmount: s.settings.vat_diff_tolerance_amount,
    discountPosting: s.settings.discount_posting,
    ownerWithdrawalAccount: s.settings.owner_withdrawal_account,
    paymentOrgCommissionAccount: s.settings.payment_org_commission_account,
    turnoverTaxAccount: s.settings.turnover_tax_account,
    markingPrecheck: s.settings.marking_precheck,
    negativeStockPolicy: s.settings.negative_stock_policy,
    debtReceiptSplit: s.settings.fiscal_policy.debt_receipt_split,
    creditSaleReceipt: s.settings.fiscal_policy.credit_sale_receipt,
    supplierOverpayPolicy: s.settings.supplier_overpay_policy,
    aiTrainingConsent: s.settings.ai_training_consent,
  };
}

function sameDecimal(a: string, b: string): boolean {
  try {
    return toDecimal(a).equals(toDecimal(b));
  } catch {
    return a === b;
  }
}

/**
 * Only the changed fields go into the merge-PATCH (20 #40b); `ai_cross_border_enabled`,
 * `go_live_date`, `accepted_terms_*` are never sent. `null` when nothing changed.
 */
export function buildPatch(
  base: TenantFormValues,
  values: TenantFormValues,
  version: number,
): TenantSettingsPatchIn | null {
  const patch: TenantSettingsPatchIn = { version };
  const settings: SettingsPatchIn = {};
  let changed = false;

  if (values.name.trim() !== base.name) {
    patch.name = values.name.trim();
    changed = true;
  }
  if (values.legalForm !== base.legalForm) {
    patch.legal_form = values.legalForm;
    changed = true;
  }
  const set = <K extends keyof SettingsPatchIn>(key: K, value: SettingsPatchIn[K]) => {
    settings[key] = value;
    changed = true;
  };
  if (values.bankAccount.trim() !== base.bankAccount) set("bank_account", values.bankAccount.trim() || null);
  if (values.bankMfo.trim() !== base.bankMfo) set("bank_mfo", values.bankMfo.trim() || null);
  if (!sameDecimal(values.vatDiffToleranceAmount, base.vatDiffToleranceAmount)) {
    set("vat_diff_tolerance_amount", values.vatDiffToleranceAmount);
  }
  if (values.discountPosting !== base.discountPosting) set("discount_posting", values.discountPosting);
  if (values.ownerWithdrawalAccount !== base.ownerWithdrawalAccount) {
    set("owner_withdrawal_account", values.ownerWithdrawalAccount);
  }
  if (values.paymentOrgCommissionAccount !== base.paymentOrgCommissionAccount) {
    set("payment_org_commission_account", values.paymentOrgCommissionAccount);
  }
  if (values.turnoverTaxAccount !== base.turnoverTaxAccount)
    set("turnover_tax_account", values.turnoverTaxAccount);
  if (values.markingPrecheck !== base.markingPrecheck) set("marking_precheck", values.markingPrecheck);
  if (values.negativeStockPolicy !== base.negativeStockPolicy)
    set("negative_stock_policy", values.negativeStockPolicy);
  if (values.supplierOverpayPolicy !== base.supplierOverpayPolicy) {
    set("supplier_overpay_policy", values.supplierOverpayPolicy);
  }
  if (values.aiTrainingConsent !== base.aiTrainingConsent)
    set("ai_training_consent", values.aiTrainingConsent);
  if (
    values.debtReceiptSplit !== base.debtReceiptSplit ||
    values.creditSaleReceipt !== base.creditSaleReceipt
  ) {
    set("fiscal_policy", {
      ...(values.debtReceiptSplit !== base.debtReceiptSplit
        ? { debt_receipt_split: values.debtReceiptSplit }
        : {}),
      ...(values.creditSaleReceipt !== base.creditSaleReceipt
        ? { credit_sale_receipt: values.creditSaleReceipt }
        : {}),
    });
  }

  if (!changed) return null;
  if (Object.keys(settings).length > 0) patch.settings = settings;
  return patch;
}

/** Tax regime changes take effect from the 1st of next month (20 #40c). */
export function nextMonthStart(today: Date = new Date()): string {
  return dayjs(today).add(1, "month").startOf("month").format("YYYY-MM-DD");
}

/** Current consent text version for AI cross-border transfer (GET /auth/terms, kind=ai_cross_border). */
export function aiTermsOf(terms: readonly TermsVersion[]): TermsVersion | null {
  return terms.find((t) => t.kind === "ai_cross_border") ?? null;
}

/**
 * BO-14 form field → the tab it is rendered on. One form spans all six tabs and Radix unmounts the
 * inactive ones, so an error on another tab must switch to it (WEB-03).
 */
export const TENANT_FIELD_TAB: Readonly<Record<keyof TenantFormValues, TenantTab>> = {
  name: "shop",
  legalForm: "shop",
  bankAccount: "shop",
  bankMfo: "shop",
  vatDiffToleranceAmount: "tax",
  discountPosting: "tax",
  ownerWithdrawalAccount: "tax",
  paymentOrgCommissionAccount: "tax",
  turnoverTaxAccount: "tax",
  markingPrecheck: "fiscal",
  negativeStockPolicy: "fiscal",
  debtReceiptSplit: "fiscal",
  creditSaleReceipt: "fiscal",
  supplierOverpayPolicy: "security",
  aiTrainingConsent: "security",
};

/** Tabs holding at least one of the errored fields, in tab order (unknown names are ignored). */
export function tabsWithErrors(fields: Iterable<string>): TenantTab[] {
  const tabs = new Set<TenantTab>();
  for (const field of fields) {
    const tab = (TENANT_FIELD_TAB as Readonly<Record<string, TenantTab>>)[field];
    if (tab) tabs.add(tab);
  }
  return TENANT_TABS.filter((tab) => tabs.has(tab));
}

/** First errored field in tab order (the one to focus after switching tabs). */
export function firstErrorField(fields: Iterable<string>): keyof TenantFormValues | null {
  const set = new Set(fields);
  const order = Object.keys(TENANT_FIELD_TAB) as (keyof TenantFormValues)[];
  const sorted = order
    .filter((f) => set.has(f))
    .sort((a, b) => TENANT_TABS.indexOf(TENANT_FIELD_TAB[a]) - TENANT_TABS.indexOf(TENANT_FIELD_TAB[b]));
  return sorted[0] ?? null;
}
