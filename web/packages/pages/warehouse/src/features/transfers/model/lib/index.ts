import type { ListTransfersParams } from "@shared/models";

import {
  compareQty,
  isDecimal,
  lineValue,
  subtractQty,
  sumMoney,
  sumQty,
  trimQty,
} from "#/shared/lib/decimal.ts";

import {
  TRANSFER_PAGE_SIZE,
  TRANSFER_STATUSES,
  type EttnView,
  type ListRequest,
  type Transfer,
  type TransferAction,
  type TransferLine,
  type TransferStatus,
} from "../types/index.ts";

export function toQuery({ status, cursor }: ListRequest): ListTransfersParams {
  return {
    ...(status ? { status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: TRANSFER_PAGE_SIZE,
  };
}

export function isTransferStatus(value: string | null): value is TransferStatus {
  return value !== null && (TRANSFER_STATUSES as readonly string[]).includes(value);
}

/** 07 BO-03 e-TTN column: on foot / public transport → «talab qilinmaydi» (qaror #63). */
export function ettnViewOf(t: Pick<Transfer, "transport_mode" | "ettn">): EttnView {
  if (t.transport_mode === "on_foot_or_public") return "not_required";
  return t.ettn?.status ?? "none";
}

/** «Jo'natish» only when the e-TTN is registered or none is required (19 §13 `send`, 409 ETTN_REQUIRED). */
export function isSendReady(t: Pick<Transfer, "status" | "transport_mode" | "ettn">): boolean {
  return (
    t.status === "posted" && (t.transport_mode === "on_foot_or_public" || t.ettn?.status === "registered")
  );
}

/** Posted vehicle transfer still waiting for its e-TTN (signing/registration is Bosqich 5 in the UI). */
export function isWaitingForEttn(t: Pick<Transfer, "status" | "transport_mode" | "ettn">): boolean {
  return t.status === "posted" && !isSendReady(t);
}

export interface TransferRights {
  create: boolean;
  receive: boolean;
  /** Branches of the user (receiving side check — the destination must be one of them). */
  branchIds: readonly string[];
}

export function actionsOf(t: Transfer, rights: TransferRights): TransferAction[] {
  const out: TransferAction[] = [];
  if (rights.create && t.status === "draft") out.push("post");
  if (rights.create && isSendReady(t)) out.push("send");
  if (rights.receive && t.status === "sent" && rights.branchIds.includes(t.to_branch_id)) out.push("receive");
  if (rights.create && (t.status === "draft" || t.status === "posted" || t.status === "sent")) {
    out.push("cancel");
  }
  return out;
}

/** Σ qty_sent × unit_cost — known once sent (unit_cost is set on send, 19 §13); `null` before. */
export function transferValue(t: Pick<Transfer, "lines">): string | null {
  if (t.lines.length === 0 || t.lines.some((l) => l.unit_cost === null)) return null;
  return sumMoney(t.lines.map((l) => lineValue(l.qty_sent, l.unit_cost ?? "0")));
}

/** Σ (sent − received) of received lines — the shortage of a `discrepancy` transfer. */
export function shortageOf(lines: readonly TransferLine[]): string {
  return sumQty(lines.map((l) => (l.qty_received === null ? "0" : subtractQty(l.qty_sent, l.qty_received))));
}

/** Receive dialog defaults: everything arrived (qty_received = qty_sent). */
export function receiveDefaults(t: Pick<Transfer, "lines">): Record<string, string> {
  return Object.fromEntries(t.lines.map((l) => [l.id, trimQty(l.qty_sent)]));
}

/** `0 ≤ received ≤ sent` per line (19 §13 receive validation, else 422). */
export function receiveLineError(sent: string, received: string): "required" | "range" | null {
  if (!isDecimal(received)) return "required";
  if (compareQty(received, "0") < 0 || compareQty(received, sent) > 0) return "range";
  return null;
}

export function replaceTransfer(list: readonly Transfer[], t: Transfer): Transfer[] {
  return list.some((x) => x.id === t.id) ? list.map((x) => (x.id === t.id ? t : x)) : [t, ...list];
}

/** Badge of the tab (07 BO-03): in transit, of which overdue. */
export function transitCounts(list: readonly Pick<Transfer, "status" | "is_overdue">[]): {
  inTransit: number;
  overdue: number;
} {
  const sent = list.filter((t) => t.status === "sent");
  return { inTransit: sent.length, overdue: sent.filter((t) => t.is_overdue).length };
}
