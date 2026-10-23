/**
 * SegmentedControl — 08 §7.2 / §7.4. Box bg-card border rounded-xl p-1; segments rounded-md
 * (BO 36px, POS 48px), 13px/700. `solid` = selected bg-foreground text-background (period, UZ · RU);
 * `soft` = selected bg-primary-soft text-primary-strong (POS-02 view switch). Buttons use aria-pressed.
 */
import { cn } from "#/lib/cn.ts";

export interface SegmentedOption<V extends string> {
  value: V;
  label: string;
  /** Accessible name when the visible label is an abbreviation (e.g. "UZ"). */
  ariaLabel?: string;
}

export interface SegmentedControlProps<V extends string> {
  options: readonly SegmentedOption<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
  variant?: "solid" | "soft";
  density?: "compact" | "touch";
  className?: string;
}

export function SegmentedControl<V extends string>({
  options,
  value,
  onChange,
  label,
  variant = "solid",
  density = "compact",
  className,
}: SegmentedControlProps<V>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn("inline-flex gap-0.5 rounded-xl border border-border bg-card p-1", className)}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            aria-label={option.ariaLabel}
            onClick={() => onChange(option.value)}
            className={cn(
              "min-w-10 rounded-md px-3 text-[13px] font-bold transition-colors",
              density === "touch" ? "h-12" : "h-9",
              selected
                ? variant === "solid"
                  ? "bg-foreground text-background"
                  : "bg-primary-soft font-extrabold text-primary-strong"
                : "text-foreground-secondary hover:bg-accent",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
