/**
 * shadcn/ui Button themed per 08-dizayn-tizimi.md §7.4 (USLUB recipes) and §5 (density).
 */
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "#/lib/cn.ts";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-bold no-underline transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
    "disabled:pointer-events-none disabled:opacity-60 " +
    // touch density (08 §5, POS): every button is at least the tap size
    "[[data-density=touch]_&]:min-h-[var(--tap-min)]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-primary-strong hover:text-primary-foreground active:bg-primary-strong",
        secondary: "border border-border bg-card text-foreground hover:bg-accent hover:text-foreground",
        outline: "border border-input bg-card text-foreground hover:bg-accent hover:text-foreground",
        "destructive-outline":
          "border border-destructive-border bg-card text-destructive hover:bg-destructive-soft",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive-strong",
        warning: "border border-warning-border bg-warning-soft text-warning-strong hover:bg-warning-soft/80",
        "warning-solid": "bg-warning-strong text-warning-foreground hover:bg-warning-strong/90",
        dashed:
          "border border-dashed border-muted-foreground/50 bg-card text-foreground-secondary hover:bg-accent",
        ghost: "text-foreground-secondary hover:bg-accent hover:text-foreground",
        link: "h-auto px-0 text-primary underline-offset-4 hover:text-primary-strong hover:underline",
        inverse: "bg-foreground text-background hover:bg-foreground/90 hover:text-background",
      },
      size: {
        default: "h-11 rounded-lg px-5 text-[14px]",
        sm: "h-9 rounded-md px-3.5 text-[13px]",
        lg: "h-12 rounded-lg px-6 text-[15px]",
        pos: "h-14 rounded-xl px-6 text-[16px]",
        "pos-cta": "h-16 rounded-xl px-6 text-[19px] font-extrabold shadow-cta",
        icon:
          "h-11 w-11 rounded-lg border border-input bg-card text-foreground-secondary hover:bg-accent " +
          "[[data-density=touch]_&]:min-w-[var(--tap-min)]",
        "icon-pos":
          "h-12 w-12 rounded-lg border border-input bg-card text-foreground-secondary hover:bg-accent",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ className, variant, size, asChild = false, type, ref, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      ref={ref}
      type={asChild ? undefined : (type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
