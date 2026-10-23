/**
 * ApiError `details[]` → form field errors (17 §7.1, 24 §3: "409/422 → forma maydonlariga xato").
 *
 * The server reports `{field: "payments[0].amount", message_key: "validation.max_length"}`;
 * react-hook-form addresses the same field as `payments.0.amount`. The helper is form-library
 * agnostic (no react-hook-form import here): it calls the `setError` you pass with the message KEY
 * — the form field component translates it (`t("common:" + key)`), never raw JSON (32 §5.1).
 */
import type { ApiError, ApiErrorDetail } from "./errors.ts";

export interface ApiFieldError {
  /** Field path in dot notation (`payments.0.amount`). */
  path: string;
  /** i18n key in `common` (`validation.required`). */
  messageKey: string;
}

/** `"payments[0].amount"` → `"payments.0.amount"`; `"body.name"` → `"name"` (FastAPI loc prefix). */
export function toFieldPath(field: string): string {
  const dotted = field.replace(/\[(\d+)\]/g, ".$1").replace(/^\./, "");
  return dotted.startsWith("body.") ? dotted.slice("body.".length) : dotted;
}

export function apiFieldErrors(error: ApiError): ApiFieldError[] {
  return error.details.map((d: ApiErrorDetail) => ({ path: toFieldPath(d.field), messageKey: d.messageKey }));
}

export type SetFieldError<TField extends string> = (
  name: TField,
  error: { type: string; message: string },
  options?: { shouldFocus: boolean },
) => void;

export interface ApplyFieldErrorsResult {
  /** Details whose field is not part of the form (show them in a banner / toast instead). */
  unmatched: ApiFieldError[];
  /** True when at least one form field received an error. */
  applied: boolean;
}

/**
 * Puts every `details[]` entry whose path is in `fields` on the form (first one focused) and returns
 * the rest. `fieldMap` renames server paths to form paths (`{ "branch_ids": "branches" }`).
 *
 *   const { unmatched } = applyApiFieldErrors(error, form.setError, ["name", "phone"]);
 */
export function applyApiFieldErrors<TField extends string>(
  error: ApiError,
  setError: SetFieldError<TField>,
  fields: readonly TField[],
  fieldMap: Readonly<Record<string, TField>> = {},
): ApplyFieldErrorsResult {
  const known = new Set<string>(fields);
  const unmatched: ApiFieldError[] = [];
  let applied = false;
  for (const fe of apiFieldErrors(error)) {
    const mapped = fieldMap[fe.path] ?? fe.path;
    if (known.has(mapped)) {
      setError(mapped as TField, { type: "server", message: fe.messageKey }, { shouldFocus: !applied });
      applied = true;
    } else {
      unmatched.push(fe);
    }
  }
  return { unmatched, applied };
}
