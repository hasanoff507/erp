/**
 * Scanner / manual code field of POS-08/09/10 (07 «F1 skaner fokus», 06 §1.6): a USB HID scanner is caught
 * anywhere on the screen (`useBarcodeWedge`, capture phase), the field itself accepts typed codes + Enter.
 * F1 focuses it. 256 chars max (GS1 DataMatrix with GS separators).
 */
import { ScanLine } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";

import { useTranslation } from "@shared/i18n";
import { Button, Icon, Input, Kbd } from "@shared/ui";

import { useBarcodeWedge } from "#/shared/lib/use-barcode-wedge.ts";

export interface ScanFieldProps {
  onScan: (code: string) => void;
  disabled?: boolean;
  /** Listen to the scanner even when the field is not focused (default true). */
  wedge?: boolean;
  label?: string;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}

export function ScanField({ onScan, disabled = false, wedge = true, label, inputRef }: ScanFieldProps) {
  const { t } = useTranslation("pos");
  const own = useRef<HTMLInputElement | null>(null);
  const ref = inputRef ?? own;
  const [value, setValue] = useState("");

  useBarcodeWedge((code) => {
    if (!disabled) onScan(code);
  }, wedge && !disabled);

  const submit = () => {
    const code = value.trim();
    if (!code || disabled) return;
    setValue("");
    onScan(code);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      submit();
    }
  };

  return (
    <div className="flex items-center gap-2">
      <label className="relative flex-1">
        <span className="sr-only">{label ?? t("wh.scan.label")}</span>
        <Icon
          as={ScanLine}
          size="md"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          ref={ref}
          value={value}
          maxLength={256}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={label ?? t("wh.scan.placeholder")}
          className="h-14 pl-11 text-[16px]"
          data-testid="wh-scan-input"
          autoComplete="off"
        />
        <Kbd keys="F1" className="absolute right-3 top-1/2 -translate-y-1/2" />
      </label>
      <Button size="pos" variant="secondary" onClick={submit} disabled={disabled || !value.trim()}>
        {t("wh.scan.add")}
      </Button>
    </div>
  );
}
