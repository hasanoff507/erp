/** Effect helpers of the e-document screens (24 §3: an effect's failure is always a normalised ApiError). */
import { createEffect } from "effector";

import { ApiError, toApiError } from "@shared/api";
import { i18next, serverErrorText } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { EimzoError } from "@shared/lib/eimzo";

/** A local E-IMZO failure becomes an ApiError with `common:eimzo.errors.<CODE>` (21 §5 "Xato UX"). */
function normalise(e: unknown): ApiError {
  if (e instanceof EimzoError) {
    return new ApiError({ status: null, code: e.code, messageKey: `eimzo.errors.${e.code}`, cause: e });
  }
  return toApiError(e);
}

export function apiFx<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw normalise(e);
    }
  });
}

/** Local calendar date `YYYY-MM-DD` (Tashkent is the device zone). */
export function todayIso(): string {
  return dayjs().format("YYYY-MM-DD");
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

const SIGN_REASONS = new Set([
  "challenge_invalid",
  "content_mismatch",
  "certificate_expired",
  "bad_format",
  "document_changed",
  "verification_unavailable",
]);

/**
 * ApiError → user text (32 §5.1). `EIMZO_SIGN_FAILED` gets the reason of 19 §19 (`edocs:signReasons.*`),
 * `DOC_INVALID_STATE` with a known `params.reason` — `edocs:stateReasons.*`.
 */
export function errorText(error: ApiError): string {
  const t = i18next.t.bind(i18next) as unknown as Translate;
  const reason = error.params.reason;
  if (error.code === "EIMZO_SIGN_FAILED" && typeof reason === "string" && SIGN_REASONS.has(reason)) {
    return t(`edocs:signReasons.${reason}`);
  }
  if (
    error.code === "DOC_INVALID_STATE" &&
    typeof reason === "string" &&
    i18next.exists(`edocs:stateReasons.${reason}`)
  ) {
    return t(`edocs:stateReasons.${reason}`);
  }
  return serverErrorText(error);
}
