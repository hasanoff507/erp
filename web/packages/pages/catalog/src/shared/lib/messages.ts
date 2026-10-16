/**
 * Server `message_key` → text for the catalog screens (08 §11, 17 §7.1) — thin wrappers over the
 * shared translator of @shared/i18n. Keys resolve in `common` first; the legacy `catalog:server.*`
 * keys (and the client-side `client.*` codes) are still consulted after it. Unknown keys never show
 * raw text.
 */
import { hasServerMessage, serverErrorText, translateServerMessage } from "@shared/i18n";

import type { ApiError } from "@shared/api";

const NAMESPACES = ["catalog:server"] as const;

/** True when `key` resolves either in `common` or in `catalog:server`. */
export function hasMessage(key: string): boolean {
  return hasServerMessage(key, NAMESPACES);
}

/**
 * Message key (optionally `key?param=value`, the @shared/ui/form `withParams` encoding) → text.
 * `fallback` is used when the key is unknown (default `errors.internal_error`).
 */
export function messageText(
  message: string,
  params: Record<string, unknown> = {},
  fallback = "errors.internal_error",
): string {
  return translateServerMessage(message, params, { namespaces: NAMESPACES, fallback });
}

/** A field-level message: unknown keys fall back to `validation.invalid_format`. */
export function fieldMessageText(message: string): string {
  return messageText(message, {}, "validation.invalid_format");
}

/**
 * Banner/toast text of an ApiError: its message_key with its params; a VALIDATION_ERROR without a
 * useful top-level key shows the first detail instead.
 */
export function apiErrorText(error: ApiError): string {
  return serverErrorText(error, { namespaces: NAMESPACES, fallback: "errors.internal_error" });
}
