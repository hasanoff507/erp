import type {
  BankImportResult,
  BankSettlementDetail,
  BankSettlementIn,
  BankSettlementOut,
  BankSettlementPage,
  BankSettlementPatch,
  TransitBalance,
  TransitBalances,
  UnmatchedCardTransaction,
  UnmatchedLine,
} from "@shared/models";

import type { Attachment } from "#/shared/lib/attachments.ts";

export type Settlement = BankSettlementOut;
export type SettlementDetail = BankSettlementDetail;
export type {
  BankImportResult,
  BankSettlementIn,
  BankSettlementPage,
  BankSettlementPatch,
  TransitBalance,
  TransitBalances,
  UnmatchedCardTransaction,
  UnmatchedLine,
};

/** 07 BO-24 «Usul» (qaror #42): card, UzQR, Click, Payme, Uzum, collection (inkassa). */
export const METHODS = ["card", "uzqr", "click", "payme", "uzum", "collection"] as const;
export type Method = (typeof METHODS)[number];
export const STATUSES = ["draft", "posted", "cancelled"] as const;
export type SettlementStatus = (typeof STATUSES)[number];
export type SettlementSource = "manual" | "statement_import";

export interface SettlementFilters {
  branchId: string | null;
  method: Method | null;
  status: SettlementStatus | null;
  source: SettlementSource | null;
  from: string | null;
  to: string | null;
}

export interface ListRequest {
  filters: SettlementFilters;
  cursor: string | null;
}

/** The BO-24 form (MoneyInput strings; dates `YYYY-MM-DD`). */
export interface BankForm {
  branchId: string;
  docDate: string;
  method: Method | null;
  settledFrom: string;
  settledTo: string;
  gross: string;
  commission: string;
  variance: string;
  bankRef: string;
  comment: string;
  attachment: Attachment | null;
}

export type BankFormField =
  | "branchId"
  | "docDate"
  | "method"
  | "settledFrom"
  | "settledTo"
  | "gross"
  | "commission"
  | "variance"
  | "bankRef"
  | "comment";
export type BankFormErrors = Partial<Record<BankFormField, string>>;

/** One preview posting line (13 §2.18a). */
export interface PreviewLine {
  dt: string;
  kt: string;
  amount: string;
}

/** Transit panel: one method row with an amount per branch and the total. */
export interface TransitRow {
  key: Method | "card_integrated" | "card_manual";
  byBranch: Record<string, string>;
  total: string;
  oldest: string | null;
}

export const BANK_REF_MAX = 64;
export const COMMENT_MAX = 500;
/** 07 BO-24 `cancel_reason`: ≥ 10, ≤ 500. */
export const CANCEL_MIN = 10;
export const CANCEL_MAX = 500;
export const PAGE_SIZE = 50;

export interface BankMountParams {
  today: string;
  /** Topbar branch — the list filter and the form default. */
  branchId: string | null;
}
