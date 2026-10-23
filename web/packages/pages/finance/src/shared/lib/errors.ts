/**
 * ApiError → user text (17 §7.1, 32 §5.1: only `t(message_key)`, never raw JSON). Server keys live in
 * `common`; a refusal whose real reason is in `params.reason` gets a finance-specific text
 * (`finance:reasons.*`) — e.g. a cash expense of a closed shift is never cancelled (BO-17).
 */
import { toApiError } from "@shared/api";
import { i18next, serverErrorText } from "@shared/i18n";

type Translate = (key: string, options?: Record<string, unknown>) => string;

function t(key: string, options?: Record<string, unknown>): string {
  return (i18next.t.bind(i18next) as unknown as Translate)(key, options);
}

/** `params.reason` values with their own explanation (`finance:reasons.*`). */
const REASONS = new Set(["shift_closed"]);

export function errorText(error: unknown): string {
  const e = toApiError(error);
  const reason = e.params.reason;
  if (e.code === "DOC_INVALID_STATE" && typeof reason === "string" && REASONS.has(reason)) {
    return t(`finance:reasons.${reason}`);
  }
  return serverErrorText(e);
}
