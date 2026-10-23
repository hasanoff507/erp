import { toApiError } from "@shared/api";
import type { FieldPath, FieldValues, UseFormReturn } from "@shared/ui/form";

import { errorText, splitFieldErrors } from "./errors.ts";

/**
 * Server error of a form submit → field errors (first focused) + the remaining text for a Banner.
 * Returns `null` when everything landed on a field.
 */
export function applyServerErrors<TValues extends FieldValues, TOut extends FieldValues = TValues>(
  form: Pick<UseFormReturn<TValues, unknown, TOut>, "setError" | "getValues">,
  error: unknown,
  fieldMap: Readonly<Record<string, FieldPath<TValues>>> = {},
): string | null {
  const apiError = toApiError(error);
  const fields = Object.keys(form.getValues());
  const { fieldErrors, other } = splitFieldErrors(apiError, fields, fieldMap);
  fieldErrors.forEach((fe, i) =>
    form.setError(
      fe.field as FieldPath<TValues>,
      { type: "server", message: fe.message },
      { shouldFocus: i === 0 },
    ),
  );
  if (other.length > 0) return other.join(" ");
  if (fieldErrors.length > 0) return null;
  return errorText(apiError);
}
