/** shadcn/ui Skeleton — loading placeholder (the "loading" state in 07). */
import type { HTMLAttributes } from "react";

import { cn } from "#/lib/cn.ts";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-lg bg-track", className)} {...props} />;
}
