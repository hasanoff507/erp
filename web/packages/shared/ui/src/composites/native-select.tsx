/**
 * NativeSelect — styled native <select> (08 §7.4 Input/Select recipe). Used for short lists such as
 * the topbar branch filter (mockup Bo02Dashboard). Native select needs no portal and no scroll-lock
 * <style> injection, so it stays within the strict CSP (qaror #57).
 */
import { ChevronDown } from "lucide-react";
import type { Ref, SelectHTMLAttributes } from "react";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export interface NativeSelectOption {
  value: string;
  label: string;
}

export interface NativeSelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  options: readonly NativeSelectOption[];
  ref?: Ref<HTMLSelectElement>;
  wrapperClassName?: string;
}

export function NativeSelect({ options, className, wrapperClassName, ref, ...props }: NativeSelectProps) {
  return (
    <span className={cn("relative inline-flex", wrapperClassName)}>
      <select
        ref={ref}
        className={cn(
          "h-[42px] w-full appearance-none rounded-lg border border-input bg-card pl-3 pr-9 text-[14px] font-semibold text-foreground",
          "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none focus-visible:ring-0",
          className,
        )}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Icon
        as={ChevronDown}
        size="sm"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
    </span>
  );
}
