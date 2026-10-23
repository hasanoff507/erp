/**
 * PinPad — 08 POS PIN (4–6 digits): masked dots + 3×4 keypad (≥ 56 px keys, touch density). Physical keys
 * are wired by the screen (digits / Backspace / Enter / Esc through `useHotkeys`); the pad itself never
 * shows or keeps the digits anywhere but in the caller's state.
 */
import { Delete } from "lucide-react";

import { Icon, cn } from "@shared/ui";

export interface PinPadProps {
  value: string;
  onChange: (value: string) => void;
  maxLength?: number;
  disabled?: boolean;
  /** Accessible name of the dots row ("PIN kod"). */
  label: string;
  /** "Oxirgi raqamni o'chirish". */
  backspaceLabel: string;
  className?: string;
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "back"] as const;

export function PinPad({
  value,
  onChange,
  maxLength = 6,
  disabled,
  label,
  backspaceLabel,
  className,
}: PinPadProps) {
  const press = (key: (typeof KEYS)[number]) => {
    if (disabled) return;
    if (key === "back") onChange(value.slice(0, -1));
    else if (key && value.length < maxLength) onChange(value + key);
  };
  return (
    <div className={cn("flex flex-col items-center gap-5", className)}>
      <div
        role="status"
        aria-label={label}
        data-testid="pin-dots"
        data-length={value.length}
        className="flex gap-3"
      >
        {Array.from({ length: maxLength }, (_, i) => (
          <span
            key={i}
            className={cn(
              "h-4 w-4 rounded-full border-2",
              i < value.length ? "border-primary bg-primary" : "border-input bg-card",
              i >= 4 && i >= value.length ? "opacity-50" : "",
            )}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {KEYS.map((key, i) =>
          key === "" ? (
            <span key={i} />
          ) : (
            <button
              key={i}
              type="button"
              disabled={disabled}
              aria-label={key === "back" ? backspaceLabel : key}
              onClick={() => press(key)}
              className="flex h-16 w-20 items-center justify-center rounded-xl border border-border bg-card text-[24px] font-bold shadow-card hover:bg-accent disabled:opacity-60"
            >
              {key === "back" ? <Icon as={Delete} size="lg" /> : key}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
