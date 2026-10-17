/**
 * Row and DTO types of @shared/offline — 16-offline-sync.md §1 (local tables), §2 (outbox event),
 * 18-api-kassa.md §2.1/§2.2/§2.6 (envelope, PushResultEntry, SyncPushRequest), §2.7 (CardResult).
 * Money / qty stay decimal strings (qaror #26, #57).
 */
import type { Money } from "@shared/lib/money";

/** 16 §2 — closed list of outbox event types. */
export const OUTBOX_EVENT_TYPES = [
  "shift.opened",
  "shift.closed",
  "sale.created",
  "sale.draft_voided",
  "receipt.reprinted",
  "return.created",
  "debt_payment.created",
  "cash_movement.created",
  "counterparty.created",
  "expense.created",
  "transfer.sent",
  "transfer.received",
  "stock_count.line_recorded",
] as const;
export type OutboxEventType = (typeof OUTBOX_EVENT_TYPES)[number];

/** Event types whose payload carries a fiscal receipt (16 §6 timer, §2 receipt_seq). */
export const FISCAL_EVENT_TYPES: ReadonlySet<OutboxEventType> = new Set([
  "sale.created",
  "return.created",
  "debt_payment.created",
]);

export type OutboxStatus = "pending" | "accepted" | "duplicate" | "rejected";

/** 18 §2.1 SyncEventEnvelope. */
export interface SyncEventEnvelope {
  client_event_id: string;
  device_id: string;
  seq: number;
  type: OutboxEventType;
  created_at: string;
  actor_user_id: string;
  payload: Record<string, unknown>;
}

/** Local outbox row = envelope + local sync state (16 §3.4: rejected rows are never deleted). */
export interface OutboxRow extends SyncEventEnvelope {
  status: OutboxStatus;
  error_code: string | null;
  message: string | null;
  retryable: boolean | null;
  warnings: string[];
  server: Record<string, unknown> | null;
  attempts: number;
  last_attempt_at: string | null;
  /** Earliest time (ms) the next automatic attempt of a retryable rejected row may run. */
  next_attempt_at: number;
  result_at: string | null;
  receipt_seq: number | null;
  cash_register_id: string | null;
  shift_id: string | null;
  fiscal: boolean;
  ofd_acked_at: string | null;
  /** Index helper: 1 = fiscal receipt still without OFD ack (16 §6 timer), else 0. */
  fiscal_unacked: 0 | 1;
  /** Index helper: 1 = needs to reach the server (pending or rejected), else 0. */
  unsynced: 0 | 1;
  /**
   * 1 = rejected with `retryable: false` — waits for a manual fix / escalation (POS-12 «Eskalatsiya»,
   * 16 §3.4). Such a row no longer holds back `shift.closed` and, without `payload.fiscal_result`,
   * no longer counts toward the 48 h timer (no receipt exists — founder decision F-1). Absent = 0.
   */
  escalated?: 0 | 1;
}

/** 18 §2.2 PushResultEntry. */
export interface PushResultEntry {
  client_event_id: string;
  status: "accepted" | "rejected" | "duplicate";
  server?: Record<string, unknown> | null;
  error_code?: string | null;
  message?: string | null;
  retryable?: boolean;
  warnings?: string[];
}

/** 18 §2.6 SyncPushRequest. */
export interface SyncPushRequest {
  device_id: string;
  events: SyncEventEnvelope[];
  outbox_state: { pending_count: number; oldest_pending_created_at: string | null };
}

export interface SyncPushResponse {
  results: PushResultEntry[];
}

/** 16 §3.2 pull scopes. */
export const PULL_SCOPES = [
  "catalog",
  "barcodes",
  "prices",
  "customers",
  "stock",
  "limits",
  "permissions",
  "shift",
  "marking_codes",
  "fiscal",
  "settings",
] as const;
export type PullScope = (typeof PULL_SCOPES)[number];

export interface SyncPullParams {
  scope: string;
  cursor: string;
  page_size: number;
}

/**
 * contracts/sync-pull.md: delta arrays (catalog, barcodes, prices, customers, stock, marking_codes,
 * fiscal — upsert by id, `deleted: true` removes) and snapshot objects (permissions, limits, shift,
 * settings — replace the whole local table, `null` = unchanged). Rows are normalised by sync/apply.ts.
 */
export interface SyncPullResponse {
  cursor: string;
  has_more: boolean;
  server_time?: string;
  device?: { id: string; branch_id: string; cash_register_id: string | null } | null;
  [scope: string]: unknown;
}

export interface DeviceIdentity {
  deviceId: string;
  tenantId: string;
  branchId: string;
  cashRegisterId: string | null;
}

// ---- reference rows (pull scopes) -----------------------------------------------------------

/** A pulled row keeps every server field; the typed ones are what the queries rely on. */
export interface ProductRow {
  id: string;
  name: string;
  name_ru: string | null;
  category_id: string | null;
  unit_code: string;
  code?: string | null;
  mxik_code?: string | null;
  vat_rate?: string | null;
  is_marked?: boolean;
  is_weighed?: boolean;
  archived_at?: string | null;
  /** Lower-cased word prefixes source (name, name_ru, code) — multiEntry index. */
  tokens: string[];
  [extra: string]: unknown;
}

export interface CategoryRow {
  id: string;
  name: string;
  name_ru?: string | null;
  parent_id?: string | null;
  sort_order?: number | null;
  [extra: string]: unknown;
}

export interface UnitRow {
  code: string;
  is_fractional?: boolean;
  [extra: string]: unknown;
}

export interface BarcodeRow {
  /** `<product_id>:<barcode>` */
  id: string;
  product_id: string;
  barcode: string;
  units_per_barcode: string;
  [extra: string]: unknown;
}

export interface PriceRow {
  /** server `price_id` */
  id: string;
  product_id: string;
  branch_id: string | null;
  /** Index helper: branch_id or "*" (tenant-wide) — IndexedDB cannot index null. */
  branch_key: string;
  price: string;
  valid_from: string;
  [extra: string]: unknown;
}

export interface CustomerRow {
  id: string;
  name: string;
  phone?: string | null;
  receivable_balance?: string;
  credit_limit?: string | null;
  version?: number;
  open_debt_docs?: unknown[];
  tokens: string[];
  [extra: string]: unknown;
}

export interface StockRow {
  id: string;
  product_id: string;
  warehouse_id?: string;
  qty?: string;
  [extra: string]: unknown;
}

/** `limits` snapshot: most generous limit per permission code for one user (null = unlimited). */
export interface LimitRow {
  user_id: string;
  limits: Record<string, string | null>;
}

/** Staff / PIN row (permissions snapshot — contracts/sync-pull.md, device-auth.md `StaffPinRow`, D1). */
export interface StaffRow {
  user_id: string;
  full_name: string;
  role_codes: string[];
  branch_ids: string[];
  active: boolean;
  must_change_pin: boolean;
  pin_local_hash: string | null;
  permissions: { code: string; limit_value: string | null }[];
  [extra: string]: unknown;
}

export interface MarkingCodeRow {
  id: string;
  code: string;
  status: string;
  [extra: string]: unknown;
}

export interface FiscalRegisterRow {
  id: string;
  fm_state?: string | null;
  last_unacked_receipt_at?: string | null;
  fm_receipts_pending?: number | null;
  [extra: string]: unknown;
}

export interface FiscalReceiptRow {
  id: string;
  client_event_id?: string | null;
  cash_register_id?: string | null;
  shift_id?: string | null;
  receipt_seq?: number | null;
  ofd_acked_at?: string | null;
  created_at?: string | null;
  status?: string | null;
  [extra: string]: unknown;
}

export interface SettingRow {
  key: string;
  value: unknown;
}

export interface CardTerminalRow {
  id: string;
  cash_register_id?: string | null;
  branch_id?: string | null;
  adapter?: string;
  is_default?: boolean;
  [extra: string]: unknown;
}

export interface WeightBarcodeTemplate {
  prefixes: string[];
  item_code_len: number;
  value_len: number;
  value_kind: string;
  decimals: number;
  enabled: boolean;
  [field: string]: unknown;
}

export type CardManualFallback = "allow" | "manager_approval" | "forbid";

export interface PosSettings {
  weightBarcodeTemplates: WeightBarcodeTemplate[];
  weightBarcodeVersion: string | null;
  cardManualFallback: CardManualFallback;
  cardTerminals: CardTerminalRow[];
  discountRules: Record<string, unknown>[];
  markingPrecheck: "off" | "warn" | "block";
  subscriptionStatus: string | null;
  raw: Record<string, unknown>;
}

/** `shift` snapshot (server view of this register). */
export interface ServerShiftSnapshot {
  cash_register_id: string | null;
  open_shift: {
    id: string;
    shift_no: number;
    status: string;
    device_id: string;
    opened_by: string;
    opened_at: string;
    opening_cash: string;
  } | null;
  last_shift_no: number | null;
}

// ---- local-only rows -----------------------------------------------------------------------

export interface LocalShift {
  id: string;
  cash_register_id: string;
  shift_no: number;
  opened_at: string;
  opened_by: string;
  status: "open" | "closed";
  client_event_id?: string | null;
  [extra: string]: unknown;
}

export type CardAttemptStatus = "pending" | "approved" | "declined" | "unknown" | "voided";

/** 16 §2.1 local card attempt (PAN-free). */
export interface CardAttempt {
  attempt_id: string;
  card_terminal_id: string;
  local_id?: string | null;
  kind: "purchase" | "refund" | "void";
  amount: Money | string;
  client_event_id: string | null;
  status: CardAttemptStatus;
  started_at: string;
  original_attempt_id?: string | null;
  /** CardResult (18 §2.7) — PAN-free by contract. */
  result?: Record<string, unknown> | null;
  resolved_by?: "auto" | "status_query" | "manager" | null;
  [extra: string]: unknown;
}

export interface SalesHistoryInput {
  id: string;
  kind: "sale" | "return";
  total: string;
  number?: string | null;
  customer_id?: string | null;
  summary?: Record<string, unknown>;
}

export interface SalesHistoryRow extends SalesHistoryInput {
  client_event_id: string;
  created_at: string;
  cash_register_id: string | null;
  shift_id: string | null;
  receipt_seq: number | null;
}

export interface PinLockoutRow {
  user_id: string;
  failures: number;
  /** Number of lockouts so far → 1 / 5 / 15 / 60 min. */
  level: number;
  locked_until: number | null;
}

export interface MetaRow {
  key: string;
  value: unknown;
}
