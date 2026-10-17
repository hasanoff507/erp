/**
 * ApiError → user text (17 §7.1, 32 §5.1: only `t(message_key)`, never raw JSON). Server keys live
 * in `common`; a few refusals carry the real reason in `params.reason` (19 §12, §13) and get a
 * warehouse-specific text.
 */
import { toApiError, type ApiError } from "@shared/api";
import { i18next, serverErrorText } from "@shared/i18n";

type Translate = (key: string, options?: Record<string, unknown>) => string;

function t(key: string, options?: Record<string, unknown>): string {
  return (i18next.t.bind(i18next) as unknown as Translate)(key, options);
}

/** `params.reason` values with their own explanation (`warehouse:reasons.*`). */
const REASONS = new Set(["reverse_sale_required", "gratuitous_receipt", "receipt_not_posted"]);

export function errorText(error: unknown): string {
  const e = toApiError(error);
  const reason = e.params.reason;
  if (e.code === "DOC_INVALID_STATE" && typeof reason === "string" && REASONS.has(reason)) {
    return t(`warehouse:reasons.${reason}`, { date: e.params.receipt_doc_date ?? "" });
  }
  if (e.code === "ETTN_REQUIRED") {
    const status = e.params.ettn_status;
    const label =
      typeof status === "string" && i18next.exists(`warehouse:ettn.${status}`)
        ? t(`warehouse:ettn.${status}`)
        : t("warehouse:ettn.none");
    return t("warehouse:reasons.ettn_required", { status: label });
  }
  return serverErrorText(e);
}

export function isStatus(error: ApiError | null, status: number): boolean {
  return error?.status === status;
}
