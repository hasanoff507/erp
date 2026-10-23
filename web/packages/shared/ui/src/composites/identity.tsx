/**
 * Brand mark and avatar — 08 §6.2 (logo tile: primary bg, white "E", rounded-md) and §7.4
 * (Avatar: circle 34–36px, bg-primary-soft text-primary-strong, initials 12–13px/800).
 */
import { cn } from "#/lib/cn.ts";

export interface LogoMarkProps {
  size?: 36 | 38;
  className?: string;
}

export function LogoMark({ size = 36, className }: LogoMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center rounded-md bg-primary text-[15px] font-extrabold text-primary-foreground",
        size === 38 ? "h-[38px] w-[38px] rounded-[11px]" : "h-9 w-9",
        className,
      )}
    >
      E
    </span>
  );
}

/** "Akmal Karimov" → "AK" (first letters of the first two words, locale-aware upper case). */
export function initialsOf(fullName: string): string {
  const words = fullName
    .trim()
    .split(" ")
    .filter((w) => w.length > 0);
  const letters = words.slice(0, 2).map((w) => w.charAt(0));
  return letters.join("").toLocaleUpperCase();
}

export interface AvatarProps {
  name: string;
  size?: 34 | 36;
  className?: string;
}

export function Avatar({ name, size = 34, className }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-primary-soft font-extrabold text-primary-strong",
        size === 36 ? "h-9 w-9 text-[13px]" : "h-[34px] w-[34px] text-[12px]",
        className,
      )}
    >
      {initialsOf(name)}
    </span>
  );
}
