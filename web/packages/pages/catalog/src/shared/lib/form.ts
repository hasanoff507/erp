/**
 * Server error → form fields for the catalog forms (17 §7.1, 24 §3 "409/422 → forma maydonlariga xato").
 * Like `applyApiErrorToForm` from @shared/ui/form, but the message is resolved through
 * `fieldMessageText` so catalog-only `validation.*` keys (catalog:server.*) are translated too, and
 * error CODES without details (e.g. 409 BARCODE_DUPLICATE) can be pinned to a field.
 */
import { applyApiFieldErrors, toFieldPath, type ApiError } from "@shared/api";
import type { FieldPath, FieldValues, UseFormReturn } from "@shared/ui/form";

import { apiErrorText, fieldMessageText } from "./messages.ts";

export interface ServerErrorOptions<TValues extends FieldValues> {
  /** Server field path → form field. */
  fieldMap?: Readonly<Record<string, string>>;
  /** Error code without `details[]` → the form field that shows `apiErrorText(error)`. */
  codeFields?: Readonly<Record<string, FieldPath<TValues>>>;
}

/**
 * Applies the error to the form; returns the text for a banner when part of it matched no field
 * (or `null` when everything landed on fields).
 */
export function applyServerError<TValues extends FieldValues, TOut extends FieldValues = TValues>(
  form: Pick<UseFormReturn<TValues, unknown, TOut>, "setError" | "getValues">,
  error: ApiError,
  { fieldMap = {}, codeFields = {} }: ServerErrorOptions<TValues> = {},
): string | null {
  const byCode = codeFields[error.code];
  if (byCode && error.details.length === 0) {
    form.setError(byCode, { type: "server", message: apiErrorText(error) }, { shouldFocus: true });
    return null;
  }
  const values = form.getValues() as Record<string, unknown>;
  const known = error.details
    .map((d) => {
      const path = toFieldPath(d.field);
      return fieldMap[path] ?? path;
    })
    .filter((path) => (path.split(".")[0] ?? "") in values);
  const { unmatched, applied } = applyApiFieldErrors<string>(
    error,
    (name, err, opts) =>
      form.setError(
        name as FieldPath<TValues>,
        { type: err.type, message: fieldMessageText(err.message) },
        opts,
      ),
    known,
    fieldMap,
  );
  if (!applied) return apiErrorText(error);
  return unmatched.length > 0 ? unmatched.map((u) => fieldMessageText(u.messageKey)).join(" · ") : null;
}
