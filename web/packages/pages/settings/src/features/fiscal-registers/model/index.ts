/**
 * BO-14 «Fiskal» → kassalar fiskal holati (contracts/fiscal.md §4; 18 §14.3/§14.4): per register the fiscal
 * module state, the FM's own unsent count (agent `fiscal.status`), server receipts without the OFD ack (48 h
 * timer) and failed ones — `GET /fiscal-registers` (`reports.sales.view`); «Qayta yuborish» for a register
 * served by a Do'kon agenti — `POST /cash-registers/{id}/fiscal-resend` (`integrations.retry`, Idempotency-Key)
 * → `202 {task_id, status:"queued"}` (agent task `fiscal.resend_unsent`); a register without an agent → 409.
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { FiscalRegisterOut, FiscalResendOut } from "@shared/models";

export type FiscalRegister = FiscalRegisterOut;
export type LoadStatus = "idle" | "loading" | "error";

/** 48 h offline limit (16 §6) — the register is locked by the FM after it; 24 h = BO-02 alert. */
export const WARN_AGE_S = 24 * 3600;
export const BLOCK_AGE_S = 48 * 3600;

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const fiscalRegistersOpened = createEvent();
export const fiscalRegistersReloadRequested = createEvent();
export const resendRequested = createEvent<string>();
export const resendDismissed = createEvent();

export const listFiscalRegistersFx = wrap<void, FiscalRegister[]>(async () => {
  const { items } = await api.sales.listFiscalRegisters();
  return items;
});
export const resendFx = wrap<string, FiscalResendOut>((id) => api.sales.resendFiscalUnsent(id, {}));

export const $fiscalRegisters = createStore<FiscalRegister[]>([]);
export const $fiscalRegistersStatus = createStore<LoadStatus>("idle");
export const $fiscalRegistersError = createStore<ApiError | null>(null, { skipVoid: false });
export const $resending = createStore<readonly string[]>([]);
/** Registers whose resend task was queued in this visit («Navbatga qo'yildi»). */
export const $resendQueued = createStore<readonly string[]>([]);
export const $resendError = createStore<ApiError | null>(null, { skipVoid: false });

sample({ clock: [fiscalRegistersOpened, fiscalRegistersReloadRequested], target: listFiscalRegistersFx });
$fiscalRegisters.on(listFiscalRegistersFx.doneData, (_, list) => byAttention(list));
$fiscalRegistersStatus
  .on(listFiscalRegistersFx, () => "loading")
  .on(listFiscalRegistersFx.done, () => "idle")
  .on(listFiscalRegistersFx.fail, () => "error");
$fiscalRegistersError.on(listFiscalRegistersFx.failData, (_, e) => e).reset(listFiscalRegistersFx);

// One request per register at a time; only agent-bound registers (others → 409 on the server).
sample({
  clock: resendRequested,
  source: { list: $fiscalRegisters, busy: $resending, queued: $resendQueued },
  filter: ({ list, busy, queued }, id) =>
    !busy.includes(id) && !queued.includes(id) && list.some((r) => r.cash_register_id === id && canResend(r)),
  fn: (_, id) => id,
  target: resendFx,
});
$resending
  .on(resendFx, (ids, id) => [...ids, id])
  .on(resendFx.finally, (ids, { params }) => ids.filter((x) => x !== params));
$resendQueued.on(resendFx.done, (ids, { params }) => [...ids, params]).reset(fiscalRegistersOpened);
$resendError.on(resendFx.failData, (_, e) => e).reset(resendFx, resendDismissed);
sample({
  clock: resendFx.failData,
  filter: (e) => e.status === 409 || e.status === 404,
  fn: () => undefined,
  target: fiscalRegistersReloadRequested,
});

// --- lib -----------------------------------------------------------------------------------------------

/** «Qayta yuborish» exists only for a local-bridge register (bound Do'kon agenti) — 18 §14.4. */
export function canResend(r: Pick<FiscalRegister, "fiscal_agent_id">): boolean {
  return r.fiscal_agent_id !== null;
}

export type Severity = "ok" | "warn" | "blocked";

/** Oldest unacknowledged receipt age → ok / ≥24 h warn / ≥48 h blocked; a locked FM is always blocked. */
export function severityOf(r: Pick<FiscalRegister, "fm_state" | "oldest_unacked_age_s">): Severity {
  if (r.fm_state === "locked" || r.fm_state === "ack_overdue" || r.fm_state === "memory_full") return "blocked";
  const age = r.oldest_unacked_age_s ?? 0;
  if (age >= BLOCK_AGE_S) return "blocked";
  if (age >= WARN_AGE_S) return "warn";
  return "ok";
}

const WEIGHT: Record<Severity, number> = { blocked: 0, warn: 1, ok: 2 };

/** Registers needing attention first (blocked, warn, failed receipts), then by name. */
export function byAttention(list: readonly FiscalRegister[]): FiscalRegister[] {
  return [...list].sort(
    (a, b) =>
      WEIGHT[severityOf(a)] - WEIGHT[severityOf(b)] ||
      (b.failed_count > 0 ? 1 : 0) - (a.failed_count > 0 ? 1 : 0) ||
      a.name.localeCompare(b.name),
  );
}

/** Seconds → whole hours (age column «N soat»); `null` stays `null`. */
export function ageHours(seconds: number | null): number | null {
  return seconds === null ? null : Math.floor(seconds / 3600);
}
