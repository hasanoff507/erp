/**
 * POS-13 «Yangi va'da sanasi»: 7 / 14 / 30-day quick buttons + a date (≥ today). Touch targets ≥ 48 px
 * (08 §2, WEB-09) — `size="pos"` buttons and an `h-12` input, as the POS-03 debt panel.
 */
import { Button, Input } from "@shared/ui";

export const PROMISE_DAYS = [7, 14, 30] as const;

export interface PromiseDatePickerProps {
  value: string;
  today: string;
  label: string;
  /** Labels of the 7 / 14 / 30 buttons, in `PROMISE_DAYS` order. */
  dayLabels: readonly string[];
  /** Date of «today + n days» (Asia/Tashkent). */
  dateFor: (n: number) => string;
  onChange: (date: string) => void;
}

export function PromiseDatePicker({ value, today, label, dayLabels, dateFor, onChange }: PromiseDatePickerProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PROMISE_DAYS.map((d, i) => (
        <Button
          key={d}
          size="pos"
          variant={value === dateFor(d) ? "default" : "secondary"}
          onClick={() => onChange(dateFor(d))}
        >
          {dayLabels[i]}
        </Button>
      ))}
      <Input
        type="date"
        min={today}
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value >= today ? e.target.value : "")}
        className="h-12 w-48"
      />
    </div>
  );
}
