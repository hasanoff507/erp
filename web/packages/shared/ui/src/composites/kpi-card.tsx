/**
 * KpiCard — 08 §7.2 / §7.4: card recipe px-5 py-[18px] gap-2; label 13px/600 muted-foreground,
 * 34px icon tile (X-soft / X-strong), value text-kpi tabular-nums, note 12px/600.
 * `value` is an already formatted display string (from @shared/lib/format) — never a number.
 */
import { Icon, type LucideIcon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { SOFT_TONE, STRONG_TEXT_TONE, type Tone } from "./tone.ts";

export interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  tone: Tone;
  note?: string;
  noteTone?: Tone;
  className?: string;
}

export function KpiCard({ label, value, icon, tone, note, noteTone = "neutral", className }: KpiCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-2xl border border-border bg-card px-5 py-[18px] shadow-card",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] font-semibold text-muted-foreground">{label}</span>
        <span
          className={cn("flex h-[34px] w-[34px] items-center justify-center rounded-md", SOFT_TONE[tone])}
        >
          <Icon as={icon} size="md" />
        </span>
      </div>
      <div className="text-kpi tabular-nums">{value}</div>
      {note ? (
        <div className={cn("text-[12px] font-semibold", STRONG_TEXT_TONE[noteTone])}>{note}</div>
      ) : null}
    </div>
  );
}
