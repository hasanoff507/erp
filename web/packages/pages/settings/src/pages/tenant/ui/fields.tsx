import type { ReactNode } from "react";

import { FormField, NativeSelect, SegmentedControl, Switch } from "@shared/ui";
import { Controller, type Control, type FieldPath } from "@shared/ui/form";

import type { TenantFormValues } from "../model/index.ts";

interface Option<V extends string> {
  value: V;
  label: string;
}

/** Enum policy as a SegmentedControl (07 BO-14: markingPrecheck, supplierOverpayPolicy). */
export function SegmentField<V extends string>({
  control,
  name,
  label,
  hint,
  options,
  disabled,
}: {
  control: Control<TenantFormValues>;
  name: FieldPath<TenantFormValues>;
  label: string;
  hint?: ReactNode;
  options: readonly Option<V>[];
  disabled?: boolean;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormField label={label} hint={hint} error={fieldState.error?.message}>
          <div
            className={disabled ? "pointer-events-none opacity-60" : undefined}
            aria-disabled={disabled || undefined}
          >
            <SegmentedControl<V>
              label={label}
              value={field.value as V}
              onChange={field.onChange}
              options={options}
              className="flex-wrap"
            />
          </div>
        </FormField>
      )}
    />
  );
}

/** Enum setting as a native select (account choices). */
export function SelectField<V extends string>({
  control,
  name,
  label,
  hint,
  options,
  disabled,
}: {
  control: Control<TenantFormValues>;
  name: FieldPath<TenantFormValues>;
  label: string;
  hint?: ReactNode;
  options: readonly Option<V>[];
  disabled?: boolean;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormField label={label} hint={hint} error={fieldState.error?.message}>
          {(a11y) => (
            <NativeSelect
              {...a11y}
              ref={field.ref}
              name={field.name}
              options={options}
              value={field.value as string}
              disabled={disabled}
              onBlur={field.onBlur}
              onChange={(e) => field.onChange(e.target.value)}
              wrapperClassName="w-full max-w-sm"
            />
          )}
        </FormField>
      )}
    />
  );
}

export function SwitchField({
  control,
  name,
  label,
  hint,
  disabled,
}: {
  control: Control<TenantFormValues>;
  name: FieldPath<TenantFormValues>;
  label: string;
  hint?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <div className="flex items-start gap-3">
          <Switch
            id={`sw-${name}`}
            checked={field.value === true}
            disabled={disabled}
            onCheckedChange={field.onChange}
            className="mt-0.5"
          />
          <label htmlFor={`sw-${name}`} className="flex flex-col">
            <span className="text-[14px] font-semibold">{label}</span>
            {hint ? <span className="text-[12px] text-muted-foreground">{hint}</span> : null}
          </label>
        </div>
      )}
    />
  );
}
