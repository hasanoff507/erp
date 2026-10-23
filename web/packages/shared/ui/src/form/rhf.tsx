/**
 * react-hook-form glue: `useZodForm` (zod resolver, validate on blur then on change), `RhfField`
 * (FormField bound to a Controller) and `applyApiErrorToForm` (server `details[]` → field errors).
 */
import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactNode } from "react";
import {
  Controller,
  useForm,
  type Control,
  type ControllerFieldState,
  type ControllerRenderProps,
  type FieldPath,
  type FieldValues,
  type Resolver,
  type UseFormProps,
  type UseFormReturn,
} from "react-hook-form";
import type { z } from "zod";

import { applyApiFieldErrors, toFieldPath, type ApiError, type ApiFieldError } from "@shared/api";

import { FormField, type FieldControlProps } from "#/composites/form-field.tsx";

import "./schema.ts";

type AnySchema = z.ZodType<FieldValues, FieldValues>;

export function useZodForm<S extends AnySchema>(
  schema: S,
  options: Omit<UseFormProps<z.input<S>, unknown, z.output<S>>, "resolver"> = {},
): UseFormReturn<z.input<S>, unknown, z.output<S>> {
  return useForm<z.input<S>, unknown, z.output<S>>({
    mode: "onTouched",
    ...options,
    // zodResolver infers from the zod instance; the generic S is only known structurally here.
    resolver: zodResolver(schema) as unknown as Resolver<z.input<S>, unknown, z.output<S>>,
  });
}

export interface RhfFieldProps<
  TValues extends FieldValues,
  TName extends FieldPath<TValues>,
  TOut extends FieldValues = TValues,
> {
  control: Control<TValues, unknown, TOut>;
  name: TName;
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  optional?: boolean;
  hideLabel?: boolean;
  className?: string;
  render: (args: {
    field: ControllerRenderProps<TValues, TName>;
    control: FieldControlProps;
    fieldState: ControllerFieldState;
  }) => ReactNode;
}

/**
 *   <RhfField control={form.control} name="phone" label={t("…")} required
 *     render={({ field, control }) => <PhoneInput {...control} {...field} />} />
 */
export function RhfField<
  TValues extends FieldValues,
  TName extends FieldPath<TValues>,
  TOut extends FieldValues = TValues,
>({ control, name, render, ...fieldProps }: RhfFieldProps<TValues, TName, TOut>) {
  return (
    <Controller<TValues, TName, TOut>
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormField {...fieldProps} error={fieldState.error?.message}>
          {(a11y) => render({ field, control: a11y, fieldState })}
        </FormField>
      )}
    />
  );
}

/**
 * Applies a 422/409 ApiError's `details[]` to the form fields whose top-level key exists in the form
 * values; returns the details that matched no field (show them in a Banner/toast).
 */
export function applyApiErrorToForm<TValues extends FieldValues, TOut extends FieldValues = TValues>(
  form: Pick<UseFormReturn<TValues, unknown, TOut>, "setError" | "getValues">,
  error: ApiError,
  fieldMap: Readonly<Record<string, FieldPath<TValues>>> = {},
): ApiFieldError[] {
  const values = form.getValues() as Record<string, unknown>;
  const known = error.details
    .map((d) => {
      const path = toFieldPath(d.field);
      return fieldMap[path] ?? path;
    })
    .filter((path) => (path.split(".")[0] ?? "") in values) as FieldPath<TValues>[];
  const { unmatched } = applyApiFieldErrors<FieldPath<TValues>>(
    error,
    (name, err, opts) => form.setError(name, err, opts),
    known,
    fieldMap,
  );
  return unmatched;
}
