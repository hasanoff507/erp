import type { ApiError } from "@shared/api";

export type PinError =
  { kind: "invalid" } | { kind: "mustChange" } | { kind: "locked"; minutes: number | null };

/**
 * PIN step-up errors of 18 §9.4: `PIN_INVALID` (wrong PIN; `params.reason="must_change_pin"` — the PIN
 * was reset / never set), `ACCOUNT_LOCKED` (`params.retry_after_s`, 14 §12). Any other error → `null`
 * (the shared server text is shown).
 */
export function pinError(e: ApiError): PinError | null {
  if (e.code === "PIN_INVALID") {
    return e.params.reason === "must_change_pin" ? { kind: "mustChange" } : { kind: "invalid" };
  }
  if (e.code === "ACCOUNT_LOCKED") {
    const raw = e.params.retry_after_s;
    const seconds = typeof raw === "number" ? raw : NaN;
    return {
      kind: "locked",
      minutes: Number.isFinite(seconds) && seconds > 0 ? Math.max(1, Math.ceil(seconds / 60)) : null,
    };
  }
  return null;
}
