/**
 * ApiError → user text (17 §7.1, 32 §5.1: only `t(message_key)`, never raw JSON) — thin wrappers over
 * the shared translator of @shared/i18n (08 §11); every server key lives in `common`.
 */
import { toApiError, toFieldPath, type ApiError } from "@shared/api";
import { hasServerMessage, serverErrorText, translateServerMessage } from "@shared/i18n";

/** `true` when `key` is resolvable in `common` (FormField can show it as a key). */
export function isCommonKey(key: string): boolean {
  return hasServerMessage(key);
}

/** Message key → translated text (unknown `validation.*` → invalid format, else generic error). */
export function messageText(key: string, params: Readonly<Record<string, unknown>> = {}): string {
  return translateServerMessage(key, params);
}

/** Any thrown value → translated text for a toast / banner / ErrorState. */
export function errorText(error: unknown): string {
  return serverErrorText(toApiError(error));
}

/**
 * Value for react-hook-form `setError(..., { message })`: FormField translates `common` keys itself;
 * any other key is passed as already translated text (FormField shows non-key text as is).
 */
export function fieldErrorMessage(key: string): string {
  return isCommonKey(key) ? key : messageText(key);
}

export interface ServerFieldError {
  field: string;
  message: string;
}

/**
 * Splits `details[]` into errors for known form fields (with `fieldMap` server → form names) and
 * the rest (translated text for a banner).
 */
export function splitFieldErrors(
  error: ApiError,
  fields: readonly string[],
  fieldMap: Readonly<Record<string, string>> = {},
): { fieldErrors: ServerFieldError[]; other: string[] } {
  const known = new Set(fields);
  const fieldErrors: ServerFieldError[] = [];
  const other: string[] = [];
  for (const d of error.details) {
    const path = toFieldPath(d.field);
    const mapped = fieldMap[path] ?? fieldMap[path.split(".")[0] ?? ""] ?? path;
    if (known.has(mapped)) fieldErrors.push({ field: mapped, message: fieldErrorMessage(d.messageKey) });
    else other.push(messageText(d.messageKey, error.params));
  }
  return { fieldErrors, other };
}
