/**
 * `LocalBridgeFiscalAdapter` — `FiscalPort` over the Do'kon agenti local API (`/v1/fiscal/*`, 21 §16.1,
 * .claude-scratch/b5/contracts/agent-local-api.md §3) for the `multikassa_local` / `fiscaldrive_local` providers.
 *
 * Error model (21 §16 «Fiskal modul ulanmagan», 18 §4.10):
 * - agent not reachable / not paired / 401·403 / 404 (unknown `local_id`) / 503 → `FISCAL_MODULE_NOT_CONNECTED`
 *   (nothing was signed — local state, the sale is not closed);
 * - timeout, dropped connection after sending, `502 FISCAL_PROVIDER_ERROR params.reason="outcome_unknown"` →
 *   `FISCAL_RESULT_UNKNOWN` — the caller sends the SAME payload with the SAME `receipt_seq` again; the agent
 *   journal returns the stored result (idempotency key `(cash_register_id, receipt_seq)`), never a 2nd signature;
 * - `409 FISCAL_DEVICE_LOCKED`, `409 FISCAL_OFFLINE_48H_BLOCKED`, `409 SHIFT_NOT_OPEN|SHIFT_ALREADY_OPEN`,
 *   `409 RECEIPT_SEQ_CONFLICT`, `502 FISCAL_PROVIDER_ERROR`, `422 VALIDATION_ERROR` keep their catalog code.
 * The adapter never retries by itself.
 */
import { AgentError, type AgentClient } from "#/agent/index.ts";

import {
  FiscalError,
  type CashRegisterRef,
  type FiscalDeviceStatus,
  type FiscalErrorCode,
  type FiscalPort,
  type FiscalReceiptPayload,
  type FiscalResult,
  type FiscalShiftResult,
  type ResendResult,
  type UnsentReceipt,
  type ZReport,
} from "./types.ts";

/** 21 §16.1 has no explicit fiscal timeout; the FM signs locally — 20 s covers a slow USB reader. */
export const FISCAL_TIMEOUTS = Object.freeze({ receipt: 20_000, shift: 30_000, status: 5_000, resend: 60_000 });

const CATALOG: ReadonlySet<string> = new Set<FiscalErrorCode>([
  "FISCAL_DEVICE_LOCKED",
  "FISCAL_OFFLINE_48H_BLOCKED",
  "FISCAL_PROVIDER_ERROR",
  "SHIFT_NOT_OPEN",
  "SHIFT_ALREADY_OPEN",
  "RECEIPT_SEQ_CONFLICT",
  "VALIDATION_ERROR",
]);

/** AgentError → FiscalError. `sent` = the request may have reached the FM (receipt calls). */
export function toFiscalError(error: unknown, sent: boolean): FiscalError {
  if (error instanceof FiscalError) return error;
  if (error instanceof AgentError) {
    const params = { ...(error.params ?? {}) };
    if (error.kind === "http") {
      if (error.code === "FISCAL_PROVIDER_ERROR" && params.reason === "outcome_unknown") {
        return new FiscalError("FISCAL_RESULT_UNKNOWN", params, error);
      }
      if (CATALOG.has(error.code)) return new FiscalError(error.code as FiscalErrorCode, params, error);
      return new FiscalError("FISCAL_MODULE_NOT_CONNECTED", { ...params, status: error.status }, error);
    }
    if (sent && (error.kind === "timeout" || error.kind === "aborted" || error.kind === "protocol")) {
      return new FiscalError("FISCAL_RESULT_UNKNOWN", { reason: error.kind }, error);
    }
    return new FiscalError("FISCAL_MODULE_NOT_CONNECTED", { reason: error.kind }, error);
  }
  return new FiscalError(sent ? "FISCAL_RESULT_UNKNOWN" : "FISCAL_MODULE_NOT_CONNECTED", {}, error);
}

const RESULT_KEYS = ["fm_terminal_id", "fm_receipt_seq", "fiscal_sign", "qr_url", "fiscal_at"] as const;

/** Only the five 18 §4.1 fields leave the adapter (the server refuses extra ones). */
export function parseFiscalResult(raw: unknown): FiscalResult {
  const r = (raw ?? {}) as Record<string, unknown>;
  const ok =
    typeof r.fm_terminal_id === "string" &&
    /^[A-Za-z0-9]{1,64}$/.test(r.fm_terminal_id) &&
    typeof r.fm_receipt_seq === "number" &&
    Number.isSafeInteger(r.fm_receipt_seq) &&
    r.fm_receipt_seq >= 0 &&
    typeof r.fiscal_sign === "string" &&
    /^[0-9]{12}$/.test(r.fiscal_sign) &&
    typeof r.qr_url === "string" &&
    r.qr_url.startsWith("https://") &&
    typeof r.fiscal_at === "string" &&
    !Number.isNaN(Date.parse(r.fiscal_at));
  // a signed receipt whose answer we cannot read is still signed — resend the same payload
  if (!ok) throw new FiscalError("FISCAL_RESULT_UNKNOWN", { reason: "malformed_result" });
  return Object.fromEntries(RESULT_KEYS.map((k) => [k, r[k]])) as unknown as FiscalResult;
}

export function createLocalBridgeFiscalAdapter(agent: Pick<AgentClient, "request">): FiscalPort {
  async function call<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    timeoutMs: number,
    sent: boolean,
  ): Promise<T> {
    try {
      return await agent.request<T>(method, path, body, { timeoutMs });
    } catch (error) {
      throw toFiscalError(error, sent);
    }
  }
  const q = (r: CashRegisterRef) => `?local_id=${encodeURIComponent(r.local_id)}`;
  return {
    openShift: (register, shiftNo, cashierName) =>
      call<FiscalShiftResult>(
        "POST",
        "/v1/fiscal/open-shift",
        { cash_register: register, shift_no: shiftNo, cashier_name: cashierName.slice(0, 128) },
        FISCAL_TIMEOUTS.shift,
        false,
      ),
    closeShift: (register, shiftNo) =>
      call<ZReport>(
        "POST",
        "/v1/fiscal/close-shift",
        { cash_register: register, shift_no: shiftNo },
        FISCAL_TIMEOUTS.shift,
        false,
      ),
    async registerSale(receipt: FiscalReceiptPayload) {
      if (receipt.kind === "return") throw new FiscalError("VALIDATION_ERROR", { field: "kind" });
      return parseFiscalResult(
        await call("POST", "/v1/fiscal/sale", receipt, FISCAL_TIMEOUTS.receipt, true),
      );
    },
    async registerRefund(receipt: FiscalReceiptPayload) {
      if (receipt.kind !== "return" || !receipt.refund_info) {
        throw new FiscalError("VALIDATION_ERROR", { field: "refund_info" });
      }
      return parseFiscalResult(
        await call("POST", "/v1/fiscal/refund", receipt, FISCAL_TIMEOUTS.receipt, true),
      );
    },
    getDeviceStatus: (register) =>
      call<FiscalDeviceStatus>(
        "GET",
        `/v1/fiscal/device-status${q(register)}`,
        undefined,
        FISCAL_TIMEOUTS.status,
        false,
      ),
    async listUnsent(register) {
      const res = await call<{ items: UnsentReceipt[] }>(
        "GET",
        `/v1/fiscal/unsent${q(register)}`,
        undefined,
        FISCAL_TIMEOUTS.status,
        false,
      );
      return res.items ?? [];
    },
    resendUnsent: (register) =>
      call<ResendResult>(
        "POST",
        "/v1/fiscal/resend",
        { local_id: register.local_id },
        FISCAL_TIMEOUTS.resend,
        false,
      ),
  };
}
