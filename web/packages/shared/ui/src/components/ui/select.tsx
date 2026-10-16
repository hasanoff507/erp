/**
 * shadcn/ui Select (Radix) — 08 §7.4 Input/Select recipe (h-11, border-input, rounded-lg, focus-soft).
 * Use for styled single choice with rich items; `NativeSelect` stays for tiny topbar filters.
 * Floating content uses z-dialog so it also opens above a Sheet/Dialog (portal order wins).
 *
 *   <SimpleSelect options={[{value:"llc", label:"MChJ"}]} value={v} onValueChange={setV} aria-label="…" />
 */
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ComponentProps, Ref } from "react";

import { useTranslation } from "@shared/i18n";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export const Select = SelectPrimitive.Root;
export const SelectGroup = SelectPrimitive.Group;
export const SelectValue = SelectPrimitive.Value;

export function SelectTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex h-11 w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-input bg-card px-3.5 text-left text-[15px] text-foreground",
        "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none",
        "data-[placeholder]:text-muted-foreground aria-[invalid=true]:border-destructive",
        "disabled:cursor-not-allowed disabled:text-disabled-foreground [&>span]:truncate",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <Icon as={ChevronDown} size="sm" className="shrink-0 text-muted-foreground" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  position = "popper",
  ...props
}: ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position={position}
        className={cn(
          "relative z-dialog max-h-[min(var(--radix-select-content-available-height),320px)] min-w-[8rem] overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-popover",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          position === "popper" &&
            "w-full min-w-[var(--radix-select-trigger-width)] data-[side=bottom]:translate-y-1",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectLabel({ className, ...props }: ComponentProps<typeof SelectPrimitive.Label>) {
  return (
    <SelectPrimitive.Label
      className={cn("px-2.5 py-1.5 text-small text-muted-foreground", className)}
      {...props}
    />
  );
}

export function SelectItem({ className, children, ...props }: ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex min-h-9 w-full cursor-default select-none items-center rounded-md py-1.5 pl-2.5 pr-8 text-[14px] font-semibold outline-none",
        "focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <span className="absolute right-2 flex h-4 w-4 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Icon as={Check} size="sm" className="text-primary" />
        </SelectPrimitive.ItemIndicator>
      </span>
    </SelectPrimitive.Item>
  );
}

export function SelectSeparator({ className, ...props }: ComponentProps<typeof SelectPrimitive.Separator>) {
  return <SelectPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-divider", className)} {...props} />;
}

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SimpleSelectProps {
  options: readonly SelectOption[];
  value: string | undefined;
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  name?: string;
  className?: string;
  ref?: Ref<HTMLButtonElement>;
  onBlur?: () => void;
  "aria-label"?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  "aria-required"?: boolean;
}

/** Options-array convenience over the primitives (works with FormField / RhfField). */
export function SimpleSelect({
  options,
  value,
  onValueChange,
  placeholder,
  disabled,
  id,
  name,
  className,
  ref,
  onBlur,
  ...aria
}: SimpleSelectProps) {
  const { t } = useTranslation("common");
  return (
    <Select value={value ?? ""} onValueChange={onValueChange} disabled={disabled} name={name}>
      <SelectTrigger id={id} ref={ref} className={className} onBlur={onBlur} {...aria}>
        <SelectValue placeholder={placeholder ?? t("ui.select.placeholder")} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
