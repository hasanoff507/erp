/**
 * Local-bridge fiscalisation of the web POS (B5; 21 §1, §16, §16.1; 24 §6.4; 18 §4.1/§4.10; qaror #60/#68).
 *
 * Mode: the register is bound to a Do'kon agenti fiscal device in BO-12 (`cash_registers.fiscal_agent_id` +
 * `fiscal_local_device_id`, pulled in `settings.cash_register`) → every fiscal receipt of this POS is signed by
 * the FM through the agent BEFORE the event is written; the event carries `receipt_seq` + `fiscal_result`.
 * Without a binding the server fiscalises (fake / partner cloud) and nothing here runs.
 *
 * `signFiscalReceipt` order (07 POS-03: card approval → fiscal receipt → `sale.created`):
 *  1. readiness from `$agentStatus` — not connected → `FISCAL_MODULE_NOT_CONNECTED` (sale NOT closed, cart
 *     kept, restart instructions); FM locked → `FISCAL_DEVICE_LOCKED`;
 *  2. `reserveReceiptSeq` (same counter / Web Lock as the outbox; same request → same number, 48 h block);
 *  3. a stored signature for the same request is reused, otherwise `/v1/fiscal/sale|refund`; `SHIFT_NOT_OPEN` →
 *     `/v1/fiscal/open-shift` for this shift and the same request once more;
 *  4. the answer is remembered with the reservation; the caller writes the event and calls `fiscalSigned.done`.
 * A lost answer (`FISCAL_RESULT_UNKNOWN`) is retried by the cashier with the SAME number and payload — the agent
 * journal returns the signed result, the FM never signs the same receipt twice (21 §16.1).
 */
import { combine, createEvent, createStore, sample } from "effector";

import {
  createLocalBridgeFiscalAdapter,
  FiscalError,
  isFiscalError,
  localFiscalReadiness,
  type CashRegisterRef,
  type FiscalPort,
  type FiscalReceiptPayload,
  type FiscalResult,
  type LocalFiscalReadiness,
} from "@shared/lib/fiscal";
import {
  isOfflineError,
  pullApplied,
  rememberFiscalResult,
  releaseReservation,
  reserveReceiptSeq,
  settings,
} from "@shared/offline";
import { $agentStatus, type AgentStatus } from "@shared/state/device";

import { posAgentClient } from "#/shared/lib/device-runtime.ts";

/** BO-12 binding of this register (`settings.cash_register`, 16 §3.2). */
export interface FiscalBinding {
  cashRegisterId: string;
  agentId: string;
  localId: string;
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

export function fiscalBindingOf(raw: Record<string, unknown> | null | undefined): FiscalBinding | null {
  const reg = raw?.cash_register;
  if (!reg || typeof reg !== "object") return null;
  const r = reg as Record<string, unknown>;
  const id = str(r.id);
  const agentId = str(r.fiscal_agent_id);
  const localId = str(r.fiscal_local_device_id);
  return id && agentId && localId ? { cashRegisterId: id, agentId, localId } : null;
}

export interface LocalFiscalDeps {
  port(): FiscalPort;
  agent(): AgentStatus;
  binding(): Promise<FiscalBinding | null>;
}

let port: FiscalPort | null = null;
const defaults: LocalFiscalDeps = {
  port: () => (port ??= createLocalBridgeFiscalAdapter(posAgentClient())),
  agent: () => $agentStatus.getState(),
  binding: async () => fiscalBindingOf((await settings.get()).raw),
};
let deps: LocalFiscalDeps = defaults;
/** Tests: replace the agent port / status / binding. */
export function configureLocalFiscal(patch: Partial<LocalFiscalDeps> | null): void {
  deps = patch ? { ...defaults, ...patch } : defaults;
}

// ---- binding + readiness stores (banners) ----------------------------------------------------------
export const fiscalBindingRefreshed = createEvent();
const fiscalBindingLoaded = createEvent<FiscalBinding | null>();
export const $fiscalBinding = createStore<FiscalBinding | null>(null, { skipVoid: false }).on(
  fiscalBindingLoaded,
  (_, b) => b,
);
fiscalBindingRefreshed.watch(() => {
  void deps
    .binding()
    .then(fiscalBindingLoaded)
    .catch(() => undefined);
});
sample({
  clock: pullApplied,
  filter: (scopes) => scopes.includes("settings"),
  fn: () => undefined,
  target: fiscalBindingRefreshed,
});

/** null — not the local-bridge mode (server-side fiscalisation). */
export const $localFiscal = combine(
  $fiscalBinding,
  $agentStatus,
  (binding, agent): LocalFiscalReadiness | null => (binding ? localFiscalReadiness(agent, binding.localId) : null),
);

// ---- signing ---------------------------------------------------------------------------------------
export interface SignInput {
  /** Document key of the reservation (draft ref / payment id) — survives a reload of the tab. */
  ref: string;
  binding: FiscalBinding;
  shiftId: string;
  shiftNo: number | null;
  cashierName: string;
  /** Builds the FM request for the given receipt number. */
  build(receiptSeq: number): FiscalReceiptPayload;
}

export interface Signed {
  receiptSeq: number;
  result: FiscalResult;
}

/** Throws `FiscalError` (or `OfflineError` FISCAL_OFFLINE_48H_BLOCKED / FISCAL_RESULT_PENDING). */
export async function signFiscalReceipt(input: SignInput): Promise<Signed> {
  const readiness = localFiscalReadiness(deps.agent(), input.binding.localId);
  if (readiness.state === "not_connected") {
    throw new FiscalError("FISCAL_MODULE_NOT_CONNECTED", { reason: readiness.reason });
  }
  if (readiness.state === "locked") {
    throw new FiscalError("FISCAL_DEVICE_LOCKED", { fm_state: readiness.fmState });
  }
  const request = JSON.stringify(input.build(0));
  const reservation = await reserveReceiptSeq({
    ref: input.ref,
    cashRegisterId: input.binding.cashRegisterId,
    shiftId: input.shiftId,
    request,
  });
  if (reservation.result) {
    return { receiptSeq: reservation.receipt_seq, result: reservation.result as unknown as FiscalResult };
  }
  const payload = input.build(reservation.receipt_seq);
  const fm = deps.port();
  const send = () => (payload.kind === "return" ? fm.registerRefund(payload) : fm.registerSale(payload));
  let result: FiscalResult;
  try {
    result = await send();
  } catch (error) {
    if (!(isFiscalError(error) && error.code === "SHIFT_NOT_OPEN" && input.shiftNo)) throw error;
    const register: CashRegisterRef = payload.cash_register;
    try {
      await fm.openShift(register, input.shiftNo, input.cashierName);
    } catch (opened) {
      // another FM shift is open (not closed by Z yet) — the FM refused; show that state
      if (!(isFiscalError(opened) && opened.code === "SHIFT_ALREADY_OPEN")) throw opened;
    }
    result = await send();
  }
  await rememberFiscalResult(input.ref, result as unknown as Record<string, unknown>);
  return { receiptSeq: reservation.receipt_seq, result };
}

/** The event with this signature is in the outbox. */
export function fiscalSigned(ref: string): Promise<void> {
  return releaseReservation(ref);
}

/** Error → `{code, params}` for the screens (`errorText`). */
export function fiscalErrorOf(error: unknown): { code: string; params: Record<string, unknown> } | null {
  if (isFiscalError(error)) return { code: error.code, params: error.params };
  if (isOfflineError(error) && (error.code === "FISCAL_RESULT_PENDING" || error.code === "FISCAL_OFFLINE_48H_BLOCKED")) {
    return { code: error.code, params: { ...error.params } };
  }
  return null;
}

/**
 * POS-07 (best effort): close the FM shift right after the POS shift — the server's `fiscal.zreport` agent task
 * closes it anyway (21 §16), so a failure here never blocks the shift close.
 */
export async function closeFiscalShift(binding: FiscalBinding, shiftNo: number): Promise<boolean> {
  try {
    await deps.port().closeShift({ cash_register_id: binding.cashRegisterId, local_id: binding.localId }, shiftNo);
    return true;
  } catch {
    return false;
  }
}
