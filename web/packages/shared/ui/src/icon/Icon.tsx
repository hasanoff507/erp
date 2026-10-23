/**
 * The only way to draw a lucide icon — 24-frontend-arxitekturasi.md §4.2, 08-dizayn-tizimi.md §4.
 * <Icon as={ScanLine} size="md" />: strokeWidth 1.8 and aria-hidden by default.
 * Sizes: sm 16 (chips) / md 18 (sidebar, KPI tile, topbar search) / lg 20 (icon buttons) / xl 24 (POS).
 */
import type { LucideIcon, LucideProps } from "lucide-react";

export const ICON_SIZES = { sm: 16, md: 18, lg: 20, xl: 24 } as const;
export type IconSize = keyof typeof ICON_SIZES;
export type { LucideIcon };

export interface IconProps extends Omit<LucideProps, "size" | "ref"> {
  as: LucideIcon;
  size?: IconSize;
  /** Accessible name — only for meaningful standalone icons; decorative icons stay aria-hidden. */
  label?: string;
}

export function Icon({ as: Glyph, size = "md", strokeWidth = 1.8, label, ...rest }: IconProps) {
  return (
    <Glyph
      size={ICON_SIZES[size]}
      strokeWidth={strokeWidth}
      absoluteStrokeWidth={false}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
      focusable="false"
      {...rest}
    />
  );
}
