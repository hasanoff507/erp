/**
 * shadcn/ui Tabs (Radix) — BO-11 "Bo'lim" tablist (mockup Bo11Xodimlar): box bg-accent rounded-lg p-1,
 * tab h-9 rounded-md 13px/700; selected = bg-card text-foreground shadow-card, others
 * text-foreground-secondary. role="tablist"/"tab"/"tabpanel" + arrow-key navigation from Radix.
 */
import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";

import { cn } from "#/lib/cn.ts";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex flex-wrap items-center gap-0.5 rounded-lg bg-accent p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[13px] font-bold text-foreground-secondary transition-colors",
        "hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-card",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn(
        "mt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    />
  );
}
