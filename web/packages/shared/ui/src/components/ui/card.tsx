/** shadcn/ui Card — 08 §7.4: bg-card, border, rounded-2xl, shadow-card, padding 20–24px. */
import type { HTMLAttributes } from "react";

import { cn } from "#/lib/cn.ts";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn("rounded-2xl border border-border bg-card p-5 shadow-card", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-h2 font-extrabold text-card-foreground", className)} {...props} />;
}
