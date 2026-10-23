/**
 * OfflineError — the package never produces user-facing text: `code` is a catalog code (17 §15) when
 * one exists (FISCAL_OFFLINE_48H_BLOCKED, CARD_OUTCOME_UNKNOWN, DEVICE_REVOKED…) or a local code
 * (`OUTBOX_NOT_EMPTY`, `DEVICE_NOT_REGISTERED`, `CARD_DATA_FORBIDDEN`). Screens map it to i18n.
 */
export type OfflineErrorCode =
  | "FISCAL_OFFLINE_48H_BLOCKED"
  | "CARD_OUTCOME_UNKNOWN"
  | "CARD_DATA_FORBIDDEN"
  | "OUTBOX_NOT_EMPTY"
  | "DEVICE_NOT_REGISTERED"
  | "DEVICE_REVOKED"
  | "UNKNOWN_EVENT_TYPE"
  | "VALIDATION_ERROR";

export class OfflineError extends Error {
  readonly code: OfflineErrorCode;
  readonly params: Readonly<Record<string, unknown>>;

  constructor(code: OfflineErrorCode, params: Record<string, unknown> = {}) {
    super(code);
    this.name = "OfflineError";
    this.code = code;
    this.params = params;
  }
}

export function isOfflineError(error: unknown, code?: OfflineErrorCode): error is OfflineError {
  return error instanceof OfflineError && (code === undefined || error.code === code);
}
