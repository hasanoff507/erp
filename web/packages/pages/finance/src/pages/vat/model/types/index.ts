import type {
  ListVatMovesDocType,
  ListVatMovesKind,
  PendingCreditInvoiceOut,
  VatMoveOut,
  VatMovePage,
  VatSummaryOut,
} from "@shared/models";

export type VatSummary = VatSummaryOut;
export type VatMove = VatMoveOut;
/** A red / unknown inbound e-invoice whose VAT credit is not (fully) confirmed yet (20 #1, US-M10-03). */
export type PendingCreditInvoice = PendingCreditInvoiceOut;
export type { VatMovePage };
export type MoveKind = Exclude<ListVatMovesKind, null>;
export type MoveDocType = Exclude<ListVatMovesDocType, null>;

export const MOVE_KINDS: readonly MoveKind[] = ["output", "input"];
/** 20 #2 `doc_type` filter (vat_moves sources). */
export const MOVE_DOC_TYPES: readonly MoveDocType[] = [
  "sales",
  "returns",
  "goods_receipts",
  "supplier_returns",
  "write_offs",
  "supplier_payments",
];

export type LoadStatus = "idle" | "loading" | "error";

/**
 * 07 BO-07 `period`: a month `YYYY-MM` or a quarter `YYYY-Qn` — the API answers monthly only, a quarter
 * is summed on the client from its three months.
 */
export type PeriodKey = string;

/** The page's summary: one month as returned, or the client-side sum of a quarter's months. */
export interface SummaryView {
  period: PeriodKey;
  /** Months included (1 or 3). */
  months: readonly string[];
  regime: VatSummary["regime"];
  outputVat: string | null;
  inputVat: string | null;
  netVat: string | null;
  pendingRedInvoices: number | null;
  /** «Riskli kiruvchi e-fakturalar»: the period's red / unknown invoices with VAT still pending (all months). */
  pendingCreditInvoices: readonly PendingCreditInvoice[];
  /** Σ `pending_vat` of those invoices — «Kutilayotgan QQS krediti» (`null` — not a VAT payer). */
  pendingCreditTotal: string | null;
  /** Share of the period's input VAT (only for a single month — not additive). */
  pendingCreditPct: string | null;
  turnoverBase: string | null;
  turnoverRatePct: string | null;
  turnoverAmount: string | null;
  /** A month of the quarter had another regime (the sum shows the last month's regime only). */
  mixedRegime: boolean;
  taxSettlementId: string | null;
}

export interface MovesFilters {
  kind: MoveKind | null;
  docType: MoveDocType | null;
}

export interface MovesRequest {
  months: readonly string[];
  /** Index of the month in `months` being read. */
  monthIndex: number;
  filters: MovesFilters;
  cursor: string | null;
}

export const MOVES_PAGE_SIZE = 50;
/** 26 — the red-invoice credit share limit shown on the «Kutilayotgan QQS krediti» card (VM 830). */
export const PENDING_CREDIT_LIMIT_PCT = "10.00";

export interface VatMountParams {
  /** Local date `YYYY-MM-DD` — the default period is the current month. */
  today: string;
}
