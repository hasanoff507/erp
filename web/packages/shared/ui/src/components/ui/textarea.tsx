/** shadcn/ui Textarea — Input recipe (08 §7.4) with min-h 88px; free text ≤ 1000 chars (17 §3). */
import type { Ref, TextareaHTMLAttributes } from "react";

import { cn } from "#/lib/cn.ts";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  ref?: Ref<HTMLTextAreaElement>;
}

export function Textarea({ className, ref, ...props }: TextareaProps) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[88px] w-full min-w-0 rounded-lg border border-input bg-card px-3.5 py-2.5 text-[15px] text-foreground",
        "placeholder:text-muted-foreground transition-[border-color,box-shadow]",
        "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none focus-visible:ring-0",
        "aria-[invalid=true]:border-destructive disabled:cursor-not-allowed disabled:text-disabled-foreground",
        className,
      )}
      {...props}
    />
  );
}
