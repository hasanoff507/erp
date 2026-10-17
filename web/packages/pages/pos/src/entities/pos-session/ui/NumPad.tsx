/**
 * NumPad — POS-14 amount keypad (07: digits, `000`, `⌫`). Works on a whole-so'm digit string; the caller
 * turns it into Money ("12000.00") — no JS number is ever built from the amount.
 */
import { Delete } from "lucide-react";

import { Icon, cn } from "@shared/ui";

export interface NumPadProps {
  /** Whole so'm digits ("150000" or ""). */
  value: string;
  onChange: (value: string) => void;
  /** Max digits (9 999 999 999 → 10). */
  maxDigits?: number;
  backspaceLabel: string;
  className?: string;
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "000", "0", "back"] as const;

/** Appends a key to a whole-number digit string (no leading zeros, length cap). */
export function numPadAppend(value: string, key: string, maxDigits = 10): string {
  if (key === "back") return value.slice(0, -1);
  const next = (value + key).replace(/^0+(?=\d)/, "");
  if (next === "0" || next === "000") return value === "" ? "" : value;
  return next.length > maxDigits ? value : next;
}

export function NumPad({ value, onChange, maxDigits = 10, backspaceLabel, className }: NumPadProps) {
  return (
    <div className={cn("grid grid-cols-3 gap-2", className)}>
      {KEYS.map((key) => (
        <button
          key={key}
          type="button"
          aria-label={key === "back" ? backspaceLabel : key}
          onClick={() => onChange(numPadAppend(value, key, maxDigits))}
          className="flex h-14 items-center justify-center rounded-xl border border-border bg-card text-[20px] font-bold hover:bg-accent"
        >
          {key === "back" ? <Icon as={Delete} size="lg" /> : key}
        </button>
      ))}
    </div>
  );
}
