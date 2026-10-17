/**
 * shadcn/ui Input — 08 §7.4 "Input / Select": BO h-11, POS h-[52px]; border-input, rounded-lg,
 * focus = ring-focus-soft (2px primary border + 4px primary-soft halo); invalid = destructive border.
 */
import type { InputHTMLAttributes, Ref } from "react";

import { cn } from "#/lib/cn.ts";

export const inputClassName =
  "flex h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3.5 text-[15px] text-foreground " +
  "placeholder:text-muted-foreground transition-[border-color,box-shadow] " +
  "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none focus-visible:ring-0 " +
  "aria-[invalid=true]:border-destructive disabled:cursor-not-allowed disabled:text-disabled-foreground " +
  "[[data-density=touch]_&]:min-h-[52px]";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  ref?: Ref<HTMLInputElement>;
}

export function Input({ className, type = "text", ref, ...props }: InputProps) {
  return <input ref={ref} type={type} className={cn(inputClassName, className)} {...props} />;
}
