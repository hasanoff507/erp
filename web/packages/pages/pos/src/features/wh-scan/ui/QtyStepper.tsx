/**
 * `QtyInput` of the POS warehouse screens (08 touch density, ≥ 48 px): `−` / value / `+`. The value is a
 * decimal string (3 dp, qaror #57); typing is sanitised (`sanitizeDecimalInput`), never parsed to a number.
 */
import { Minus, Plus } from "lucide-react";

import { sanitizeDecimalInput } from "@shared/lib/decimal-input";
import { useTranslation } from "@shared/i18n";
import { Button, Icon, Input } from "@shared/ui";

import { addQty, decrementQty, isQty, trimQty } from "../lib/qty.ts";

export interface QtyStepperProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  disabled?: boolean;
  testId?: string;
}

export function QtyStepper({ value, onChange, label, disabled = false, testId }: QtyStepperProps) {
  const { t } = useTranslation("pos");
  return (
    <div className="flex items-center gap-1.5" data-testid={testId}>
      <Button
        size="icon-pos"
        variant="secondary"
        aria-label={t("wh.qty.minus")}
        disabled={disabled}
        onClick={() => onChange(decrementQty(value))}
      >
        <Icon as={Minus} size="md" />
      </Button>
      <Input
        aria-label={label}
        inputMode="decimal"
        disabled={disabled}
        value={/^\d+\.\d{3}$/.test(value) ? trimQty(value) : value}
        onChange={(e) => onChange(sanitizeDecimalInput(e.target.value, { scale: 3 }))}
        className="h-12 w-24 text-center text-[16px] font-bold tabular-nums"
      />
      <Button
        size="icon-pos"
        variant="secondary"
        aria-label={t("wh.qty.plus")}
        disabled={disabled}
        onClick={() => onChange(addQty(isQty(value) ? value : "0", "1"))}
      >
        <Icon as={Plus} size="md" />
      </Button>
    </div>
  );
}
