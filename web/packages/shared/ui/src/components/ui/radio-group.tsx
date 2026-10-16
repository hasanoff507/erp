/**
 * shadcn/ui RadioGroup (Radix) + RadioCard — BO-21 "Tashkiliy-huquqiy shakl" cards (mockup Bo21Royxat):
 * card `rounded-lg border border-input bg-card px-3.5 py-2.5`, title 14px/700 + sub 12px;
 * selected = `border-2 border-primary bg-primary-soft`, title text-primary-strong 800.
 * Arrow keys move the selection (Radix roving focus); the whole card is the radio.
 */
import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "#/lib/cn.ts";

export function RadioGroup({ className, ...props }: ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return <RadioGroupPrimitive.Root className={cn("grid gap-2.5", className)} {...props} />;
}

/** Classic radio dot (20px) — pair with a <Label htmlFor>. */
export function RadioGroupItem({ className, ...props }: ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-input bg-card",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary",
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="h-2.5 w-2.5 rounded-full bg-primary" />
    </RadioGroupPrimitive.Item>
  );
}

export interface RadioCardProps extends Omit<
  ComponentProps<typeof RadioGroupPrimitive.Item>,
  "title" | "children"
> {
  title: ReactNode;
  description?: ReactNode;
}

export function RadioCard({ className, title, description, ...props }: RadioCardProps) {
  return (
    <RadioGroupPrimitive.Item
      className={cn(
        "group flex min-h-[56px] flex-col items-start justify-center gap-0.5 rounded-lg border border-input bg-card px-3.5 py-2.5 text-left transition-colors",
        "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:border-2 data-[state=checked]:border-primary data-[state=checked]:bg-primary-soft",
        "data-[state=checked]:px-[13px] data-[state=checked]:py-[9px]",
        className,
      )}
      {...props}
    >
      <span className="text-[14px] font-bold text-foreground group-data-[state=checked]:font-extrabold group-data-[state=checked]:text-primary-strong">
        {title}
      </span>
      {description ? (
        <span className="text-[12px] text-muted-foreground group-data-[state=checked]:text-foreground-secondary">
          {description}
        </span>
      ) : null}
    </RadioGroupPrimitive.Item>
  );
}
