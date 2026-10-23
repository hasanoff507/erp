/**
 * PhoneInput — `+998 XX XXX XX XX` (08 §8, BO-01/BO-11/BO-21). Fixed "+998" prefix, live mask of the
 * 9 national digits via @shared/lib/phone (no regex masks). Accepts a pasted "+998 90 …" or E.164.
 *
 * `value` may be national digits or E.164; `onChange` emits the NATIONAL DIGITS ("901234567", partial
 * while typing). Send `toE164(value)` to the API; validate with `zPhone()` from @shared/ui/form.
 */
import type { InputHTMLAttributes, Ref } from "react";

import { useTranslation } from "@shared/i18n";
import { maskNationalPhone, nationalDigits } from "@shared/lib/phone";

import { inputClassName } from "#/components/ui/input.tsx";
import { cn } from "#/lib/cn.ts";

export interface PhoneInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "type" | "defaultValue"
> {
  value: string;
  onChange: (nationalDigits: string) => void;
  ref?: Ref<HTMLInputElement>;
}

export function PhoneInput({ value, onChange, className, ref, placeholder, ...props }: PhoneInputProps) {
  const { t } = useTranslation("common");
  return (
    <div className={cn("relative flex w-full", className)}>
      <span
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[15px] font-semibold tabular-nums text-foreground-secondary"
        aria-hidden="true"
        title={t("ui.phone.countryCode")}
      >
        +998
      </span>
      <input
        ref={ref}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        placeholder={placeholder ?? "90 123 45 67"}
        className={cn(inputClassName, "pl-[60px] tabular-nums")}
        value={maskNationalPhone(value)}
        onChange={(e) => onChange(nationalDigits(e.target.value))}
        {...props}
      />
    </div>
  );
}
