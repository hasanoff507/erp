/**
 * enqueueEvent — 16 §2 (event format), §3.3 (receipt_seq given by the device inside the same lock as
 * seq), §11 (Web Lock "erp-outbox-writer"), §2.1 (approved card attempts leave card_attempts in the
 * same Dexie transaction the event enters the outbox), §6 (48 h block), §7 (offline-sold marking codes).
 */
import { validate as uuidValidate, version as uuidVersion, v7 as uuidv7 } from "uuid";

import { META } from "../db/meta.ts";
import { deviceIdentity, readCounterFloors } from "../device-settings.ts";
import { outboxChanged } from "../events.ts";
import { computeFiscalLadder, refreshFiscalLadder } from "../fiscal/ladder.ts";
import { runBackground } from "../lib/background.ts";
import { broadcast } from "../lib/broadcast.ts";
import { OfflineError } from "../lib/errors.ts";
import { OUTBOX_WRITER_LOCK, withLock } from "../lib/locks.ts";
import { trustedNow } from "../lib/clock.ts";
import { triggerCounters, triggerPush } from "../lib/triggers.ts";
import { now, posDb } from "../runtime.ts";
import {
  FISCAL_EVENT_TYPES,
  OUTBOX_EVENT_TYPES,
  type OutboxEventType,
  type OutboxRow,
  type SalesHistoryInput,
} from "../types.ts";

export interface EnqueueOptions {
  /**
   * Pre-allocated UUIDv7 (e.g. the card flow recorded the attempt with it before the sale, 16 §2.1).
   * Used instead of a new id; an id already in the outbox is refused (VALIDATION_ERROR, nothing written).
   */
  clientEventId?: string;
  /** The cashier who did it (local PIN, 14 §4.3) — not the session user. */
  actorUserId: string;
  /**
   * Fiscal receipt of this (cash register, shift): the device assigns `payload.receipt_seq`.
   * `count: 2` (SYNC-09, `fiscal_policy.credit_sale_receipt=credit_type` + a debt part) allocates the
   * next number too, written to `payload.credit_receipt_seq` — both inside the same Web Lock.
   * `target: "credit_receipt_seq"` (count 1 only — debt-only sale under `credit_type`): the single number
   * goes to `payload.credit_receipt_seq`, `payload.receipt_seq` stays as given (null).
   */
  receiptSeq?: {
    cashRegisterId: string;
    shiftId: string;
    count?: 1 | 2;
    target?: "receipt_seq" | "credit_receipt_seq";
  };
  /** 16 §2.1: approved attempts whose result is inside this event — deleted in the same transaction. */
  removeCardAttemptIds?: string[];
  /** 16 §7: marking codes sold offline → local cache `pending_verification` (duplicate check). */
  markingCodes?: string[];
  /** Local 90-day receipt history row (16 §10). */
  history?: SalesHistoryInput;
}

export interface EnqueueResult {
  clientEventId: string;
  seq: number;
  receiptSeq: number | null;
  /** Second device receipt number (`receiptSeq.count: 2`), else null. */
  creditReceiptSeq: number | null;
  createdAt: string;
}

const KNOWN_TYPES: ReadonlySet<string> = new Set(OUTBOX_EVENT_TYPES);

function payloadReceiptSeq(payload: Record<string, unknown>): number | null {
  const value = payload.receipt_seq;
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

function isFiscalDoc(type: OutboxEventType, payload: Record<string, unknown>, opts: EnqueueOptions): boolean {
  return (
    FISCAL_EVENT_TYPES.has(type) && (opts.receiptSeq !== undefined || payloadReceiptSeq(payload) !== null)
  );
}

export async function enqueueEvent(
  type: OutboxEventType,
  payload: Record<string, unknown>,
  opts: EnqueueOptions,
): Promise<EnqueueResult> {
  if (!KNOWN_TYPES.has(type)) throw new OfflineError("UNKNOWN_EVENT_TYPE", { type });
  if (!opts.actorUserId) throw new OfflineError("VALIDATION_ERROR", { field: "actorUserId" });
  if (
    opts.clientEventId !== undefined &&
    !(uuidValidate(opts.clientEventId) && uuidVersion(opts.clientEventId) === 7)
  ) {
    throw new OfflineError("VALIDATION_ERROR", { field: "clientEventId", reason: "not_uuid_v7" });
  }

  const result = await withLock(OUTBOX_WRITER_LOCK, async () => {
    if (
      opts.clientEventId !== undefined &&
      (await posDb().outbox.where("client_event_id").equals(opts.clientEventId).count()) > 0
    ) {
      throw new OfflineError("VALIDATION_ERROR", { field: "clientEventId", reason: "duplicate" });
    }
    const identity = await deviceIdentity.get();
    if (!identity) throw new OfflineError("DEVICE_NOT_REGISTERED");
    if ((await posDb().meta.get(META.deviceRevoked))?.value === true)
      throw new OfflineError("DEVICE_REVOKED");

    if (isFiscalDoc(type, payload, opts)) {
      const ladder = await computeFiscalLadder();
      if (ladder.level === "blocked48") {
        throw new OfflineError("FISCAL_OFFLINE_48H_BLOCKED", { oldest_unacked_at: ladder.oldestUnackedAt });
      }
    }

    // SYNC-08: fiscal documents carry the trusted (monotonic, server-anchored) time — the 48 h timer
    // is computed on the same clock; the server clamps it anyway (16 §8).
    const fiscalDoc = isFiscalDoc(type, payload, opts);
    const createdAt = new Date(fiscalDoc ? await trustedNow() : now()).toISOString();
    const floors = await readCounterFloors();
    const db = posDb();
    return db.transaction(
      "rw",
      [db.meta, db.outbox, db.card_attempts, db.marking_codes, db.sales_history],
      async () => {
        const lastSeq = ((await db.meta.get(META.seq))?.value as number | undefined) ?? 0;
        const seq = Math.max(lastSeq, floors.seq) + 1;
        await db.meta.put({ key: META.seq, value: seq });

        let receiptSeq: number | null = payloadReceiptSeq(payload);
        let creditReceiptSeq: number | null = null;
        if (opts.receiptSeq) {
          const key = META.receiptSeq(opts.receiptSeq.cashRegisterId, opts.receiptSeq.shiftId);
          const last = ((await db.meta.get(key))?.value as number | undefined) ?? 0;
          const first = Math.max(last, floors.receiptSeq[key] ?? 0) + 1;
          if (opts.receiptSeq.count === 2) {
            receiptSeq = first;
            creditReceiptSeq = first + 1;
          } else if (opts.receiptSeq.target === "credit_receipt_seq") {
            creditReceiptSeq = first;
          } else {
            receiptSeq = first;
          }
          await db.meta.put({ key, value: creditReceiptSeq ?? first });
        }

        const removeIds = opts.removeCardAttemptIds ?? [];
        if (removeIds.length > 0) {
          const attempts = await db.card_attempts.bulkGet(removeIds);
          attempts.forEach((attempt, i) => {
            if (!attempt || attempt.status !== "approved") {
              throw new OfflineError("CARD_OUTCOME_UNKNOWN", {
                attempt_id: removeIds[i],
                status: attempt?.status ?? null,
              });
            }
          });
          await db.card_attempts.bulkDelete(removeIds);
        }

        const clientEventId = opts.clientEventId ?? uuidv7();
        const finalPayload: Record<string, unknown> =
          opts.receiptSeq && opts.receiptSeq.target !== "credit_receipt_seq"
            ? { ...payload, receipt_seq: receiptSeq }
            : { ...payload };
        if (creditReceiptSeq !== null) finalPayload.credit_receipt_seq = creditReceiptSeq;
        const fiscal = FISCAL_EVENT_TYPES.has(type) && (receiptSeq !== null || creditReceiptSeq !== null);
        const shiftId =
          opts.receiptSeq?.shiftId ?? (typeof payload.shift_id === "string" ? payload.shift_id : null);
        const row: OutboxRow = {
          client_event_id: clientEventId,
          device_id: identity.deviceId,
          seq,
          type,
          created_at: createdAt,
          actor_user_id: opts.actorUserId,
          payload: finalPayload,
          status: "pending",
          error_code: null,
          message: null,
          retryable: null,
          warnings: [],
          server: null,
          attempts: 0,
          last_attempt_at: null,
          next_attempt_at: 0,
          result_at: null,
          receipt_seq: receiptSeq,
          cash_register_id: opts.receiptSeq?.cashRegisterId ?? identity.cashRegisterId,
          shift_id: shiftId,
          fiscal,
          ofd_acked_at: null,
          fiscal_unacked: fiscal ? 1 : 0,
          unsynced: 1,
          escalated: 0,
        };
        await db.outbox.add(row);

        const codes = opts.markingCodes ?? [];
        if (codes.length > 0) {
          await db.marking_codes.bulkPut(
            codes.map((code) => ({
              id: `local:${code}`,
              code,
              status: "pending_verification",
              client_event_id: clientEventId,
            })),
          );
        }
        if (opts.history) {
          await db.sales_history.put({
            ...opts.history,
            client_event_id: clientEventId,
            created_at: createdAt,
            cash_register_id: row.cash_register_id,
            shift_id: row.shift_id,
            receipt_seq: receiptSeq,
          });
        }
        return { clientEventId, seq, receiptSeq, creditReceiptSeq, createdAt };
      },
    );
  });

  outboxChanged();
  triggerCounters();
  broadcast({ type: "outbox-changed" });
  if (FISCAL_EVENT_TYPES.has(type)) runBackground(refreshFiscalLadder);
  triggerPush();
  return result;
}
