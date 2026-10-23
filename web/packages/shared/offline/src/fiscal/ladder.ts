/**
 * 48 h fiscal ladder — 16 §6 (qaror #43), 24 §5. Timer = `created_at` of the OLDEST fiscal receipt of
 * this cash register without `ofd_acked_at`: the local outbox (sale/return/debt_payment events with a
 * receipt_seq) and the server's `cash_registers.last_unacked_receipt_at` (fiscal pull scope), whichever
 * is older. Time is the trusted monotonic clock (16 §8). At 48 h new fiscal documents are refused
 * locally (`enqueueEvent` → FISCAL_OFFLINE_48H_BLOCKED); sync keeps working.
 */
import Dexie from "dexie";
import { createEvent, createStore } from "effector";

import { deviceIdentity } from "../device-settings.ts";
import { observeTime, trustedNow } from "../lib/clock.ts";
import { now, posDb } from "../runtime.ts";

export const OFFLINE_WARN_HOURS = [24, 40, 46] as const;
export const OFFLINE_BLOCK_HOURS = 48;
const HOUR_MS = 60 * 60 * 1000;

export type FiscalLadderLevel = "ok" | "warn24" | "red40" | "modal46" | "blocked48";

export interface FiscalLadder {
  level: FiscalLadderLevel;
  oldestUnackedAt: string | null;
  /** Elapsed hours since the oldest unacked receipt (fractional; 0 when none). */
  hours: number;
}

export const FISCAL_LADDER_OK: FiscalLadder = { level: "ok", oldestUnackedAt: null, hours: 0 };

/** Pure: level for an oldest-unacked timestamp at `nowMs`. */
export function fiscalLadderLevel(oldestIso: string | null, nowMs: number): FiscalLadderLevel {
  if (oldestIso === null) return "ok";
  const started = Date.parse(oldestIso);
  if (Number.isNaN(started)) return "ok";
  const hours = (nowMs - started) / HOUR_MS;
  if (hours >= OFFLINE_BLOCK_HOURS) return "blocked48";
  if (hours >= OFFLINE_WARN_HOURS[2]) return "modal46";
  if (hours >= OFFLINE_WARN_HOURS[1]) return "red40";
  if (hours >= OFFLINE_WARN_HOURS[0]) return "warn24";
  return "ok";
}

function older(a: string | null, b: string | null): string | null {
  if (a === null) return b;
  if (b === null) return a;
  return Date.parse(a) <= Date.parse(b) ? a : b;
}

/** Oldest unacked fiscal receipt of the device's cash register (null = none). */
export async function oldestUnackedReceiptAt(): Promise<string | null> {
  const identity = await deviceIdentity.get();
  const register = identity?.cashRegisterId ?? null;
  const db = posDb();
  const local = await db.outbox
    .where("[fiscal_unacked+created_at]")
    .between([1, Dexie.minKey], [1, Dexie.maxKey])
    .filter((row) => register === null || row.cash_register_id === null || row.cash_register_id === register)
    .first();
  let server: string | null = null;
  if (register !== null) {
    const row = await db.fiscal.get(register);
    server = row?.last_unacked_receipt_at ?? null;
  }
  return older(local?.created_at ?? null, server);
}

export async function computeFiscalLadder(): Promise<FiscalLadder> {
  const oldest = await oldestUnackedReceiptAt();
  const nowMs = await trustedNow();
  const level = fiscalLadderLevel(oldest, nowMs);
  const hours = oldest === null ? 0 : Math.max(0, (nowMs - Date.parse(oldest)) / HOUR_MS);
  return { level, oldestUnackedAt: oldest, hours };
}

export const fiscalLadderUpdated = createEvent<FiscalLadder>();
export const $fiscalLadder = createStore<FiscalLadder>(FISCAL_LADDER_OK).on(fiscalLadderUpdated, (_, v) => v);

/** Recomputes `$fiscalLadder` (after enqueue / push / pull, and every 60 s by the engine). */
export async function refreshFiscalLadder(): Promise<FiscalLadder> {
  await observeTime(now()); // keep the trusted clock monotonic even without server contact
  const ladder = await computeFiscalLadder();
  fiscalLadderUpdated(ladder);
  return ladder;
}
