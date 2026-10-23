/**
 * ApiError → user text (17 §7.1, 32 §5.1: only `t(message_key)`, never raw JSON). Server keys live in
 * `common` (`errors.*`, `validation.*`); a few refusals carry the real reason in `params.reason`
 * (18 §12.5a, §12.6) and get a debts-specific text.
 */
import { toApiError } from "@shared/api";
import { i18next, serverErrorText } from "@shared/i18n";

type Translate = (key: string, options?: Record<string, unknown>) => string;

function t(key: string, options?: Record<string, unknown>): string {
  return (i18next.t.bind(i18next) as unknown as Translate)(key, options);
}

/** `params.reason` values with their own explanation (`debts:reasons.*`). */
const REASONS = new Set([
  "already_flagged",
  "has_allocations",
  "pos_fiscal_receipt",
  "supplier_payment_allocated",
]);

export function errorText(error: unknown): string {
  const e = toApiError(error);
  const reason = e.params.reason;
  if (e.code === "DOC_INVALID_STATE" && typeof reason === "string" && REASONS.has(reason)) {
    return t(`debts:reasons.${reason}`);
  }
  return serverErrorText(e);
}

/** A field error of the screen models: `debts:*` keys are translated here, `validation.*` by FormField. */
export function fieldError(key: string | null | undefined): string | null {
  if (!key) return null;
  return key.startsWith("debts:") ? t(key) : key;
}
