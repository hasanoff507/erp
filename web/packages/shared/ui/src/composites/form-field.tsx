/**
 * FormField — label + control + hint + error (08 §7.4 Input recipe: label `text-label` above, error
 * `text-small text-destructive` below, invalid control = destructive border via aria-invalid).
 *
 * The control receives `{ id, aria-invalid, aria-describedby, aria-required }` either through a render
 * function or by cloning a single child element:
 *   <FormField label="Telefon" required error={errors.phone?.message}>
 *     {(a11y) => <PhoneInput {...a11y} value={v} onChange={setV} />}
 *   </FormField>
 *
 * `error` is an i18n key from `common` (`validation.required`, `errors.barcode_duplicate`, optionally
 * with params encoded by `withParams`) or already translated text — never raw JSON (08 §11).
 */
import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

import { i18next, useTranslation } from "@shared/i18n";

import { cn } from "#/lib/cn.ts";

export interface FieldControlProps {
  id: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  "aria-required"?: boolean;
}

/** Encodes params into a message key for zod/RHF messages: `withParams("validation.min_length", {min: 2})`. */
export function withParams(key: string, params: Record<string, string | number>): string {
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
  return query ? `${key}?${query}` : key;
}

const KEY_PREFIXES = ["validation.", "errors.", "warnings."];

/** Field error → text. Keys resolve in `common` (fallback `validation.invalid_format`); text passes through. */
export function translateFieldError(message: string | undefined | null): string | null {
  if (!message) return null;
  const q = message.indexOf("?");
  const key = q === -1 ? message : message.slice(0, q);
  if (!KEY_PREFIXES.some((p) => key.startsWith(p))) return message;
  const params: Record<string, string> = {};
  if (q !== -1) new URLSearchParams(message.slice(q + 1)).forEach((v, k) => (params[k] = v));
  const t = i18next.t.bind(i18next) as (k: string, o?: Record<string, unknown>) => string;
  return i18next.exists(`common:${key}`) ? t(`common:${key}`, params) : t("common:validation.invalid_format");
}

export interface FormFieldProps {
  label: ReactNode;
  children: ReactElement<Partial<FieldControlProps>> | ((control: FieldControlProps) => ReactNode);
  hint?: ReactNode;
  /** i18n key or translated text. */
  error?: string | null;
  required?: boolean;
  /** Shows "· ixtiyoriy" after the label (BO-21 AI consent style). */
  optional?: boolean;
  /** Explicit control id (default: generated). */
  id?: string;
  className?: string;
  /** Visually hide the label (still the accessible name). */
  hideLabel?: boolean;
}

export function FormField({
  label,
  children,
  hint,
  error,
  required = false,
  optional = false,
  id: idProp,
  className,
  hideLabel = false,
}: FormFieldProps) {
  const { t } = useTranslation("common");
  const generated = useId();
  const id = idProp ?? `f${generated}`;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorText = translateFieldError(error);
  const errorId = errorText ? `${id}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

  const control: FieldControlProps = {
    id,
    "aria-invalid": errorText ? true : undefined,
    "aria-describedby": describedBy,
    "aria-required": required || undefined,
  };

  const rendered =
    typeof children === "function"
      ? children(control)
      : isValidElement(children)
        ? cloneElement(children, { ...control, ...stripUndefined(children.props) })
        : children;

  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className={cn("text-label text-foreground-secondary", hideLabel && "sr-only")}>
        {label}
        {required ? (
          <span aria-hidden="true" className="ml-0.5 text-destructive">
            *
          </span>
        ) : null}
        {optional ? (
          <span className="font-normal text-muted-foreground"> · {t("ui.field.optional")}</span>
        ) : null}
      </label>
      {rendered}
      {errorText ? (
        <p id={errorId} role="alert" className="text-small font-semibold text-destructive">
          {errorText}
        </p>
      ) : null}
      {hint ? (
        <p id={hintId} className="text-[12px] text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** Child props win over generated ones only when actually set. */
function stripUndefined(props: Partial<FieldControlProps>): Partial<FieldControlProps> {
  return Object.fromEntries(Object.entries(props).filter(([, v]) => v !== undefined));
}
