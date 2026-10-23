/**
 * Catalog error code → text (17 §15: `errors.<code lower-case>` in `common`, translated through the one
 * server-message translator). Local library codes that are not in the catalog (`OfflineError` codes such as
 * `DEVICE_NOT_REGISTERED`) are looked up in `pos:errors.*`; anything unknown → a generic text, never a code.
 */
import { translateServerMessage } from "@shared/i18n";

export type DynamicT = (key: string, options?: Record<string, unknown>) => string;

/** `t` of `useTranslation("pos")` for keys built from enum values (all of them exist in uz + ru). */
export const dyn = (t: unknown): DynamicT => t as DynamicT;

export function errorText(code: string | null | undefined, params: Record<string, unknown> = {}): string {
  const key = (code ?? "internal_error").toLowerCase();
  return translateServerMessage(`errors.${key}`, params, {
    namespaces: ["pos:sale"],
    fallback: "errors.internal_error",
  });
}

/** Server `message_key` (push result `message`) → text; falls back to the code. */
export function messageText(
  message: string | null | undefined,
  code: string | null | undefined,
  params: Record<string, unknown> = {},
): string {
  if (message) return translateServerMessage(message, params, { namespaces: ["pos:sale"] });
  return errorText(code, params);
}
