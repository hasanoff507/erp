/**
 * POS-07 — Smena yopish, Z-hisobot (07 POS-07; 18 §3.2, §3.3, §16a.6; 16 §2.1; US-M01-04, US-M16-02/-03;
 * QT-M01-06/-07). Closing is refused while a card attempt of this register is unresolved
 * (CARD_OUTCOME_UNKNOWN); every integrated terminal bound to the register is settled first (the result
 * travels in `shift.closed.card_settlements[]`); then ONE `shift.closed` goes to the outbox. The Z-report is
 * the push result `server.z_report` (online) or the local figures (offline, «OFD'ga keyin yuboriladi»), later
 * `GET /shifts/{id}/z-report`.
 */
import { createEffect } from "effector";

import { api } from "@shared/api";
import type { ZReport, ZReportOut } from "@shared/models";
import {
  terminalRef,
  type CardTerminalClient,
  type SettlementResult,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import { fromTiyin, money, type Money } from "@shared/lib/money";
import type { ReceiptDoc } from "@shared/lib/receipt";
import {
  awaitEventResult,
  cardAttempts,
  deviceSettings,
  enqueueEvent,
  shift as localShift,
  type PushResultEntry,
} from "@shared/offline";

import {
  uuidv7,
  type LocalShiftTotals,
  type PosShift,
  type ShiftCount,
} from "#/entities/pos-session/index.ts";

export const LAST_COUNTED_CASH_KEY = "pos.last_counted_cash";
export const CLOSED_SHIFTS_KEY = "pos.closed_shifts";
export const VARIANCE_NOTE_MAX = 200;

/** 18 §3.2 `card_settlements[]` item (= §16a.6 body). */
export interface SettlementItem {
  id: string;
  card_terminal_id: string;
  batch_no: string | null;
  business_date: string;
  settled_at: string;
  purchase_count: number;
  purchase_total: Money;
  refund_count: number;
  refund_total: Money;
  status: "failed" | null;
  terminal_response: Record<string, unknown>;
}

/** Tashkent business day of an ISO instant (Asia/Tashkent = UTC+5, no DST). */
export function tashkentDate(iso: string): string {
  const t = new Date(new Date(iso).getTime() + 5 * 3_600_000);
  return t.toISOString().slice(0, 10);
}

export function settlementItem(terminalId: string, r: SettlementResult, id: string): SettlementItem {
  return {
    id,
    card_terminal_id: terminalId,
    batch_no: r.batch_no,
    business_date: tashkentDate(r.settled_at),
    settled_at: r.settled_at,
    purchase_count: r.count,
    purchase_total: fromTiyin(r.total_tiyin),
    refund_count: r.refund_count ?? 0,
    refund_total: fromTiyin(r.refund_total_tiyin ?? 0),
    status: null,
    terminal_response: { tid: r.tid, by_scheme: r.by_scheme },
  };
}

export function failedSettlement(terminalId: string, id: string, at: string, code: string): SettlementItem {
  return {
    id,
    card_terminal_id: terminalId,
    batch_no: null,
    business_date: tashkentDate(at),
    settled_at: at,
    purchase_count: 0,
    purchase_total: "0.00" as Money,
    refund_count: 0,
    refund_total: "0.00" as Money,
    status: "failed",
    terminal_response: { error: code },
  };
}

/** 18 §3.2 payload (exactly the documented fields). */
export function shiftClosedPayload(shiftId: string, count: ShiftCount, settlements: SettlementItem[]) {
  return {
    shift_id: shiftId,
    counted_cash: money(count.countedCash),
    counted_card_total: count.countedCardTotal === null ? null : money(count.countedCardTotal),
    card_settlements: settlements,
    variance_note: count.varianceNote?.trim() ? count.varianceNote.trim() : null,
  };
}

/** The Z-report shown after closing: server object when known, else the local figures (offline). */
export interface ZView {
  source: "server" | "local";
  shiftId: string;
  shiftNo: number;
  report: ZReport;
  fiscalStatus: string | null;
}

export function localZReport(totals: LocalShiftTotals, count: ShiftCount): ZReport {
  return {
    expected_cash: count.expectedCash,
    counted_cash: count.countedCash,
    variance: count.variance,
    totals_by_method: { ...totals.totalsByMethod },
    card_split: { ...totals.cardSplit },
    card_settlements: [],
    vat_total: "0.00",
    discount_total: "0.00",
    returns_total: totals.returnsTotal,
    sales_count: totals.salesCount,
    returns_count: totals.returnsCount,
  };
}

export function zFromPush(result: PushResultEntry | null): ZReport | null {
  const server = result?.server as { z_report?: ZReport } | null | undefined;
  return result && (result.status === "accepted" || result.status === "duplicate")
    ? (server?.z_report ?? null)
    : null;
}

export interface CloseDeps {
  unresolvedAttempts(): Promise<number>;
  terminals(cashRegisterId: string): Promise<TerminalInfo[]>;
  client(terminal: TerminalInfo): CardTerminalClient | null;
  enqueue(
    payload: ReturnType<typeof shiftClosedPayload>,
    actorUserId: string,
  ): Promise<{ clientEventId: string }>;
  markClosed(shift: PosShift, countedCash: Money): Promise<void>;
  awaitResult(clientEventId: string): Promise<PushResultEntry | null>;
  zReport(shiftId: string): Promise<ZReportOut>;
  now(): string;
}

export type CloseOutcome =
  | { ok: true; clientEventId: string; z: ZReport | null; settlements: SettlementItem[] }
  | { ok: false; error: "CARD_OUTCOME_UNKNOWN" };

export async function closeShift(
  deps: CloseDeps,
  input: { shift: PosShift; count: ShiftCount; actorUserId: string },
): Promise<CloseOutcome> {
  if ((await deps.unresolvedAttempts()) > 0) return { ok: false, error: "CARD_OUTCOME_UNKNOWN" };
  const settlements: SettlementItem[] = [];
  for (const terminal of await deps.terminals(input.shift.cash_register_id)) {
    if ((terminal.status ?? "active") !== "active") continue;
    const client = deps.client(terminal);
    if (!client) continue;
    const id = uuidv7();
    try {
      settlements.push(settlementItem(terminal.id, await client.settlement(terminalRef(terminal)), id));
    } catch (e) {
      const code = (e as { code?: string }).code ?? "CARD_TERMINAL_ERROR";
      settlements.push(failedSettlement(terminal.id, id, deps.now(), code));
    }
  }
  const payload = shiftClosedPayload(input.shift.id, input.count, settlements);
  const { clientEventId } = await deps.enqueue(payload, input.actorUserId);
  await deps.markClosed(input.shift, input.count.countedCash);
  const result = await deps.awaitResult(clientEventId);
  return { ok: true, clientEventId, z: zFromPush(result), settlements };
}

/** `card` — the card feature's collaborators (`defaultCardPaymentDeps()`): terminals of the register, clients. */
export function defaultCloseDeps(card: {
  terminals(cashRegisterId: string): Promise<TerminalInfo[]>;
  client(terminal: TerminalInfo): CardTerminalClient | null;
}): CloseDeps {
  return {
    unresolvedAttempts: async () => (await cardAttempts.unresolved()).length,
    terminals: (cashRegisterId) => card.terminals(cashRegisterId),
    client: (terminal) => card.client(terminal),
    enqueue: async (payload, actorUserId) => {
      const r = await enqueueEvent("shift.closed", payload, { actorUserId });
      return { clientEventId: r.clientEventId };
    },
    markClosed: async (shift, countedCash) => {
      await localShift.save({ ...shift, status: "closed" });
      // SYNC-01: the pulled server view no longer lists this shift as open
      await localShift.markServerClosed(shift.id);
      await deviceSettings.set(LAST_COUNTED_CASH_KEY, countedCash);
      // SYNC-01: the pull snapshot may still list this shift as open — POS-01 must not re-adopt it
      const closed = (await deviceSettings.get<string[]>(CLOSED_SHIFTS_KEY)) ?? [];
      await deviceSettings.set(
        CLOSED_SHIFTS_KEY,
        [...closed.filter((id) => id !== shift.id), shift.id].slice(-20),
      );
    },
    awaitResult: (clientEventId) => awaitEventResult(clientEventId, { timeoutMs: 8_000 }),
    zReport: (shiftId) => api.cash.getZReport(shiftId),
    now: () => new Date().toISOString(),
  };
}

const m = (v: string | null | undefined): Money => money(v ?? "0.00");

/** Z-report print document — `kind: "z_report"` of @shared/lib/receipt (08 §13, 18 §3.2, hw-api.md §3). */
export function zReceiptDoc(
  z: ZView,
  ctx: {
    storeName: string;
    branchName: string | null;
    cashierName: string;
    registerName: string | null;
    at: string;
    openedAt?: string | null;
  },
): ReceiptDoc {
  const r = z.report;
  const t = r.totals_by_method;
  return {
    kind: "z_report",
    store: { name: ctx.storeName, branchName: ctx.branchName },
    number: `Z-${z.shiftNo}`,
    issuedAt: ctx.at,
    cashierName: ctx.cashierName,
    shiftNo: z.shiftNo,
    registerNo: ctx.registerName,
    lines: [],
    totals: null,
    payments: null,
    fiscal: null,
    fiscalPending: true,
    zReport: {
      openedAt: ctx.openedAt ?? null,
      closedAt: ctx.at,
      salesCount: r.sales_count,
      returnsCount: r.returns_count,
      totalsByMethod: {
        cash: m(t.cash),
        card: m(t.card),
        uzqr: m(t.uzqr),
        click: m(t.click),
        payme: m(t.payme),
        uzum: m(t.uzum),
        debt: m(t.debt),
      },
      cardSplit: { integrated: m(r.card_split.integrated), manual: m(r.card_split.manual) },
      cardSettlements: r.card_settlements.map((c) => ({
        terminal: c.card_terminal_id,
        netTotal: m(c.net_total),
        expectedTotal: m(c.expected_total),
        variance: m(c.variance),
        status: c.status,
      })),
      returnsTotal: m(r.returns_total),
      discountTotal: m(r.discount_total),
      vatTotal: m(r.vat_total),
      expectedCash: m(r.expected_cash),
      countedCash: m(r.counted_cash),
      variance: m(r.variance),
    },
  };
}

/** Effect wrapper (pending flag for the screen). */
export const closeShiftFx = createEffect(
  ({
    deps,
    input,
  }: {
    deps: CloseDeps;
    input: { shift: PosShift; count: ShiftCount; actorUserId: string };
  }) => closeShift(deps, input),
);

/**
 * ACC-01: the push engine holds `shift.closed` while an earlier event of the same shift is unsynced
 * (`outbox.heldShiftCloses()`). Returns how many documents it waits for, or 0 when it is not held.
 */
export function heldCloseCount(
  held: readonly { clientEventId: string; shiftId: string | null; waitingFor: readonly string[] }[],
  shiftId: string,
  clientEventId: string | null,
): number {
  const row = held.find(
    (h) => h.shiftId === shiftId || (clientEventId !== null && h.clientEventId === clientEventId),
  );
  return row ? row.waitingFor.length : 0;
}
