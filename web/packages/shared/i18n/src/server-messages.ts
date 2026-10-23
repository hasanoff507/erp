/**
 * Server `message_key` → user text, the ONE translator for every page (08 §11, 17 §7.1, 32 §5.1:
 * only `t(message_key)`, never raw codes/JSON). Keys resolve in `common` (errors.*, validation.*);
 * a page may pass extra namespace prefixes that are consulted after `common` (e.g. the legacy
 * `catalog:server` keys). An unknown key never shows raw text: `validation.*` → "invalid format",
 * anything else → `errors.internal_error`.
 */
import i18next from "i18next";

type Translate = (key: string, options?: Record<string, unknown>) => string;

function t(): Translate {
  return i18next.t.bind(i18next) as unknown as Translate;
}

export interface ServerMessageOptions {
  /** Extra `ns:prefix` lookups after `common`, e.g. `["catalog:server"]` → `catalog:server.<key>`. */
  namespaces?: readonly string[];
  /** `common` key for an unknown key (default: by prefix — `validation.invalid_format` / `errors.internal_error`). */
  fallback?: string;
}

/** Structural subset of `@shared/api` ApiError (this package must not depend on the API client). */
export interface ServerErrorLike {
  code: string;
  messageKey: string;
  params?: Readonly<Record<string, unknown>>;
  details?: readonly { messageKey: string }[];
}

/** `key?param=value` (the @shared/ui/form `withParams` encoding) → key + params. */
function splitKey(message: string): { key: string; params: Record<string, unknown> } {
  const q = message.indexOf("?");
  if (q === -1) return { key: message, params: {} };
  const params: Record<string, unknown> = {};
  new URLSearchParams(message.slice(q + 1)).forEach((v, k) => (params[k] = v));
  return { key: message.slice(0, q), params };
}

function resolve(key: string, namespaces: readonly string[] = []): string | null {
  if (i18next.exists(`common:${key}`)) return `common:${key}`;
  for (const ns of namespaces) {
    if (i18next.exists(`${ns}.${key}`)) return `${ns}.${key}`;
  }
  return null;
}

/** `true` when the key (without `?params`) has a translation in `common` or the given namespaces. */
export function hasServerMessage(message: string, namespaces?: readonly string[]): boolean {
  return resolve(splitKey(message).key, namespaces) !== null;
}

/** Message key (optionally `key?param=value`) → translated text. */
export function translateServerMessage(
  message: string,
  params: Readonly<Record<string, unknown>> = {},
  options: ServerMessageOptions = {},
): string {
  const { key, params: encoded } = splitKey(message);
  const found = resolve(key, options.namespaces);
  if (found) return t()(found, { ...params, ...encoded });
  const fallback =
    options.fallback ??
    (key.startsWith("validation.") ? "validation.invalid_format" : "errors.internal_error");
  return t()(`common:${fallback}`);
}

/**
 * Whole server error → text for a toast / banner / ErrorState. A VALIDATION_ERROR whose top-level key
 * is the generic `errors.validation` (or unknown) shows its first detail instead; RATE_LIMITED with
 * `retry_after_s` says how many minutes to wait (14 §12).
 */
export function serverErrorText(error: ServerErrorLike, options: ServerMessageOptions = {}): string {
  const params = error.params ?? {};
  const first = error.details?.[0];
  if (
    error.code === "VALIDATION_ERROR" &&
    first &&
    (error.messageKey === "errors.validation" || !hasServerMessage(error.messageKey, options.namespaces))
  ) {
    return translateServerMessage(first.messageKey, params, {
      namespaces: options.namespaces,
      fallback: "validation.invalid_format",
    });
  }
  if (error.code === "RATE_LIMITED") {
    const seconds = params.retry_after_s;
    if (typeof seconds === "number" && seconds > 0) {
      return t()("common:errors.rate_limited_wait", { minutes: Math.max(1, Math.ceil(seconds / 60)) });
    }
  }
  return translateServerMessage(error.messageKey, params, options);
}
