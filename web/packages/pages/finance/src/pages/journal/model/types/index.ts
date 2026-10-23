import type { LedgerEntryOut, LedgerEntryPage, RecostJobOut, RecostJobPage } from "@shared/models";

export type LedgerEntry = LedgerEntryOut;
export type RecostJob = RecostJobOut;
export type { LedgerEntryPage, RecostJobPage };

/**
 * 20 #9 filters `account_dt` / `account_kt` are separate: the single «Hisob» filter of 07 BO-08 is
 * applied to the chosen side (Debet by default).
 */
export type AccountSide = "dt" | "kt";

/** 07 BO-08 filters: `dateFrom`/`dateTo` (entry_date, YYYY-MM-DD), `accountFilter`, document type. */
export interface JournalFilters {
  dateFrom: string;
  dateTo: string;
  /** 4-digit account code or `null` (all accounts). */
  account: string | null;
  side: AccountSide;
  /** `ledger_entries.doc_type` (document table name) or `null` (all documents). */
  docType: string | null;
}

export type LoadStatus = "idle" | "loading" | "error";

/** 19 §18 `recost_jobs.status`. */
export type RecostStatus = "queued" | "running" | "done" | "failed" | "rejected_period_closed";
export const RECOST_STATUSES: readonly RecostStatus[] = [
  "queued",
  "running",
  "done",
  "failed",
  "rejected_period_closed",
];

/** Sentinel option value of the «all» choice in selects (Radix Select has no empty value). */
export const ALL = "all";

/**
 * Accounts in use (backend `chart_of_accounts.py`, 13 §1, NSBU №21 MVP subset; 6710 is out of scope —
 * qaror #52). Names are translated (`finance:accounts.<code>`).
 */
export const ACCOUNT_CODES = [
  "0000",
  "2910",
  "2920",
  "2970",
  "4010",
  "4310",
  "4410",
  "4730",
  "4890",
  "4910",
  "5010",
  "5110",
  "5710",
  "5910",
  "6010",
  "6310",
  "6410",
  "6610",
  "8330",
  "8530",
  "8710",
  "8720",
  "9020",
  "9040",
  "9050",
  "9120",
  "9390",
  "9410",
  "9420",
  "9430",
  "9820",
  "9910",
] as const;
export type AccountCode = (typeof ACCOUNT_CODES)[number];

/**
 * Documents that post ledger entries (`ledger_entries.doc_type` = document table name, 12 §2.9 /
 * backend `DOC_TYPE_CODES`; price changes and purchase orders never post). Labels: `finance:docTypes.*`.
 */
export const DOC_TYPES = [
  "sales",
  "returns",
  "goods_receipts",
  "supplier_returns",
  "transfers",
  "stock_counts",
  "write_offs",
  "stock_openings",
  "debt_openings",
  "debt_payments",
  "debt_writeoffs",
  "supplier_payments",
  "expenses",
  "cash_movements",
  "bank_settlements",
  "tax_settlements",
  "ledger_adjustments",
] as const;
export type DocType = (typeof DOC_TYPES)[number];

export const JOURNAL_PAGE_SIZE = 50;
export const RECOST_PAGE_SIZE = 20;

export interface JournalMountParams {
  /** Local calendar date `YYYY-MM-DD` (the default period is the current month up to today). */
  today: string;
  /** `stock.view` — `GET /recost-jobs` (19 §18) is shown only then. */
  canViewRecost: boolean;
}

export interface EntriesRequest {
  filters: JournalFilters;
  cursor: string | null;
}

export interface RecostRequest {
  status: RecostStatus | null;
  cursor: string | null;
}
