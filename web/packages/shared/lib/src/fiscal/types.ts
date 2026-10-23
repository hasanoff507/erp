/**
 * `FiscalPort` (TypeScript) — 21 §1 port and 21 §16.1 local-API schemas, field for field. Amounts at this
 * boundary are integer tiyin (`int64`, qaror #12/#26), quantities are milli-units; everything else in the web
 * POS stays decimal strings (`@shared/lib/money`). The local bridge (`multikassa_local` / `fiscaldrive_local`)
 * talks to the Do'kon agenti (`/v1/fiscal/*`); the FM signs offline as well, so the result is final the
 * moment it arrives and travels in the POS event as `fiscal_result` (18 §4.1, qaror #68).
 */

/** `CashRegisterRef` — `local_id` = `cash_registers.fiscal_local_device_id` (BO-12 binding). */
export interface CashRegisterRef {
  cash_register_id: string;
  local_id: string;
}

/** `sale`, `debt_settlement`, `credit_sale` → `/v1/fiscal/sale`; `return` → `/v1/fiscal/refund`. */
export type FiscalKind = "sale" | "debt_settlement" | "credit_sale" | "return";
export type PaymentForm = "cash" | "card" | "qr" | "mixed";
export type FiscalCardType = "personal" | "corporate" | "social" | "unknown";

export interface FiscalItem {
  name: string;
  /** MXIK — exactly 17 digits or null (the agent refuses anything else). */
  mxik: string | null;
  package_code: string | null;
  unit_code: string | null;
  qty_milli: number;
  price_tiyin: number;
  amount_tiyin: number;
  vat_rate: string;
  vat_tiyin: number;
  /** DataMatrix codes exactly as scanned (GS kept, qaror #62). */
  marking_codes: string[];
}

export interface FiscalPayments {
  payment_form: PaymentForm;
  cash_tiyin: number;
  card_tiyin: number;
  qr_tiyin: number;
  /** Integrated card only (terminal result); a card without terminal → null (21 §1, 26 #178). */
  card_type: FiscalCardType | null;
  card_mask: string | null;
  rrn: string | null;
}

/** `RefundInfo` — FM requisites of the original receipt (21 §1). */
export interface RefundInfo {
  fm_terminal_id: string;
  fm_receipt_seq: number;
  fiscal_sign: string;
}

export interface FiscalReceiptPayload {
  cash_register: CashRegisterRef;
  receipt_seq: number;
  kind: FiscalKind;
  items: FiscalItem[];
  payments: FiscalPayments;
  total_tiyin: number;
  refund_info?: RefundInfo;
}

/** `FiscalResult` — exactly what goes into the event as `fiscal_result` (18 §4.1). */
export interface FiscalResult {
  fm_terminal_id: string;
  fm_receipt_seq: number;
  fiscal_sign: string;
  qr_url: string;
  fiscal_at: string;
}

export interface FiscalShiftResult {
  fm_terminal_id: string;
  opened_at: string;
}

export interface ZReport {
  fm_terminal_id: string;
  z_number: number;
  totals: { sale: number; return: number; by_payment_form: Record<string, number> };
  closed_at: string;
}

export type FmState = "ok" | "locked" | "ack_overdue" | "memory_full" | "unknown";

export interface FiscalDeviceStatus {
  fm_state: FmState | string;
  pending_count: number;
  oldest_unacked_at: string | null;
}

export interface UnsentReceipt {
  fm_receipt_seq: number;
  fiscal_at: string;
  amount_tiyin: number;
}

export interface ResendResult {
  sent: number;
  failed: number;
  acked: { fm_terminal_id: string; fm_receipt_seq: number; acked_at: string }[];
}

/** 21 §1 `FiscalPort` — the same seven operations as the backend Protocol. */
export interface FiscalPort {
  openShift(register: CashRegisterRef, shiftNo: number, cashierName: string): Promise<FiscalShiftResult>;
  closeShift(register: CashRegisterRef, shiftNo: number): Promise<ZReport>;
  registerSale(receipt: FiscalReceiptPayload): Promise<FiscalResult>;
  registerRefund(receipt: FiscalReceiptPayload): Promise<FiscalResult>;
  getDeviceStatus(register: CashRegisterRef): Promise<FiscalDeviceStatus>;
  listUnsent(register: CashRegisterRef): Promise<UnsentReceipt[]>;
  resendUnsent(register: CashRegisterRef): Promise<ResendResult>;
}

/**
 * Error codes of the local bridge. Catalog codes (17 §15) keep their name (`common:errors.<lower>`); the two
 * local states are not server codes (21 §16 «Fiskal modul ulanmagan», 18 §4.10) and live in `pos:sale.errors`:
 * - `FISCAL_MODULE_NOT_CONNECTED` — the agent/FM did not answer before anything was signed, the token was
 *   refused, the FM state is unknown, or the register is bound to a device the agent does not have;
 * - `FISCAL_RESULT_UNKNOWN` — the request may have reached the FM (timeout / dropped connection /
 *   `502 outcome_unknown`): the SAME payload with the SAME `receipt_seq` is sent again (the agent journal
 *   answers it without a second signature, 21 §16.1).
 */
export type FiscalErrorCode =
  | "FISCAL_MODULE_NOT_CONNECTED"
  | "FISCAL_RESULT_UNKNOWN"
  | "FISCAL_DEVICE_LOCKED"
  | "FISCAL_OFFLINE_48H_BLOCKED"
  | "FISCAL_PROVIDER_ERROR"
  | "SHIFT_NOT_OPEN"
  | "SHIFT_ALREADY_OPEN"
  | "RECEIPT_SEQ_CONFLICT"
  | "VALIDATION_ERROR";

export const LOCAL_FISCAL_CODES: ReadonlySet<FiscalErrorCode> = new Set([
  "FISCAL_MODULE_NOT_CONNECTED",
  "FISCAL_RESULT_UNKNOWN",
]);

export class FiscalError extends Error {
  readonly code: FiscalErrorCode;
  readonly params: Record<string, unknown>;

  constructor(code: FiscalErrorCode, params: Record<string, unknown> = {}, cause?: unknown) {
    super(code, cause !== undefined ? { cause } : undefined);
    this.name = "FiscalError";
    this.code = code;
    this.params = params;
  }

  /** True when the same payload may (and must) be sent again with the same receipt_seq. */
  get retrySame(): boolean {
    return this.code === "FISCAL_RESULT_UNKNOWN" || this.code === "FISCAL_MODULE_NOT_CONNECTED";
  }
}

export const isFiscalError = (e: unknown): e is FiscalError => e instanceof FiscalError;
