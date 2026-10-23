/**
 * Server error → text (08 §11) — thin wrappers over the shared translator of @shared/i18n: every
 * server key (incl. the signup/credential ones such as `validation.phone_taken`) lives in `common`.
 */
import type { ApiError } from "@shared/api";
import { serverErrorText, translateServerMessage } from "@shared/i18n";

/** Message key → translated text (unknown `validation.*` → invalid format, else generic error). */
export function translateServerKey(messageKey: string, params?: Record<string, unknown>): string {
  return translateServerMessage(messageKey, params);
}

/** The detail message for one request field (17 §7.1 `details[].field`), translated; else null. */
export function fieldError(error: ApiError | null, ...fields: string[]): string | null {
  if (!error) return null;
  const detail = error.details.find((d) => fields.includes(d.field));
  return detail ? translateServerKey(detail.messageKey, error.params) : null;
}

/** Whole-error text for a banner: RATE_LIMITED carries `retry_after_s` (14 §12). */
export function errorText(error: ApiError): string {
  return serverErrorText(error);
}
