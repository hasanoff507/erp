/**
 * shadcn/ui Checkbox (Radix) — 20px box (`rounded-[5px]`, border-input), checked = bg-primary + Check
 * (strokeWidth 2.2, 08 §4). The clickable area is the wrapping <label> (≥36px row, 08 §5).
 * Supports `checked="indeterminate"` (select-all in a checkbox list).
 */
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check, Minus } from "lucide-react";
import type { ComponentProps } from "react";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export function Checkbox({ className, ...props }: ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        "peer flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px] border border-input bg-card text-primary-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-destructive",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        "data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="group flex items-center justify-center">
        <Icon as={Check} size="sm" strokeWidth={2.2} className="group-data-[state=indeterminate]:hidden" />
        <Icon
          as={Minus}
          size="sm"
          strokeWidth={2.2}
          className="hidden group-data-[state=indeterminate]:block"
        />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
