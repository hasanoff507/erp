/**
 * @shared/ui — shadcn/ui components (components/ui) + project composites (08 §7.2),
 * themed by styles/theme.css tokens through the Tailwind preset (24 §4.3).
 * Styles entry: import "@shared/ui/styles.css" once in the app.
 */
export { cn } from "./lib/cn.ts";
export { Icon, ICON_SIZES, type IconProps, type IconSize, type LucideIcon } from "./icon/Icon.tsx";

export { Button, buttonVariants, type ButtonProps } from "./components/ui/button.tsx";
export { Input, inputClassName, type InputProps } from "./components/ui/input.tsx";
export { Label } from "./components/ui/label.tsx";
export { Card, CardTitle } from "./components/ui/card.tsx";
export { Skeleton } from "./components/ui/skeleton.tsx";
export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu.tsx";

export { type Tone } from "./composites/tone.ts";
export { Kbd, type KbdProps } from "./composites/kbd.tsx";
export { StatusChip, type StatusChipProps } from "./composites/status-chip.tsx";
export {
  SegmentedControl,
  type SegmentedControlProps,
  type SegmentedOption,
} from "./composites/segmented-control.tsx";
export { KpiCard, type KpiCardProps } from "./composites/kpi-card.tsx";
export { Banner, EmptyState, type BannerProps, type EmptyStateProps } from "./composites/states.tsx";
export { Avatar, LogoMark, initialsOf } from "./composites/identity.tsx";
export { NativeSelect, type NativeSelectOption } from "./composites/native-select.tsx";
