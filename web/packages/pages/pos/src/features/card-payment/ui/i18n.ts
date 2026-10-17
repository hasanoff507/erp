/** Dynamic keys of `pos:cardPayment.*` (phase / status / adapter names) and catalog error texts. */
import { translateServerMessage } from "@shared/i18n";

export type DynamicT = (key: string, options?: Record<string, unknown>) => string;

/** `t` of `useTranslation("pos")` for keys built from enum values (all of them exist in uz + ru). */
export const dyn = (t: unknown): DynamicT => t as DynamicT;

/** Catalog code (17 §15) → `common:errors.<code>` text. */
export const codeText = (code: string, params: Record<string, unknown> = {}): string =>
  translateServerMessage(`errors.${code.toLowerCase()}`, params);
