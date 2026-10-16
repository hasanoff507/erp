/**
 * StatusChip — 08 §7.2 / §7.4: dot or 16px icon + text, bg-X-soft + text-X-strong, rounded-full.
 * Colour is never the only signal (§10 band 5): always pass text.
 */
import type { ReactNode } from "react";

import { Icon, type LucideIcon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { DOT_TONE, SOFT_TONE, type Tone } from "./tone.ts";

export interface StatusChipProps {
  tone?: Tone;
  icon?: LucideIcon;
  dot?: boolean;
  children: ReactNode;
  className?: string;
}

export function StatusChip({ tone = "neutral", icon, dot = false, children, className }: StatusChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-caption",
        SOFT_TONE[tone],
        className,
      )}
    >
      {dot ? <span aria-hidden="true" className={cn("h-2 w-2 rounded-full", DOT_TONE[tone])} /> : null}
      {icon ? <Icon as={icon} size="sm" /> : null}
      {children}
    </span>
  );
}
