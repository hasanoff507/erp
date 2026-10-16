import type { TenantSettingsFullOut, TermsVersionOut } from "@shared/models";

export type TenantSettings = TenantSettingsFullOut;
export type TermsVersion = TermsVersionOut;

/** BO-14 section tabs (07): Do'kon · Soliq rejimi · Integratsiyalar · Fiskal · Chek · Xavfsizlik. */
export type TenantTab = "shop" | "tax" | "integrations" | "fiscal" | "receipt" | "security";
export const TENANT_TABS: readonly TenantTab[] = [
  "shop",
  "tax",
  "integrations",
  "fiscal",
  "receipt",
  "security",
];

export type LegalForm = "llc" | "jsc" | "private_enterprise" | "sole_proprietor";
export const LEGAL_FORMS: readonly LegalForm[] = ["llc", "jsc", "private_enterprise", "sole_proprietor"];
export type TaxRegime = "vat" | "turnover";

/** Editable part of `PATCH /tenant/settings` (20 #40b) as form values. */
export interface TenantFormValues {
  name: string;
  legalForm: LegalForm;
  bankAccount: string;
  bankMfo: string;
  vatDiffToleranceAmount: string;
  discountPosting: "gross_9050" | "net";
  ownerWithdrawalAccount: "4890" | "8720";
  paymentOrgCommissionAccount: "9430" | "9410";
  turnoverTaxAccount: "9430" | "9820";
  markingPrecheck: "off" | "warn" | "block";
  negativeStockPolicy: "allow" | "block";
  debtReceiptSplit: "single" | "per_sale";
  creditSaleReceipt: "none" | "credit_type";
  supplierOverpayPolicy: "warn" | "block";
  aiTrainingConsent: boolean;
}
