import type {
  ApprovalRequestOut,
  ApprovalRequestOutKind,
  ApprovalRequestOutStatus,
  ApprovalRequestPage,
  ApproveOut,
  RejectOut,
} from "@shared/models";

export type ApprovalRequest = ApprovalRequestOut;
export type ApprovalKind = ApprovalRequestOutKind;
export type ApprovalStatus = ApprovalRequestOutStatus;
export type { ApprovalRequestPage, ApproveOut, RejectOut };

/**
 * 07 BO-16 status tabs — one per 18 §9.1 status (`?status=`): «Kutilmoqda · Tasdiqlangan · Hujjatda
 * ishlatilgan · Rad etilgan · Muddati o'tgan» (`consumed` = approved and already used by its document).
 */
export type QueueTab = ApprovalRequestOutStatus;
export const QUEUE_TABS: readonly QueueTab[] = ["pending", "approved", "consumed", "rejected", "expired"];

/** 18 §9.1 `kind` (order of the filter chips, mockup). */
export const APPROVAL_KINDS: readonly ApprovalKind[] = [
  "discount_over_limit",
  "return_over_limit",
  "return_no_receipt",
  "cash_withdrawal_over_limit",
  "price_change",
  "debt_over_limit",
  "expense_over_limit",
  "write_off_over_limit",
  "card_manual_entry",
];

/** Kinds whose `requested_value` is a percent (18 §9.2: `context.requested_pct`), the rest — so'm. */
export const PERCENT_KINDS: readonly ApprovalKind[] = ["discount_over_limit", "price_change"];

export type LoadStatus = "idle" | "loading" | "error";

/** Queue refresh while the page is open (18 §9.3: the POS polls every 3 s; the manager's list — 15 s). */
export const POLL_MS = 15_000;
export const PAGE_SIZE = 50;
/** «Bugun hal qilinganlar»: the newest resolved requests of each status, filtered to today. */
export const RESOLVED_PAGE_SIZE = 50;

export interface ListRequest {
  tab: QueueTab;
  cursor: string | null;
  /** Poll refresh: no skeleton, the list is replaced quietly. */
  silent: boolean;
}

export interface ApproveRequest {
  id: string;
  pin: string;
}

export interface RejectRequest {
  id: string;
  reason: string;
}

export interface ApprovalsMountParams {
  /** Local calendar date `YYYY-MM-DD` («Bugun hal qilinganlar»). */
  today: string;
  /** `Date.now()` of the visit (time left until `expires_at`). */
  now: number;
}

/**
 * `context.reason` of a cash withdrawal (18 §13.1 `cash_movements.reason`) — plus `expense`: POS-14
 * «Xarajat» asks the same `cash_withdrawal_over_limit` approval for a cash expense (18 §13.2, B4).
 */
export const CASH_REASONS = ["collection", "deposit", "owner_withdrawal", "other", "expense"] as const;
export type CashReason = (typeof CASH_REASONS)[number];
/** `context.source` of an `expense_over_limit` request (20 #43). */
export const EXPENSE_SOURCES = ["cash", "bank", "card"] as const;
export type ExpenseSource = (typeof EXPENSE_SOURCES)[number];
/** `context.manual_reason` of a terminalsiz card request (18 §4.1). */
export const MANUAL_REASONS = [
  "standalone_terminal",
  "terminal_offline",
  "terminal_error",
  "unknown_result",
] as const;
export type ManualReason = (typeof MANUAL_REASONS)[number];

/** Linked documents with their own label (18 §9.1 `linked_doc_type`); others → «Bog'langan hujjat». */
export const DOC_TYPES = [
  "sales",
  "returns",
  "debt_payments",
  "cash_movements",
  "price_changes",
  "write_offs",
  "expenses",
] as const;
export type LinkedDocType = (typeof DOC_TYPES)[number];

/** One line of the request card's details (`context` snapshot, 18 §9.1). */
export type ContextLine =
  | { key: "reason"; value: CashReason }
  | { key: "manualReason"; value: ManualReason }
  | { key: "comment"; value: string }
  | { key: "lines"; count: number }
  | { key: "category"; value: string }
  | { key: "source"; value: ExpenseSource }
  | { key: "docDate"; value: string }
  | { key: "customer"; value: string }
  | { key: "creditLimit"; value: string }
  | { key: "currentDebt"; value: string };
