import { addMoney, money, type Money } from "@shared/lib/money";
import type { ListLedgerEntriesParams } from "@shared/models";

import {
  ACCOUNT_CODES,
  DOC_TYPES,
  JOURNAL_PAGE_SIZE,
  RECOST_STATUSES,
  type AccountCode,
  type DocType,
  type JournalFilters,
  type LedgerEntry,
  type RecostJob,
  type RecostStatus,
} from "../types/index.ts";

/** `YYYY-MM-01` of the month of `today` (`YYYY-MM-DD`). */
export function monthStart(today: string): string {
  return `${today.slice(0, 7)}-01`;
}

/** 07 BO-08 default period: the current month up to today (mockup «01.10–16.10.2026»). */
export function defaultFilters(today: string): JournalFilters {
  return { dateFrom: monthStart(today), dateTo: today, account: null, side: "dt", docType: null };
}

/** Both ends set and `dateFrom ≤ dateTo` (ISO dates compare as strings). */
export function isRangeValid(f: Pick<JournalFilters, "dateFrom" | "dateTo">): boolean {
  return f.dateFrom !== "" && f.dateTo !== "" && f.dateFrom <= f.dateTo;
}

export function sameFilters(a: JournalFilters, b: JournalFilters): boolean {
  return (
    a.dateFrom === b.dateFrom &&
    a.dateTo === b.dateTo &&
    a.account === b.account &&
    a.side === b.side &&
    a.docType === b.docType
  );
}

/** Filters → `GET /ledger-entries` query (20 #9: column-named filters `entry_date__gte/__lte`, `account_dt/kt`). */
export function toQuery(f: JournalFilters, cursor: string | null): ListLedgerEntriesParams {
  return {
    entry_date__gte: f.dateFrom,
    entry_date__lte: f.dateTo,
    ...(f.account ? (f.side === "dt" ? { account_dt: f.account } : { account_kt: f.account }) : {}),
    ...(f.docType ? { doc_type: f.docType } : {}),
    ...(cursor ? { cursor } : {}),
    limit: JOURNAL_PAGE_SIZE,
  };
}

/**
 * «Jami — Dt oboroti = Kt oboroti» of the rows shown: every entry is one Dt and one Kt line of the same
 * amount, so both turnovers equal Σ amount (decimal strings, never floats — qaror #26).
 */
export function turnoverOf(entries: readonly LedgerEntry[]): Money {
  return addMoney(...entries.map((e) => money(e.amount)));
}

/** `POST /recost-jobs/{id}/retry` is allowed only for `failed` (19 §18; `rejected_period_closed` is final). */
export function isRetryable(job: Pick<RecostJob, "status">): boolean {
  return job.status === "failed";
}

export function isRecostStatus(value: string | null): value is RecostStatus {
  return value !== null && (RECOST_STATUSES as readonly string[]).includes(value);
}

/** A code of the chart of accounts the UI has a name for. */
export function isAccountCode(value: string): value is AccountCode {
  return (ACCOUNT_CODES as readonly string[]).includes(value);
}

/** A posting document type the UI has a label for. */
export function isDocType(value: string): value is DocType {
  return (DOC_TYPES as readonly string[]).includes(value);
}

/** Ids not yet resolved to names (deduplicated, order kept). */
export function missingIds(ids: readonly string[], known: Readonly<Record<string, string>>): string[] {
  return [...new Set(ids)].filter((id) => !(id in known));
}

/** Replaces a job in the list by id (retry answer), keeping the order. */
export function replaceJob(list: readonly RecostJob[], job: RecostJob): RecostJob[] {
  return list.map((j) => (j.id === job.id ? job : j));
}
