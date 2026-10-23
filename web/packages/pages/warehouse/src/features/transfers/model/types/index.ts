import type { ApiError } from "@shared/api";
import type {
  EttnOutStatus,
  ReceiveLineIn,
  TransferCreate,
  TransferLineOut,
  TransferOut,
  TransferOutStatus,
  TransferPage,
} from "@shared/models";

export type Transfer = TransferOut;
export type TransferLine = TransferLineOut;
export type TransferStatus = TransferOutStatus;
export type EttnStatus = EttnOutStatus;
export type { TransferCreate, TransferPage, ReceiveLineIn };

/** 19 §13 statuses in list-filter order. */
export const TRANSFER_STATUSES: readonly TransferStatus[] = [
  "draft",
  "posted",
  "sent",
  "received",
  "discrepancy",
  "cancelled",
];

/** e-TTN column (07 BO-03): an operator status, «talab qilinmaydi» (on foot) or none yet (draft). */
export type EttnView = EttnStatus | "not_required" | "none";

export type LoadStatus = "idle" | "loading" | "error";

export interface ListRequest {
  status: TransferStatus | null;
  cursor: string | null;
}

export interface CreateTransferParams {
  body: TransferCreate;
  /** «O'tkazish» right after creating (POST /transfers → /post), else the draft is kept. */
  post: boolean;
}

export interface CreateTransferResult {
  transfer: Transfer;
  /** Set when the draft was created but `post` was refused (422 NEGATIVE_STOCK_NOT_ALLOWED, …). */
  postError: ApiError | null;
}

export interface ReceiveParams {
  id: string;
  lines: ReceiveLineIn[];
}

export interface CancelParams {
  id: string;
  reason: string;
}

/** Row actions (07 BO-03 «Ko'chirishlar»): permission + state decide which are offered. */
export type TransferAction = "post" | "send" | "receive" | "cancel";

export const TRANSFER_PAGE_SIZE = 50;
/** 07 BO-03 «vehiclePlate» max 16. */
export const VEHICLE_PLATE_MAX = 16;
