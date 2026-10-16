/**
 * MoneyInput / PriceInput / DecimalInput — 08 §7.2 (decimal STRING in/out, qaror #26/#57).
 *
 * The value never becomes a JS number: keystrokes go through @shared/lib/decimal-input (string
 * sanitizing + NBSP grouping, caret kept on the same digit). Display "1 240 000" + "so'm" suffix;
 * `onChange` emits the API string with `outputScale` places ("1240000.00"), or "" when empty.
 *
 * - MoneyInput: whole so'm typed (`precision` 0, 08 §7.2 "ekranda butun son"), output 2 places.
 * - PriceInput: up to 4 fraction digits typed and emitted (cost/purchase price, 17 §3).
 * - DecimalInput: generic (qty 3 places with a unit suffix, percent 2 places …).
 */
import { useLayoutEffect, useRef, useState, type InputHTMLAttributes, type Ref } from "react";

import { useTranslation } from "@shared/i18n";
import {
  caretAfterSignificantChars,
  fromDecimalString,
  groupDecimalInput,
  sanitizeDecimalInput,
  significantCharsBefore,
  toDecimalString,
} from "@shared/lib/decimal-input";

import { inputClassName } from "#/components/ui/input.tsx";
import { cn } from "#/lib/cn.ts";

type NativeProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "type" | "defaultValue" | "inputMode" | "max" | "min"
>;

export interface DecimalInputProps extends NativeProps {
  /** API decimal string ("12000.00") or "". */
  value: string;
  onChange: (value: string) => void;
  /** Fraction digits the user may type. */
  precision: number;
  /** Fraction digits of the emitted string (≥ precision). */
  outputScale: number;
  allowNegative?: boolean;
  /** Text after the number ("so'm", "kg", "%"). */
  suffix?: string;
  ref?: Ref<HTMLInputElement>;
}

export function DecimalInput({
  value,
  onChange,
  precision,
  outputScale,
  allowNegative = false,
  suffix,
  className,
  ref,
  onBlur,
  ...props
}: DecimalInputProps) {
  const inner = useRef<HTMLInputElement | null>(null);
  const options = { scale: precision, allowNegative };
  // Canonical partial kept locally so "12," survives a render while the emitted value is "12.00";
  // `synced` is the last value we emitted or adopted — any other incoming value is an external reset.
  const [state, setState] = useState(() => ({
    canonical: fromDecimalString(value, precision),
    synced: value,
  }));
  const pendingCaret = useRef<number | null>(null);
  if (value !== state.synced) setState({ canonical: fromDecimalString(value, precision), synced: value });
  const canonical = value !== state.synced ? fromDecimalString(value, precision) : state.canonical;

  const display = groupDecimalInput(canonical);

  useLayoutEffect(() => {
    const el = inner.current;
    if (el && pendingCaret.current !== null && document.activeElement === el) {
      const pos = caretAfterSignificantChars(display, pendingCaret.current);
      el.setSelectionRange(pos, pos);
    }
    pendingCaret.current = null;
  }, [display]);

  return (
    <div className={cn("relative flex w-full", className)}>
      <input
        ref={(el) => {
          inner.current = el;
          if (typeof ref === "function") ref(el);
          else if (ref) ref.current = el;
        }}
        type="text"
        inputMode={precision > 0 ? "decimal" : "numeric"}
        autoComplete="off"
        className={cn(inputClassName, "text-right font-semibold tabular-nums", suffix && "pr-14")}
        value={display}
        onChange={(e) => {
          const raw = e.target.value;
          const caret = e.target.selectionStart ?? raw.length;
          const next = sanitizeDecimalInput(raw, options);
          pendingCaret.current = significantCharsBefore(raw, caret);
          const emitted = toDecimalString(next, outputScale);
          setState({ canonical: next, synced: emitted });
          onChange(emitted);
        }}
        onBlur={(e) => {
          // "12," → "12" on blur.
          if (canonical.endsWith(".")) setState({ canonical: canonical.slice(0, -1), synced: state.synced });
          onBlur?.(e);
        }}
        {...props}
      />
      {suffix ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[14px] font-semibold text-muted-foreground"
        >
          {suffix}
        </span>
      ) : null}
    </div>
  );
}

export interface MoneyInputProps extends Omit<DecimalInputProps, "precision" | "outputScale" | "suffix"> {
  /** Typed fraction digits: 0 (default, whole so'm) or 2 (tiyin, fiscal/accounting forms). */
  precision?: 0 | 2;
  /** Hide the "so'm" suffix (table cells with a currency header). */
  withCurrency?: boolean;
}

export function MoneyInput({ precision = 0, withCurrency = true, ...props }: MoneyInputProps) {
  const { t } = useTranslation("common");
  return (
    <DecimalInput
      precision={precision}
      outputScale={2}
      suffix={withCurrency ? t("ui.money.currency") : undefined}
      {...props}
    />
  );
}

export interface PriceInputProps extends Omit<DecimalInputProps, "precision" | "outputScale" | "suffix"> {
  /** Typed and emitted fraction digits (default 4 — NUMERIC(18,4), 17 §3). */
  precision?: number;
  withCurrency?: boolean;
}

export function PriceInput({ precision = 4, withCurrency = true, ...props }: PriceInputProps) {
  const { t } = useTranslation("common");
  return (
    <DecimalInput
      precision={precision}
      outputScale={precision}
      suffix={withCurrency ? t("ui.money.currency") : undefined}
      {...props}
    />
  );
}
