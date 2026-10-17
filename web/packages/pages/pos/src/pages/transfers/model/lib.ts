/**
 * POS-09 pure logic (07 POS-09, 19 §13): the send form (lines added by scanning, −/+ qty, source balance
 * warning), the `transfer.sent` / `transfer.received` payloads, validation, and the device history built from
 * the outbox. Decimal strings only.
 */
import type { TransferOut } from "@shared/models";

import {
  addQty,
  compareQty,
  isPositiveQty,
  qty3,
  sumQty,
  type ScannedProduct,
} from "#/features/wh-scan/index.ts";

export const TRANSFER_SENT = "transfer.sent";
export const TRANSFER_RECEIVED = "transfer.received";
export const PLATE_MAX = 16;

export type TransportMode = "vehicle" | "on_foot_or_public";

export interface SendLine {
  productId: string;
  name: string;
  qty: string;
  /** Balance in the source warehouse (local stock scope), null = unknown. */
  available: string | null;
  markingCodes: string[];
}

export interface SendForm {
  fromWarehouseId: string | null;
  toWarehouseId: string | null;
  lines: SendLine[];
  transportMode: TransportMode;
  vehiclePlate: string;
  driverName: string;
}

export const EMPTY_FORM: SendForm = {
  fromWarehouseId: null,
  toWarehouseId: null,
  lines: [],
  transportMode: "vehicle",
  vehiclePlate: "",
  driverName: "",
};

export type SendFieldError = "to_required" | "same_warehouse" | "no_lines" | "plate_required" | "qty_invalid";

/** Scan → add a line or increment it (marking codes are counted, never twice). */
export function addScanned(lines: readonly SendLine[], item: ScannedProduct): SendLine[] {
  const i = lines.findIndex((l) => l.productId === item.productId);
  if (i === -1) {
    return [
      ...lines,
      {
        productId: item.productId,
        name: item.name,
        qty: qty3(item.qty),
        available: null,
        markingCodes: item.markingCode ? [item.markingCode] : [],
      },
    ];
  }
  return lines.map((l, j) => {
    if (j !== i) return l;
    if (item.markingCode && l.markingCodes.includes(item.markingCode)) return l;
    return {
      ...l,
      qty: addQty(l.qty, item.qty),
      markingCodes: item.markingCode ? [...l.markingCodes, item.markingCode] : l.markingCodes,
    };
  });
}

export function setLineQty(lines: readonly SendLine[], productId: string, qty: string): SendLine[] {
  return lines.map((l) => (l.productId === productId ? { ...l, qty } : l));
}

export function setAvailable(lines: readonly SendLine[], productId: string, qty: string | null): SendLine[] {
  return lines.map((l) => (l.productId === productId ? { ...l, available: qty } : l));
}

/** «… kam — davom etish mumkin» (overselling only warns, 07 POS-09). */
export function isShort(line: Pick<SendLine, "qty" | "available">): boolean {
  return line.available !== null && isPositiveQty(line.qty) && compareQty(line.qty, line.available) > 0;
}

export function sendErrors(form: SendForm): SendFieldError[] {
  const out: SendFieldError[] = [];
  if (!form.toWarehouseId) out.push("to_required");
  else if (form.toWarehouseId === form.fromWarehouseId) out.push("same_warehouse");
  if (form.lines.length === 0) out.push("no_lines");
  if (form.lines.some((l) => !isPositiveQty(l.qty))) out.push("qty_invalid");
  if (form.transportMode === "vehicle" && !form.vehiclePlate.trim()) out.push("plate_required");
  return out;
}

export function totalsOf(lines: readonly SendLine[]): { lines: number; qty: string; marking: number } {
  return {
    lines: lines.length,
    qty: sumQty(lines.filter((l) => isPositiveQty(l.qty)).map((l) => l.qty)),
    marking: lines.reduce((n, l) => n + l.markingCodes.length, 0),
  };
}

/** 19 §13 `transfer.sent` — new document (UUIDv7 ids made on the device). */
export function sentPayload(
  form: SendForm,
  ids: { id: string; lineId: () => string; tempNumber: string },
  docDate: string,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    id: ids.id,
    temp_number: ids.tempNumber,
    doc_date: docDate,
    from_warehouse_id: form.fromWarehouseId,
    to_warehouse_id: form.toWarehouseId,
    transport_mode: form.transportMode,
    lines: form.lines.map((l) => ({ line_id: ids.lineId(), product_id: l.productId, qty_sent: qty3(l.qty) })),
  };
  if (form.transportMode === "vehicle") payload.vehicle_plate = form.vehiclePlate.trim().slice(0, PLATE_MAX);
  return payload;
}

/** REST `POST /transfers` body of «O'tkazish» (online). */
export function createBody(form: SendForm, docDate: string) {
  return {
    from_warehouse_id: form.fromWarehouseId ?? "",
    to_warehouse_id: form.toWarehouseId ?? "",
    doc_date: docDate,
    transport_mode: form.transportMode,
    vehicle_plate: form.transportMode === "vehicle" ? form.vehiclePlate.trim().slice(0, PLATE_MAX) : null,
    driver_name: form.driverName.trim() || null,
    lines: form.lines.map((l) => ({ product_id: l.productId, qty_sent: qty3(l.qty) })),
  };
}

/** Receive defaults: everything arrived (qty_received = qty_sent). */
export function receiveDefaults(t: Pick<TransferOut, "lines">): Record<string, string> {
  return Object.fromEntries(t.lines.map((l) => [l.id, l.qty_sent]));
}

/** `0 ≤ received ≤ sent` (19 §13; more → separate goods receipt). */
export function receiveLineError(sent: string, received: string): "required" | "range" | null {
  if (received.trim() === "" || qty3(received) === "") return "required";
  if (compareQty(received, "0") < 0 || compareQty(received, sent) > 0) return "range";
  return null;
}

export function receivedPayload(t: Pick<TransferOut, "id" | "lines">, qty: Record<string, string>) {
  return {
    transfer_id: t.id,
    lines: t.lines.map((l) => ({ transfer_line_id: l.id, qty_received: qty3(qty[l.id] ?? l.qty_sent) })),
  };
}

/** `posted` and the e-TTN registered (or none needed) → «Jo'natish» (19 §13 `send`). */
export function isSendReady(t: Pick<TransferOut, "status" | "transport_mode" | "ettn">): boolean {
  return (
    t.status === "posted" && (t.transport_mode === "on_foot_or_public" || t.ettn?.status === "registered")
  );
}

/** Minimal outbox row (structurally `OutboxRow`). */
export interface TransferEventRow {
  client_event_id: string;
  type: string;
  status: string;
  retryable: boolean | null;
  created_at: string;
  payload: Record<string, unknown>;
  server: Record<string, unknown> | null;
  warnings: string[];
  error_code: string | null;
  message: string | null;
}

export interface HistoryItem {
  clientEventId: string;
  kind: "sent" | "received";
  createdAt: string;
  transferId: string | null;
  number: string | null;
  status: string | null;
  sync: "pending" | "accepted" | "rejected";
  lines: number;
  warnings: string[];
  errorCode: string | null;
  message: string | null;
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

export function historyFromOutbox(rows: readonly TransferEventRow[]): HistoryItem[] {
  return rows
    .filter((r) => r.type === TRANSFER_SENT || r.type === TRANSFER_RECEIVED)
    .map((r) => {
      const server = r.server ?? {};
      const lines = Array.isArray(r.payload.lines) ? r.payload.lines.length : 0;
      return {
        clientEventId: r.client_event_id,
        kind: r.type === TRANSFER_SENT ? ("sent" as const) : ("received" as const),
        createdAt: r.created_at,
        transferId: str(server.id) ?? str(r.payload.id) ?? str(r.payload.transfer_id),
        number: str(server.number) ?? str(r.payload.temp_number),
        status: str(server.status),
        sync:
          r.status === "accepted" || r.status === "duplicate"
            ? ("accepted" as const)
            : r.status === "rejected"
              ? ("rejected" as const)
              : ("pending" as const),
        lines,
        warnings: r.warnings,
        errorCode: r.error_code,
        message: r.message,
      };
    })
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

/** Transfers already received on this device (pending events too) — hidden from the incoming list. */
export function locallyReceivedIds(rows: readonly TransferEventRow[]): Set<string> {
  const out = new Set<string>();
  for (const r of rows) {
    if (r.type !== TRANSFER_RECEIVED) continue;
    if (r.status === "rejected" && r.retryable !== true) continue;
    const id = str(r.payload.transfer_id);
    if (id) out.add(id);
  }
  return out;
}
