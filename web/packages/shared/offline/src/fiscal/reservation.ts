/**
 * Local-bridge receipt numbers (B5; 21 §16, 18 §4.1, 16 §3.3, qaror #12/#68). In the local-bridge mode the FM
 * signs the receipt BEFORE the event enters the outbox (card approval → fiscal receipt → `sale.created`), so the
 * device number `receipt_seq` is taken first — from the same per-(cash register, shift) counter and under the
 * same Web Lock `enqueueEvent` uses — and the event later carries it in `payload.receipt_seq` together with the
 * FM's `fiscal_result`.
 *
 * The reservation is remembered per document (`ref` — the draft / payment id) with a hash of the signed
 * request: a retry of the SAME request reuses the number (the agent journal answers it without a second
 * signature); a signed result whose event was not written yet is reused as is. A changed request after a
 * signature is refused (`FISCAL_RESULT_PENDING`) — the FM already holds a receipt for this document.
 */
import { deviceIdentity, readCounterFloors } from "../device-settings.ts";
import { META } from "../db/meta.ts";
import { computeFiscalLadder } from "./ladder.ts";
import { OfflineError } from "../lib/errors.ts";
import { OUTBOX_WRITER_LOCK, withLock } from "../lib/locks.ts";
import { posDb } from "../runtime.ts";

export interface FiscalReservation {
  ref: string;
  cash_register_id: string;
  shift_id: string;
  receipt_seq: number;
  /** Canonical JSON of the request the FM is asked to sign (without nothing volatile). */
  request: string;
  /** The FM answer once signed (18 §4.1 `fiscal_result`), else null. */
  result: Record<string, unknown> | null;
}

const key = (ref: string) => `fiscal.pending:${ref}`;

async function read(ref: string): Promise<FiscalReservation | undefined> {
  return (await posDb().meta.get(key(ref)))?.value as FiscalReservation | undefined;
}

/**
 * The `receipt_seq` for `ref`: the remembered one when the request is the same, else the next number of
 * (cash register, shift). 48 h block (16 §6) is checked like `enqueueEvent` does.
 */
export async function reserveReceiptSeq(input: {
  ref: string;
  cashRegisterId: string;
  shiftId: string;
  request: string;
}): Promise<FiscalReservation> {
  return withLock(OUTBOX_WRITER_LOCK, async () => {
    const identity = await deviceIdentity.get();
    if (!identity) throw new OfflineError("DEVICE_NOT_REGISTERED");
    const existing = await read(input.ref);
    if (
      existing &&
      existing.cash_register_id === input.cashRegisterId &&
      existing.shift_id === input.shiftId
    ) {
      if (existing.request === input.request) return existing;
      if (existing.result) {
        throw new OfflineError("FISCAL_RESULT_PENDING", { receipt_seq: existing.receipt_seq });
      }
    }
    const ladder = await computeFiscalLadder();
    if (ladder.level === "blocked48") {
      throw new OfflineError("FISCAL_OFFLINE_48H_BLOCKED", { oldest_unacked_at: ladder.oldestUnackedAt });
    }
    const floors = await readCounterFloors();
    const db = posDb();
    return db.transaction("rw", db.meta, async () => {
      const counter = META.receiptSeq(input.cashRegisterId, input.shiftId);
      const last = ((await db.meta.get(counter))?.value as number | undefined) ?? 0;
      const next = Math.max(last, floors.receiptSeq[counter] ?? 0) + 1;
      await db.meta.put({ key: counter, value: next });
      const row: FiscalReservation = {
        ref: input.ref,
        cash_register_id: input.cashRegisterId,
        shift_id: input.shiftId,
        receipt_seq: next,
        request: input.request,
        result: null,
      };
      await db.meta.put({ key: key(input.ref), value: row });
      return row;
    });
  });
}

/** Remembers the FM answer of a reservation (before the event is written). */
export async function rememberFiscalResult(ref: string, result: Record<string, unknown>): Promise<void> {
  const db = posDb();
  await db.transaction("rw", db.meta, async () => {
    const row = (await db.meta.get(key(ref)))?.value as FiscalReservation | undefined;
    if (row) await db.meta.put({ key: key(ref), value: { ...row, result } });
  });
}

/** The event with this reservation is in the outbox — forget it. */
export async function releaseReservation(ref: string): Promise<void> {
  await posDb().meta.delete(key(ref));
}

export const fiscalReservations = { get: read, release: releaseReservation, remember: rememberFiscalResult };
