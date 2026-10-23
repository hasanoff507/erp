/**
 * Shift figures for POS-07 / POS-14 / POS-15: the local computation over this shift's outbox events and
 * local receipt history (works offline, 16 §1) and — online, when nothing of the shift is still unsynced —
 * the server's `running_totals` (`GET /shifts/{id}`, 18 §3.3) for `expected_cash`.
 */
import { api } from "@shared/api";
import type { RunningTotals } from "@shared/models";
import { money, type Money } from "@shared/lib/money";
import { outbox, salesHistory, type OutboxRow, type SalesHistoryRow } from "@shared/offline";

import { countsLocally, eventShiftId, localShiftTotals, type LocalShiftTotals } from "../lib/index.ts";

export interface ShiftDataDeps {
  events(): Promise<OutboxRow[]>;
  history(): Promise<SalesHistoryRow[]>;
  runningTotals(shiftId: string): Promise<RunningTotals | null>;
  isOnline(): boolean;
}

export interface ShiftSnapshot {
  totals: LocalShiftTotals;
  /** Events of this shift not yet accepted by the server. */
  unsynced: number;
  /** `running_totals` when the server view is complete (online, nothing unsynced). */
  server: RunningTotals | null;
  /** The expected cash the screens show (server when complete, else local). */
  expectedCash: Money;
  /** POS-07 «Fiskal holat»: fiscal receipts of the shift, OFD-acknowledged, not yet sent (oldest). */
  fiscal: { total: number; acked: number; unsent: number; oldestUnsentAt: string | null };
}

export const SERVER_WAIT_MS = 3_000;

export const defaultShiftDataDeps = (isOnline: () => boolean): ShiftDataDeps => ({
  events: () => outbox.list({ limit: 5000 }),
  history: () => salesHistory.list({ limit: 2000 }),
  runningTotals: async (shiftId) => (await api.cash.getShift(shiftId)).running_totals ?? null,
  isOnline,
});

export async function loadShiftSnapshot(
  deps: ShiftDataDeps,
  shift: { id: string; opening_cash?: string | null },
): Promise<ShiftSnapshot> {
  const all = await deps.events();
  const events = all.filter((e) => eventShiftId(e) === shift.id);
  const history = (await deps.history()).filter((h) => h.shift_id === shift.id || h.shift_id === null);
  const totals = localShiftTotals(shift.opening_cash ?? "0.00", events, history);
  const unsynced = events.filter(
    (e) => e.status === "pending" || (e.status === "rejected" && countsLocally(e)),
  ).length;
  let server: RunningTotals | null = null;
  if (deps.isOnline() && unsynced === 0) {
    try {
      // never block the cashier on the network: no answer in 3 s → the local figures stand
      server = await Promise.race([
        deps.runningTotals(shift.id),
        new Promise<null>((resolve) => setTimeout(() => resolve(null), SERVER_WAIT_MS)),
      ]);
    } catch {
      server = null;
    }
  }
  const fiscalRows = events.filter((e) => e.fiscal && countsLocally(e));
  const unsentRows = fiscalRows.filter((e) => e.status === "pending" || e.status === "rejected");
  const fiscal = {
    total: fiscalRows.length,
    acked: fiscalRows.filter((e) => e.ofd_acked_at !== null).length,
    unsent: unsentRows.length,
    oldestUnsentAt: unsentRows.map((e) => e.created_at).sort()[0] ?? null,
  };
  return {
    totals,
    unsynced,
    server,
    fiscal,
    expectedCash: server ? money(server.expected_cash) : totals.expectedCash,
  };
}
