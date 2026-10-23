/** Kbd — keyboard hint chip (F1, F4, Enter…), 08 §7.2 / §7.4. `inverted` inside filled buttons. */
import { cn } from "#/lib/cn.ts";

export interface KbdProps {
  keys: string;
  inverted?: boolean;
  className?: string;
}

export function Kbd({ keys, inverted = false, className }: KbdProps) {
  return (
    <kbd
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 font-sans text-kbd",
        inverted ? "border-white/50 text-primary-foreground" : "border-input text-muted-foreground",
        className,
      )}
    >
      {keys}
    </kbd>
  );
}
