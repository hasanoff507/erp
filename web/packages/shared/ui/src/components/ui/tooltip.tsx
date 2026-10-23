/**
 * shadcn/ui Tooltip (Radix) — short hint on hover/focus (e.g. why an action is disabled, icon-button
 * names). Never the only carrier of essential information (08 §10). Wrap the app (or a test) in
 * <TooltipProvider>; `SimpleTooltip` is the one-liner.
 */
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "#/lib/cn.ts";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-toast max-w-xs rounded-md bg-foreground px-2.5 py-1.5 text-[12px] font-semibold text-background shadow-popover",
          "data-[state=delayed-open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}

export interface SimpleTooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

/** `children` must be a single focusable element (it is used asChild). */
export function SimpleTooltip({ content, children, side = "top" }: SimpleTooltipProps) {
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side}>{content}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
