/**
 * Error envelope — 17-api-umumiy.md §7.1, 32-kod-qoidalari.md §5.1:
 * `{"error": {code, message_key, params?, details[], request_id}}`.
 * The UI only ever shows `t("common:" + messageKey)` — never raw JSON.
 */
import { isAxiosError, isCancel } from "axios";

export interface ApiErrorDetail {
  field: string;
  messageKey: string;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly messageKey: string;
  readonly params: Readonly<Record<string, unknown>>;
  readonly details: readonly ApiErrorDetail[];
  readonly requestId: string | null;

  constructor(init: {
    status: number | null;
    code: string;
    messageKey: string;
    params?: Record<string, unknown>;
    details?: ApiErrorDetail[];
    requestId?: string | null;
    cause?: unknown;
  }) {
    super(init.code, { cause: init.cause });
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.messageKey = init.messageKey;
    this.params = init.params ?? {};
    this.details = init.details ?? [];
    this.requestId = init.requestId ?? null;
  }
}

export const NETWORK_ERROR = "NETWORK_ERROR";
export const INTERNAL_ERROR = "INTERNAL_ERROR";
/** Aborted by the caller (AbortController / unmount): not a network failure, never "offline". */
export const REQUEST_CANCELED = "REQUEST_CANCELED";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseDetails(value: unknown): ApiErrorDetail[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((d: unknown) =>
    isRecord(d) && typeof d.field === "string" && typeof d.message_key === "string"
      ? [{ field: d.field, messageKey: d.message_key }]
      : [],
  );
}

/** Normalises anything thrown by axios/effects into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;

  if (isCancel(error)) {
    return new ApiError({
      status: null,
      code: REQUEST_CANCELED,
      messageKey: "errors.request_canceled",
      cause: error,
    });
  }

  if (isAxiosError(error)) {
    if (!error.response) {
      return new ApiError({ status: null, code: NETWORK_ERROR, messageKey: "errors.network", cause: error });
    }
    const { status, headers } = error.response;
    const data: unknown = error.response.data;
    const body = isRecord(data) && isRecord(data.error) ? data.error : null;
    if (body && typeof body.code === "string") {
      const headerRequestId: unknown = headers["x-request-id"];
      return new ApiError({
        status,
        code: body.code,
        messageKey: typeof body.message_key === "string" ? body.message_key : "errors.internal_error",
        params: isRecord(body.params) ? body.params : {},
        details: parseDetails(body.details),
        requestId:
          typeof body.request_id === "string"
            ? body.request_id
            : typeof headerRequestId === "string"
              ? headerRequestId
              : null,
        cause: error,
      });
    }
    return new ApiError({ status, code: INTERNAL_ERROR, messageKey: "errors.internal_error", cause: error });
  }

  return new ApiError({
    status: null,
    code: INTERNAL_ERROR,
    messageKey: "errors.internal_error",
    cause: error,
  });
}
